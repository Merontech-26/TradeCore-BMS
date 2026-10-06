const CACHE_NAME = 'tradecore-pwa-v1';
const STATIC_ASSETS = [
    '/',
    '/static/tradecore_pwa.css',
    '/static/tradecore_pwa.js',
    '/static/tradecore-icon-192.png',
    '/static/tradecore-icon-512.png'
];

// 1. WAKATI WA KU-INSTALL APP
self.addEventListener('install', (event) => {
    self.skipWaiting(); // Iruhusu app ianze kufanya kazi mara moja
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('Inahifadhi mafaili muhimu ya TradeCore...');
            return cache.addAll(STATIC_ASSETS).catch(() => {
                console.log('Baadhi ya assets hazikupatikana kwa sasa, lakini tutaendelea.');
            });
        })
    );
});

// 2. WAKATI WA KUWASHA APP (Kusafisha takataka za zamani)
self.addEventListener('activate', (event) => {
    event.waitUntil(self.clients.claim());
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((name) => {
                    if (name !== CACHE_NAME) {
                        return caches.delete(name);
                    }
                })
            );
        })
    );
});

// 3. WAKATI WA KUTUMIA APP (Kama huna internet, vuta kwenye kumbu kumbu)
self.addEventListener('fetch', (event) => {
    // Tunadaka request za GET pekee
    if (event.request.method !== 'GET') return;

    event.respondWith(
        fetch(event.request)
            .then((response) => {
                // Copy mpya inahifadhiwa kwenye cache
                const responseClone = response.clone();
                caches.open(CACHE_NAME).then((cache) => {
                    cache.put(event.request, responseClone);
                });
                return response;
            })
            .catch(() => {
                // Internet ikikata, tunatumia kilichopo kwenye cache
                return caches.match(event.request);
            })
    );
});

// 4. KUDADISI BACKGROUND SYNC KUTOKA KWENYE tradecore_pwa.js
self.addEventListener('sync', (event) => {
    if (event.tag === 'tradecore-sale-sync') {
        console.log('Mtandao umerudi! Background sync inasubiri UI imalizie kazi...');
        // Kazi halisi ya ku-sync inaongozwa na tradecore_pwa.js kule kwenye browser
    }
});