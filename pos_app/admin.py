from django.contrib import admin
from .models import (
    ActivityLog,
    Bidhaa,
    Duka,
    Kategoria,
    LoginHistory,
    Mauzo,
    Mteja,
    MzigoUlioingia,
    Notification,
    PurchaseRequest,
    PurchaseRequestItem,
    Profile,
    VochaYaDuka,
    Matumizi,
    SaleReturn,
    CustomerCampaign,
)


# =========================================================
# 1. PROFILE
# =========================================================
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_select_related = ("user",)
    show_full_result_count = False
    list_per_page = 50

    list_display = (
        "user",
        "jukumu_display",
        "yuko_online",
        "muda_wa_mwisho",
    )
    list_filter = (
        "ni_admin",
        "ni_cashier",
        "ni_stoo",
    )
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
    )
    autocomplete_fields = ("user",)
    readonly_fields = ("muda_wa_mwisho",)

    @admin.display(description="Jukumu")
    def jukumu_display(self, obj):
        return obj.jukumu or "Hana Jukumu"

    @admin.display(boolean=True, description="Online")
    def yuko_online(self, obj):
        return obj.yuko_online


# =========================================================
# 2. DUKA
# =========================================================
@admin.register(Duka)
class DukaAdmin(admin.ModelAdmin):
    list_select_related = ("mwenye_duka",)
    show_full_result_count = False
    list_per_page = 50

    list_display = (
        "jina_la_duka",
        "mwenye_duka",
        "anwani_au_mahali",
    )
    search_fields = (
        "jina_la_duka",
        "anwani_au_mahali",
        "mwenye_duka__username",
    )
    autocomplete_fields = ("mwenye_duka",)


# =========================================================
# 3. MTEJA
# =========================================================
@admin.register(Mteja)
class MtejaAdmin(admin.ModelAdmin):
    list_select_related = ("duka",)
    show_full_result_count = False
    list_per_page = 50

    list_display = (
        "majina_kamili",
        "namba_ya_simu",
        "whatsapp_no",
        "aina",
        "outstanding_balance",
        "tarehe_ya_kusajiliwa",
    )
    list_filter = ("aina", "tarehe_ya_kusajiliwa")
    search_fields = (
        "majina_kamili",
        "namba_ya_simu",
        "whatsapp_no",
    )
    readonly_fields = ("tarehe_ya_kusajiliwa",)
    ordering = ("majina_kamili",)


# =========================================================
# 4. KATEGORIA
# =========================================================
@admin.register(Kategoria)
class KategoriaAdmin(admin.ModelAdmin):
    show_full_result_count = False
    list_per_page = 50

    list_display = ("jina",)
    search_fields = ("jina",)
    ordering = ("jina",)


# =========================================================
# 5. BIDHAA
# =========================================================
@admin.register(Bidhaa)
class BidhaaAdmin(admin.ModelAdmin):
    list_select_related = ("kategoria", "duka")
    show_full_result_count = False
    list_per_page = 50

    list_display = (
        "jina_la_bidhaa",
        "kategoria",
        "bei_ya_kununulia",
        "bei_ya_kuuzia",
        "idadi_stoo",
        "faida_kwa_bidhaa_display",
        "tarehe_iliyoingia",
    )
    list_filter = (
        "kategoria",
        "tarehe_iliyoingia",
    )
    search_fields = (
        "jina_la_bidhaa",
        "qr_code",
        "kategoria__jina",
    )
    autocomplete_fields = ("kategoria",)
    readonly_fields = (
        "tarehe_iliyoingia",
        "faida_kwa_bidhaa_display",
        "idadi_stoo",
    )
    list_editable = (
        "bei_ya_kununulia",
        "bei_ya_kuuzia",
    )
    ordering = ("jina_la_bidhaa",)

    @admin.display(description="Faida / bidhaa")
    def faida_kwa_bidhaa_display(self, obj):
        return obj.faida_kwa_bidhaa


