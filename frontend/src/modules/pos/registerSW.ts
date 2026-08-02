/** Lazily registers the POS offline service worker (pos-sw.js) -- called
 * from POSCheckoutView.vue's onMounted, not main.ts, so it only ever loads
 * for a tenant/user actually using the POS module (technical.md §10.6). */
export function registerPOSServiceWorker() {
  if (!('serviceWorker' in navigator)) return
  navigator.serviceWorker.register('/pos-sw.js').catch(() => {
    // Best-effort -- a failed SW registration (e.g. unsupported browser
    // context, blocked by an extension) shouldn't block the POS screen
    // itself from working; it only degrades offline-reload resilience.
  })
}
