// sw.js - X1.0 Market Monitor Service Worker
//
// 策略：
//   - HTML / API / WebSocket       → network-first（保证永远是新版）
//   - 静态资源（图标、manifest）   → cache-first（离线可用）
//
// 修改任何前端文件后，只需改 CACHE_VERSION，
// 老 cache 会在 activate 时自动清理。

const CACHE_VERSION = "x1-v4";
const CORE_ASSETS = [
  "/manifest.webmanifest",
  "/icon-192.png",
  "/icon-512.png",
];

// ---------- install ----------
self.addEventListener("install", (event) => {
  self.skipWaiting();   // 立刻激活新 SW，不等旧页面关闭
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => {
      return cache.addAll(CORE_ASSETS).catch((e) => {
        console.warn("[sw] preload core assets failed:", e);
      });
    })
  );
});

// ---------- activate ----------
self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      // 清掉所有旧版本 cache
      const keys = await caches.keys();
      await Promise.all(
        keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))
      );
      // 立刻接管所有打开的页面
      await self.clients.claim();
      console.log("[sw] activated:", CACHE_VERSION);
    })()
  );
});

// ---------- fetch ----------
self.addEventListener("fetch", (event) => {
  const req = event.request;

  // 只处理 GET
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // 只处理同源
  if (url.origin !== self.location.origin) return;

  // WebSocket：直接放行
  if (url.pathname.startsWith("/ws")) return;

  // HTML / 根路径 / API → network-first
  const isHTML =
    url.pathname === "/" ||
    url.pathname.endsWith(".html") ||
    url.pathname.endsWith(".htm");

  const isAPI = url.pathname.startsWith("/api/");

  // 注册脚本本身 → network-first
  const isSw = url.pathname === "/sw.js";

  if (isHTML || isAPI || isSw) {
    event.respondWith(networkFirst(req));
    return;
  }

  // 其它静态资源 → cache-first
  event.respondWith(cacheFirst(req));
});

// ---------- 策略实现 ----------

async function networkFirst(req) {
  try {
    const fresh = await fetch(req);
    // 200 才缓存；避免缓存 404 / 500
    if (fresh && fresh.status === 200 && fresh.type === "basic") {
      const copy = fresh.clone();
      caches.open(CACHE_VERSION).then((c) => c.put(req, copy));
    }
    return fresh;
  } catch (e) {
    // 网络挂了才用缓存
    const cached = await caches.match(req);
    if (cached) return cached;
    throw e;
  }
}

async function cacheFirst(req) {
  const cached = await caches.match(req);
  if (cached) return cached;

  try {
    const fresh = await fetch(req);
    if (fresh && fresh.status === 200 && fresh.type === "basic") {
      const copy = fresh.clone();
      caches.open(CACHE_VERSION).then((c) => c.put(req, copy));
    }
    return fresh;
  } catch (e) {
    // 静态资源没有 fallback，直接抛错
    throw e;
  }
}

// ---------- message：允许页面主动触发 skipWaiting ----------
self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") {
    self.skipWaiting();
  }
});