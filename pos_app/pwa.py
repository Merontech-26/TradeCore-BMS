from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


# TradeCore application release. Keep in sync with templates and the PWA updater.
APP_VERSION = "1.1.9"

# Static asset cache + safe client-side background-sync queue.
# No Django business data is cached here. Sales data lives in the PWA's
# IndexedDB queue and is posted back to the existing /mauzo/ endpoint.
SERVICE_WORKER_JS = r'''const APP_VERSION = "1.1.9";
const CACHE_NAME = "tradecore-static-v1.1.9-owner-scope-inventory-firstpaint-01";
const CACHE_PREFIX = "tradecore-static-";
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

async function notifyClients(type, details = {}) {
  const clients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  for (const client of clients) {
    client.postMessage({ type, version: APP_VERSION, ...details });
  }
}

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    try {
      const total = STATIC_ASSETS.length;
      let completed = 0;
      let cached = 0;
      let skipped = 0;

      await notifyClients("TRADECORE_UPDATE_STARTED", { total, percent: 0 });
      const cache = await caches.open(CACHE_NAME);

      for (const asset of STATIC_ASSETS) {
        try {
          const request = new Request(new URL(asset, self.location.origin).href, {
            cache: "reload",
            credentials: "same-origin"
          });
          const response = await fetch(request);
          if (!response || !response.ok) {
            throw new Error(`Asset response ${response ? response.status : 0}`);
          }
          await cache.put(request, response.clone());
          cached += 1;
        } catch (error) {
          // A static asset may use a hashed URL in production. Do not block the
          // release: the app can still request that asset through the network.
          skipped += 1;
        }

        completed += 1;
        await notifyClients("TRADECORE_UPDATE_PROGRESS", {
          completed,
          total,
          cached,
          skipped,
          percent: Math.round((completed / total) * 100)
        });
      }

      await notifyClients("TRADECORE_UPDATE_READY", {
        completed: total,
        total,
        cached,
        skipped,
        percent: 100
      });

      // Activate the new worker only after the static asset preparation finishes.
      await self.skipWaiting();
    } catch (error) {
      await notifyClients("TRADECORE_UPDATE_FAILED", {
        message: error?.message || "Service worker installation failed"
      }).catch(() => {});
      throw error;
    }
  })());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys
      .filter(key => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME)
      .map(key => caches.delete(key)));

    // Preserve other applications' caches and all TradeCore IndexedDB data,
    // including unsynchronized offline sales.
    await self.clients.claim();
    await notifyClients("TRADECORE_UPDATE_ACTIVATED", { percent: 100 });
  })());
});

self.addEventListener("fetch", event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  if (!url.pathname.startsWith("/static/")) return;

  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    // Ignore the cache-busting query string: the release cache itself is versioned.
    const cached = await cache.match(request, { ignoreSearch: true });
    if (cached) {
      // Refresh the canonical path in the background without creating query-key variants.
      fetch(request).then(response => {
        if (response && response.ok) {
          const canonicalRequest = new Request(url.origin + url.pathname, { credentials: "same-origin" });
          return cache.put(canonicalRequest, response.clone());
        }
      }).catch(() => {});
      return cached;
    }

    const response = await fetch(request);
    if (response && response.ok) {
      cache.put(request, response.clone()).catch(() => {});
    }
    return response;
  })());
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


/* Fail closed: Background Sync must only submit items belonging to the user
   whose authenticated page last set the existing IndexedDB active_owner key. */
function getActiveOwnerKeyFromDb() {
  return openDb().then(db => new Promise((resolve, reject) => {
    let ownerKey = "";
    const tx = db.transaction("meta", "readonly");
    const req = tx.objectStore("meta").get("active_owner");
    req.onsuccess = () => {
      const value = String(req.result?.ownerKey || "").trim();
      ownerKey = /^\d+$/.test(value) ? value : "";
    };
    req.onerror = () => {
      db.close();
      reject(req.error || new Error("Active owner metadata could not be read."));
    };
    tx.oncomplete = () => {
      db.close();
      resolve(ownerKey);
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error || new Error("Active owner transaction failed."));
    };
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
    let activeOwnerKey = "";
    try {
      activeOwnerKey = await getActiveOwnerKeyFromDb();
    } catch (error) {
      // Do not submit any queued sale if ownership cannot be established.
      console.warn("TradeCore background sync paused: active owner unavailable.", error);
      return;
    }
    if (!activeOwnerKey) {
      console.warn("TradeCore background sync paused: no authenticated queue owner.");
      return;
    }

    const items = (await getSales())
      .filter(item => String(item.ownerKey || "") === activeOwnerKey && item.state === "pending")
      .sort((a, b) => (a.createdAt || 0) - (b.createdAt || 0));

    for (const item of items) {

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
            "X-TradeCore-Queue-Owner": activeOwnerKey,
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
          item.lastError = data?.code === "queue_owner_mismatch"
            ? (data.message || "Offline sale hii ni ya akaunti nyingine.")
            : "CSRF Session imeisha. Fungua App ukiwa na internet ili kusync.";
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
  const data = event.data || {};
  if (data.type === "TRADECORE_SET_ACTIVE_OWNER") {
    // Page code has already persisted this value to IndexedDB. Validate the
    // message for diagnostics/forward compatibility; the DB remains authoritative.
    const ownerKey = String(data.ownerKey || "").trim();
    if (!/^\d+$/.test(ownerKey)) {
      console.warn("TradeCore ignored an invalid active-owner message.");
    }
    return;
  }
  if (data.type === "TRADECORE_SYNC_NOW") {
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
    response["X-TradeCore-App-Version"] = APP_VERSION
    return response
