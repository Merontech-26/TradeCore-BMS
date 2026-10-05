# TradeCore PWA — Phone QA Checklist

## Start
```bash
source .venv/bin/activate
python manage.py check
python manage.py runserver 0.0.0.0:8000
```
Use the Mac LAN IP on the phone, for example `http://192.168.x.x:8000`.

## POS / Mobile UI
- [ ] Product grid uses the full phone width with no desktop sidebar/header leakage.
- [ ] Product size control switches 4× → 3× → 2× and remembers the choice after reload.
- [ ] Search opens and can find products by name/barcode.
- [ ] Scan button opens the scanner sheet.
- [ ] On HTTPS + supported browser, camera opens and barcode detection adds the product to cart.
- [ ] On LAN HTTP, scanner sheet clearly offers HID/Bluetooth/USB keyboard-scanner input instead of failing silently.

## Floating cart
- [ ] Cart is only a floating icon + item badge while browsing.
- [ ] Floating cart shows no price/details.
- [ ] Tapping it opens the existing cart as a full-screen invoice drawer.
- [ ] Closing the drawer does NOT clear the cart.
- [ ] Adding more products after closing keeps all previous items.
- [ ] Reloading the POS restores the existing draft cart when the normal POS draft is available.
- [ ] Only Complete Sale / Clear Cart / Cancel Sale clears the cart.

## Stoo / Barcode
- [ ] Zaidi → Stoo opens the existing Stoo page.
- [ ] Sajili Bidhaa uses the existing product form and server logic.
- [ ] Product details → Generate New uses the existing barcode endpoint.
- [ ] Product details/row → Print Barcode opens the existing Barcode Print Studio.
- [ ] Barcode Print Studio can select roll/label settings and print.

## Matumizi
- [ ] Print / PDF on the Matumizi page opens the existing report URL.
- [ ] The report auto-opens the device print dialog when `?print=1` is loaded.

## More / Zaidi
- [ ] Dashboard, Stoo, Mauzo, Matumizi, Wateja, Wafanyakazi, Mawasiliano, Ripoti appear according to the user's role.
- [ ] Notifications, Profile, Settings, Offline & Sync buttons open their existing UI.
- [ ] Logout still opens the existing logout confirmation.

## PWA install
- [ ] HTTPS production build shows the native install prompt on supported browsers.
- [ ] iOS Safari guide explains Share → Add to Home Screen.
- [ ] Local HTTP testing explains why native install may not be available; it does not fail silently.

## Network / offline
- [ ] Online indicator changes when network changes.
- [ ] Offline sale is queued locally.
- [ ] Reconnecting triggers sync.
- [ ] Duplicate transaction IDs do not create duplicate sales.
