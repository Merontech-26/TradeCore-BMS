from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse


class TrialAndSubscriptionMiddleware:
    """Gate authenticated application access without deleting expired-trial data."""

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    def __init__(self, get_response):
        self.get_response = get_response

    def _billing_url(self):
        return reverse("billing")

    def __call__(self, request):
        allowed_urls = (
            reverse("login"),
            reverse("logout"),
            reverse("register"),
            reverse("password_reset"),
            self._billing_url(),
        )

        path = request.path
        is_allowed_path = any(
            path == url or path.startswith(url)
            for url in allowed_urls
        )

        request.tradecore_read_only = False

        if (
            request.user.is_authenticated
            and not request.user.is_superuser
            and not is_allowed_path
        ):
            subscription = getattr(request.user, "subscription", None)

            if subscription is not None:
                # Expired trial remains accessible for reading existing data.
                # No data is deleted. All write requests are blocked server-side.
                if (
                    subscription.plan_type == "TRIAL"
                    and subscription.is_trial_expired
                ):
                    request.tradecore_read_only = True

                    if request.method not in self.SAFE_METHODS:
                        messages.info(
                            request,
                            "Trial yako ya siku 30 imeisha. Taarifa zako bado zipo salama. "
                            "Fungua Premium ili uanze kufanya shughuli za biashara tena.",
                        )
                        return redirect(self._billing_url())

                # Premium expiry remains a hard access gate.
                elif subscription.is_premium_expired:
                    return redirect(self._billing_url())

                elif not subscription.is_active:
                    return redirect(self._billing_url())

        return self.get_response(request)
