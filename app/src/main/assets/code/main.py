import time
import threading
import urllib.parse
import urllib.request
import ssl
import webview
from http.server import BaseHTTPRequestHandler, HTTPServer

# ================= =================
# 1. البروكسي الداخلي (المدمج)
# ================= =================
class IntegratedProxyHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_path.query)
        
        target_url = query.get('url', [None])[0]
        if not target_url and len(self.path) > 1:
            target_url = self.path[1:].lstrip('/')

        if not target_url:
            self._set_headers(400)
            self.wfile.write(b'Missing url parameter')
            return

        if 'appassets.androidplatform.net' in target_url:
            target_url = target_url.replace('https://appassets.androidplatform.net', 'https://azorafly.com')
            target_url = target_url.replace('http://appassets.androidplatform.net', 'https://azorafly.com')

        if not target_url.startswith('http://') and not target_url.startswith('https://'):
            target_url = 'https://' + target_url

        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
            
            req = urllib.request.Request(
                target_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Referer': 'https://azorafly.com/'
                }
            )

            with opener.open(req, timeout=20) as response:
                content = response.read()
                self._set_headers(200)
                self.wfile.write(content)

        except Exception as e:
            self._set_headers(200)
            self.wfile.write(f'Error fetching site: {str(e)}'.encode('utf-8'))

    def log_message(self, format, *args):
        return

def run_proxy_server():
    while True:
        try:
            server_address = ('127.0.0.1', 8080)
            httpd = HTTPServer(server_address, IntegratedProxyHandler)
            print("🚀 Proxy server running on port 8080...")
            httpd.serve_forever()
        except Exception as e:
            print(f"⚠️ إعادة تشغيل البروكسي: {e}")
            time.sleep(2)