# =========================================================
# 6. GRN / MZIGO ULIOINGIA
# =========================================================
@admin.register(MzigoUlioingia)
class MzigoUlioingiaAdmin(admin.ModelAdmin):
    list_select_related = ("bidhaa", "duka", "location", "received_by")
    show_full_result_count = False
    list_per_page = 50

    list_display = (
        "bidhaa",
        "supplier",
        "quantity",
        "buying_price",
        "tarehe",
    )
    list_filter = ("tarehe",)
    search_fields = (
        "supplier",
        "bidhaa__jina_la_bidhaa",
    )
    autocomplete_fields = ("bidhaa",)
    readonly_fields = ("tarehe",)
    ordering = ("-tarehe",)


# =========================================================
# 7. MAUZO
# =========================================================
@admin.register(Mauzo)
class MauzoAdmin(admin.ModelAdmin):
    list_select_related = ("bidhaa", "mteja", "muuzaji", "stock_location")
    show_full_result_count = False
    list_per_page = 50

    list_display = (
        "namba_ya_invoice",
        "bidhaa",
        "mteja",
        "idadi",
        "muuzaji",
        "njia_ya_malipo",
        "jumla_pesa_iliyopokelewa",
        "tarehe_ya_mauzo",
    )
    list_filter = (
        "njia_ya_malipo",
        "aina_ya_punguzo",
        "aina_ya_ongezeko",
        "tarehe_ya_mauzo",
    )
    search_fields = (
        "namba_ya_invoice",
        "bidhaa__jina_la_bidhaa",
        "mteja__majina_kamili",
        "muuzaji__username",
    )
    autocomplete_fields = (
        "bidhaa",
        "mteja",
        "muuzaji",
    )
    readonly_fields = (
        "bei_ya_kuuzia_stoo",
        "jumla_pesa_iliyopokelewa",
        "tarehe_ya_mauzo",
    )
    ordering = ("-tarehe_ya_mauzo",)

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.muuzaji_id:
            obj.muuzaji = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        # Sales are immutable records; use the return/correction workflow instead.
        return False

    def has_module_permission(self, request):
        profile = getattr(request.user, "profile", None)
        if profile and profile.jukumu == "stoo":
            return False
        return super().has_module_permission(request)


# =========================================================
# 8. PURCHASE REQUESTS
# =========================================================
class PurchaseRequestItemInline(admin.TabularInline):
    model = PurchaseRequestItem
    extra = 0
    fields = (
        "bidhaa",
        "current_stock",
        "quantity",
        "unit_price",
        "total_display",
    )
    readonly_fields = (
        "current_stock",
        "total_display",
    )

    @admin.display(description="Jumla")
    def total_display(self, obj):
        return obj.total_amount


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_select_related = ("requested_by", "reviewed_by", "duka")
    show_full_result_count = False
    list_per_page = 50

    list_display = (
        "display_number",
        "requested_by",
        "source_department",
        "status",
        "total_display",
        "created_at",
        "reviewed_by",
        "reviewed_at",
    )
    list_filter = (
        "status",
        "source_department",
        "created_at",
    )
    search_fields = (
        "requested_by__username",
        "notes",
    )
    autocomplete_fields = (
        "requested_by",
        "reviewed_by",
    )
    readonly_fields = (
        "request_number",
        "created_at",
        "reviewed_at",
        "total_display",
    )
    inlines = (PurchaseRequestItemInline,)
    ordering = ("-created_at",)

    @admin.display(description="Request No.")
    def display_number(self, obj):
        return obj.display_number

    @admin.display(description="Total")
    def total_display(self, obj):
        return obj.total_amount


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_select_related = ("recipient", "purchase_request")
    show_full_result_count = False
    list_per_page = 50

    list_display = (
        "title",
        "recipient",
        "notification_type",
        "is_read",
        "created_at",
        "purchase_request",
    )
    list_filter = (
        "notification_type",
        "is_read",
        "created_at",
    )
    search_fields = (
        "title",
        "message",
        "recipient__username",
    )
    autocomplete_fields = (
        "recipient",
        "purchase_request",
    )
    readonly_fields = (
        "created_at",
    )
    ordering = ("-created_at",)


