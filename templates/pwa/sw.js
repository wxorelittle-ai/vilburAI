{% load static %}// Service Worker Вильбур AI (раздел 7.5 ТЗ)
const VERSION = 'wilbur-v2';
const STATIC_CACHE = VERSION + '-static';
const RUNTIME_CACHE = VERSION + '-runtime';
const OFFLINE_URL = '/offline/';

// Оболочка приложения — кэшируется при установке.
// CSS теперь свой (не Play CDN), поэтому офлайн приложение остаётся со стилями.
const PRECACHE = [
  OFFLINE_URL,
  '{% static "css/app.css" %}',
  '{% static "js/app.js" %}',
  '{% static "js/offline-calc.js" %}',
  '{% static "icons/icon-192.png" %}',
  '{% static "img/wilbur-horse-white.png" %}',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(PRECACHE).catch(() => {})).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Навигации: network-first, при офлайне — кэш страницы или offline-фолбэк
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(RUNTIME_CACHE).then((c) => c.put(req, copy));
          return resp;
        })
        .catch(() => caches.match(req).then((cached) => cached || caches.match(OFFLINE_URL)))
    );
    return;
  }

  // Статика/CDN/шрифты: cache-first с дозаписью
  if (
    url.origin === location.origin ||
    url.host.includes('fonts.googleapis.com') ||
    url.host.includes('fonts.gstatic.com')
  ) {
    event.respondWith(
      caches.match(req).then(
        (cached) =>
          cached ||
          fetch(req).then((resp) => {
            const copy = resp.clone();
            caches.open(RUNTIME_CACHE).then((c) => c.put(req, copy));
            return resp;
          }).catch(() => cached)
      )
    );
  }
});
