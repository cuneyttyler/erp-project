// REQ-POS-008 / technical.md §10.6: keeps the POS screen itself loadable
// during a short outage (a reload, or reopening the browser tab) -- the
// IndexedDB queue (src/modules/pos/offlineQueue.ts) is what keeps *taking
// sales* working offline; this is the other half, the app shell staying
// available at all. Registered lazily from src/modules/pos/registerSW.ts,
// only once a POS route is actually visited (not from main.ts) -- scoped to
// POS by when it's registered, not by service-worker `scope`, since `scope`
// alone can't reach the hashed /assets/* files a Vite build produces without
// a build-time precache manifest (that's what vite-plugin-pwa would add;
// deliberately not pulled in for this pass -- see this file's caller for
// what that tradeoff means in practice).
//
// Strategy: network-first, falling back to a same-origin cache. Every
// successful same-origin GET response is cached opportunistically as the
// user browses while online; when a request fails outright (offline), the
// most recent cached response for that exact URL is served instead. API
// requests (/api/*) are explicitly never cached or served stale -- serving
// yesterday's stock count while offline would be actively wrong, not
// helpful; those requests are left to fail through to the app's own
// IndexedDB queue, which is what actually understands how to recover them.
//
// Known limits, not hidden: the very first visit must happen online (there's
// nothing to fall back to before that); this does not survive the browser's
// site data being cleared; it's opportunistic caching, not a versioned
// precache, so a stale asset can linger until it's re-fetched online again.

const CACHE_NAME = 'pos-shell-v1'

self.addEventListener('install', (event) => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)
  if (event.request.method !== 'GET') return
  if (url.origin !== self.location.origin) return
  if (url.pathname.startsWith('/api/')) return

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone()
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy))
        return response
      })
      .catch(() => caches.match(event.request).then((cached) => cached || Response.error())),
  )
})
