// Fixate Service Worker — offline-first PWA
const CACHE_NAME = 'fixate-v1';
const STATIC_ASSETS = [
  '/',
  '/dashboard/',
  '/static/css/main.css',
  '/static/js/rsvp.js',
  '/static/js/bionic.js',
  '/static/js/noise.js',
  '/static/js/hyperfocus.js',
  '/static/js/video-background.js',
  '/static/js/sound-cues.js',
  '/static/js/tts.js',
  '/static/js/attention-hacks.js',
  '/static/js/bilateral-stimulation.js',
  '/static/js/cliffhanger.js',
  '/static/manifest.json',
];

// Install: cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// Activate: clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch: cache-first for static, network-first for API
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET
  if (event.request.method !== 'GET') return;

  // API requests: network-first
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request)
        .catch(() => caches.match('/offline/'))
    );
    return;
  }

  // Static + pages: cache-first
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const fetched = fetch(event.request).then((response) => {
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      });
      return cached || fetched;
    })
  );
});
