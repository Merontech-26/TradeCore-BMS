# TradeCore Mobile POS v2 Fix

- Preserves the existing POS DOM and business JavaScript. The existing invoice is presented as a mobile drawer instead of cloned markup.
- On screens <= 767px, #cartSection is a sticky collapsed Current Order bar near the top of the app.
- The Current Order header shows the live order total and item count and can be tapped to expand the full existing invoice.
- Expanded invoice keeps the existing customer selector, cart items, discount/markup controls and payment button.
- A backdrop prevents accidental interaction with the product grid while the invoice is open.
- Mobile cart state and total mirror existing #itemCountBadge and #totalDisplay using a MutationObserver.
- Install no longer silently does nothing: native beforeinstallprompt is used when available; iPhone/iPad gets Add to Home Screen guidance; unsupported/local HTTP testing gets a clear explanation.
- Desktop behavior remains protected by mobile-only media queries.
- No changes were made to models.py, views.py, db.sqlite3, pos_app/urls.py or tradecore/urls.py in this patch.
