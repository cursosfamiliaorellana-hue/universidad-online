// sw.js - Service Worker Nuclear Anti-Caché (Versión 20261019124744)
const CACHE_NAME = 'uo-pwa-20261019124744';

self.addEventListener('install', (e) => {
  self.skipWaiting(); 
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.map(k => k !== CACHE_NAME && caches.delete(k))
    ))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  // REGLA ESTRICTA: El archivo HTML principal JAMÁS debe servirse desde el caché.
  if (e.request.mode === 'navigate' || (e.request.headers.get('accept') && e.request.headers.get('accept').includes('text/html'))) {
    e.respondWith(
      fetch(e.request, { cache: 'no-store' })
      .catch(() => caches.match(e.request))
    );
    return;
  }
  
  // Resto de recursos
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});
