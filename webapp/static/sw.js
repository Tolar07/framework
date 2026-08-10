// Service Worker for OLP XDV Dashboard
// Cache-first for static assets, network-first for HTML/API
// Offline fallback for the dashboard shell

const CACHE_NAME = 'olp-xdv-v1';
const STATIC_ASSETS = [
  '/static/css/app.css',
  '/static/js/assets.js',
  '/static/js/date_nav.js',
  '/static/js/scan.js',
  '/static/js/tab.js',
  '/static/js/chat.js',
  '/static/js/admin_search.js',
  '/static/js/market_select.js',
  '/static/js/produce.js',
  '/static/js/signoff.js',
  '/static/js/client_search.js',
  '/static/js/theme.js',
  '/static/fonts/Inter-normal-400.woff2',
  '/static/fonts/Inter-normal-500.woff2',
  '/static/fonts/Inter-normal-600.woff2',
  '/static/fonts/BarlowCondensed-normal-600.woff2',
  '/static/fonts/BarlowCondensed-normal-700.woff2',
  '/static/fonts/IBMPlexMono-normal-400.woff2',
  '/static/fonts/IBMPlexMono-normal-600.woff2',
  '/manifest.json'
];

const HTML_PAGES = ['/dashboard', '/admin', '/'];

// Install: cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// Activate: clean old caches, claim clients
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== CACHE_NAME)
          .map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// Fetch: strategy depends on request type
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Only handle same-origin requests
  if (url.origin !== location.origin) {
    return;
  }

  const isStatic = STATIC_ASSETS.some((asset) => url.pathname === asset || url.pathname.endsWith(asset.split('/').pop()));
  const isHtmlPage = HTML_PAGES.some((p) => url.pathname === p || url.pathname.startsWith(p + '/'));
  const isApi = url.pathname.startsWith('/api/') || url.pathname === '/metrics';

  // Static assets: cache-first
  if (isStatic) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // HTML pages & API: network-first with offline fallback
  if (isHtmlPage || isApi) {
    event.respondWith(networkFirst(request));
    return;
  }

  // Default: network-first
  event.respondWith(networkFirst(request));
});

async function cacheFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  if (cached) {
    return cached;
  }
  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    // Offline fallback for static assets not in cache
    return new Response('Offline', { status: 503 });
  }
}

async function networkFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const response = await fetch(request);
    if (response.ok) {
      // Clone before caching - only cache GET responses
      if (request.method === 'GET') {
        cache.put(request, response.clone());
      }
    }
    return response;
  } catch {
    // Network failed - try cache
    const cached = await cache.match(request);
    if (cached) {
      return cached;
    }
    // Offline fallback for HTML pages
    if (request.mode === 'navigate') {
      const offlineHtml = await cache.match('/dashboard');
      if (offlineHtml) {
        return offlineHtml;
      }
    }
    return new Response('Offline', { status: 503 });
  }
}

// Background sync for offline actions (future enhancement)
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-favorites') {
    event.waitUntil(syncFavorites());
  }
});

async function syncFavorites() {
  // Placeholder for syncing favorite fixtures when back online
  console.log('[SW] Background sync: favorites');
}