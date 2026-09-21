/* =====================================================================
   مهايئات السحب التلقائي والمباشر (Olympus, MangaLik, Azora)
   ===================================================================== */

// دالة مساعدة لتجاوز قيود CORS وقراءة الـ HTML من المتصفح
async function fetchHTML(url) {
  try {
    const proxyUrl = 'https://api.allorigins.win/raw?url=' + encodeURIComponent(url);
    const res = await fetch(proxyUrl);
    if (!res.ok) throw new Error('فشل الوصول عبر Proxy');
    return await res.text();
  } catch (e) {
    const res = await fetch(url);
    return await res.text();
  }
}

// دالة تنظيف الرموز والوسوم
function cleanText(str) {
  if (!str) return '';
  return str
    .replace(/<[^>]*>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/\s+/g, ' ')
    .trim();
}

/* ================= ================= =================
   1. مهايئ موقع Olympus
   ===================================================== */
const OlympusAdapter = {
  id: 'olympus',
  name: 'أوليمبوس (Olympus)',

  async listSeries(baseUrl) {
    const targetUrl = baseUrl.replace(/\/$/, '') + '/series';
    const html = await fetchHTML(targetUrl);
    const results = [];
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    const links = doc.querySelectorAll('a[href*="/series/"]');
    links.forEach((a) => {
      const url = a.href;
      const title = cleanText(a.innerText || a.getAttribute('title'));
      if (url && title && title.length > 2 && !results.some((r) => r.url === url)) {
        results.push({ title, url });
      }
    });

    return results;
  },

  async parseSeriesPage(seriesUrl) {
    const html = await fetchHTML(seriesUrl);
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    const title =
      cleanText(doc.querySelector('h1')?.innerText) ||
      cleanText(doc.querySelector('meta[property="og:title"]')?.content);

    const cover =
      doc.querySelector('meta[property="og:image"]')?.content ||
      doc.querySelector('.summary_image img, .thumb img')?.src || '';

    const description =
      cleanText(doc.querySelector('.entry-content, .synopsis, .manga-excerpt')?.innerText) ||
      cleanText(doc.querySelector('meta[name="description"]')?.content);

    const genres = [];
    doc.querySelectorAll('a[href*="/genre/"]').forEach((g) => {
      const txt = cleanText(g.innerText);
      if (txt && !genres.includes(txt)) genres.push(txt);
    });

    return {
      title: title.replace(/ - Olympus.*$/i, ''),
      cover,
      description,
      genres,
      status: html.includes('مكتمل') ? 'مكتمل' : 'مستمر',
    };
  },
};

/* ================= ================= =================
   2. مهايئ موقع MangaLik
   ===================================================== */
const MangaLikAdapter = {
  id: 'mangalik',
  name: 'مانجا ليك (MangaLik)',

  async listSeries(baseUrl) {
    const targetUrl = baseUrl.replace(/\/$/, '') + '/manga';
    const html = await fetchHTML(targetUrl);
    const results = [];
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    const links = doc.querySelectorAll('a[href*="/manga/"]');
    links.forEach((a) => {
      const url = a.href;
      const title = cleanText(a.innerText || a.getAttribute('title'));
      if (url && title && title.length > 2 && !results.some((r) => r.url === url)) {
        results.push({ title, url });
      }
    });

    return results;
  },

  async parseSeriesPage(seriesUrl) {
    const html = await fetchHTML(seriesUrl);
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    const title =
      cleanText(doc.querySelector('h1')?.innerText) ||
      cleanText(doc.querySelector('meta[property="og:title"]')?.content);

    const cover =
      doc.querySelector('meta[property="og:image"]')?.content ||
      doc.querySelector('.manga-thumbnail img, .summary_image img')?.src || '';

    const description =
      cleanText(doc.querySelector('.manga-excerpt, .entry-content, .synopsis')?.innerText) ||
      cleanText(doc.querySelector('meta[name="description"]')?.content);

    const genres = [];
    doc.querySelectorAll('a[href*="/genre/"], a[href*="/category/"]').forEach((g) => {
      const txt = cleanText(g.innerText);
      if (txt && !genres.includes(txt)) genres.push(txt);
    });

    return {
      title: title.replace(/ - MangaLik.*$/i, ''),
      cover,
      description,
      genres,
      status: html.includes('مكتمل') ? 'مكتمل' : 'مستمر',
    };
  },
};

/* ================= ================= =================
   3. مهايئ موقع Azora
   ===================================================== */
const AzoraAdapter = {
  id: 'azora',
  name: 'أزورا (Azora)',

  async listSeries(baseUrl) {
    const targetUrl = baseUrl.replace(/\/$/, '') + '/series';
    const html = await fetchHTML(targetUrl);
    const results = [];
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    const links = doc.querySelectorAll('a[href*="/series/"]');
    links.forEach((a) => {
      const url = a.href;
      const title = cleanText(a.innerText || a.getAttribute('title'));
      if (url && title && title.length > 2 && !results.some((r) => r.url === url)) {
        results.push({ title, url });
      }
    });

    return results;
  },

  async parseSeriesPage(seriesUrl) {
    const html = await fetchHTML(seriesUrl);
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    const title =
      cleanText(doc.querySelector('h1')?.innerText) ||
      cleanText(doc.querySelector('meta[property="og:title"]')?.content);

    const cover =
      doc.querySelector('meta[property="og:image"]')?.content ||
      doc.querySelector('.summary_image img, .thumb img')?.src || '';

    const description =
      cleanText(doc.querySelector('.entry-content, .synopsis, .manga-excerpt')?.innerText) ||
      cleanText(doc.querySelector('meta[name="description"]')?.content);

    const genres = [];
    doc.querySelectorAll('a[href*="/genre/"]').forEach((g) => {
      const txt = cleanText(g.innerText);
      if (txt && !genres.includes(txt)) genres.push(txt);
    });

    return {
      title: title.replace(/ - Azora.*$/i, ''),
      cover,
      description,
      genres,
      status: html.includes('مكتمل') ? 'مكتمل' : 'مستمر',
    };
  },
};
