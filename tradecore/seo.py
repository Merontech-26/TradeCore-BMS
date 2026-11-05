"""Public TradeCore marketing and search-crawler endpoints.

Only the public product landing page is listed in the sitemap. Authenticated
application pages remain noindex and are never included here.
"""

from xml.sax.saxutils import escape

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.http import require_GET


def _site_origin():
    return getattr(settings, "TRADECORE_PUBLIC_SITE_URL", "https://merontech.co.tz").rstrip("/")


def _public_landing_url():
    return f"{_site_origin()}/tradecore/"


@require_GET
def tradecore_public_home(request):
    """Public, server-rendered page intended for visitors and search engines."""
    canonical_url = _public_landing_url()
    hero_image_url = f"{_site_origin()}{static('tradecore_market_welcome_banner.png')}"
    return render(request, "public/tradecore_landing.html", {
        "canonical_url": canonical_url,
        "site_origin": _site_origin(),
        "hero_image_url": hero_image_url,
        "google_site_verification": getattr(settings, "GOOGLE_SITE_VERIFICATION", ""),
    })


@require_GET
def robots_txt(request):
    """Allow the public product page and static assets; avoid crawler noise on APIs."""
    body = "\n".join([
        "User-agent: *",
        "Allow: /tradecore/",
        "Allow: /static/",
        "Disallow: /admin/",
        "Disallow: /api/",
        "Disallow: /notifications/",
        "Disallow: /purchase-requests/",
        "Disallow: /returns/",
        "Disallow: /billing/mobile/",
        "Disallow: /upload_profile_picture/",
        "Disallow: /delete_profile_picture/",
        "Disallow: /ujumbe/whatsapp/send/",
        f"Sitemap: {_site_origin()}/sitemap.xml",
        "",
    ])
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


@require_GET
def sitemap_xml(request):
    """A focused sitemap containing only the public, indexable TradeCore page."""
    location = escape(_public_landing_url())
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{location}</loc></url>\n"
        '</urlset>\n'
    )
    return HttpResponse(body, content_type="application/xml; charset=utf-8")
