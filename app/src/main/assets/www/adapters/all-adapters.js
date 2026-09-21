/* =====================================================================
   المحرك الموحد للسحب (Smart Scraper Engine) — نسخة محدّثة كاملة
   =====================================================================
   ملاحظة ثابتة ما تتغير مهما تكرر الطلب:
   هذا الملف يستخرج "بيانات وصفية فقط" لكل عمل — عنوان، رابط مصدر،
   غلاف، وصف، تصنيفات، حالة. ما فيه ولا سطر واحد يحمّل أو ينسخ صور
   فصول (صفحات القراءة نفسها) من موقع ثاني. القراءة الفعلية تصير من
   الموقع الأصلي عبر sourceUrl، بالضبط متل ما هو موضح بـ README.md و
   GEMINI_BRIEFING.md بهذا المجلد. إذا احتجت تتأكد ليش، اقرا الملفين.

   شنو تغيّر بهذي النسخة:
   1) fetchHTML صار "دالة جلب موحدة" حقيقية: مهلة زمنية (timeout) عبر
      AbortController، وسلسلة مصادر بديلة (Local Proxy → Backup Proxy 1
      → Backup Proxy 2) بدل مصدر واحد بديل بس.
   2) مصفوفة المحددات (Selectors) توسّعت لأكثر من 20 نمط شائع لمواقع
      المانجا/المانهوا (ثيمات ووردبريس المختلفة + بنى مخصصة).
   3) أضيفت خوارزمية Fallback ثانية تعتمد على قراءة نصية للرابط ونصه
      المجاور مباشرة (Regex) لما الـ DOMParser + المحددات كلها تفشل —
      مفيدة لصفحات HTML مشوّهة أو غير قياسية. ملاحظة مهمة: هذا Fallback
      نصّي على نفس الـ HTML المُستلم، وليس حلاً لمواقع الـ Client-side
      Rendering (React/Vue تبني المحتوى بجافاسكربت بعد التحميل) — تلك
      تحتاج فعلياً Headless Browser بالسيرفر، وهذا خارج نطاق ملف يشتغل
      بالمتصفح. الحل المقترح لها موجود بـ GEMINI_BRIEFING.md (دالة
      Netlify Function تسوي render وترجع HTML جاهز).
   4) دالة parseSeriesPage صارت عامة (generic) بمحددات موسّعة، وتقدر أي
      مهايئ موقع جديد يستخدمها مباشرة أو يعطيها محددات إضافية خاصة فيه.
   5) كل مهايئ اتغلّف بكائن Adapter موحّد الشكل: {id, name, listSeries,
      parseSeriesPage} — جاهز للتسجيل مباشرة بمتغير ADAPTERS بـ admin.html.
   ===================================================================== */

/* ---------------------------------------------------------------------
   1) CORS & Fetch Handler — دالة جلب موحدة مع مهلة زمنية ومصادر بديلة
   --------------------------------------------------------------------- */
const FETCH_SOURCES = [
  // المصدر المحلي أولاً (لو مشغّل عندك سيرفر بروكسي محلي على هذا المنفذ)
  { name: 'local', build: (url) => 'http://localhost:8080/proxy?url=' + encodeURIComponent(url) },
  // مصدر بديل 1
  { name: 'corsproxy.io', build: (url) => 'https://corsproxy.io/?' + encodeURIComponent(url) },
  // مصدر بديل 2 (احتياطي إضافي لو الأول فشل أو رجع فاضي)
  { name: 'allorigins', build: (url) => 'https://api.allorigins.win/raw?url=' + encodeURIComponent(url) },
];

function fetchWithTimeout(url, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { signal: controller.signal }).finally(() => clearTimeout(timer));
}

/* يجرب كل مصدر بالترتيب لين وحد ينجح ويرجع HTML غير فاضي.
   timeoutMs: مهلة كل محاولة لحالها (مو المجموع). */
async function fetchHTML(targetUrl, timeoutMs = 12000) {
  let lastError = null;
  for (const source of FETCH_SOURCES) {
    try {
      const res = await fetchWithTimeout(source.build(targetUrl), timeoutMs);
      if (!res.ok) { lastError = new Error(`(${source.name}) رمز الحالة ${res.status}`); continue; }
      const html = await res.text();
      if (html && html.length > 50) return html; // تجاهل ردود فاضية/قصيرة جداً واعتبرها فشل
      lastError = new Error(`(${source.name}) رد فاضي أو قصير جداً`);
    } catch (e) {
      lastError = e && e.name === 'AbortError' ? new Error(`(${source.name}) انتهت المهلة الزمنية`) : e;
      continue; // جرب المصدر التالي
    }
  }
  throw new Error('فشلت كل مصادر الجلب: ' + (lastError ? (lastError.message || lastError) : 'سبب غير معروف'));
}

/* ---------------------------------------------------------------------
   أدوات مساعدة عامة
   --------------------------------------------------------------------- */
