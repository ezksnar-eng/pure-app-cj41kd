/* =====================================================================
   Queue — مدير مهام عام (قائمة انتظار + تتبع تقدم)
   =====================================================================
   هذا ملف بنية تحتية عامة بس: ينشئ مهمة، يعطيها رقم (Job ID)، يحفظ
   حالتها وتقدمها بالتخزين المحلي، وتقدر تسرد كل المهام. ما فيه أي
   منطق مرتبط بموقع معين — هذا شغل adapters/ (راجع الملف داخلها).
   ===================================================================== */
const Queue = (function(){
  const KEY = 'rafe_jobs_v1';
  function all(){ try{ return JSON.parse(localStorage.getItem(KEY))||[]; }catch(e){ return []; } }
  function save(a){ localStorage.setItem(KEY, JSON.stringify(a)); }

  function create(job){
    const a = all();
    const j = Object.assign({
      id: 'job_'+Date.now().toString(36)+Math.random().toString(36).slice(2,6),
      status: 'queued',      // queued | running | done | failed | canceled
      progress: 0,           // 0-100
      message: '',
      found: 0,               // عدد الأعمال المكتشفة لحد الآن
      imported: 0,             // عدد الأعمال اللي انحفظت فعلياً بالمكتبة
      createdAt: Date.now(),
      updatedAt: Date.now(),
    }, job);
    a.unshift(j);
    save(a);
    return j;
  }
  function update(id, patch){
    const a = all();
    const j = a.find(x=>x.id===id);
    if(!j) return null;
    Object.assign(j, patch, {updatedAt: Date.now()});
    save(a);
    return j;
  }
  function get(id){ return all().find(x=>x.id===id); }
  function list(){ return all(); }
  function remove(id){ save(all().filter(x=>x.id!==id)); }

  return {create, update, get, list, remove};
})();
