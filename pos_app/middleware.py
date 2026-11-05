from django.utils.timezone import now

from .tenant import reset_current_duka, set_current_duka_id


HEARTBEAT_INTERVAL_SECONDS = 60


class MtambuaOnlineMiddleware:
    """Updates activity heartbeat and establishes the request's tenant.

    The tenant is derived only from server-side User -> Duka / Profile -> Duka
    relationships. A POST/GET parameter can never choose the tenant.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # SURGERY: Tunatafuta tenant_id kwanza KABLA ya kutengeneza token.
        # Hii inazuia memory leak na data spillage kati ya Thread za server.
        tenant_id = None
        if request.user.is_authenticated:
            own_duka = getattr(request.user, "duka", None)
            profile = getattr(request.user, "profile", None)
            duka = own_duka or (getattr(profile, "duka", None) if profile else None)

            if duka is not None:
                tenant_id = duka.pk
                request.tradecore_duka = duka
                request.tradecore_duka_id = duka.pk
            else:
                tenant_id = 0 # Ulinzi: Akikosa duka anapewa 0 (isiyokuwepo) asione data za watu wengine
                request.tradecore_duka = None
                request.tradecore_duka_id = None

            if profile is not None:
                current_time = now()
                last_seen = profile.muda_wa_mwisho
                if (
                    last_seen is None
                    or (current_time - last_seen).total_seconds() >= HEARTBEAT_INTERVAL_SECONDS
                ):
                    profile.muda_wa_mwisho = current_time
                    profile.save(update_fields=["muda_wa_mwisho"])
        else:
            request.tradecore_duka = None
            request.tradecore_duka_id = None

        # Sasa tunatengeneza token MARA MOJA TU kwa usalama!
        token = set_current_duka_id(tenant_id)
        
        try:
            return self.get_response(request)
        finally:
            reset_current_duka(token)
