# TradeCore PWA Final Integration

This package is the uploaded TradeCore source with the mobile PWA layer completed.

## Preserved

- Existing `models.py` and all database models.
- Existing migration history (no new migration required for this PWA layer).
- Existing `db.sqlite3`.
- Existing business calculations and stock locking in `Mauzo.save()` and `mauzo_view()`.
- Existing routes and existing non-AJAX form behavior.
- Existing TradeCore desktop UI and page-specific JavaScript functions.

## Added / completed

- Apple-style mobile app shell for phones: glass app bar, touch navigation, bottom tab bar, quick-action sheet and responsive spacing.
- Purple + gold + white TradeCore visual system on mobile.
- Installable PWA manifest and icons.
- Service worker for PWA static assets.
- Online/offline connection state indicator.
- IndexedDB offline sales queue.
- Automatic sync when the connection returns.
- Browser Background Sync support where the browser exposes the Sync API.
- Offline/Sync popup showing pending transactions and any item that needs attention.
- CSRF refresh/retry during queued sync when needed.
- Server-side AJAX JSON response path for POS checkout, while ordinary POST/redirect behavior remains intact.
- Sale idempotency marker using the existing ActivityLog, preventing duplicate sales when an HTTP response is lost and the same offline transaction is retried.
- Cached POS product catalog snapshot for the current signed-in browser session.

## Important behavior

The mobile PWA is one TradeCore application using the existing Django backend/database. Desktop browsers keep the existing desktop experience; phone-sized screens receive the mobile UI.

Offline sales are queued locally and are submitted to the existing `/mauzo/` endpoint when connectivity returns. Server-side stock and price validation remains authoritative. A queued transaction that is rejected because of a real business rule (for example insufficient stock, invalid customer or expired session) is marked `Needs attention` instead of being retried forever.

The PWA layer intentionally does not cache private dashboard/business HTML pages. Static PWA assets are cached; business transactions remain server-authoritative.

## Verification performed

- Python syntax compilation: passed.
- JavaScript syntax check (`tradecore_pwa.js`): passed.
- Service-worker JavaScript syntax check: passed.
- Django template parsing for `base.html`, `mauzo.html`, and `dashboard.html`: passed.
- `python manage.py check`: passed with 0 issues.
- `python manage.py test`: 0 tests discovered in the uploaded project.
- `/service-worker.js` endpoint smoke test: passed.
- `/mauzo/` anonymous-auth redirect smoke test: passed.
- `models.py`, `db.sqlite3`, and source migration files were not changed by the final PWA work.
