const CACHE_NAME = 'kolosok-cache-v41';
const ASSETS = [
  './index.html',
  './style.css',
  './app.js',
  './icon.svg',
  './daytee_logo_192.png',
  './daytee_logo_512.png',
  './daytee_logo_maskable_192.png',
  './daytee_logo_maskable_512.png',
  './daytee_logo.png',
  './kolosok_vector.png',
  './manifest.json',
  './golden_kolosok.jpg',
  './slavic_ornament.jpg'
];
// API paths must always go to the network (POSTs + polling like /result, /chat).
const API_PREFIXES = ['/submit', '/result', '/chat', '/admin', '/stats'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET' || !req.url.startsWith(self.location.origin)) {
    return; // never intercept API POSTs or cross-origin requests
  }

  const url = new URL(req.url);

  // Never cache API calls — always hit the network so results stay fresh.
  if (API_PREFIXES.some((p) => url.pathname === p || url.pathname.startsWith(p + '/'))) {
    return;
  }

  // Network-first for the HTML shell and app code, so code updates always win.
  const isCode = req.mode === 'navigate'
    || url.pathname === '/'
    || url.pathname.endsWith('.html')
    || url.pathname.endsWith('.js');

  if (isCode) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res && res.status === 200) {
            const clone = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
          }
          return res;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // Cache-first for static assets (images, css) with background refresh.
  event.respondWith(
    caches.match(req).then((cached) => {
      const networkFetch = fetch(req).then((res) => {
        if (res && res.status === 200) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
        }
        return res;
      }).catch(() => cached);
      return cached || networkFetch;
    })
  );
});
