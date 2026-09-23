"""
azora-scraper
=============
Mass ingestion engine for https://azorafly.com/series/ into Firestore
(project: pure-library-2d45d by default — override with FIREBASE_PROJECT_ID).

All outbound requests to the target site go through the proxy-gateway
service (see ../proxy-gateway) rather than hitting azorafly.com directly.

Credentials
-----------
This script deliberately does NOT contain any embedded service-account
key. Provide one of:
  FIREBASE_CREDENTIALS_PATH   path to a service-account JSON file, or
  FIREBASE_CREDENTIALS_JSON   the full JSON content as a single env var
If you pasted a private key anywhere outside a secrets manager (chat,
a shared doc, a public repo), treat it as compromised and rotate it in
Firebase Console -> Project Settings -> Service Accounts.

Run:
    python main.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field

import aiohttp
import firebase_admin
from bs4 import BeautifulSoup
from firebase_admin import credentials, firestore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("azora-scraper")

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

PROXY_URL = os.environ.get("PROXY_URL", "http://127.0.0.1:8000/fetch")
SERIES_LISTING_URL = os.environ.get("TARGET_SERIES_URL", "https://azorafly.com/series/")
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "pure-library-2d45d")
NUM_WORKERS = int(os.environ.get("NUM_WORKERS", "616"))
MAX_LISTING_PAGES = int(os.environ.get("MAX_LISTING_PAGES", "50"))
HTTP_TIMEOUT = int(os.environ.get("HTTP_TIMEOUT", "40"))

# --------------------------------------------------------------------------
# CSS selectors — site-specific, adjust to azorafly.com's actual markup.
# Defaults target the common "Madara" WordPress manga-theme layout.
# --------------------------------------------------------------------------

SEL = {
    "listing_card": "div.page-item-detail",
    "listing_link": "h3.h5 a, .post-title a",
    "next_page": "a.next.page-numbers, .nav-previous a",
    "title": "h1.entry-title, div.post-title h1",
    "score": ".score, .rating .score, span.total_votes",
    "cover": "div.summary_image img, div.thumb img",
    "genres": ".genres-content a, .summary-content .genres a",
    "description": "div.summary__content, div.description-summary .summary__content",
    "chapter_row": "li.wp-manga-chapter a, ul.main.version-chap li a",
    "page_image": "div.reader-area img, div#readerarea img, div.page-break img",
}


# --------------------------------------------------------------------------
# Firebase init (no embedded secrets)
# --------------------------------------------------------------------------

def init_firestore() -> firestore.Client:
    if not firebase_admin._apps:
        cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
        cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")
        if cred_json:
            cred = credentials.Certificate(json.loads(cred_json))
        elif cred_path:
            cred = credentials.Certificate(cred_path)
        else:
            raise RuntimeError(
                "Set FIREBASE_CREDENTIALS_PATH or FIREBASE_CREDENTIALS_JSON "
                "(never hardcode the key in source)."
            )
        firebase_admin.initialize_app(cred, {"projectId": FIREBASE_PROJECT_ID})
    return firestore.client()


db = init_firestore()
manga_collection = db.collection("manga")

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def safe_doc_id(text: str) -> str:
    if not text:
        return "manga_doc"
    normalized = unicodedata.normalize("NFKC", text).strip().lower()
    normalized = re.sub(r"[^\w\u0600-\u06FF]+", "_", normalized, flags=re.UNICODE)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return (normalized or "manga_doc")[:150]


def normalize_for_compare(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def normalize_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip().lower().split("#")[0]
    return url[:-1] if url.endswith("/") else url


@dataclass
class ChapterData:
    title: str
    url: str
    pages: list[str] = field(default_factory=list)


@dataclass
class SeriesData:
    title: str
    source_url: str
    slug: str = ""
    score: str = ""
    cover_url: str = ""
    genres: list[str] = field(default_factory=list)
    description: str = ""
    chapters: list[ChapterData] = field(default_factory=list)


# --------------------------------------------------------------------------
# Proxy-backed HTTP fetch
# --------------------------------------------------------------------------

async def fetch_via_proxy(session: aiohttp.ClientSession, target_url: str, retries: int = 3) -> str | None:
    for attempt in range(1, retries + 1):
        try:
            async with session.get(
                PROXY_URL, params={"url": target_url}, timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
            ) as resp:
                if resp.status == 200:
                    return await resp.text()
                log.warning("Proxy returned %s for %s", resp.status, target_url)
        except Exception as e:
            log.warning("Proxy fetch error (attempt %s/%s) for %s: %s", attempt, retries, target_url, e)
        if attempt < retries:
            await asyncio.sleep(2 * attempt)
    return None


# --------------------------------------------------------------------------
# Scraping
# --------------------------------------------------------------------------

async def discover_series_links(session: aiohttp.ClientSession) -> list[str]:
    links: set[str] = set()
    url = SERIES_LISTING_URL
    seen_pages = set()

    for _ in range(MAX_LISTING_PAGES):
        if not url or url in seen_pages:
            break
        seen_pages.add(url)

        html = await fetch_via_proxy(session, url)
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select(SEL["listing_card"]):
            a = card.select_one(SEL["listing_link"])
            href = a.get("href") if a else None
            if href:
                links.add(href)

        next_el = soup.select_one(SEL["next_page"])
        url = next_el.get("href") if next_el else None

    log.info("Discovered %d series links", len(links))
    return list(links)


async def scrape_chapter_pages(session: aiohttp.ClientSession, chapter_url: str) -> list[str]:
    html = await fetch_via_proxy(session, chapter_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    pages = []
    for img in soup.select(SEL["page_image"]):
        src = img.get("data-src") or img.get("src")
        if src and src.strip():
            pages.append(src.strip())
    return pages


async def scrape_series(session: aiohttp.ClientSession, series_url: str) -> SeriesData | None:
    html = await fetch_via_proxy(session, series_url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one(SEL["title"])
    if not title_el:
        return None
    title = title_el.get_text(strip=True)

    score_el = soup.select_one(SEL["score"])
    cover_el = soup.select_one(SEL["cover"])
    desc_el = soup.select_one(SEL["description"])
    genre_els = soup.select(SEL["genres"])

    series = SeriesData(
        title=title,
        source_url=series_url,
        slug=safe_doc_id(title),
        score=score_el.get_text(strip=True) if score_el else "",
        cover_url=(cover_el.get("data-src") or cover_el.get("src") or "") if cover_el else "",
        genres=[g.get_text(strip=True) for g in genre_els],
        description=desc_el.get_text(strip=True) if desc_el else "",
    )

    chapter_rows = soup.select(SEL["chapter_row"])
    chapter_stubs = []
    for row in chapter_rows:
        ch_title = row.get_text(strip=True)
        ch_url = row.get("href")
        if ch_url:
            chapter_stubs.append((ch_title or "Untitled", ch_url))

    # Fetch pages for every chapter concurrently, bounded by the same
    # semaphore the caller already holds one slot of.
    async def load_chapter(ch_title, ch_url):
        pages = await scrape_chapter_pages(session, ch_url)
        return ChapterData(title=ch_title, url=ch_url, pages=pages)

    results = await asyncio.gather(*(load_chapter(t, u) for t, u in chapter_stubs))
    series.chapters = list(results)
    return series


# --------------------------------------------------------------------------
# Firestore upsert (non-duplicate)
# --------------------------------------------------------------------------

def existing_chapter_count(doc_ref) -> int | None:
    snap = doc_ref.get()
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    return data.get("chapter_count")


def upsert_series(series: SeriesData) -> str:
    doc_ref = manga_collection.document(series.slug)
    prior_count = existing_chapter_count(doc_ref)

    if prior_count is not None and prior_count == len(series.chapters):
        log.info("Skip %s — already up to date (%d chapters)", series.title, prior_count)
        return "skipped"

    doc_ref.set(
        {
            "title": series.title,
            "title_normalized": normalize_for_compare(series.title),
            "source_url": series.source_url,
            "source_url_normalized": normalize_url(series.source_url),
            "score": series.score,
            "cover_url": series.cover_url,
            "genres": series.genres,
            "description": series.description,
            "chapter_count": len(series.chapters),
            "updated_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )

    chapters_ref = doc_ref.collection("chapters")
    for chapter in series.chapters:
        ch_id = safe_doc_id(chapter.title) or safe_doc_id(chapter.url)
        chapters_ref.document(ch_id).set(
            {
                "title": chapter.title,
                "url": chapter.url,
                "pages": chapter.pages,
                "page_count": len(chapter.pages),
            },
            merge=True,
        )

    log.info("Upserted %s (%d chapters)", series.title, len(series.chapters))
    return "written"


# --------------------------------------------------------------------------
# Worker pool: asyncio.Queue + in-progress lock set
# --------------------------------------------------------------------------

in_progress_manhwas: set[str] = set()
in_progress_lock = asyncio.Lock()


async def try_claim(url: str) -> bool:
    async with in_progress_lock:
        if url in in_progress_manhwas:
            return False
        in_progress_manhwas.add(url)
        return True


async def release(url: str):
    async with in_progress_lock:
        in_progress_manhwas.discard(url)


async def worker(worker_id: int, queue: asyncio.Queue, session: aiohttp.ClientSession):
    while True:
        url = await queue.get()
        if url is None:  # sentinel -> shut down
            queue.task_done()
            break

        claimed = await try_claim(url)
        if not claimed:
            log.debug("Worker %d: %s already claimed, skipping", worker_id, url)
            queue.task_done()
            continue

        try:
            series = await scrape_series(session, url)
            if series:
                await asyncio.to_thread(upsert_series, series)
            else:
                log.warning("Worker %d: could not parse %s", worker_id, url)
        except Exception:
            log.exception("Worker %d: failed on %s", worker_id, url)
        finally:
            await release(url)
            queue.task_done()


async def run_ingestion():
    connector = aiohttp.TCPConnector(limit=NUM_WORKERS + 20)
    async with aiohttp.ClientSession(connector=connector) as session:
        series_links = await discover_series_links(session)
        if not series_links:
            log.warning("No series links discovered — nothing to do.")
            return

        queue: asyncio.Queue = asyncio.Queue()
        for link in series_links:
            queue.put_nowait(link)

        num_workers = min(NUM_WORKERS, max(1, len(series_links)))
        workers = [
            asyncio.create_task(worker(i, queue, session)) for i in range(num_workers)
        ]

        await queue.join()

        for _ in workers:
            queue.put_nowait(None)
        await asyncio.gather(*workers)

        log.info("Ingestion run complete. %d series processed.", len(series_links))


# --------------------------------------------------------------------------
# Deep clean / duplicate purger
# --------------------------------------------------------------------------

def _delete_series_doc(doc_ref):
    for chapter_doc in doc_ref.collection("chapters").stream():
        chapter_doc.reference.delete()
    doc_ref.delete()


async def purge_duplicates():
    """Group all `manga` docs by normalized title OR normalized source
    URL, keep the single most complete doc per group (highest
    chapter_count), and delete the rest along with their `chapters`
    sub-collections.
    """

    def _scan_and_purge():
        docs = list(manga_collection.stream())
        parent = list(range(len(docs)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i, j):
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[rj] = ri

        by_title: dict[str, int] = {}
        by_url: dict[str, int] = {}

        for idx, doc in enumerate(docs):
            data = doc.to_dict() or {}
            t = data.get("title_normalized") or normalize_for_compare(data.get("title", ""))
            u = data.get("source_url_normalized") or normalize_url(data.get("source_url", ""))
            if t:
                if t in by_title:
                    union(idx, by_title[t])
                else:
                    by_title[t] = idx
            if u:
                if u in by_url:
                    union(idx, by_url[u])
                else:
                    by_url[u] = idx

        groups: dict[int, list] = {}
        for idx, doc in enumerate(docs):
            groups.setdefault(find(idx), []).append(doc)

        dup_groups = [g for g in groups.values() if len(g) > 1]
        kept, removed = 0, 0

        for group in dup_groups:
            group_sorted = sorted(
                group,
                key=lambda d: -(d.to_dict() or {}).get("chapter_count", 0),
            )
            keep_doc = group_sorted[0]
            kept += 1
            for dupe in group_sorted[1:]:
                _delete_series_doc(dupe.reference)
                removed += 1
            log.info("Group kept=%s removed=%d others", keep_doc.id, len(group_sorted) - 1)

        return len(dup_groups), kept, removed

    num_groups, kept, removed = await asyncio.to_thread(_scan_and_purge)
    log.info("purge_duplicates: %d duplicate groups, kept %d, removed %d", num_groups, kept, removed)
    return {"duplicate_groups": num_groups, "kept": kept, "removed": removed}


# --------------------------------------------------------------------------
# Entrypoint
# --------------------------------------------------------------------------

async def main():
    await run_ingestion()
    await purge_duplicates()


if __name__ == "__main__":
    asyncio.run(main())