# ================= =================
# 2. واجهة التطبيق (HTML / JS)
# ================= =================
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ساحب أزورا الشامل والتصنيفات 🚀</title>
  <style>
    :root { --main: #ff9800; --bg: #0b0b0e; --card: #16161a; --border: #26262e; }
    body { font-family: system-ui, -apple-system, sans-serif; background: var(--bg); color: #fff; padding: 15px; margin: 0; }
    .container { background: var(--card); padding: 20px; border-radius: 18px; max-width: 650px; margin: auto; border: 1px solid var(--border); box-shadow: 0 10px 30px rgba(0,0,0,0.9); }
    h2 { color: var(--main); text-align: center; margin: 0 0 10px; font-size: 22px; }
    .status-badge { display: block; text-align: center; padding: 8px 15px; border-radius: 12px; font-size: 13px; font-weight: bold; background: #1f1a0e; color: var(--main); border: 1px solid var(--main); margin-bottom: 15px; }
    .grid-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 15px; }
    .stat-card { background: #0e0e11; padding: 12px; border-radius: 10px; text-align: center; border: 1px solid var(--border); }
    .stat-card h3 { margin: 0; color: var(--main); font-size: 20px; }
    .stat-card p { margin: 3px 0 0; font-size: 11px; color: #888; }
    #logBox { font-size: 12px; color: #64b5f6; white-space: pre-line; text-align: right; background: #060608; padding: 12px; border-radius: 10px; height: 350px; overflow-y: auto; border: 1px solid var(--border); font-family: monospace; line-height: 1.6; }
    .controls { display: flex; gap: 10px; margin-bottom: 15px; }
    .btn { flex: 1; padding: 12px; border-radius: 10px; border: none; font-weight: bold; cursor: pointer; background: var(--main); color: #000; font-size: 15px; }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  </style>
</head>
<body>

  <div class="container">
    <h2>ساحب أزورا الشامل والتصنيفات (9 أعمال سوية) ⚡</h2>
    <div class="status-badge" id="status">⚡ البروكسي الداخلي متصل وجاهز...</div>

    <div class="controls">
      <button class="btn" id="startBtn">🚀 بدء المسح الشامل والتصنيفات (سرعة 9X)</button>
    </div>

    <div class="grid-stats">
      <div class="stat-card"><h3 id="statManga">0</h3><p>أعمال جديدة</p></div>
      <div class="stat-card"><h3 id="statChaps">0</h3><p>فصول معالجة</p></div>
      <div class="stat-card"><h3 id="statImgs">0</h3><p>صور مرفوعة</p></div>
    </div>

    <div id="logBox">اضغط على زر البدء لبدء السحب الشامل عبر البروكسي الداخلي...</div>
  </div>

  <script type="module">
    import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
    import { getFirestore, collection, addDoc, query, where, getDocs, serverTimestamp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore.js";

    const firebaseConfig = {
      apiKey: "AIzaSyBkaDrsjial5W6xyXPPt1-trJhR7E9n2p4",
      authDomain: "pure-library-2d45d.firebaseapp.com",
      projectId: "pure-library-2d45d",
      storageBucket: "pure-library-2d45d.firebasestorage.app",
      messagingSenderId: "953898341477",
      appId: "1:953898341477:web:85409f5597f894ff13e28c"
    };

    const app = initializeApp(firebaseConfig);
    const db = getFirestore(app);

    let mangaCount = 0, chapCount = 0, imgCount = 0;
    const processedUrls = new Set();
    const CONCURRENCY_LIMIT = 9;

    function printLog(txt) {
      const b = document.getElementById('logBox');
      b.innerText += "\\n> " + txt;
      b.scrollTop = b.scrollHeight;
    }

    function cleanUrl(url) {
      if (!url) return "";
      let cleaned = url.trim();
      if (cleaned.includes('androidplatform.net')) {
        cleaned = cleaned.replace(/https?:\\/\\/appassets\\.androidplatform\\.net/g, 'https://azorafly.com');
      }
      if (cleaned.startsWith("//")) return "https:" + cleaned;
      if (cleaned.startsWith("/")) return "https://azorafly.com" + cleaned;
      if (!cleaned.startsWith("http")) return "https://azorafly.com/" + cleaned;
      return cleaned;
    }

    // جلب حصرياً عن طريق البروكسي الداخلي (Port 8080)
    async function fetchViaInternalProxy(targetUrl) {
      const safeUrl = cleanUrl(targetUrl);
      const endpoint = `http://127.0.0.1:8080/?url=${encodeURIComponent(safeUrl)}`;

      const res = await fetch(endpoint);
      if (res.ok) {
        const text = await res.text();
        if (text && text.length > 100) {
          return new DOMParser().parseFromString(text, 'text/html');
        }
      }
      throw new Error("فشل الجلب عبر البروكسي الداخلي.");
    }

    async function processSingleManga(mUrl) {
      if (processedUrls.has(mUrl)) return;
      processedUrls.add(mUrl);

      try {
        const q = query(collection(db, "manga"), where("sourceUrl", "==", mUrl));
        const snap = await getDocs(q);

        let mangaId;
        const mDoc = await fetchViaInternalProxy(mUrl);
        const title = mDoc.querySelector('meta[property="og:title"]')?.content || mDoc.title || "عمل أزورا";
        const cover = cleanUrl(mDoc.querySelector('meta[property="og:image"]')?.content || "");

        if (!snap.empty) {
          printLog(`  ⚠️ [موجود سابقاً]: ${title}`);
          mangaId = snap.docs[0].id;
        } else {
          const docRef = await addDoc(collection(db, "manga"), {
            title: title,
            cover: cover,
            coverUrl: cover,
            image: cover,
            sourceUrl: mUrl,
            sourceSite: "Azora",
            type: "مانهوا",
            status: "مستمر",
            rating: 8.0,
            createdAt: serverTimestamp()
          });
          mangaId = docRef.id;
          mangaCount++;
          document.getElementById('statManga').innerText = mangaCount;
          printLog(`  ✨ [رفع جديد]: ${title}`);
        }

        const chAnchors = Array.from(mDoc.querySelectorAll('a'))
          .map(a => ({ url: cleanUrl(a.href || a.getAttribute('href')), txt: a.innerText.trim() }))
          .filter(c => c.url && (c.url.includes('chapter') || c.url.includes('/ch-') || c.txt.includes('فصل')));

        const uniqueChaps = [];
        chAnchors.forEach(c => {
          if (!uniqueChaps.some(x => x.url === c.url)) uniqueChaps.push(c);
        });

        for (let j = 0; j < uniqueChaps.length; j++) {
          const ch = uniqueChaps[j];
          try {
            const chDoc = await fetchViaInternalProxy(ch.url);
            const imgElements = Array.from(chDoc.querySelectorAll('img'));
            
            const rawImgs = imgElements.map(img => img.getAttribute('data-src') || img.getAttribute('lazy-src') || img.src).filter(Boolean);
            const validImgs = [...new Set(rawImgs)].map(cleanUrl).filter(src => src && (src.includes('.jpg') || src.includes('.png') || src.includes('.webp') || src.includes('uploads')));

            await addDoc(collection(db, `manga/${mangaId}/chapters`), {
              title: ch.txt || `فصل ${j + 1}`,
              sourceUrl: ch.url,
              images: validImgs,
              order: j + 1
            });

            chapCount++;
            imgCount += validImgs.length;
            document.getElementById('statChaps').innerText = chapCount;
            document.getElementById('statImgs').innerText = imgCount;

          } catch (chErr) {}
        }
      } catch (err) {}
    }

    async function processBatchInParallel(mangaUrls) {
      for (let i = 0; i < mangaUrls.length; i += CONCURRENCY_LIMIT) {
        const batch = mangaUrls.slice(i, i + CONCURRENCY_LIMIT);
        printLog(`\\n⚡ جاري معالجة 9 أعمال سوية عبر البروكسي الداخلي...`);
        await Promise.all(batch.map(url => processSingleManga(url)));
      }
    }

    async function startFullArchiving() {
      document.getElementById('startBtn').disabled = true;
      document.getElementById('status').innerText = "🚀 المسح الشامل شغال بالخلفية...";

      try {
        printLog("🔍 جاري فحص جميع التصنيفات عبر البروكسي الداخلي...");
        let uniqueGenres = [
          "https://azorafly.com/series?type=manhwa",
          "https://azorafly.com/series?type=manga",
          "https://azorafly.com/series"
        ];

        try {
          const homeDoc = await fetchViaInternalProxy("https://azorafly.com");
          const fetchedLinks = Array.from(homeDoc.querySelectorAll('a'))
            .map(a => cleanUrl(a.href || a.getAttribute('href')))
            .filter(h => h.includes('/genre') || h.includes('/genres') || h.includes('/category') || h.includes('/type/'));
          
          if (fetchedLinks.length > 0) {
            uniqueGenres = [...new Set([...fetchedLinks, ...uniqueGenres])];
          }
        } catch (e) {}

        printLog(`🎯 عثرنا على (${uniqueGenres.length}) تصنيف وسيتم مسحهن بكتفاء ذاتي!`);

        for (let g = 0; g < uniqueGenres.length; g++) {
          const genreUrl = uniqueGenres[g];
          printLog(`\\n📁 [تصنيف ${g + 1}/${uniqueGenres.length}] فحص: ${genreUrl}`);

          for (let p = 1; p <= 200; p++) {
            const pageUrl = genreUrl.includes('?') ? `${genreUrl}&page=${p}` : `${genreUrl}?page=${p}`;
            try {
              const pDoc = await fetchViaInternalProxy(pageUrl);
              const links = Array.from(pDoc.querySelectorAll('a'))
                .map(a => cleanUrl(a.href || a.getAttribute('href')))
                .filter(h => h && (h.includes('/series/') || h.includes('/manga/') || h.includes('/work/')));

              const mangaList = [...new Set(links)].filter(url => !processedUrls.has(url));

              if (mangaList.length === 0) {
                printLog(`  🏁 اكتمل مسح التصنيف عند الصفحة ${p - 1}.`);
                break;
              }

              printLog(`  📑 الصفحة ${p}: عثرنا على ${mangaList.length} عمل.`);
              await processBatchInParallel(mangaList);

            } catch (pErr) {
              break;
            }
          }
        }

      } catch (err) {
        printLog(`❌ خطأ عام: ${err.message}`);
      }

      document.getElementById('status').innerText = "🎉 اكتمل سحب كافة الأعمال بنجاح!";
    }

    document.getElementById('startBtn').addEventListener('click', startFullArchiving);
  </script>
</body>
</html>
"""

# ================= =================
# 3. التشغيل المزدوج (بروكسي + واجهة)
# ================= =================
if __name__ == '__main__':
    # تشغيل سيرفر البروكسي كـ Thread مكتفي ذاتياً
    proxy_thread = threading.Thread(target=run_proxy_server, daemon=True)
    proxy_thread.start()

    print("✅ سيرفر البروكسي شغّال بكتفاء ذاتي على المنفذ 8080.")

    # فتح واجهة التطبيق مباشرة
    webview.create_window('ساحب أزورا الشامل', html=HTML_CONTENT, width=700, height=800)
    webview.start()
