import concurrent.futures
import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("azora-scraper")

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

PROXY_URL = os.environ.get("PROXY_URL", "http://127.0.0.1:8000/fetch")
SERIES_LISTING_URL = os.environ.get("TARGET_SERIES_URL", "https://azorafly.com/series/")
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "pure-library-2d45d")
NUM_WORKERS = int(os.environ.get("NUM_WORKERS", "15"))  # عدد متناسب مع الجوال
MAX_LISTING_PAGES = int(os.environ.get("MAX_LISTING_PAGES", "50"))
HTTP_TIMEOUT = int(os.environ.get("HTTP_TIMEOUT", "40"))

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

session = requests.Session()

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
# Proxy Fetching
# --------------------------------------------------------------------------

def fetch_via_proxy(target_url: str, retries: int = 3) -> str | None:
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(PROXY_URL, params={"url": target_url}, timeout=HTTP_TIMEOUT)
            if resp.status_code == 200:
                return resp.text
            log.warning("Proxy returned %s for %s", resp.status_code, target_url)
        except Exception as e:
            log.warning("Proxy fetch error (attempt %s/%s) for %s: %s", attempt, retries, target_url, e)
    return None

# --------------------------------------------------------------------------
# Firestore via Lightweight REST API
# --------------------------------------------------------------------------

def upsert_firestore_rest(series: SeriesData):
    base_url = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents"
    doc_path = f"{base_url}/manga/{series.slug}"
    
    # تحويل البيانات لصيغة Firestore REST API
    payload = {
        "fields": {
            "title": {"stringValue": series.title},
            "title_normalized": {"stringValue": normalize_for_compare(series.title)},
            "source_url": {"stringValue": series.source_url},
            "source_url_normalized": {"stringValue": normalize_url(series.source_url)},
            "score": {"stringValue": series.score},
            "cover_url": {"stringValue": series.cover_url},
            "description": {"stringValue": series.description},
            "chapter_count": {"integerValue": str(len(series.chapters))},
            "genres": {"arrayValue": {"values": [{"stringValue": g} for g in series.genres]}},
        }
    }
    
    try:
        session.patch(doc_path, json=payload)
        log.info("Upserted %s to Firestore", series.title)
    except Exception as e:
        log.error("Failed to push %s to Firestore REST: %s", series.title, e)

# --------------------------------------------------------------------------
# Scraping Logic
# --------------------------------------------------------------------------

def discover_series_links() -> list[str]:
    links = set()
    url = SERIES_LISTING_URL
    seen_pages = set()

    for _ in range(MAX_LISTING_PAGES):
        if not url or url in seen_pages:
            break
        seen_pages.add(url)

        html = fetch_via_proxy(url)
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

def scrape_chapter_pages(chapter_url: str) -> list[str]:
    html = fetch_via_proxy(chapter_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    pages = []
    for img in soup.select(SEL["page_image"]):
        src = img.get("data-src") or img.get("src")
        if src and src.strip():
            pages.append(src.strip())
    return pages

def scrape_and_process(series_url: str):
    html = fetch_via_proxy(series_url)
    if not html:
        return

    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one(SEL["title"])
    if not title_el:
        return
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
    for row in chapter_rows:
        ch_title = row.get_text(strip=True)
        ch_url = row.get("href")
        if ch_url:
            pages = scrape_chapter_pages(ch_url)
            series.chapters.append(ChapterData(title=ch_title, url=ch_url, pages=pages))

    upsert_firestore_rest(series)

# --------------------------------------------------------------------------
# Entrypoint
# --------------------------------------------------------------------------

def main():
    links = discover_series_links()
    if not links:
        log.warning("No links found.")
        return

    log.info("Starting extraction with ThreadPool...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        executor.map(scrape_and_process, links)

    log.info("Processing complete!")

if __name__ == "__main__":
    main()
