const CACHE_NAME = 'excalidraw-offline-v1';
const urlsToCache = [
  '/',
  '/static/js/react.production.min.js',
  '/static/js/react-dom.production.min.js',
  '/static/js/excalidraw.production.min.js',
  '/static/fonts/Virgil.woff2',
  '/static/fonts/Cascadia.woff2'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});