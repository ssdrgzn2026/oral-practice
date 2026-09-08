/* MiscHub Service Worker：只缓存静态资源，页面和接口始终走网络 */
const CACHE = "mischub-static-v1";
const STATIC = [
    "/static/css/style.css",
    "/static/js/track.js",
    "/static/img/bg.jpg",
    "/static/manifest.json",
];

self.addEventListener("install", (e) => {
    e.waitUntil(caches.open(CACHE).then((c) => c.addAll(STATIC)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
    e.waitUntil(
        caches.keys()
            .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
            .then(() => self.clients.claim())
    );
});

self.addEventListener("fetch", (e) => {
    const url = new URL(e.request.url);
    if (e.request.method !== "GET") return;
    if (url.pathname.startsWith("/static/")) {
        e.respondWith(
            caches.match(e.request).then((hit) => hit || fetch(e.request).then((resp) => {
                const copy = resp.clone();
                caches.open(CACHE).then((c) => c.put(e.request, copy));
                return resp;
            }))
        );
    }
    // 其余请求（页面、API、Streamlit）一律走网络
});