function cleanText(str) {
  if (!str) return '';
  return String(str)
    .replace(/<[^>]*>/g, '')
    .replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ').trim();
}

function urlIsCategory(url) {
  return /\/(genre|category|tag|page|author|status|type)\//i.test(url) || /[?&]page=/i.test(url);
}

function resolveUrl(href, baseUrl) {
  try { return new URL(href, baseUrl).href; } catch (e) { return href; }
}

/* ---------------------------------------------------------------------
   2) Robust Engine — أكثر من 20 محدد/خوارزمية لاستخراج قائمة الأعمال
   --------------------------------------------------------------------- */
const LISTING_SELECTORS = [
  // أنماط روابط مباشرة حسب بنية الرابط نفسه
  'a[href*="/manga/"]', 'a[href*="/series/"]', 'a[href*="/work/"]',
  'a[href*="/comic/"]', 'a[href*="/comics/"]', 'a[href*="/read/"]',
  'a[href*="/title/"]', 'a[href*="/titles/"]', 'a[href*="/book/"]',
  'a[href*="/project/"]', 'a[href*="/novel/"]', 'a[href*="/webtoon/"]',
  // أنماط شائعة لثيمات ووردبريس مانجا (Madara, WPMangaStream وغيرها)
  '.page-item-detail a.chapter-name', '.page-item-detail h3 a',
  '.manga-item a', '.bsx a', '.animposx a', '.bs .bsx a',
  '.utao .luf a', '.listupd .bsx a',
  // أنماط عناوين عامة (WordPress قياسي)
  '.post-title a', '.entry-title a', '.manga-title a', 'article .title a',
  // أنماط شبكية/بطاقات عامة (fallback واسع قبل اللجوء لـ Regex)
  '.grid .card a', '.item-summary a', 'ul.manga-list li a',
  // عناوين ضمن article/h2/h3 عامة (آخر خط دفاع قبل Regex)
  'article a', 'h3 a', 'h2 a',
];

/* يجرب المحددات بالترتيب، ويوقف أول ما يوحد نتائج كافية */
function runSelectorEngine(doc, baseUrl) {
  const results = [];
  for (const selector of LISTING_SELECTORS) {
    let nodes;
    try { nodes = doc.querySelectorAll(selector); } catch (e) { continue; } // محدد غير صالح بمتصفح معين، تجاوزه
    nodes.forEach((a) => {
      const href = a.getAttribute('href');
      if (!href) return;
      const url = resolveUrl(href, baseUrl);
      const title = cleanText(a.getAttribute('title') || a.textContent);
      if (url && title && title.length > 1 && !urlIsCategory(url)) {
        if (!results.some((r) => r.url === url)) results.push({ title, url });
      }
    });
    if (results.length >= 3) break; // كفاية نتائج تدل إن هذا المحدد صحيح لهذا الموقع
  }
  return results;
}

/* ---------------------------------------------------------------------
   3) Fallback Mechanism — تحليل نصّي (Regex) لما كل المحددات تفشل
   --------------------------------------------------------------------- */
const WORK_PATH_PATTERN = /\/(manga|series|comic|comics|work|book|read|title|titles|novel|webtoon)\/[a-zA-Z0-9\u0600-\u06FF_-]+\/?/i;

function runRegexFallback(html, baseUrl) {
  const results = [];
  // يمسك كل وسم <a ...>محتوى</a> ويقرا الرابط والنص المجاور له مباشرة
  const anchorPattern = /<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi;
  let match;
  while ((match = anchorPattern.exec(html)) !== null) {
    const rawHref = match[1];
    const rawInner = match[2];
    if (!WORK_PATH_PATTERN.test(rawHref)) continue;
    const url = resolveUrl(rawHref, baseUrl);
    if (urlIsCategory(url)) continue;

    let title = cleanText(rawInner);
    // إذا النص داخل الرابط فاضي (صورة بس مثلاً)، دوّر على title="" بنفس وسم الرابط
    if (!title) {
      const titleAttr = /title=["']([^"']+)["']/i.exec(match[0]);
      if (titleAttr) title = cleanText(titleAttr[1]);
    }
    if (!title || title.length < 2) continue;
    if (!results.some((r) => r.url === url)) results.push({ title, url });
  }
  return results;
}

/* نقطة الدخول الموحدة لاستخراج قائمة الأعمال: محددات → Regex fallback */
async function runSmartScraperEngine(baseUrl) {
  const targetUrl = baseUrl.replace(/\/$/, '');
  const html = await fetchHTML(targetUrl);

  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');

  let results = runSelectorEngine(doc, targetUrl);
  if (results.length === 0) results = runRegexFallback(html, targetUrl);

  return results;
}

/* ---------------------------------------------------------------------
   4) قراءة صفحة عمل واحد — بيانات وصفية فقط (بدون فصول/صور)
   --------------------------------------------------------------------- */
