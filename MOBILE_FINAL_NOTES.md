# TradeCore mobile final delivery

- Desktop layout is preserved; mobile-only PWA layer is responsive under 768px.
- POS cart is a floating icon+count; the existing cart DOM becomes a full-screen persistent drawer when opened. Closing it never clears cart state.
- Product density: 4x / 3x / 2x columns, persisted per user/device.
- Camera scanner uses BarcodeDetector where available over HTTPS; HTTP LAN testing falls back to HID keyboard scanner input.
- Stoo is exposed from Zaidi and keeps the existing product/barcode routes and forms.
- Matumizi Print/PDF uses the existing report URL and opens the native print dialog from a user gesture/new tab.
- No changes made to views.py, models.py, pos_app/urls.py, tradecore/urls.py, or db.sqlite3 by this delivery patch.
