// Service worker: cache the app shell + all /data/*.json with a
// stale-while-revalidate strategy so the site opens offline.
// CACHE_VERSION is bumped from the export manifest's generated_at at
// build time (see scripts/gen-sw.mjs) so a new week invalidates the old
// cache.
const CACHE_VERSION = "__CACHE_VERSION__";
const CACHE_NAME = `bl-hub-${CACHE_VERSION}`;

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE_NAME).then((c) => c.add("/")));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  const isData = url.pathname.startsWith("/data/") && url.pathname.endsWith(".json");
  const isShell = request.mode === "navigate" || url.pathname === "/";

  if (!isData && !isShell) return;

  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(request, { ignoreSearch: true });
      const network = fetch(request)
        .then((resp) => {
          if (resp && resp.status === 200) cache.put(request, resp.clone());
          return resp;
        })
        .catch(() => cached);
      return cached || network;
    }),
  );
});
