import asyncio
import aiohttp
import json
import re
import base64
from bs4 import BeautifulSoup

# =========================================================
# ⚙️ إعدادات مستودعك بجيتهاب
# =========================================================
# حسابك ومستودعك الموضحين بتطبيق بيور:
REPO_OWNER = "ezksnar-eng"            # اسم حسابك المربوط[span_0](start_span)[span_0](end_span)
REPO_NAME = "pure-app"                # اكتب هنا اسم مستودع تطبيقك بجيتهاب بالضبط
FILE_PATH = "manga.json"              # اسم الملف داخل المستودع

# التوكن الخارجي المربوط بحسابك (ضع توكين جيتهاب الخاص بك هنا)
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# =========================================================
# 🕷️ محرك سحب البيانات السريع
# =========================================================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

PROXIES = [
    "https://corsproxy.io/?",
    "https://api.allorigins.win/raw?url="
]

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    return ' '.join(text.split()).strip()

async def fetch_html(session, url):
    try:
        async with session.get(url, headers=HEADERS, timeout=10) as resp:
            if resp.status == 200:
                return await resp.text()
    except Exception:
        pass

    for proxy in PROXIES:
        try:
            proxy_url = f"{proxy}{url}"
            async with session.get(proxy_url, headers=HEADERS, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.text()
        except Exception:
            continue
    return None

async def scrape_manga_site(base_url, max_pages=2):
    print(f"🚀 بدء سحب الأعمال من: {base_url}")
    results = []
    
    async with aiohttp.ClientSession() as session:
        for page in range(1, max_pages + 1):
            target_url = base_url if page == 1 else f"{base_url.rstrip('/')}?page={page}"
            print(f"🔄 جاري سحب الصفحة {page}...")
            
            html = await fetch_html(session, target_url)
            if not html:
                break

            soup = BeautifulSoup(html, 'html.parser')
            selectors = [
                '.utao .uta .imgu a', '.listupd .bs .bsx a',
                '.page-item-detail h3 a', '.manga-item a',
                'a[href*="/manga/"]', 'a[href*="/series/"]', 'a[href*="/work/"]'
            ]
            
            found_items = 0
            for sel in selectors:
                elements = soup.select(sel)
                if elements:
                    for a in elements:
                        href = a.get('href')
                        title = clean_text(a.get('title') or a.text)
                        img_tag = a.find('img')
                        cover = img_tag.get('src') if img_tag else ""
                        
                        if href and title and len(title) > 1:
                            if not any(item['url'] == href for item in results):
                                results.append({
                                    "title": title,
                                    "url": href,
                                    "cover": cover
                                })
                                found_items += 1
                    if found_items > 0:
                        break
            
            if found_items == 0:
                break

    print(f"✅ تم سحب {len(results)} عمل بنجاح!")
    return results

# =========================================================
# 📤 تحديث ملف manga.json بجيتهاب تلقائياً
# =========================================================
async def update_github_json(data):
    print("📤 جاري رفع البيانات إلى ملف manga.json في مستودع GitHub...")
    github_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    content_str = json.dumps(data, ensure_ascii=False, indent=2)
    content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

    async with aiohttp.ClientSession() as session:
        # جلب الـ SHA الخاص بالملف الحالي إن وجد لتحديثه
        sha = None
        async with session.get(github_url, headers=headers) as resp:
            if resp.status == 200:
                res_json = await resp.json()
                sha = res_json.get("sha")

        payload = {
            "message": "تحديث تلقائي لقائمة الأعمال عبر Pure Scraper",
            "content": content_b64
        }
        if sha:
            payload["sha"] = sha

        async with session.put(github_url, headers=headers, json=payload) as resp:
            if resp.status in [200, 201]:
                print("🎉 تم تحديث الملف بنجاح! الأعمال أصبحت معروضة داخل تطبيقك الآن.")
            else:
                err_text = await resp.text()
                print(f"❌ حدث خطأ أثناء الرفع: {resp.status}\nالتفاصيل: {err_text}")

# =========================================================
# 🎬 تشغيل السكربت
# =========================================================
async def main():
    # رابط الموقع المراد سحب الأعمال منه (تقدر تغيره لأي موقع مانجا)
    target_site = "https://azorafly.com/"
    
    scraped_data = await scrape_manga_site(target_site, max_pages=2)
    if scraped_data:
        await update_github_json(scraped_data)

if __name__ == "__main__":
    asyncio.run(main())
