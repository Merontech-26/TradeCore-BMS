from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


# Static asset cache + safe client-side background-sync queue.
# No Django business data is cached here. Sales data lives in the PWA's
# IndexedDB queue and is posted back to the existing /mauzo/ endpoint.
SERVICE_WORKER_JS = r'''const CACHE_NAME = "tradecore-static-v9";
const STATIC_ASSETS = [
  "/static/tradecore_pwa.css",
  "/static/tradecore_pwa.js",
  "/static/logo.png",
  "/static/tradecore-icon-192.png",
  "/static/tradecore-icon-512.png"
];

const DB_NAME = "tradecore-pwa-v2";
const DB_VERSION = 2;
const SALES_STORE = "sales";
const SYNC_TAG = "tradecore-sale-sync";

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => Promise.all(
        STATIC_ASSETS.map(asset => cache.add(asset).catch(() => null))
      ))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  if (!url.pathname.startsWith("/static/")) return;

  event.respondWith(
    caches.match(request).then(cached => {
      const networkFetch = fetch(request).then(response => {
        if (response && response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
        }
        return response;
      }).catch(() => {
        /* Ignore offline failures for static assets */
      });
      return cached || networkFetch;
    })
  );
});

function openDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(SALES_STORE)) {
        const store = db.createObjectStore(SALES_STORE, { keyPath: "id" });
        store.createIndex("state", "state", { unique: false });
        store.createIndex("createdAt", "createdAt", { unique: false });
      }
      if (!db.objectStoreNames.contains("meta")) {
        db.createObjectStore("meta", { keyPath: "key" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function getSales() {
  return openDb().then(db => new Promise((resolve, reject) => {
    const tx = db.transaction(SALES_STORE, "readonly");
    const req = tx.objectStore(SALES_STORE).getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => db.close();
  }));
}

function putSale(item) {
  return openDb().then(db => new Promise((resolve, reject) => {
    const tx = db.transaction(SALES_STORE, "readwrite");
    tx.objectStore(SALES_STORE).put(item);
    tx.oncomplete = () => { db.close(); resolve(item); };
    tx.onerror = () => { db.close(); reject(tx.error); };
  }));
}

function deleteSale(id) {
  return openDb().then(db => new Promise((resolve, reject) => {
    const tx = db.transaction(SALES_STORE, "readwrite");
    tx.objectStore(SALES_STORE).delete(id);
    tx.oncomplete = () => { db.close(); resolve(true); };
    tx.onerror = () => { db.close(); reject(tx.error); };
  }));
}

function toFormData(data) {
  const body = new URLSearchParams();
  Object.entries(data || {}).forEach(([key, value]) => body.append(key, String(value ?? "")));
  return body;
}

let syncInFlight = null;

function backgroundSyncSales() {
  if (syncInFlight) return syncInFlight;

  syncInFlight = (async () => {
    const items = (await getSales()).sort((a, b) => (a.createdAt || 0) - (b.createdAt || 0));

    for (const item of items) {
      if (item.state !== "pending") continue;

      item.attempts = Number(item.attempts || 0) + 1;
      item.updatedAt = Date.now();
      await putSale(item);

      try {
        const actionUrl = new URL(item.action || "", self.location.origin);
        if (actionUrl.origin !== self.location.origin || actionUrl.pathname !== "/mauzo/") {
          item.state = "needs_attention";
          item.lastError = "Sync endpoint si salama au haitambuliki.";
          await putSale(item);
          continue;
        }

        const response = await fetch(actionUrl.pathname + actionUrl.search, {
        method: "POST",
        body: toFormData(item.data),
        credentials: "include",
        redirect: "follow",
        cache: "no-store",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
          "X-Requested-With": "XMLHttpRequest",
          "Accept": "application/json"
        }
      });

      const data = await response.json().catch(() => null);
      const finalPath = response.url ? new URL(response.url, self.location.origin).pathname : "";

      if (finalPath === "/login/" || finalPath.startsWith("/login/")) {
        item.state = "needs_attention";
        item.lastError = "Session imekwisha. Ingia tena kisha sync.";
        await putSale(item);
        continue;
      }

      if (response.status === 403) {
        item.state = "needs_attention";
        item.lastError = "CSRF Session imeisha. Fungua App ukiwa na internet ili kusync.";
        await putSale(item);
        continue;
      }

      if (response.ok && data && data.ok) {
        await deleteSale(item.id);
        continue;
      }

      if (data && data.ok === false) {
        item.state = "needs_attention";
        item.lastError = data.message || "Server imekataa muamala huu.";
        await putSale(item);
        continue;
      }

      // Preserve the item for the next retry when the failure is transient.
      item.lastError = `Server response ${response.status || 0}`;
      await putSale(item);
      break;
    } catch (error) {
      item.lastError = error?.message || "Network error";
      await putSale(item);
      break;
    }
    }

    // Ask any open clients to refresh their badge/list.
    const clients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const client of clients) {
      client.postMessage({ type: "TRADECORE_SYNC_FINISHED" });
    }
  })().finally(() => {
    syncInFlight = null;
  });

  return syncInFlight;
}

self.addEventListener("sync", event => {
  if (event.tag !== SYNC_TAG) return;
  event.waitUntil(backgroundSyncSales());
});

self.addEventListener("message", event => {
  if (event.data?.type === "TRADECORE_SYNC_NOW") {
    event.waitUntil?.(backgroundSyncSales());
  }
});
'''


@require_GET
@never_cache
def service_worker(request):
    response = HttpResponse(
        SERVICE_WORKER_JS,
        content_type="application/javascript",
    )
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response
