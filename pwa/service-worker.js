const AGROMEGA_CACHE_VERSION = "agromega-v1";
const RUNTIME_CACHE = `${AGROMEGA_CACHE_VERSION}-runtime`;
const CACHEABLE_DESTINATIONS = new Set(["font", "image", "script", "style"]);

self.addEventListener("install", function (event) {
    event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", function (event) {
    event.waitUntil(
        caches.keys()
            .then(function (cacheNames) {
                return Promise.all(
                    cacheNames
                        .filter(function (cacheName) {
                            return cacheName !== RUNTIME_CACHE;
                        })
                        .map(function (cacheName) {
                            return caches.delete(cacheName);
                        })
                );
            })
            .then(function () {
                return self.clients.claim();
            })
    );
});

self.addEventListener("fetch", function (event) {
    const request = event.request;

    if (request.method !== "GET") {
        return;
    }

    const url = new URL(request.url);
    if (url.origin !== self.location.origin || url.pathname === "/service-worker.js") {
        return;
    }

    if (!CACHEABLE_DESTINATIONS.has(request.destination)) {
        return;
    }

    event.respondWith(staleWhileRevalidate(request));
});

function staleWhileRevalidate(request) {
    return caches.open(RUNTIME_CACHE).then(function (cache) {
        return cache.match(request).then(function (cachedResponse) {
            const networkResponse = fetch(request)
                .then(function (response) {
                    if (isCacheableResponse(response)) {
                        cache.put(request, response.clone());
                    }
                    return response;
                })
                .catch(function () {
                    return cachedResponse;
                });

            return cachedResponse || networkResponse;
        });
    });
}

function isCacheableResponse(response) {
    return response && response.ok && response.type === "basic";
}
