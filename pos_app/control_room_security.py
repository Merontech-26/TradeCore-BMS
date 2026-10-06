"""
TradeCore Control Room security boundary.

Purpose:
- Protect /control/ as an owner-only surface at the HTTP layer.
- Fail closed for unauthenticated/non-superuser requests.
- Prevent browser/proxy caching of sensitive Control Room responses.
- Emit an audit entry for each allowed Control Room request.
- Add defense-in-depth response headers.

This middleware is intentionally scoped to /control/ and does not alter
normal TradeCore application routes or business logic.
"""

import logging

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden
from django.utils.http import url_has_allowed_host_and_scheme

logger = logging.getLogger("tradecore.control_room_security")


class ControlRoomSecurityMiddleware:
    CONTROL_PREFIX = "/control/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(self.CONTROL_PREFIX):
            return self.get_response(request)

        # Control Room is an owner/superuser surface, not a normal staff page.
        if not getattr(request.user, "is_authenticated", False):
            # Reuse Django's safe login redirect behavior.
            return redirect_to_login(request.get_full_path(), login_url="/login/")

        if not getattr(request.user, "is_superuser", False):
            logger.warning(
                "CONTROL_ROOM_DENIED user=%s path=%s method=%s ip=%s",
                getattr(request.user, "username", ""),
                request.path,
                request.method,
                self._client_ip(request),
            )
            response = HttpResponseForbidden("Access denied.")
            return self._harden_response(response)

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
        # Do not trust arbitrary X-Forwarded-For values as identity proof.
        # This is only for log context, and the first forwarded value is used
        # when Railway's proxy is present.
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
        response["Content-Security-Policy"] = (
            "default-src 'none'; "
            "style-src 'unsafe-inline'; "
            "img-src 'self' data:; "
            "form-action 'self'; "
            "base-uri 'none'; "
            "frame-ancestors 'none'"
        )
        return response
