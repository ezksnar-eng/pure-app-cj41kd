/* =====================================================================
   Sites — سجل المواقع المضافة (لا يوجد أي حد أقصى لعددها)
   =====================================================================
   كل موقع تضيفه ينحفظ هنا مرة وحدة (اسم + رابط + المهايئ المختار)،
   وبعدين تقدر تضغط "استورد الجديد" على نفس الموقع بأي وقت — بدون
   ما تعيد كتابة الرابط، وبدون ما يكرر الأعمال المستوردة سابقاً
   (هذا الجزء يسويه worker.js عن طريق مقارنة رابط المصدر).
   ===================================================================== */
const Sites = (function(){
  const KEY = 'rafe_sites_v1';
  function all(){ try{ return JSON.parse(localStorage.getItem(KEY))||[]; }catch(e){ return []; } }
  function save(a){ localStorage.setItem(KEY, JSON.stringify(a)); }

  function add(site){
    const a = all();
    const s = Object.assign({
      id: 'site_'+Date.now().toString(36)+Math.random().toString(36).slice(2,6),
      createdAt: Date.now(),
      lastImportAt: 0,
      lastResult: '',
    }, site);
    a.unshift(s);
    save(a);
    return s;
  }
  function update(id, patch){
    const a = all();
    const s = a.find(x=>x.id===id);
    if(!s) return null;
    Object.assign(s, patch);
    save(a);
    return s;
  }
  function remove(id){ save(all().filter(x=>x.id!==id)); }
  function list(){ return all(); }

  return {add, update, remove, list};
})();
