const CACHE_NAME = "sage-school-app-v10";
const APP_SHELL = [
  "/",
  "/index.html",
  "/styles.css",
  "/app.js",
  "/manifest.webmanifest",
  "/sage-logo.svg",
  "/sage-app-icon-192.png",
  "/sage-app-icon-512.png",
  "/sage-school-life.jpg",
  "/sage-sports-day.jpg",
  "/sage-independence-day.jpg",
  "/sage-playground.jpg",
  "/creative-studio.svg",
  "/garden-club.svg",
  "/creative-studio-photo.jpg",
  "/garden-club-photo.jpg",
];

function cacheResponse(request, response, event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.put(request, response.clone()))
      .catch((error) => {
        console.error("Could not save an app resource for offline use:", error);
      }),
  );
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => Promise.all(
        cacheNames
          .filter((cacheName) => cacheName.startsWith("sage-school-app-") && cacheName !== CACHE_NAME)
          .map((cacheName) => caches.delete(cacheName)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const requestUrl = new URL(request.url);
  if (
    request.method !== "GET"
    || requestUrl.origin !== self.location.origin
    || requestUrl.pathname.startsWith("/api/")
  ) {
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            cacheResponse("/", response, event);
          }
          return response;
        })
        .catch(async () => {
          const cachedPage = await caches.match("/");
          if (cachedPage) {
            return cachedPage;
          }
          throw new Error("The school app is offline and its page has not been cached yet.");
        }),
    );
    return;
  }

  event.respondWith(
    caches.match(request)
      .then((cachedResponse) => cachedResponse || fetch(request).then((response) => {
        if (response.ok) {
          cacheResponse(request, response, event);
        }
        return response;
      })),
  );
});
