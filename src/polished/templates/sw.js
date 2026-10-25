// Polished service worker (DESIGN 11): precache the offline page and static files, serve
// /static cache-first, answer a failed navigation with /offline. It never caches HTML,
// partials or cross-origin requests and never touches a non-GET request.
const VERSION = {{ version|tojson }};
const CACHE = `polished-static-${VERSION}`;
const SUFFIX = `?v=${VERSION}`;
const PRECACHE = [
  "/offline",
  `/static/css/app.css${SUFFIX}`,
  `/static/vendor/htmx.min.js${SUFFIX}`,
  `/static/js/register-sw.js${SUFFIX}`,
  "/static/icons/apple-touch-icon.png",
  "/static/icons/icon-192.png",
];
// A development server has version "dev", so its URLs never change: leave static files alone.
const CACHE_STATIC = VERSION !== "dev";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names.filter((n) => n.startsWith("polished-static-") && n !== CACHE).map((n) => caches.delete(n))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match("/offline")));
    return;
  }

  if (CACHE_STATIC && url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.open(CACHE).then((cache) =>
        cache.match(request).then(
          (hit) =>
            hit ||
            fetch(request).then((response) => {
              if (response.ok) cache.put(request, response.clone());
              return response;
            })
        )
      )
    );
  }
});