const TITLE_SELECTORS = ['h1', '.post-title h1', '.entry-title', 'meta[property="og:title"]'];
const COVER_SELECTORS = ['meta[property="og:image"]', '.summary_image img', '.thumb img', '.post-thumbnail img', '.manga-thumbnail img'];
const DESC_SELECTORS = ['.entry-content', '.synopsis', '.manga-excerpt', '.summary__content', 'meta[name="description"]'];
const GENRE_SELECTORS = ['a[href*="/genre/"]', 'a[href*="/genres/"]', 'a[href*="/manga-genre/"]', 'a[href*="/category/"]'];

function pickFirst(doc, selectors) {
  for (const sel of selectors) {
    const el = doc.querySelector(sel);
    if (!el) continue;
    const val = el.tagName === 'META' ? el.getAttribute('content') : (el.innerText || el.textContent);
    const cleaned = cleanText(val);
    if (cleaned) return cleaned;
  }
  return '';
}

function pickFirstAttr(doc, selectors, attr) {
  for (const sel of selectors) {
    const el = doc.querySelector(sel);
    if (!el) continue;
    const val = el.tagName === 'META' ? el.getAttribute('content') : el.getAttribute(attr);
    if (val) return val;
  }
  return '';
}

/* دالة عامة تصلح لأغلب المواقع، وأي مهايئ يقدر يستخدمها مباشرة أو
   يمررلها محددات إضافية خاصة بموقعه عبر extra */
async function parseGenericSeriesPage(seriesUrl, extra = {}) {
  const html = await fetchHTML(seriesUrl);
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');

  const titleSelectors = (extra.titleSelectors || []).concat(TITLE_SELECTORS);
  const coverSelectors = (extra.coverSelectors || []).concat(COVER_SELECTORS);
  const descSelectors = (extra.descSelectors || []).concat(DESC_SELECTORS);
  const genreSelectors = (extra.genreSelectors || []).concat(GENRE_SELECTORS);

  let title = pickFirst(doc, titleSelectors);
  if (extra.titleSuffixStrip) title = title.replace(extra.titleSuffixStrip, '');

  const cover = pickFirstAttr(doc, coverSelectors, 'src');
  const description = pickFirst(doc, descSelectors);

  const genres = [];
  genreSelectors.forEach((sel) => {
    let nodes; try { nodes = doc.querySelectorAll(sel); } catch (e) { return; }
    nodes.forEach((g) => {
      const txt = cleanText(g.textContent);
      if (txt && !genres.includes(txt)) genres.push(txt);
    });
  });

  const bodyText = doc.body ? doc.body.textContent : html;
  const status = /مكتمل|completed/i.test(bodyText) ? 'مكتمل' : 'مستمر';

  return { title, cover, description, genres, status };
}

/* ---------------------------------------------------------------------
   5) Export Adapter Object — غلاف موحّد لتسجيل أي موقع بسهولة
   --------------------------------------------------------------------- */
function createAdapter({ id, name, titleSuffixStrip, ...extra }) {
  return {
    id,
    name,
    async listSeries(baseUrl) {
      return await runSmartScraperEngine(baseUrl);
    },
    async parseSeriesPage(seriesUrl) {
      return await parseGenericSeriesPage(seriesUrl, { titleSuffixStrip, ...extra });
    },
  };
}

/* ---------------------------------------------------------------------
   المهايئات المسجّلة حالياً — بنفس الأسماء العامة (Global) القديمة حتى
   admin.html يستمر يشتغل من غير أي تعديل فيه
   --------------------------------------------------------------------- */
const OlympusAdapter = createAdapter({
  id: 'olympus',
  name: 'أوليمبوس (Olympus)',
  titleSuffixStrip: / - Olympus.*$/i,
});

const MangaLikAdapter = createAdapter({
  id: 'mangalik',
  name: 'مانجا ليك (MangaLik)',
  titleSuffixStrip: / - MangaLik.*$/i,
  coverSelectors: ['.manga-thumbnail img'],
  descSelectors: ['.manga-excerpt'],
});

const AzoraAdapter = createAdapter({
  id: 'azora',
  name: 'أزورا (Azora)',
  titleSuffixStrip: / - Azora.*$/i,
  coverSelectors: ['.post-thumbnail img'],
  genreSelectors: ['a[href*="/manga-genre/"]'],
});

/* لإضافة موقع جديد بسرعة بدون كتابة أي كود تحليل يدوي:
   const NewSiteAdapter = createAdapter({ id: 'new-site', name: 'اسم الموقع' });
   ثم سجّله بـ admin.html بنفس طريقة الباقي. إذا احتاج محددات خاصة به
   (لأن بنية موقعه مختلفة)، مرّرها كـ extra: coverSelectors/descSelectors/
   genreSelectors/titleSelectors — نفس فكرة MangaLikAdapter و AzoraAdapter فوق. */
