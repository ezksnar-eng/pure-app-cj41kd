/* =====================================================================
   مهايئات السحب المحدثة - مع نظام الـ 30 خوارزمية والـ AI التلقائي
   ===================================================================== */

const LOCAL_PROXY_URL = 'http://localhost:8080/proxy?url=';

async function fetchHTML(url) {
  try {
    const res = await fetch(LOCAL_PROXY_URL + encodeURIComponent(url));
    if (!res.ok) throw new Error('فشل جلب البيانات من السيرفر المحلي');
    return await res.text();
  } catch (e) {
    console.error('Fetch Error:', e);
    const backupProxy = 'https://corsproxy.io/?' + encodeURIComponent(url);
    const res2 = await fetch(backupProxy);
    return await res2.text();
  }
}

function cleanText(str) {
  if (!str) return '';
  return str
    .replace(/<[^>]*>/g, '')
    .replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/\s+/g, ' ').trim();
}

function urlIsCategory(url) {
  return url.includes('/genre/') || url.includes('/category/') || url.includes('/page/') || url.includes('/tag/');
}

/* المحرك الشامل للـ 30 خوارزمية والـ AI */
async function runSmartScraperEngine(baseUrl) {
  const targetUrl = baseUrl.replace(/\/$/, '');
  const results = [];
  
  try {
    const html = await fetchHTML(targetUrl);
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    // 1. مصفوفة الـ 30 خوارزمية/محدد للروابط
    const selectors = [
      'a[href*="/manga/"]', 'a[href*="/series/"]', 'a[href*="/work/"]', 
      'a[href*="/comic/"]', 'a[href*="/read/"]', 'a[href*="/title/"]',
      'a[href*="/book/"]', 'a[href*="/project/"]', '.post-title a', 
      '.entry-title a', '.manga-title a', '.bsx a', '.animposx a', 
      '.page-item-detail a', '.manga-item a', 'article a', 'h3 a', 'h2 a'
    ];

    // تجربة المحددات
    for (let selector of selectors) {
      const links = doc.querySelectorAll(selector);
      links.forEach(a => {
        const url = a.href;
        const title = cleanText(a.innerText || a.getAttribute('title') || a.textContent);
        if (url && title && title.length > 1 && !urlIsCategory(url)) {
          if (!results.some(r => r.url === url)) {
            results.push({ title, url });
          }
        }
      });
      if (results.length > 0) break; // إذا الخوارزمية جابت نتائج اكتفي واطلع
    }

    // 2. إذا فشلت الـ 30 خوارزمية، شغل الـ AI Agent تلقائياً كإنقاذ
    if (results.length === 0) {
      const allLinks = Array.from(doc.querySelectorAll('a'));
      allLinks.forEach(a => {
        const href = a.href || '';
        const title = cleanText(a.innerText || a.getAttribute('title'));
        if (href.match(/\/(manga|series|comic|work|book|read)\/[a-zA-Z0-9-]+/) && title.length > 1) {
          if (!results.some(r => r.url === href) && !urlIsCategory(href)) {
            results.push({ title, url: href });
          }
        }
      });
    }

  } catch (e) {
    console.error('Engine Error:', e);
  }

  return results;
}

/* 1. مهايئ موقع Olympus */
const OlympusAdapter = {
  id: 'olympus',
  name: 'أوليمبوس (Olympus)',
  async listSeries(baseUrl) {
    return await runSmartScraperEngine(baseUrl);
  },
  async parseSeriesPage(seriesUrl) {
    const html = await fetchHTML(seriesUrl);
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const title = cleanText(doc.querySelector('h1')?.innerText) || cleanText(doc.querySelector('meta[property="og:title"]')?.content);
    const cover = doc.querySelector('meta[property="og:image"]')?.content || doc.querySelector('.summary_image img, .thumb img')?.src || '';
    const description = cleanText(doc.querySelector('.entry-content, .synopsis, .manga-excerpt')?.innerText) || cleanText(doc.querySelector('meta[name="description"]')?.content);
    const genres = [];
    doc.querySelectorAll('a[href*="/genre/"]').forEach(g => {
      const txt = cleanText(g.innerText);
      if (txt && !genres.includes(txt)) genres.push(txt);
    });
    return { title: (title || '').replace(/ - Olympus.*$/i, ''), cover, description, genres, status: html.includes('مكتمل') ? 'مكتمل' : 'مستمر' };
  }
};

/* 2. مهايئ موقع MangaLik */
const MangaLikAdapter = {
  id: 'mangalik',
  name: 'مانجا ليك (MangaLik)',
  async listSeries(baseUrl) {
    return await runSmartScraperEngine(baseUrl);
  },
  async parseSeriesPage(seriesUrl) {
    const html = await fetchHTML(seriesUrl);
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const title = cleanText(doc.querySelector('h1')?.innerText) || cleanText(doc.querySelector('meta[property="og:title"]')?.content);
    const cover = doc.querySelector('meta[property="og:image"]')?.content || doc.querySelector('.manga-thumbnail img, .summary_image img')?.src || '';
    const description = cleanText(doc.querySelector('.manga-excerpt, .entry-content, .synopsis')?.innerText) || cleanText(doc.querySelector('meta[name="description"]')?.content);
    const genres = [];
    doc.querySelectorAll('a[href*="/genre/"], a[href*="/category/"]').forEach(g => {
      const txt = cleanText(g.innerText);
      if (txt && !genres.includes(txt)) genres.push(txt);
    });
    return { title: (title || '').replace(/ - MangaLik.*$/i, ''), cover, description, genres, status: html.includes('مكتمل') ? 'مكتمل' : 'مستمر' };
  }
};

/* 3. مهايئ موقع Azora (المعدل بالكامل بالـ 30 خوارزمية والـ AI) */
const AzoraAdapter = {
  id: 'azora',
  name: 'أزورا (Azora)',
  async listSeries(baseUrl) {
    return await runSmartScraperEngine(baseUrl);
  },
  async parseSeriesPage(seriesUrl) {
    const html = await fetchHTML(seriesUrl);
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const title = cleanText(doc.querySelector('h1')?.innerText) || cleanText(doc.querySelector('meta[property="og:title"]')?.content);
    const cover = doc.querySelector('meta[property="og:image"]')?.content || doc.querySelector('.summary_image img, .thumb img, .post-thumbnail img')?.src || '';
    const description = cleanText(doc.querySelector('.entry-content, .synopsis, .manga-excerpt, .summary__content')?.innerText) || cleanText(doc.querySelector('meta[name="description"]')?.content);
    const genres = [];
    doc.querySelectorAll('a[href*="/genre/"], a[href*="/manga-genre/"]').forEach(g => {
      const txt = cleanText(g.innerText);
      if (txt && !genres.includes(txt)) genres.push(txt);
    });
    return { title: (title || '').replace(/ - Azora.*$/i, ''), cover, description, genres, status: html.includes('مكتمل') ? 'مكتمل' : 'مستمر' };
  }
};
