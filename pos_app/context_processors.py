from django.conf import settings


def tradecore_feature_flags(request):
    """Expose small, deployment-controlled feature flags to templates."""
    return {
        "communications_enabled": bool(
            getattr(settings, "TRADECORE_COMMUNICATIONS_ENABLED", False)
        ),
    }
