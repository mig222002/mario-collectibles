/* Mario Collectibles — service worker
   - La web (index.html, iconos, fotos de firmas/) : red primero, copia guardada si no hay conexión.
   - El CSV de Google Sheets : red primero, última copia buena si no hay conexión.
   - Imágenes de otras webs : no se guardan (ocuparían muchísimo). */
const CACHE="mc-v1";
self.addEventListener("install",e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(["./","./manifest.webmanifest","./icon-192.png"])).catch(()=>{}));self.skipWaiting()});
self.addEventListener("activate",e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener("fetch",e=>{
  const r=e.request;if(r.method!=="GET")return;
  const u=new URL(r.url);
  const isCSV=/docs\.google\.com|googleusercontent\.com/.test(u.hostname)&&/output=csv/.test(u.search);
  const same=u.origin===self.location.origin;
  if(!isCSV&&!same)return;
  const key=isCSV?"csv-latest":(r.mode==="navigate"?"./":r);
  e.respondWith(fetch(r).then(res=>{if(res&&res.ok){const cp=res.clone();caches.open(CACHE).then(c=>c.put(key,cp))}return res})
    .catch(()=>caches.match(key).then(m=>m||(r.mode==="navigate"?caches.match("./"):Response.error()))));
});
