/*
 * TradeCore Mobile PWA layer.
 *
 * UI + installation + offline sales queue live here. Business calculations are
 * still performed by Django on the server; the browser only stores a pending
 * sale when the network is unavailable, then resubmits the exact form safely.
 */
(function () {
    'use strict';

    const TC = window.TradeCoreMobile = window.TradeCoreMobile || {};
    const DB_NAME = 'tradecore-pwa-v2';
    const DB_VERSION = 2;
    const SALES_STORE = 'sales';
    const META_STORE = 'meta';
    const SYNC_TAG = 'tradecore-sale-sync';
    let deferredInstallPrompt = null;
    let syncing = false;

    function getEl(id) { return document.getElementById(id); }

    function sheet() { return getEl('tradecoreMobileSheet'); }
    function actions() { return getEl('tradecoreQuickActions'); }
    function syncSheet() { return getEl('tradecoreSyncSheet'); }
    function installSheet() { return getEl('tradecoreInstallSheet'); }

    function mobileCartSection() { return getEl('cartSection'); }
    function mobileCartBackdrop() { return getEl('tradecoreMobileCartBackdrop'); }


    function toggleLayer(el, open) {
        if (!el) return;
        el.classList.toggle('is-open', open);
        el.setAttribute('aria-hidden', open ? 'false' : 'true');
    }

    function openSheet() {
        toggleLayer(sheet(), true);
        document.body.classList.add('tradecore-sheet-visible');
    }

    function closeSheet() {
        toggleLayer(sheet(), false);
        document.body.classList.remove('tradecore-sheet-visible');
    }

    TC.openMore = openSheet;
    TC.closeMore = closeSheet;

    TC.openQuickActions = function () {
        toggleLayer(actions(), true);
        document.body.classList.add('tradecore-sheet-visible');
    };

    TC.closeQuickActions = function () {
        toggleLayer(actions(), false);
        document.body.classList.remove('tradecore-sheet-visible');
    };

    TC.openSyncSheet = async function () {
        TC.closeMore();
        TC.closeQuickActions();
        toggleLayer(syncSheet(), true);
        document.body.classList.add('tradecore-sheet-visible');
        await refreshQueueUi();
    };

    TC.closeSyncSheet = function () {
        toggleLayer(syncSheet(), false);
        document.body.classList.remove('tradecore-sheet-visible');
    };

    TC.closeInstallSheet = function () {
        toggleLayer(installSheet(), false);
        document.body.classList.remove('tradecore-sheet-visible');
    };

    function isStandaloneMode() {
        return window.matchMedia?.('(display-mode: standalone)')?.matches || navigator.standalone === true;
    }

    function showInstallGuide(mode) {
        const el = installSheet();
        if (!el) return;
        ['tradecoreInstallNative','tradecoreInstallIOS','tradecoreInstallStandalone','tradecoreInstallUnavailable']
            .forEach(id => getEl(id)?.classList.add('hidden'));
        getEl('tradecoreInstallPrimary')?.classList.add('hidden');

        const title = getEl('tradecoreInstallTitle');
        const subtitle = getEl('tradecoreInstallSubtitle');
        if (mode === 'ios') {
            getEl('tradecoreInstallIOS')?.classList.remove('hidden');
            title && (title.textContent = 'Sakinisha TradeCore');
            subtitle && (subtitle.textContent = 'Safari hutumia Add to Home Screen badala ya install prompt.');
        } else if (mode === 'native') {
            getEl('tradecoreInstallNative')?.classList.remove('hidden');
            getEl('tradecoreInstallPrimary')?.classList.remove('hidden');
            title && (title.textContent = 'Sakinisha TradeCore');
            subtitle && (subtitle.textContent = 'TradeCore iko tayari kusakinishwa kama app.');
        } else if (mode === 'standalone') {
            getEl('tradecoreInstallStandalone')?.classList.remove('hidden');
            title && (title.textContent = 'TradeCore iko tayari');
            subtitle && (subtitle.textContent = 'Unaendesha app mode tayari.');
        } else {
            getEl('tradecoreInstallUnavailable')?.classList.remove('hidden');
            title && (title.textContent = 'Install haijapatikana');
            subtitle && (subtitle.textContent = 'Hii mara nyingi hutokea kwenye local HTTP testing.');
        }
        toggleLayer(el, true);
        document.body.classList.add('tradecore-sheet-visible');
    }

    TC.install = async function () {
        if (isStandaloneMode()) {
            showInstallGuide('standalone');
            return;
        }

        if (deferredInstallPrompt) {
            showInstallGuide('native');
            return;
        }

        if (/iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)) {
            showInstallGuide('ios');
            return;
        }

        showInstallGuide('unavailable');
    };

    TC.installNowFromSheet = async function () {
        if (!deferredInstallPrompt) {
            showInstallGuide('unavailable');
            return;
        }
        try {
            deferredInstallPrompt.prompt();
            await deferredInstallPrompt.userChoice;
        } finally {
            deferredInstallPrompt = null;
            document.querySelectorAll('[data-tradecore-install]').forEach(el => el.classList.add('hidden'));
            TC.closeInstallSheet();
        }
    };

    function setMobileCartOpen(open) {
        const cart = mobileCartSection();
        if (!cart) return;
        document.body.classList.toggle('tradecore-cart-open', Boolean(open));
        const header = getEl('cartHeader');
        if (header) header.setAttribute('aria-expanded', open ? 'true' : 'false');
        const close = getEl('tradecoreMobileCartBackdrop');
        if (close) close.setAttribute('aria-hidden', open ? 'false' : 'true');
        const fab = getEl('tradecoreMobileCartFab');
        if (fab) fab.setAttribute('aria-expanded', open ? 'true' : 'false');
        syncMobileCartSummary();
    }

    TC.openMobileCart = function () { setMobileCartOpen(true); };
    TC.closeMobileCart = function () { setMobileCartOpen(false); };
    TC.toggleMobileCart = function () { setMobileCartOpen(!document.body.classList.contains('tradecore-cart-open')); };

    function syncMobileCartSummary() {
        const total = getEl('totalDisplay');
        const itemCount = getEl('itemCountBadge');
        const target = getEl('mobileCartTotalDisplay');
        const state = getEl('tradecoreMobileCartStateText');
        const fabCount = getEl('tradecoreMobileCartFabCount');
        const fabButton = getEl('tradecoreMobileCartFab');
        if (target && total) target.textContent = total.textContent.replace(/\s+/g, ' ').trim();
        if (state && itemCount) {
            const text = itemCount.textContent.replace(/\s+/g, ' ').trim();
            state.textContent = text.startsWith('0') || text === '0 Items' ? 'Ongeza bidhaa; invoice itaonekana hapa juu.' : `${text} kwenye invoice.`;
        }
        if (fabCount && itemCount) {
            const raw = itemCount.textContent.replace(/[^0-9]/g, '');
            fabCount.textContent = raw || '0';
            if (fabButton) {
                fabButton.setAttribute('aria-label', raw && raw !== '0' ? `Fungua cart yenye items ${raw}` : 'Fungua cart tupu');
                fabButton.setAttribute('aria-expanded', document.body.classList.contains('tradecore-cart-open') ? 'true' : 'false');
            }
        }
    }

    // Mobile swipe navigation ------------------------------------------------
    // Swipe left/right on page content to move between the primary bottom-bar
    // destinations for the current role. Horizontal carousels and form fields
    // are ignored so product/category scrolling keeps working normally.
    let swipeStart = null;

    function ignoreSwipeTarget(target) {
        let node = target;
        while (node && node !== document.body) {
            if (node.matches?.('input, textarea, select, [contenteditable="true"], button, a, .tradecore-mobile-tab, #categoryFilters')) return true;
            const style = window.getComputedStyle(node);
            if ((style.overflowX === 'auto' || style.overflowX === 'scroll') && node.scrollWidth > node.clientWidth + 8) return true;
            node = node.parentElement;
        }
        return false;
    }

    function getSwipeRoutes() {
        return Array.from(document.querySelectorAll('#tradecoreMobileTabbar a[data-tradecore-route]'))
            .filter(link => link.offsetParent !== null && link.href);
    }

    document.addEventListener('touchstart', function (event) {
        if (event.touches.length !== 1 || !window.matchMedia?.('(max-width: 767px)').matches) {
            swipeStart = null;
            return;
        }
        if (ignoreSwipeTarget(event.target)) {
            swipeStart = null;
            return;
        }
        const point = event.touches[0];
        swipeStart = { x: point.clientX, y: point.clientY, time: Date.now() };
    }, { passive: true });

    document.addEventListener('touchend', function (event) {
        if (!swipeStart || event.changedTouches.length !== 1) return;
        const point = event.changedTouches[0];
        const dx = point.clientX - swipeStart.x;
        const dy = point.clientY - swipeStart.y;
        const elapsed = Date.now() - swipeStart.time;
        swipeStart = null;

        // Tumelainisha swipe iwe sensitive zaidi (kutoka 72px mpaka 55px)
        if (elapsed > 700 || Math.abs(dx) < 55 || Math.abs(dx) < Math.abs(dy) * 1.25) return;

        const routes = getSwipeRoutes();
        if (routes.length < 2) return;
        const currentRoute = document.body.dataset.tradecoreRoute || '';
        const currentIndex = routes.findIndex(link => link.dataset.tradecoreRoute === currentRoute);
        if (currentIndex < 0) return;

        const direction = dx < 0 ? 1 : -1;
        const next = routes[(currentIndex + direction + routes.length) % routes.length];
        if (!next) return;

        // Visual Push Effect (Inasukuma page kidogo kabla ya kuhama)
        document.body.style.opacity = '0.8';
        document.body.style.transform = `translateX(${dx < 0 ? '-15px' : '15px'})`;
        document.body.style.transition = 'all 0.2s ease-out';
        
        setTimeout(() => window.location.assign(next.href), 40);
    }, { passive: true });

    // Mobile product density -------------------------------------------------
    const DENSITY_KEY = 'tradecore_mobile_product_density_v1';
    const DENSITIES = [
        { columns: 4, media: '62px', name: '9px', gap: '6px', label: '4×' },
        { columns: 3, media: '76px', name: '10px', gap: '8px', label: '3×' },
        { columns: 2, media: '112px', name: '11px', gap: '10px', label: '2×' }
    ];
    function applyProductDensity(index) {
        const safeIndex = Math.max(0, Math.min(DENSITIES.length - 1, Number(index) || 1));
        const d = DENSITIES[safeIndex];
        const root = document.getElementById('productGridContainer');
        if (root) {
            root.style.setProperty('--tc-product-columns', d.columns);
            root.style.setProperty('--tc-product-media', d.media);
            root.style.setProperty('--tc-product-name', d.name);
            root.style.setProperty('--tc-product-gap', d.gap);
        }
        const label = getEl('tradecoreDensityValue');
        if (label) label.textContent = d.label;
        try { localStorage.setItem(DENSITY_KEY, String(safeIndex)); } catch (_) {}
    }
    TC.changeProductDensity = function(delta) {
        let current = 1;
        try { current = Number(localStorage.getItem(DENSITY_KEY) ?? 1); } catch (_) {}
        applyProductDensity(current + Number(delta || 0));
    };

    // Camera / HID scanner ---------------------------------------------------
    let scannerStream = null;
    let scannerTimer = null;
    let scannerDetector = null;
    function setScannerMessage(message) {
        const el = getEl('tradecoreScannerMessage');
        if (el) el.textContent = message;
    }
    async function stopScanner() {
        if (scannerTimer) { clearInterval(scannerTimer); scannerTimer = null; }
        scannerDetector = null;
        if (scannerStream) {
            scannerStream.getTracks().forEach(track => track.stop());
            scannerStream = null;
        }
        const video = getEl('tradecoreScannerVideo');
        if (video) video.srcObject = null;
    }
    TC.closeScanner = async function () {
        await stopScanner();
        const el = getEl('tradecoreScannerSheet');
        if (el) toggleLayer(el, false);
        document.body.classList.remove('tradecore-sheet-visible');
    };
    TC.openScanner = async function () {
        const sheetEl = getEl('tradecoreScannerSheet');
        if (!sheetEl) return;
        TC.closeSyncSheet?.();
        TC.closeMore?.();
        TC.closeQuickActions?.();
        toggleLayer(sheetEl, true);
        document.body.classList.add('tradecore-sheet-visible');
        const input = getEl('tradecoreScannerInput');
        input?.focus();
        await stopScanner();

        const video = getEl('tradecoreScannerVideo');
        if (!('BarcodeDetector' in window)) {
            setScannerMessage('Kifaa chako (k.m. Safari/iOS) hakisupport Barcode Scanner ya moja kwa moja. Tumia scanner ya Bluetooth/USB hapa chini.');
            return;
        }
        if (!navigator.mediaDevices?.getUserMedia) {
            setScannerMessage('Camera API haipatikani. Tumia scanner ya Bluetooth/USB hapa chini.');
            return;
        }
        if (window.isSecureContext !== true) {
            setScannerMessage('Camera inahitaji HTTPS kwenye simu. Kwa local HTTP tumia scanner ya Bluetooth/USB hapa chini.');
            return;
        }
        try {
            scannerStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
            if (video) {
                video.srcObject = scannerStream;
                await video.play().catch(() => {});
            }
            const formats = ['ean_13','ean_8','code_128','code_39','upc_a','upc_e','qr_code','itf'];
            try { scannerDetector = new BarcodeDetector({ formats }); } catch (_) { scannerDetector = new BarcodeDetector(); }
            setScannerMessage('Leta barcode katikati ya frame…');
            scannerTimer = setInterval(async () => {
                if (!scannerDetector || !video || video.readyState < 2) return;
                try {
                    const codes = await scannerDetector.detect(video);
                    const value = codes?.[0]?.rawValue || '';
                    if (value) {
                        const found = await window.scanBarcodeValue?.(value);
                        if (found !== false) {
                            setScannerMessage(`Barcode ${value} imeongezwa kwenye cart.`);
                            setTimeout(() => TC.closeScanner(), 500);
                        } else {
                            setScannerMessage(`Barcode ${value} haijapatikana kwenye bidhaa.`);
                        }
                    }
                } catch (_) {}
            }, 350);
        } catch (error) {
            if (error?.name === 'NotAllowedError' || error?.name === 'SecurityError') {
                setScannerMessage('Ruhusa ya camera haikupatikana. Ruhusu Camera kwenye browser, au tumia scanner ya Bluetooth/USB.');
            } else {
                setScannerMessage('Camera haikufunguka kwenye kifaa hiki. Tumia scanner ya Bluetooth/USB hapa chini.');
            }
        }
    };
    TC.submitScannerInput = async function () {
        const input = getEl('tradecoreScannerInput');
        const value = input?.value?.trim() || '';
        if (!value) { setScannerMessage('Andika au scan barcode kwanza.'); return; }
        const fn = window.scanBarcodeValue;
        if (typeof fn !== 'function') { setScannerMessage('POS barcode handler haijapatikana.'); return; }
        const found = await fn(value);
        if (found) {
            if (input) input.value = '';
            setScannerMessage(`Barcode ${value} imeongezwa kwenye cart.`);
        } else {
            setScannerMessage(`Barcode ${value} haijapatikana.`);
        }
    };

    // Inventory scanner: same camera/HID philosophy as POS, but decoupled
    // from the sales cart so Stoo can use the same engine for multiple modes.
    let inventoryScannerStream = null;
    let inventoryScannerTimer = null;
    let inventoryScannerDetector = null;
    let inventoryScannerBusy = false;
    let inventoryCameraLastValue = '';
    let inventoryCameraLastAt = 0;
    let inventorySerialPort = null;
    let inventorySerialReader = null;
    let inventorySerialBuffer = '';
    let inventorySerialFlushTimer = null;
    function stopInventoryScannerStream() {
        if (inventoryScannerTimer) { clearInterval(inventoryScannerTimer); inventoryScannerTimer = null; }
        inventoryScannerDetector = null;
        if (inventoryScannerStream) {
            inventoryScannerStream.getTracks().forEach(track => track.stop());
            inventoryScannerStream = null;
        }
        const video = getEl('tradecoreInventoryScannerVideo');
        if (video) video.srcObject = null;
        inventorySerialBuffer = '';
        if (inventorySerialFlushTimer) { clearTimeout(inventorySerialFlushTimer); inventorySerialFlushTimer = null; }
        inventoryCameraLastValue = ''; inventoryCameraLastAt = 0;
        try { inventorySerialReader?.cancel?.(); } catch (_) {}
        inventorySerialReader = null;
        if (inventorySerialPort) {
            try { inventorySerialPort.close?.(); } catch (_) {}
            inventorySerialPort = null;
        }
    }
    function setInventoryScannerMessage(message) {
        const el = getEl('tradecoreInventoryScannerMessage');
        if (el) el.textContent = message;
        try { window.setTradeCoreInventoryScannerMessage = setInventoryScannerMessage; } catch (_) {}
    }
    TC.closeInventoryScanner = async function () {
        stopInventoryScannerStream();
        const el = getEl('inventoryScannerSheet');
        if (el) toggleLayer(el, false);
        document.body.classList.remove('tradecore-sheet-visible');
        inventoryScannerBusy = false;
    };
    TC.openInventoryScanner = async function (mode) {
        const sheetEl = getEl('inventoryScannerSheet');
        if (!sheetEl) return;
        TC.closeScanner?.();
        TC.closeMore?.();
        TC.closeQuickActions?.();
        toggleLayer(sheetEl, true);
        document.body.classList.add('tradecore-sheet-visible');
        const title = getEl('tradecoreInventoryScannerTitle');
        const labels = {stock_in:'Scan Stock In', transfer:'Scan Transfer', stock_take:'Scan Stock Take', adjustment:'Scan Adjustment', lookup:'Quick Lookup'};
        if (title) title.textContent = labels[mode] || 'Scan Barcode';
        const input = getEl('tradecoreInventoryScannerInput');
        if (input) { input.value = ''; input.focus(); }
        const serialButton = getEl('tradecoreInventorySerialButton');
        if (serialButton) {
            serialButton.classList.toggle('hidden', !(('serial' in navigator)));
            serialButton.textContent = inventorySerialPort ? 'Funga Serial' : 'Serial 9600';
        }
        await stopInventoryScannerStream();
        if (serialButton) serialButton.textContent = 'Serial 9600';
        const video = getEl('tradecoreInventoryScannerVideo');
        if (!navigator.mediaDevices?.getUserMedia || window.isSecureContext !== true) {
            setInventoryScannerMessage('Camera haipatikani hapa. USB/Bluetooth scanner ya keyboard/HID inaweza kuscan moja kwa moja.');
            return;
        }
        if (!('BarcodeDetector' in window)) {
            setInventoryScannerMessage('Browser hii haina Camera BarcodeDetector. Tumia USB/Bluetooth scanner ya keyboard/HID.');
            return;
        }
        try {
            inventoryScannerStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
            if (video) { video.srcObject = inventoryScannerStream; await video.play().catch(() => {}); }
            const formats = ['ean_13','ean_8','code_128','code_39','upc_a','upc_e','qr_code','itf'];
            try { inventoryScannerDetector = new BarcodeDetector({ formats }); } catch (_) { inventoryScannerDetector = new BarcodeDetector(); }
            setInventoryScannerMessage('Leta barcode katikati ya frame…');
            inventoryScannerTimer = setInterval(async () => {
                if (inventoryScannerBusy || !inventoryScannerDetector || !video || video.readyState < 2) return;
                try {
                    const codes = await inventoryScannerDetector.detect(video);
                    const value = String(codes?.[0]?.rawValue || '').trim();
                    if (!value) return;
                    const nowMs = Date.now();
                    if (value === inventoryCameraLastValue && (nowMs - inventoryCameraLastAt) < 1200) return;
                    inventoryCameraLastValue = value;
                    inventoryCameraLastAt = nowMs;
                    inventoryScannerBusy = true;
                    const handler = window.tradecoreInventoryScanHandler;
                    if (typeof handler !== 'function') {
                        setInventoryScannerMessage('Inventory scan handler haijapatikana.');
                        inventoryScannerBusy = false;
                        return;
                    }
                    await handler(value);
                    if (input) input.value = '';
                    setTimeout(() => { inventoryScannerBusy = false; }, 450);
                } catch (e) {
                    inventoryScannerBusy = false;
                }
            }, 350);
        } catch (error) {
            if (error?.name === 'NotAllowedError' || error?.name === 'SecurityError') {
                setInventoryScannerMessage('Ruhusa ya camera haikupatikana. Ruhusu Camera au tumia Bluetooth/USB scanner.');
            } else {
                setInventoryScannerMessage('Camera haikufunguka. Tumia Bluetooth/USB scanner hapa chini.');
            }
        }
    };
    TC.submitInventoryScannerInput = async function () {
        const input = getEl('tradecoreInventoryScannerInput');
        const value = input?.value?.trim() || '';
        if (!value) { setInventoryScannerMessage('Andika au scan barcode kwanza.'); return; }
        const handler = window.tradecoreInventoryScanHandler;
        if (typeof handler !== 'function') { setInventoryScannerMessage('Inventory scan handler haijapatikana.'); return; }
        try {
            inventoryScannerBusy = true;
            const ok = await handler(value);
            if (ok !== false && input) input.value = '';
            inventoryScannerBusy = false;
        } catch (e) {
            inventoryScannerBusy = false;
            setInventoryScannerMessage(e?.message || 'Scan imeshindikana.');
        }
    };

    // Optional Web Serial bridge for scanners configured as serial devices.
    // Keyboard/HID scanners remain zero-setup and do not use this path.
    TC.connectInventorySerialScanner = async function () {
        if (!('serial' in navigator)) {
            setInventoryScannerMessage('Web Serial haipatikani. Tumia USB/Bluetooth scanner ya Keyboard/HID; haihitaji connection hapa.');
            return;
        }
        try {
            if (inventorySerialPort) {
                try { await inventorySerialReader?.cancel?.(); } catch (_) {}
                try { await inventorySerialPort.close(); } catch (_) {}
                inventorySerialReader = null; inventorySerialPort = null; inventorySerialBuffer='';
                setInventoryScannerMessage('Serial scanner imefungwa.'); const serialButton=getEl('tradecoreInventorySerialButton'); if(serialButton) serialButton.textContent='Serial 9600';
                return;
            }
            inventorySerialPort = await navigator.serial.requestPort();
            await inventorySerialPort.open({baudRate:9600,dataBits:8,stopBits:1,parity:'none',flowControl:'none'});
            const decoder = new TextDecoderStream();
            inventorySerialPort.readable.pipeTo(decoder.writable).catch(()=>{});
            inventorySerialReader = decoder.readable.getReader();
            setInventoryScannerMessage('Serial scanner imeunganishwa · 9600 baud. Sasa scan barcode.'); const serialButton=getEl('tradecoreInventorySerialButton'); if(serialButton) serialButton.textContent='Funga Serial';
            (async()=>{
                try {
                    while (inventorySerialReader && inventorySerialPort) {
                        const {value,done}=await inventorySerialReader.read();
                        if(done)break;
                        inventorySerialBuffer += value || '';
                        const parts=inventorySerialBuffer.split(/[\r\n]+/);
                        inventorySerialBuffer=parts.pop()||'';
                        for(const part of parts){const clean=String(part||'').trim();if(clean)await window.tradecoreInventoryScanHandler?.(clean);}
                        if (inventorySerialBuffer) {
                            if (inventorySerialFlushTimer) clearTimeout(inventorySerialFlushTimer);
                            inventorySerialFlushTimer = setTimeout(async () => {
                                const clean = String(inventorySerialBuffer || '').trim();
                                inventorySerialBuffer = '';
                                if (clean) await window.tradecoreInventoryScanHandler?.(clean);
                            }, 180);
                        }
                    }
                } catch (_) {}
            })();
        } catch (e) {
            inventorySerialPort=null; inventorySerialReader=null; inventorySerialBuffer='';
            setInventoryScannerMessage(e?.name==='NotFoundError'?'Hakuna scanner iliyochaguliwa.':(e?.message||'Serial scanner haijaunganishwa.'));
        }
    };

    // Mobile print bridge. Opens the existing print URL from a real tap. -----
    TC.printUrl = function (url) {
        if (!url) return false;
        try {
            const win = window.open(url, '_blank');
            if (!win) {
                window.location.href = url;
                return false;
            }
            return false;
        } catch (_) {
            window.location.href = url;
            return false;
        }
    };

    TC.go = function (url) {
        if (url) window.location.href = url;
    };

    function openDb() {
        return new Promise((resolve, reject) => {
            if (!('indexedDB' in window)) {
                reject(new Error('IndexedDB haipatikani kwenye kifaa hiki.'));
                return;
            }
            const request = indexedDB.open(DB_NAME, DB_VERSION);
            request.onupgradeneeded = function () {
                const db = request.result;
                if (!db.objectStoreNames.contains(SALES_STORE)) {
                    const store = db.createObjectStore(SALES_STORE, { keyPath: 'id' });
                    store.createIndex('state', 'state', { unique: false });
                    store.createIndex('createdAt', 'createdAt', { unique: false });
                }
                if (!db.objectStoreNames.contains(META_STORE)) {
                    db.createObjectStore(META_STORE, { keyPath: 'key' });
                }
            };
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error || new Error('IndexedDB failed.'));
        });
    }

    async function dbPut(storeName, value) {
        const db = await openDb();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readwrite');
            tx.objectStore(storeName).put(value);
            tx.oncomplete = () => { db.close(); resolve(value); };
            tx.onerror = () => { db.close(); reject(tx.error || new Error('DB write failed.')); };
        });
    }

    async function dbGetAll(storeName) {
        const db = await openDb();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readonly');
            const request = tx.objectStore(storeName).getAll();
            request.onsuccess = () => resolve(request.result || []);
            request.onerror = () => { db.close(); reject(request.error || new Error('DB read failed.')); };
            tx.oncomplete = () => db.close();
        });
    }

    async function dbGet(storeName, key) {
        const db = await openDb();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readonly');
            const request = tx.objectStore(storeName).get(key);
            request.onsuccess = () => resolve(request.result || null);
            request.onerror = () => { db.close(); reject(request.error || new Error('DB read failed.')); };
            tx.oncomplete = () => db.close();
        });
    }

    async function dbDelete(storeName, key) {
        const db = await openDb();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readwrite');
            tx.objectStore(storeName).delete(key);
            tx.oncomplete = () => { db.close(); resolve(true); };
            tx.onerror = () => { db.close(); reject(tx.error || new Error('DB delete failed.')); };
        });
    }

    function newTransactionId() {
        if (window.crypto && typeof crypto.randomUUID === 'function') {
            return crypto.randomUUID().replace(/-/g, '');
        }
        return 'tc' + Date.now().toString(36) + Math.random().toString(36).slice(2, 14);
    }

    TC.newTransactionId = newTransactionId;

    function formToObject(form) {
        const data = {};
        for (const [key, value] of new FormData(form).entries()) {
            if (typeof value === 'string') data[key] = value;
        }
        return data;
    }

    function objectToFormData(data) {
        const formData = new FormData();
        Object.entries(data || {}).forEach(([key, value]) => formData.append(key, String(value ?? '')));
        return formData;
    }

    function getQueueOwnerKey() {
        const raw = String(document.body?.dataset?.tradecoreUser || '').trim();
        // The base template exposes the authenticated numeric User id.
        // Refuse the generic 'session' fallback so an anonymous/stale page
        // cannot create an ownerless offline sale queue.
        return /^\d+$/.test(raw) ? raw : '';
    }

    async function setActiveQueueOwner() {
        const ownerKey = getQueueOwnerKey();
        if (!ownerKey) return '';
        try {
            await dbPut(META_STORE, { key: 'active_owner', ownerKey, updatedAt: Date.now() });
        } catch (error) {
            console.debug('Active queue owner metadata skipped:', error);
        }
        try {
            const registration = await navigator.serviceWorker?.ready;
            registration?.active?.postMessage?.({ type: 'TRADECORE_SET_ACTIVE_OWNER', ownerKey });
        } catch (_) {}
        return ownerKey;
    }

    async function queueSaleForm(form, transactionId) {
        const ownerKey = await setActiveQueueOwner();
        if (!ownerKey) throw new Error('Akaunti ya TradeCore haijatambuliwa kwa offline queue.');

        const data = formToObject(form);
        data.client_transaction_id = transactionId;
        const actionUrl = new URL(form.action || window.location.href, window.location.origin);
        if (actionUrl.origin !== window.location.origin) {
            throw new Error('Offline queue inaruhusu endpoint ya TradeCore pekee.');
        }

        const item = {
            id: transactionId,
            ownerKey,
            action: actionUrl.href,
            method: 'POST',
            data,
            state: 'pending',
            attempts: 0,
            createdAt: Date.now(),
            updatedAt: Date.now(),
            lastError: ''
        };

        await dbPut(SALES_STORE, item);
        await cacheCurrentPosCatalog();
        await refreshQueueUi();
        await requestBackgroundSync();

        const allPending = (await getQueueItems()).filter(x => x.state === 'pending');
        const position = allPending.findIndex(x => x.id === transactionId) + 1;
        return { position: Math.max(position, 1), id: transactionId };
    }

    TC.queueSaleForm = queueSaleForm;

    async function getQueueItems() {
        try {
            const ownerKey = getQueueOwnerKey();
            if (!ownerKey) return [];
            const items = await dbGetAll(SALES_STORE);
            return items
                .filter(item => item.ownerKey === ownerKey)
                .sort((a, b) => (a.createdAt || 0) - (b.createdAt || 0));
        } catch (error) {
            console.warn('TradeCore offline queue unavailable:', error);
            return [];
        }
    }

    async function requestBackgroundSync() {
        try {
            const ownerKey = await setActiveQueueOwner();
            const registration = await navigator.serviceWorker?.ready;
            registration?.active?.postMessage?.({ type: 'TRADECORE_SET_ACTIVE_OWNER', ownerKey });
            if (ownerKey && registration?.sync?.register) {
                await registration.sync.register(SYNC_TAG);
            }
        } catch (error) {
            console.debug('Background Sync unavailable:', error);
        }
    }


    async function refreshCsrfToken(actionUrl) {
        try {
            const target = new URL(actionUrl || window.location.href, window.location.origin);
            if (target.origin !== window.location.origin) return '';
            const response = await fetch(target.href, {
                method: 'GET',
                credentials: 'same-origin',
                cache: 'no-store',
                headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'text/html' }
            });
            if (!response.ok) return '';
            const html = await response.text();
            const match = html.match(/name=["']csrfmiddlewaretoken["'][^>]*value=["']([^"']+)["']/i) ||
                html.match(/value=["']([^"']+)["'][^>]*name=["']csrfmiddlewaretoken["']/i);
            return match ? match[1] : '';
        } catch (error) {
            return '';
        }
    }

    async function submitQueuedSale(item) {
        const ownerKey = getQueueOwnerKey();
        if (!ownerKey || item.ownerKey !== ownerKey) {
            return { success: false, terminal: true, message: 'Muamala huu si wa akaunti iliyopo sasa.' };
        }
        let payload = { ...item.data };
        let response;

        try {
            const actionUrl = new URL(item.action, window.location.origin);
            if (actionUrl.origin !== window.location.origin) {
                return { success: false, terminal: true, message: 'Endpoint ya offline sale si salama.' };
            }
            response = await fetch(actionUrl.href, {
                method: 'POST',
                body: objectToFormData(payload),
                credentials: 'same-origin',
                redirect: 'follow',
                cache: 'no-store',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json'
                }
            });

            if (response.status === 403) {
                const freshToken = await refreshCsrfToken(item.action);
                if (freshToken && freshToken !== payload.csrfmiddlewaretoken) {
                    payload.csrfmiddlewaretoken = freshToken;
                    item.data.csrfmiddlewaretoken = freshToken;
                    await dbPut(SALES_STORE, item);
                    response = await fetch(actionUrl.href, {
                        method: 'POST',
                        body: objectToFormData(payload),
                        credentials: 'same-origin',
                        redirect: 'follow',
                        cache: 'no-store',
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'Accept': 'application/json'
                        }
                    });
                }
            }

            const data = await response.json().catch(() => null);

            if (response.url && /\/login\/?(?:\?|$)/.test(new URL(response.url, window.location.origin).pathname)) {
                return { success: false, terminal: true, message: 'Session imekwisha. Ingia tena kisha sync.' };
            }

            if (response.ok && data?.ok) {
                return { success: true, data };
            }

            if (data && data.ok === false) {
                return {
                    success: false,
                    terminal: true,
                    message: data.message || 'Server imekataa muamala huu.'
                };
            }

            return {
                success: false,
                terminal: false,
                message: `Server response ${response.status}`
            };
        } catch (error) {
            return {
                success: false,
                terminal: false,
                message: error?.message || 'Network error'
            };
        }
    }

    async function syncPendingSales() {
        const ownerKey = await setActiveQueueOwner();
        if (!ownerKey || syncing || !navigator.onLine) return { synced: 0, failed: 0 };
        syncing = true;
        updateConnectionUi('syncing');

        let synced = 0;
        let failed = 0;
        try {
            const items = await getQueueItems();
            for (const item of items) {
                if (item.state !== 'pending') continue;

                item.attempts = Number(item.attempts || 0) + 1;
                item.updatedAt = Date.now();
                await dbPut(SALES_STORE, item);

                const result = await submitQueuedSale(item);
                if (result.success) {
                    await dbDelete(SALES_STORE, item.id);
                    synced += 1;
                } else if (result.terminal) {
                    item.state = 'needs_attention';
                    item.lastError = result.message || 'Muamala unahitaji attention.';
                    item.updatedAt = Date.now();
                    await dbPut(SALES_STORE, item);
                    failed += 1;
                } else {
                    item.lastError = result.message || 'Network imekatika.';
                    item.updatedAt = Date.now();
                    await dbPut(SALES_STORE, item);
                    break;
                }
            }
        } catch (error) {
            console.warn('TradeCore sync failed:', error);
        } finally {
            syncing = false;
            updateConnectionUi(navigator.onLine ? 'online' : 'offline');
            await refreshQueueUi();
        }

        if (synced > 0) {
            showSyncToast(`${synced} sale${synced === 1 ? '' : 's'} zimesync.`);
        }
        return { synced, failed };
    }

    TC.syncNow = syncPendingSales;

    async function removeQueuedSale(id) {
        await dbDelete(SALES_STORE, id);
        await refreshQueueUi();
    }

    window.tradeCoreRemoveQueuedSale = removeQueuedSale;

    function escapeHtml(value) {
        const div = document.createElement('div');
        div.textContent = String(value ?? '');
        return div.innerHTML;
    }

    function queueStateLabel(item) {
        if (item.state === 'needs_attention') return 'Needs attention';
        return 'Pending sync';
    }

    async function refreshQueueUi() {
        const items = await getQueueItems();
        const pending = items.filter(item => item.state === 'pending');
        const attention = items.filter(item => item.state === 'needs_attention');
        const activeCount = pending.length + attention.length;

        const badge = getEl('tradecorePendingCount');
        const quickCount = getEl('tradecoreQuickPendingCount');
        if (badge) {
            badge.textContent = String(activeCount);
            badge.classList.toggle('hidden', activeCount === 0);
        }
        if (quickCount) quickCount.textContent = `(${activeCount})`;

        const title = getEl('tradecoreSyncStatusTitle');
        const copy = getEl('tradecoreSyncStatusCopy');
        const icon = getEl('tradecoreSyncStatusIcon');
        if (title) {
            if (attention.length) title.textContent = `${attention.length} sale inahitaji attention`;
            else if (pending.length) title.textContent = `${pending.length} sale zinasubiri sync`;
            else title.textContent = 'Hakuna pending sales';
        }
        if (copy) {
            if (attention.length) copy.textContent = 'Stock/customer/session issue ilizuia sync. Kagua hapa.';
            else if (pending.length && navigator.onLine) copy.textContent = 'Internet ipo. TradeCore inaweza ku-sync sasa.';
            else if (pending.length) copy.textContent = 'Internet haipo. Sales zimehifadhiwa salama kwenye kifaa.';
            else copy.textContent = 'Muamala ukikatika internet, TradeCore utauweka hapa.';
        }
        if (icon) {
            icon.textContent = attention.length ? '!' : pending.length ? '↻' : '✓';
            icon.classList.toggle('needs-attention', attention.length > 0);
            icon.classList.toggle('has-pending', pending.length > 0 && !attention.length);
        }

        const list = getEl('tradecorePendingSalesList');
        if (list) {
            if (!activeCount) {
                list.innerHTML = '';
            } else {
                list.innerHTML = items.map(item => {
                    const time = new Date(item.createdAt || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                    const state = queueStateLabel(item);
                    const error = item.state === 'needs_attention' ? `<div class="tradecore-sync-error">${escapeHtml(item.lastError || 'Muamala unahitaji attention.')}</div>` : '';
                    return `<div class="tradecore-sync-item ${item.state === 'needs_attention' ? 'needs-attention' : ''}">
                        <div class="min-w-0">
                            <div class="tradecore-sync-item-title">Sale • ${escapeHtml(item.id.slice(0, 10).toUpperCase())}</div>
                            <div class="tradecore-sync-item-meta">${escapeHtml(time)} · ${escapeHtml(state)}${item.attempts ? ` · attempts ${item.attempts}` : ''}</div>
                            ${error}
                        </div>
                        <button type="button" onclick="tradeCoreRemoveQueuedSale('${escapeHtml(item.id)}')" class="tradecore-sync-delete" aria-label="Ondoa queue">×</button>
                    </div>`;
                }).join('');
            }
        }

        const button = getEl('tradecoreSyncNowButton');
        if (button) {
            button.disabled = syncing || !navigator.onLine || pending.length === 0;
            button.textContent = syncing ? '↻ Inasynchronize...' : '↻ Sync sasa';
            if (!navigator.onLine) button.textContent = 'Offline — itasubiri internet';
        }
    }

    function showSyncToast(message) {
        const toast = getEl('toastNotification');
        const messageEl = getEl('toastMessage');
        if (messageEl) messageEl.textContent = message;
        if (toast) {
            toast.classList.remove('opacity-0');
            clearTimeout(window.__tradecoreSyncToastTimer);
            window.__tradecoreSyncToastTimer = setTimeout(() => toast.classList.add('opacity-0'), 2200);
        }
    }

    TC.showOfflineQueued = function (position) {
        updateConnectionUi('offline');
        showSyncToast(`Internet haipo. Sale imehifadhiwa salama • Queue #${position}`);
        TC.openSyncSheet();
    };

    function updateConnectionUi(state) {
        const status = getEl('tradecoreConnectionStatus');
        const label = getEl('tradecoreConnectionLabel');
        if (!status || !label) return;

        status.classList.remove('is-offline', 'is-syncing', 'is-online');
        if (state === 'offline') {
            status.classList.add('is-offline');
            label.textContent = 'Offline';
        } else if (state === 'syncing') {
            status.classList.add('is-syncing');
            label.textContent = 'Syncing';
        } else {
            status.classList.add('is-online');
            label.textContent = 'Online';
        }
    }

    async function cacheCurrentPosCatalog() {
        const cards = [...document.querySelectorAll('#productGridContainer .product-card[data-id]')];
        if (!cards.length) return;

        const catalog = cards.map(card => ({
            id: card.dataset.id,
            name: card.dataset.name || '',
            barcode: card.dataset.barcode || '',
            selling_price: card.dataset.price || '0',
            stock: card.dataset.stock || '0',
            category: card.dataset.category || ''
        }));

        const userKey = document.body.dataset.tradecoreUser || 'session';
        try {
            localStorage.setItem(`tradecore_catalog_${userKey}`, JSON.stringify({ updatedAt: Date.now(), products: catalog }));
        } catch (error) {
            console.debug('Catalog cache skipped:', error);
        }
    }

    TC.cacheCurrentPosCatalog = cacheCurrentPosCatalog;

    window.addEventListener('beforeinstallprompt', function (event) {
        event.preventDefault();
        deferredInstallPrompt = event;
        document.querySelectorAll('[data-tradecore-install]').forEach(el => el.classList.remove('hidden'));
    });

    window.addEventListener('appinstalled', function () {
        deferredInstallPrompt = null;
        document.querySelectorAll('[data-tradecore-install]').forEach(el => el.classList.add('hidden'));
    });

    window.addEventListener('offline', async function () {
        updateConnectionUi('offline');
        await refreshQueueUi();
    });

    window.addEventListener('online', async function () {
        updateConnectionUi('syncing');
        await syncPendingSales();
    });

    document.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape') return;
        TC.closeMore();
        TC.closeQuickActions();
        TC.closeSyncSheet();
        TC.closeInstallSheet();
        TC.closeMobileCart();
        TC.closeScanner();
    });

    document.addEventListener('click', function (event) {
        const more = sheet();
        const quick = actions();
        const sync = syncSheet();
        const install = installSheet();
        const scanner = getEl('tradecoreScannerSheet');
        if (event.target === scanner) TC.closeScanner();
        if (event.target === more) TC.closeMore();
        if (event.target === quick) TC.closeQuickActions();
        if (event.target === sync) TC.closeSyncSheet();
        if (event.target === install) TC.closeInstallSheet();
    });

    document.addEventListener('DOMContentLoaded', function () {
        const inventoryInput = getEl('tradecoreInventoryScannerInput');
        let inventoryInputTimer = null;
        inventoryInput?.addEventListener('input', function () {
            clearTimeout(inventoryInputTimer);
            const value = String(this.value || '').trim();
            if (value.length < 4) return;
            inventoryInputTimer = setTimeout(() => {
                if (document.activeElement === inventoryInput && value === String(this.value || '').trim()) {
                    TC.submitInventoryScannerInput();
                }
            }, 350);
        });
    });

    window.addEventListener('load', async function () {
        updateConnectionUi(navigator.onLine ? 'online' : 'offline');
        await setActiveQueueOwner();
        const route = document.body.dataset.tradecoreRoute || '';
        document.querySelectorAll('[data-tradecore-route]').forEach(function (item) {
            item.classList.toggle('is-active', item.dataset.tradecoreRoute === route);
        });

        await refreshQueueUi();
        await cacheCurrentPosCatalog();
        let density = 1; try { density = Number(localStorage.getItem(DENSITY_KEY) ?? 1); } catch (_) {}
        applyProductDensity(density);
        syncMobileCartSummary();

        const totalNode = getEl('totalDisplay');
        const countNode = getEl('itemCountBadge');
        if (window.MutationObserver && (totalNode || countNode)) {
            const observer = new MutationObserver(syncMobileCartSummary);
            if (totalNode) observer.observe(totalNode, { childList: true, characterData: true, subtree: true });
            if (countNode) observer.observe(countNode, { childList: true, characterData: true, subtree: true });
        }

        const cartHeader = getEl('cartHeader');
        cartHeader?.addEventListener('keydown', function (event) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                TC.toggleMobileCart();
            }
        });

        if ('storage' in navigator && navigator.storage.persist) {
            navigator.storage.persist().catch(() => {});
        }

        if ('serviceWorker' in navigator) {
            try {
                const registration = await navigator.serviceWorker.register('/service-worker.js', { scope: '/' });
                if (registration?.active) await requestBackgroundSync();
            } catch (error) {
                console.warn('TradeCore PWA service worker registration failed:', error);
            }
        }

        // Mobile browsers can restore an online page after waking from sleep;
        // a short sync pass catches anything queued in the background.
        if (navigator.onLine) syncPendingSales();

        // Receiving/stock is server-authoritative. When the installed PWA
        // resumes, refresh the POS Duka stock so a received item cannot remain
        // visually SOLD OUT because of a stale page snapshot.
        const refreshRouteStock = () => {
            if (!navigator.onLine || typeof window.refreshPOSStockFromServer !== 'function') return;
            window.refreshPOSStockFromServer().catch(() => {});
        };
        window.addEventListener('pageshow', refreshRouteStock);
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') refreshRouteStock();
        });
    });
})();
