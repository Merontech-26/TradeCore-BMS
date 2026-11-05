"""TradeCore Control Room security boundary.

Protects the owner-only /control/ surface at the HTTP layer. This middleware
runs after Django AuthenticationMiddleware so request.user is authoritative.
It is deliberately scoped to /control/ and does not change normal POS routes.
"""

import logging

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden

logger = logging.getLogger("tradecore.control_room_security")


class ControlRoomSecurityMiddleware:
    CONTROL_PREFIX = "/control/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(self.CONTROL_PREFIX):
            return self.get_response(request)

        if not getattr(request.user, "is_authenticated", False):
            response = redirect_to_login(request.get_full_path(), login_url="/login/")
            return self._harden_response(response)

        if not getattr(request.user, "is_superuser", False):
            logger.warning(
                "CONTROL_ROOM_DENIED user=%s path=%s method=%s ip=%s",
                getattr(request.user, "username", ""),
                request.path,
                request.method,
                self._client_ip(request),
            )
            return self._harden_response(HttpResponseForbidden("Access denied."))

        logger.info(
            "CONTROL_ROOM_ACCESS user=%s path=%s method=%s ip=%s",
            getattr(request.user, "username", ""),
            request.path,
            request.method,
            self._client_ip(request),
        )
        response = self.get_response(request)
        return self._harden_response(response)

    @staticmethod
    def _client_ip(request):
        # Forwarded IP is used for audit context only, never for authorization.
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    @staticmethod
    def _harden_response(response):
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        response["Referrer-Policy"] = "no-referrer"
        response["X-Content-Type-Options"] = "nosniff"
        # Control Room's JavaScript is served as a same-origin static asset.
        # No inline script or inline event handlers are required by its template.
        response["Content-Security-Policy"] = (
            "default-src 'none'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "form-action 'self'; "
            "base-uri 'none'; "
            "object-src 'none'; "
            "frame-ancestors 'none'"
        )
        return response
