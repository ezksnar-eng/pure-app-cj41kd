import sys
import subprocess
import os

# تثبيت المكتبات أوتوماتيكياً من داخل الكود إذا كانت مفقودة
def install_and_import(package, import_name=None):
    if import_name is None:
        import_name = package
    try:
        __import__(import_name)
    except ImportError:
        print(f"📦 جاري تثبيت مكتبة [{package}] أوتوماتيكياً...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# تثبيت جميع التبعيات المطلوبة
install_and_import("aiohttp")
install_and_import("beautifulsoup4", "bs4")
install_and_import("firebase-admin", "firebase_admin")

import asyncio
import re
import aiohttp
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore

# تهيئة الفايربيس
SERVICE_KEY_FILE = 'serviceAccountKey.json'

if not os.path.exists(SERVICE_KEY_FILE):
    print(f"❌ ملف المفتاح [{SERVICE_KEY_FILE}] غير موجود بنفس المجلد!")
    sys.exit(1)

try:
    cred = credentials.Certificate(SERVICE_KEY_FILE)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"❌ خطأ في الاتصال بالفايربيس: {e}")
    sys.exit(1)

# تحديد عدد العمال (Workers) بحد آمن
MAX_WORKERS = 10
semaphore = asyncio.Semaphore(MAX_WORKERS)

async def fetch_page(session, url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        async with session.get(url, headers=headers, timeout=15) as resp:
            if resp.status == 200:
                return await resp.text()
    except Exception as e:
        print(f"❌ خطأ بالوصول للرابط: {e}")
    return None

def clean_chapter_name(text):
    match = re.search(r'(?:الفصل|chapter)\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    return f"الفصل {match.group(1)}" if match else text.strip()

async def process_chapter(session, manga_ref, ch_title, ch_url):
    async with semaphore:
        html = await fetch_page(session, ch_url)
        if not html:
            return
        
        soup = BeautifulSoup(html, 'html.parser')
        images = [img.get('data-src') or img.get('src') for img in soup.select('div.reader-area img, div#readerarea img, div.page-break img')]
        images = [i.strip() for i in images if i and i.strip()]
        
        if images:
            doc_id = re.sub(r'[^a-zA-Z0-9]', '_', ch_title)
            manga_ref.collection('chapters').document(doc_id).set({
                'title': ch_title,
                'images': images,
                'url': ch_url,
                'updated_at': firestore.SERVER_TIMESTAMP
            }, merge=True)
            print(f"  └─ ✅ تم سحب: {ch_title} ({len(images)} صورة)")

async def scrape_url(url):
    print(f"\n🚀 جاري جلب الرابط: {url}")
    async with aiohttp.ClientSession() as session:
        html = await fetch_page(session, url)
        if not html:
            print("❌ تعذر الوصول لصفحة الرابط.")
            return

        soup = BeautifulSoup(html, 'html.parser')
        title_tag = soup.select_one('h1.entry-title, h1.tit, div.post-title h1')
        if not title_tag:
            print("❌ لم يتم العثور على اسم المانجا.")
            return

        manga_title = title_tag.text.strip()
        doc_id = re.sub(r'[^a-zA-Z0-9_]', '_', manga_title)
        manga_ref = db.collection('manga').document(doc_id)

        manga_ref.set({
            'title': manga_title,
            'source_url': url,
            'updated_at': firestore.SERVER_TIMESTAMP
        }, merge=True)

        chapters = [(clean_chapter_name(a.text), a.get('href')) for a in soup.select('div#chapterlist ul li a, ul.clist li a') if a.get('href')]
        print(f"📦 تم العثور على {len(chapters)} فصل لـ [{manga_title}]. جاري التحميل...")

        tasks = [process_chapter(session, manga_ref, title, ch_url) for title, ch_url in chapters]
        await asyncio.gather(*tasks)
        print(f"🎉 اكتمل سحب {manga_title} بنجاح!")

def clean_database():
    print("\n🧹 جاري فحص وتنظيف المكررات من قاعدة البيانات...")
    docs = list(db.collection('manga').stream())
    seen_keys = set()
    deleted = 0

    for doc in docs:
        data = doc.to_dict()
        clean_title = re.sub(r'[^a-zA-Z0-9أ-ي]', '', data.get('title', '')).lower()
        key = data.get('source_url') or clean_title

        if key in seen_keys:
            for c in doc.reference.collection('chapters').list_documents():
                c.delete()
            doc.reference.delete()
            deleted += 1
        else:
            if key:
                seen_keys.add(key)

    print(f"✅ اكتمل التنظيف! تم حذف {deleted} عمل مكرر.")

def main_menu():
    while True:
        print("\n" + "="*40)
        print("   🤖 سكريبت الترمنال لسحب وتنظيف المانجا")
        print("="*40)
        print("1. سحب رابط مانجا / فصل")
        print("2. تنظيف المكررات من القاعدة")
        print("3. خروج")
        
        choice = input("\nاختر رقم الإجراء (1-3): ").strip()
        
        if choice == '1':
            target_url = input("أدخل الرابط: ").strip()
            if target_url:
                asyncio.run(scrape_url(target_url))
        elif choice == '2':
            clean_database()
        elif choice == '3':
            print("👋 في أمان الله!")
            break
        else:
            print("❌ خيار غير صحيح.")

if __name__ == "__main__":
    main_menu()
