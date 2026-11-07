const CACHE_NAME = 'artisan-bakery-v5';
const STATIC_ASSETS = [
  '/',
  '/static/css/styles.css',
  '/static/js/app.js',
  '/static/images/pwa/icon-192.png',
  '/static/images/pwa/icon-512.png',
  '/static/images/pwa/apple-touch-icon.png',
  '/static/favicon.ico',
  '/offline/'
];

// Install Event
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('PWA Precache warning (some routes may require auth/server):', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// Activate Event
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch Event
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Skip non-GET requests and Django admin/API requests
  if (req.method !== 'GET') return;
  if (url.pathname.startsWith('/django-admin/')) return;

  // Always fetch printer scripts direct from network (never serve stale driver)
  if (url.pathname.includes('niimbot') || url.pathname.includes('printer')) {
    event.respondWith(fetch(req).catch(() => caches.match(req)));
    return;
  }

  // Static Assets: Cache-First strategy
  if (url.pathname.startsWith('/static/') || url.hostname.includes('fonts.gstatic.com') || url.hostname.includes('fonts.googleapis.com')) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) return cached;
        return fetch(req).then((res) => {
          if (res && res.status === 200) {
            const clone = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
          }
          return res;
        });
      })
    );
    return;
  }

  // Navigation / HTML pages: Network-First with Offline Fallback
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then((res) => {
          // If server responded with error status or network succeeds
          return res;
        })
        .catch(async () => {
          const cached = await caches.match(req);
          if (cached) return cached;
          const offlinePage = await caches.match('/offline/');
          if (offlinePage) return offlinePage;
          return new Response(
            `<!DOCTYPE html>
            <html lang="vi">
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <title>Mất kết nối - Artisan Bakery</title>
              <style>
                body { font-family: -apple-system, sans-serif; background: #FAF6F0; color: #261309; text-align: center; padding: 40px 20px; }
                .card { max-width: 400px; margin: 40px auto; background: white; padding: 32px; border-radius: 24px; box-shadow: 0 10px 25px rgba(217,119,6,0.1); border: 1px solid #FDE68A; }
                h1 { font-size: 20px; margin-top: 16px; color: #B45309; }
                p { font-size: 14px; color: #78350F; line-height: 1.5; }
                .btn { display: inline-block; margin-top: 20px; padding: 12px 24px; background: #D97706; color: white; border-radius: 16px; text-decoration: none; font-weight: bold; border: none; cursor: pointer; }
              </style>
            </head>
            <body>
              <div class="card">
                <div style="font-size: 48px;">🥖</div>
                <h1>Đang Mất Kết Nối Mạng</h1>
                <p>Tiệm bánh không thể kết nối đến máy chủ. Vui lòng kiểm tra lại đường truyền Wi-Fi hoặc 4G của bạn.</p>
                <button class="btn" onclick="window.location.reload()">Thử Kết Nối Lại</button>
              </div>
            </body>
            </html>`,
            { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          );
        })
    );
    return;
  }
});
