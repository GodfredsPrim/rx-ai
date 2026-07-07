const CACHE_NAME = 'bisarx-v3-2026-07-07';
const STATIC_ASSETS = [
  '/logo.png',
  '/pwa-icon.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

// Network-first for navigation and app code (HTML/CSS/JS) so users always get
// the latest shipped version; cache-first only for rarely-changing icons, and
// only as an offline fallback.
self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const isStaticAsset = STATIC_ASSETS.some((path) => request.url.endsWith(path));
  if (isStaticAsset) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request))
    );
    return;
  }

  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  );
});