# =========================================================
# 11. ACTIVITY LOG
# =========================================================
@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_select_related = ("mhusika",)
    show_full_result_count = False
    list_per_page = 50

    list_display = (
        "muda",
        "mhusika",
        "aina",
        "kitendo",
    )
    list_filter = (
        "aina",
        "muda",
    )
    search_fields = (
        "kitendo",
        "mhusika__username",
    )
    autocomplete_fields = ("mhusika",)
    readonly_fields = (
        "mhusika",
        "kitendo",
        "aina",
        "muda",
    )
    ordering = ("-muda",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# =========================================================
# 12. LOGIN HISTORY
# =========================================================
@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_select_related = ("user",)
    show_full_result_count = False
    list_per_page = 50

    list_display = (
        "username_attempt",
        "user",
        "ip_address",
        "status",
        "timestamp",
        "user_agent",
    )
    list_filter = (
        "status",
        "timestamp",
    )
    search_fields = (
        "username_attempt",
        "ip_address",
        "user_agent",
        "user__username",
    )
    autocomplete_fields = ("user",)
    readonly_fields = (
        "user",
        "username_attempt",
        "ip_address",
        "user_agent",
        "status",
        "timestamp",
    )
    ordering = ("-timestamp",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# =========================================================
# 13. VOCHA YA DUKA
# =========================================================
@admin.register(VochaYaDuka)
class VochaYaDukaAdmin(admin.ModelAdmin):
    list_select_related = ("duka",)
    show_full_result_count = False
    list_per_page = 50

    list_display = (
        "jina_la_duka",
        "salio_la_sms",
    )
    search_fields = ("jina_la_duka",)
    list_editable = ("salio_la_sms",)
    
@admin.register(Matumizi)
class MatumiziAdmin(admin.ModelAdmin):
    list_select_related = ("created_by", "duka")
    show_full_result_count = False
    list_per_page = 50

    list_display = (
        "created_at",
        "category",
        "maelezo_short",
        "reference",
        "kiasi",
        "status",
        "created_by",
        "paid_at",
    )

    list_filter = (
        "category",
        "status",
        "created_at",
    )

    search_fields = (
        "category",
        "maelezo",
        "reference",
        "created_by__username",
    )

    autocomplete_fields = (
        "created_by",
    )

    readonly_fields = (
        "created_at",
        "paid_at",
    )

    ordering = (
        "-created_at",
    )

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(
        description="Maelezo"
    )
    def maelezo_short(self, obj):
        if not obj.maelezo:
            return "-"

        if len(obj.maelezo) > 60:
            return obj.maelezo[:60] + "..."

        return obj.maelezo
    
@admin.register(SaleReturn)
class SaleReturnAdmin(admin.ModelAdmin):
    list_select_related = ("sale", "requested_by", "approved_by")
    show_full_result_count = False
    list_per_page = 50

    list_display = (
        "created_at",
        "sale",
        "quantity_returned",
        "refund_amount",
        "refund_method",
        "status",
        "requested_by",
        "approved_by",
        "approved_at",
    )

    list_filter = (
        "status",
        "refund_method",
        "created_at",
    )

    search_fields = (
        "sale__namba_ya_invoice",
        "sale__bidhaa__jina_la_bidhaa",
        "reason",
        "requested_by__username",
        "approved_by__username",
    )

    autocomplete_fields = (
        "sale",
        "requested_by",
        "approved_by",
    )

    readonly_fields = (
        "refund_amount",
        "created_at",
        "approved_at",
    )

    ordering = (
        "-created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
    
@admin.register(CustomerCampaign)
class CustomerCampaignAdmin(admin.ModelAdmin):
    list_select_related = ("created_by", "duka")
    show_full_result_count = False
    list_per_page = 50

    list_display = (
        "created_at",
        "name",
        "channel",
        "recipient_count",
        "created_by",
    )

    list_filter = (
        "channel",
        "created_at",
    )

    search_fields = (
        "name",
        "message",
        "created_by__username",
    )

    readonly_fields = (
        "created_at",
    )