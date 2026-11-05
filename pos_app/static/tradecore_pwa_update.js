/* TradeCore PWA release updater — v1.1.9.
 * Shows a real cache-preparation progress screen only for an already-installed
 * PWA receiving a newer service worker. It never touches IndexedDB sales data.
 */
(function () {
    'use strict';

    const APP_VERSION = '1.1.9';
    const SERVICE_WORKER_URL = '/service-worker.js';
    let registrationPromise = null;
    let registration = null;
    let hadActiveWorker = false;
    let updateVisible = false;
    let progressValue = 0;
    let reloadScheduled = false;
    let overlay = null;
    let nodes = null;

    function isInstalledPwa() {
        return Boolean(
            window.matchMedia?.('(display-mode: standalone)')?.matches ||
            window.matchMedia?.('(display-mode: fullscreen)')?.matches ||
            navigator.standalone === true
        );
    }

    function ensureOverlay() {
        if (overlay || !document.body) return;

        const style = document.createElement('style');
        style.id = 'tradecore-pwa-upgrade-style-v119';
        style.textContent = `
            #tc-pwa-upgrade-overlay {
                position: fixed; inset: 0; z-index: 2147483647;
                display: flex; align-items: center; justify-content: center;
                padding: 24px; background: rgba(12, 16, 12, .82);
                backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
                opacity: 0; visibility: hidden; pointer-events: none;
                transition: opacity .22s ease, visibility .22s ease;
                font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", sans-serif;
            }
            #tc-pwa-upgrade-overlay.is-visible {
                opacity: 1; visibility: visible; pointer-events: auto;
            }
            #tc-pwa-upgrade-overlay .tc-upgrade-card {
                width: min(420px, 100%); padding: 34px 28px 28px;
                border: 1px solid rgba(255,255,255,.16); border-radius: 28px;
                background: linear-gradient(160deg, #fff 0%, #f4f6ee 100%);
                color: #263020; text-align: center;
                box-shadow: 0 28px 90px rgba(0,0,0,.32);
            }
            #tc-pwa-upgrade-overlay .tc-upgrade-mark {
                width: 58px; height: 58px; margin: 0 auto 18px;
                display: grid; place-items: center; border-radius: 19px;
                background: #667342; color: #fff; font-size: 21px; font-weight: 900;
                letter-spacing: -.06em; box-shadow: 0 9px 24px rgba(102,115,66,.25);
            }
            #tc-pwa-upgrade-overlay .tc-upgrade-kicker {
                color: #667342; font-size: 10px; font-weight: 850;
                letter-spacing: .19em; text-transform: uppercase;
            }
            #tc-pwa-upgrade-overlay .tc-upgrade-title {
                margin: 9px 0 7px; color: #20291b;
                font-size: 21px; font-weight: 850; letter-spacing: -.035em;
            }
            #tc-pwa-upgrade-overlay .tc-upgrade-copy {
                margin: 0 auto 23px; max-width: 290px;
                color: #68715f; font-size: 12px; line-height: 1.65;
            }
            #tc-pwa-upgrade-overlay .tc-upgrade-track {
                height: 9px; overflow: hidden; border-radius: 99px;
                background: #e4e9dc; box-shadow: inset 0 1px 2px rgba(0,0,0,.06);
            }
            #tc-pwa-upgrade-overlay .tc-upgrade-fill {
                width: 0%; height: 100%; border-radius: inherit;
                background: linear-gradient(90deg, #667342, #91a36a);
                transition: width .28s ease;
            }
            #tc-pwa-upgrade-overlay .tc-upgrade-meta {
                display: flex; justify-content: space-between; align-items: center;
                margin-top: 10px; color: #737d6b; font-size: 11px; font-weight: 750;
                font-variant-numeric: tabular-nums;
            }
            #tc-pwa-upgrade-overlay .tc-upgrade-percent {
                color: #526033; font-size: 17px; font-weight: 900;
            }
            #tc-pwa-upgrade-overlay .tc-upgrade-error {
                margin-top: 18px; color: #9f352b; font-size: 12px; line-height: 1.5;
            }
            #tc-pwa-upgrade-overlay .tc-upgrade-retry {
                margin-top: 14px; padding: 11px 18px; border: 0; border-radius: 12px;
                background: #667342; color: #fff; font-size: 12px; font-weight: 800;
                cursor: pointer;
            }
            @media (prefers-reduced-motion: reduce) {
                #tc-pwa-upgrade-overlay, #tc-pwa-upgrade-overlay .tc-upgrade-fill { transition: none; }
            }
        `;
        document.head.appendChild(style);

        overlay = document.createElement('div');
        overlay.id = 'tc-pwa-upgrade-overlay';
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-modal', 'true');
        overlay.setAttribute('aria-hidden', 'true');
        overlay.setAttribute('aria-label', 'TradeCore application update');
        overlay.innerHTML = `
            <section class="tc-upgrade-card">
                <div class="tc-upgrade-mark" aria-hidden="true">TC</div>
                <div class="tc-upgrade-kicker" id="tc-upgrade-kicker">TRADECORE UPGRADING</div>
                <h1 class="tc-upgrade-title" id="tc-upgrade-title">Inasasisha mfumo wako</h1>
                <p class="tc-upgrade-copy" id="tc-upgrade-copy">Tunaandaa toleo jipya la TradeCore. Tafadhali usifunge app wakati update inaendelea.</p>
                <div class="tc-upgrade-track" role="progressbar" aria-label="Upgrade progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" id="tc-upgrade-track">
                    <div class="tc-upgrade-fill" id="tc-upgrade-fill"></div>
                </div>
                <div class="tc-upgrade-meta">
                    <span id="tc-upgrade-version">TradeCore v${APP_VERSION}</span>
                    <span class="tc-upgrade-percent" id="tc-upgrade-percent">0%</span>
                </div>
                <div class="tc-upgrade-error" id="tc-upgrade-error" hidden></div>
                <button class="tc-upgrade-retry" id="tc-upgrade-retry" type="button" hidden>Jaribu tena</button>
            </section>
        `;
        document.body.appendChild(overlay);
        nodes = {
            kicker: overlay.querySelector('#tc-upgrade-kicker'),
            title: overlay.querySelector('#tc-upgrade-title'),
            copy: overlay.querySelector('#tc-upgrade-copy'),
            fill: overlay.querySelector('#tc-upgrade-fill'),
            track: overlay.querySelector('#tc-upgrade-track'),
            percent: overlay.querySelector('#tc-upgrade-percent'),
            version: overlay.querySelector('#tc-upgrade-version'),
            error: overlay.querySelector('#tc-upgrade-error'),
            retry: overlay.querySelector('#tc-upgrade-retry')
        };
        nodes.retry.addEventListener('click', retryUpdate);
    }

    function openUpgrade() {
        if (!hadActiveWorker || !isInstalledPwa()) return false;
        ensureOverlay();
        if (!overlay) return false;
        updateVisible = true;
        overlay.classList.add('is-visible');
        overlay.setAttribute('aria-hidden', 'false');
        document.documentElement.style.overflow = 'hidden';
        document.body.style.overflow = 'hidden';
        return true;
    }

    function setProgress(value) {
        progressValue = Math.max(progressValue, Math.min(100, Math.max(0, Number(value) || 0)));
        if (!nodes) return;
        nodes.fill.style.width = `${progressValue}%`;
        nodes.percent.textContent = `${progressValue}%`;
        nodes.track.setAttribute('aria-valuenow', String(progressValue));
    }

    function setCopy(message) {
        if (nodes && message) nodes.copy.textContent = message;
    }

    function showFailure(message) {
        if (!openUpgrade() && !updateVisible) return;
        nodes.kicker.textContent = 'UPDATE IMESIMAMA';
        nodes.title.textContent = 'Imeshindikana kukamilisha update';
        nodes.error.hidden = false;
        nodes.error.textContent = message || 'Muunganisho umekatika. Toleo la sasa limehifadhiwa; jaribu tena ukiwa online.';
        nodes.retry.hidden = false;
        setCopy('TradeCore ya sasa bado inalindwa. Unaweza kujaribu tena bila kupoteza mauzo yaliyohifadhiwa offline.');
    }

    async function retryUpdate() {
        if (!registration) return;
        nodes.error.hidden = true;
        nodes.retry.hidden = true;
        nodes.kicker.textContent = 'TRADECORE UPGRADING';
        nodes.title.textContent = 'Inaendelea kusasisha';
        setCopy('Tunajaribu kupakua tena mafaili ya toleo jipya...');
        setProgress(0);
        try {
            await registration.update();
        } catch (error) {
            showFailure('Bado hatujaweza kuwasiliana na server. Hakikisha internet inafanya kazi kisha ujaribu tena.');
        }
    }

    function finishUpgrade() {
        if (!updateVisible || reloadScheduled) return;
        reloadScheduled = true;
        setProgress(100);
        nodes.kicker.textContent = 'UPGRADED';
        nodes.title.textContent = 'TradeCore imesasishwa';
        nodes.error.hidden = true;
        nodes.retry.hidden = true;
        setCopy('Toleo v1.1.9 limewekwa tayari. Tunafungua mfumo...');
        window.setTimeout(() => window.location.reload(), 650);
    }

    function onWorkerMessage(event) {
        const data = event.data || {};
        if (!String(data.type || '').startsWith('TRADECORE_UPDATE_')) return;
        if (data.version !== APP_VERSION) return;
        if (!hadActiveWorker || !isInstalledPwa()) return;

        if (data.type === 'TRADECORE_UPDATE_STARTED') {
            openUpgrade();
            setProgress(0);
            setCopy('Tunapakua na kuandaa mafaili ya toleo jipya...');
            return;
        }

        if (data.type === 'TRADECORE_UPDATE_PROGRESS') {
            openUpgrade();
            setProgress(data.percent);
            setCopy('Inaandaa sehemu za mfumo. Tafadhali subiri...');
            return;
        }

        if (data.type === 'TRADECORE_UPDATE_READY') {
            openUpgrade();
            setProgress(100);
            setCopy('Maboresho yamepakuliwa. Tunakamilisha usakinishaji...');
            return;
        }

        if (data.type === 'TRADECORE_UPDATE_FAILED') {
            showFailure('Imeshindikana kupakua baadhi ya mafaili. Jaribu tena ukiwa na internet.');
            return;
        }

        if (data.type === 'TRADECORE_UPDATE_ACTIVATED') {
            finishUpgrade();
        }
    }

    function watchRegistration(reg) {
        registration = reg;
        reg.addEventListener('updatefound', () => {
            const installing = reg.installing;
            if (hadActiveWorker && isInstalledPwa()) openUpgrade();
            if (!installing) return;
            installing.addEventListener('statechange', () => {
                if (installing.state === 'redundant' && updateVisible && progressValue < 100) {
                    showFailure('Update haikuweza kukamilika. Toleo la sasa limeachwa salama.');
                }
            });
        });

        if (reg.installing && hadActiveWorker && isInstalledPwa()) openUpgrade();
    }

    function register() {
        if (!('serviceWorker' in navigator)) return Promise.resolve(null);
        if (registrationPromise) return registrationPromise;

        registrationPromise = (async () => {
            navigator.serviceWorker.addEventListener('message', onWorkerMessage);
            navigator.serviceWorker.addEventListener('controllerchange', () => {
                if (updateVisible && progressValue >= 100) finishUpgrade();
            });

            // Capture the controller synchronously before awaiting registration lookup;
            // an update worker can begin installing while that lookup is pending.
            hadActiveWorker = Boolean(navigator.serviceWorker.controller);
            const existing = await navigator.serviceWorker.getRegistration('/');
            hadActiveWorker = hadActiveWorker || Boolean(existing?.active);

            const reg = await navigator.serviceWorker.register(SERVICE_WORKER_URL, {
                scope: '/',
                updateViaCache: 'none'
            });
            watchRegistration(reg);
            return reg;
        })().catch(error => {
            registrationPromise = null;
            console.warn('TradeCore PWA updater could not register service worker:', error);
            return null;
        });

        return registrationPromise;
    }

    window.TradeCorePwaUpdater = {
        version: APP_VERSION,
        register,
        isInstalledPwa
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', register, { once: true });
    } else {
        register();
    }
})();
