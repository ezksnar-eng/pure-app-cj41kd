/* =====================================================================
   Worker — ينفّذ مهمة استيراد موقع
   =====================================================================
   هذا الملف بس "ينسّق": ياخذ مهمة من Queue، يشغّل المهايئ (adapter)
   المختار لها، ويحفظ أي نتيجة يرجعها المهايئ بمكتبة بيور المشتركة
   عبر نفس Store اللي يستخدمه التطبيق الرئيسي.

   استيراد تراكمي: كل مرة تشغّل نفس الموقع، يتحقق أول من الأعمال
   الموجودة بالمكتبة (بمقارنة رابط المصدر)، ويتجاوزها، ويضيف بس الجديد.
   يعني تكدر تشغّل نفس الموقع بعد فترة ويجيب بس الإضافات الجديدة.

   ما فيه هنا أي كود يتواصل مع مواقع خارجية بنفسه — هذا كله مسؤولية
   المهايئ (adapters/*.js). إذا المهايئ فاضي (متل القالب الافتراضي)،
   المهمة تفشل برسالة واضحة، وهذا متوقع ومقصود لين تكتب مهايئ حقيقي.

   ماكو أي حد أقصى بالكود لعدد المواقع أو المهام أو الأعمال — القائمة
   تكبر حسب الحاجة بس.
   ===================================================================== */
async function runImportJob(jobId, adapter){
  if(!adapter || typeof adapter.listSeries!=='function'){
    Queue.update(jobId, {status:'failed', message:'ماكو مهايئ صالح لهذا الموقع.'});
    return;
  }

  Queue.update(jobId, {status:'running', progress:1, message:'جاري قراءة قائمة الأعمال من الموقع...'});
  let job = Queue.get(jobId);
  const baseUrl = job.baseUrl;

  let seriesList;
  try{
    seriesList = await adapter.listSeries(baseUrl);
  }catch(e){
    Queue.update(jobId, {status:'failed', message:'تعذّر قراءة قائمة الأعمال: '+(e.message||e)});
    return;
  }

  if(!seriesList || !seriesList.length){
    Queue.update(jobId, {status:'failed', message:'ما تم العثور على أي أعمال بهذا الموقع.'});
    return;
  }

  // نجيب الأعمال الموجودة حالياً بالمكتبة حتى نعرف شنو جديد وشنو مستورد سابقاً
  const existingWorks = await Store.getWorks();
  const existingUrls = new Set(existingWorks.map(w=>w.sourceUrl).filter(Boolean));

  Queue.update(jobId, {found: seriesList.length, message:`تم العثور على ${seriesList.length} عمل، جاري فحص الجديد منها...`});

  let imported = 0, skippedExisting = 0;
  for(let i=0;i<seriesList.length;i++){
    job = Queue.get(jobId);
    if(!job || job.status==='canceled') return; // المستخدم ألغى المهمة

    const s = seriesList[i];
    if(existingUrls.has(s.url)){
      skippedExisting++; // موجود بالمكتبة من قبل (استيراد سابق أو أضيف يدوياً) — نتجاوزه
    } else {
      try{
        const info = await adapter.parseSeriesPage(s.url);
        const w = {
          id: 'w_'+Date.now().toString(36)+Math.random().toString(36).slice(2,6),
          title: info.title || s.title || 'بدون عنوان',
          titleEn: '', type: info.type || 'مانجا', status: info.status || 'مستمر',
          genres: info.genres || [], desc: info.description || '',
          sourceUrl: s.url, nextReleaseDate: '', cover: info.cover || null,
          source: 'استيراد آلي', publisher: baseUrl, from: new Date().getFullYear().toString(),
          chapters: 0, avgRating: 7+Math.random()*2, dist: null,
          createdAt: Date.now(), updatedAt: Date.now(),
        };
        await Store.putWork(w);
        existingUrls.add(s.url);
        imported++;
      }catch(e){
        // نتجاوز عمل فشل ونكمل الباقي، بدون ما نوقف كامل المهمة
      }
    }
    const progress = Math.round(((i+1)/seriesList.length)*100);
    Queue.update(jobId, {progress, imported, skipped:skippedExisting, message:`جديد: ${imported} — موجود سابقاً: ${skippedExisting} من ${seriesList.length}`});
  }

  Queue.update(jobId, {status:'done', progress:100, imported, skipped:skippedExisting,
    message:`اكتمل — أُضيف ${imported} عمل جديد، وتم تجاوز ${skippedExisting} كانوا موجودين بالمكتبة من قبل.`});
}
