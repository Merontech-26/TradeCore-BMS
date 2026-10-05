# TradeCore PWA Desktop UI Fix

Fixed a presentation-only regression where the new mobile PWA action sheets were visible in the desktop layout.

Change:
- `.tradecore-mobile-sheet` is now hidden by default.
- It is switched to `display:flex` only inside the existing mobile breakpoint (`max-width: 767px`).

No Django views, models, migrations, routes, database, or business logic were changed by this fix.
