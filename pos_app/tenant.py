from contextlib import contextmanager
from contextvars import ContextVar

from django.db import models


# Request-scoped tenant identifier.
# None  = no tenant context has been established (safe for migrations/admin/
#         registration and other non-tenant operations).
# 0     = an authenticated request was established without a tenant; this
#         MUST return an empty tenant queryset rather than exposing all rows.
_current_duka_id = ContextVar("tradecore_current_duka_id", default=None)

# Explicit sentinel used when an authenticated request has no valid tenant.
# None remains reserved for deliberately unscoped/non-request operations.
NO_TENANT = 0


def _normalize_tenant_id(duka_id):
    """Normalize a tenant identifier without silently truncating malformed IDs."""
    if duka_id is None:
        return None

    if isinstance(duka_id, bool):
        return NO_TENANT

    if isinstance(duka_id, int):
        tenant_id = duka_id
    else:
        raw = str(duka_id).strip()
        if not raw:
            return None
        if not raw.isdecimal():
            return NO_TENANT
        try:
            tenant_id = int(raw)
        except (TypeError, ValueError, OverflowError):
            return NO_TENANT

    return tenant_id if tenant_id > 0 else NO_TENANT


def set_current_duka_id(duka_id):
    """Set the current tenant and return the ContextVar reset token."""
    return _current_duka_id.set(_normalize_tenant_id(duka_id))


def get_current_duka_id():
    return _current_duka_id.get()


def reset_current_duka(token):
    """Restore the previous tenant context using the token returned above."""
    _current_duka_id.reset(token)


@contextmanager
def tenant_scope(duka_id):
    """Temporarily scope ORM queries to one tenant and always restore context."""
    token = set_current_duka_id(duka_id)
    try:
        yield get_current_duka_id()
    finally:
        reset_current_duka(token)


class TenantManager(models.Manager):
    tenant_lookup = "duka_id"

    def get_queryset(self):
        qs = super().get_queryset()
        tenant_id = get_current_duka_id()

        # No request tenant has been established. Keep legacy unscoped
        # behaviour for migrations, shell/admin maintenance and registration.
        if tenant_id is None:
            # Intentional escape hatch for migration/admin/maintenance callers.
            # Authenticated requests are expected to establish either a real
            # tenant ID or NO_TENANT through the middleware.
            return qs

        # The middleware uses tenant_id=0 for an authenticated user who has no
        # Duka. Fail closed: that user must see zero tenant rows, never every
        # tenant's records.
        if tenant_id == NO_TENANT:
            return qs.none()

        return qs.filter(**{self.tenant_lookup: tenant_id})


class DukaTenantManager(TenantManager):
    tenant_lookup = "duka_id"


class ProductStockTenantManager(TenantManager):
    tenant_lookup = "location__duka_id"


class TransferItemTenantManager(TenantManager):
    tenant_lookup = "transfer__duka_id"


class StockTakeItemTenantManager(TenantManager):
    tenant_lookup = "stock_take__duka_id"


class PurchaseRequestItemTenantManager(TenantManager):
    tenant_lookup = "purchase_request__duka_id"


class SaleReturnTenantManager(TenantManager):
    tenant_lookup = "sale__duka_id"


class ActivityTenantManager(TenantManager):
    tenant_lookup = "duka_id"
