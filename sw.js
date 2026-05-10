const CACHE_NAME = 'audiostudio-v1';
const ASSETS = [
  './',
  'static/css/style.css',
  'static/js/script.js',
  'static/manifest.json',
  'static/icons/icon-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS);
    })
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
