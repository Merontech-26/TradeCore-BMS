from decimal import Decimal
import uuid
from django.db import models, transaction
from datetime import timedelta, time as dt_time

BUSINESS_TYPE_CHOICES = (
    ("FASHION", "Fashion & Clothing"),
    ("COMPUTERS", "Computers & IT"),
    ("SUPERMARKET", "Supermarket / Grocery"),
    ("COSMETICS", "Cosmetics & Beauty"),
    ("PHARMACY", "Pharmacy / Health Shop"),
    ("HARDWARE", "Hardware & Building Materials"),
    ("RESTAURANT", "Restaurant / Café / Food"),
    ("STATIONERY", "Stationery & Bookshop"),
    ("PHONES", "Mobile Phones & Accessories"),
    ("AUTOPARTS", "Auto Parts & Motor"),
    ("FURNITURE", "Furniture & Home"),
    ("HOTEL_LODGE", "Hotel / Lodge / Guest House"),
    ("BAKERY", "Bakery & Pastry"),
    ("SALON", "Salon / Barber & Grooming"),
    ("ELECTRONICS", "Electronics & Appliances"),
    ("PHOTOGRAPHY", "Photography & Media"),
    ("PRINTING", "Printing & Design"),
    ("AGRICULTURE", "Agriculture & Farm Inputs"),
    ("CONSTRUCTION", "Construction Services"),
    ("TRANSPORT", "Transport & Travel"),
    ("LOGISTICS", "Logistics & Delivery"),
    ("CAR_WASH", "Car Wash & Detailing"),
    ("FITNESS", "Fitness & Sports"),
    ("EDUCATION", "Education & Training"),
    ("LAUNDRY", "Laundry & Dry Cleaning"),
    ("WHOLESALE", "Wholesale & Distribution"),
    ("PET_SUPPLIES", "Pet Supplies & Services"),
    ("AGENCY_SERVICES", "Professional & Agency Services"),
    ("OTHER_SERVICES", "Other Services"),
    ("GENERAL", "General Retail"),
)

TANZANIA_REGION_CHOICES = (
    ("Arusha", "Arusha"),
    ("Dar es Salaam", "Dar es Salaam"),
    ("Dodoma", "Dodoma"),
    ("Geita", "Geita"),
    ("Iringa", "Iringa"),
    ("Kagera", "Kagera"),
    ("Katavi", "Katavi"),
    ("Kigoma", "Kigoma"),
    ("Kilimanjaro", "Kilimanjaro"),
    ("Lindi", "Lindi"),
    ("Manyara", "Manyara"),
    ("Mara", "Mara"),
    ("Mbeya", "Mbeya"),
    ("Morogoro", "Morogoro"),
    ("Mtwara", "Mtwara"),
    ("Mwanza", "Mwanza"),
    ("Njombe", "Njombe"),
    ("Pwani", "Pwani"),
    ("Rukwa", "Rukwa"),
    ("Ruvuma", "Ruvuma"),
    ("Shinyanga", "Shinyanga"),
    ("Simiyu", "Simiyu"),
    ("Singida", "Singida"),
    ("Songwe", "Songwe"),
    ("Tabora", "Tabora"),
    ("Tanga", "Tanga"),
    ("Kaskazini Unguja", "Kaskazini Unguja"),
    ("Kusini Unguja", "Kusini Unguja"),
    ("Mjini Magharibi", "Mjini Magharibi"),
    ("Kaskazini Pemba", "Kaskazini Pemba"),
    ("Kusini Pemba", "Kusini Pemba"),
)

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db.models import Q, Sum
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from calendar import monthrange

from .tenant import (
    DukaTenantManager,
    ActivityTenantManager,
    ProductStockTenantManager,
    TransferItemTenantManager,
    StockTakeItemTenantManager,
    PurchaseRequestItemTenantManager,
    SaleReturnTenantManager,
    get_current_duka_id,
)


def _tenant_id_from_context():
    try:
        return get_current_duka_id()
    except Exception:
        return None


def _assert_current_tenant(duka_id, message="Record hai ya biashara nyingine."):
    tenant_id = _tenant_id_from_context()
    if tenant_id is not None and duka_id is not None and int(duka_id) != int(tenant_id):
        raise ValueError(message)


# =========================================================
# 1. PROFILE YA WAFANYAKAZI
# =========================================================
class Profile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    
    # SURGERY: Kiunganishi kinachomfunga mfanyakazi na duka la Bosi wake
    duka = models.ForeignKey(
        "Duka",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wafanyakazi"
    )

    # Legacy Roles (Still kept for basic structure)
    ni_admin = models.BooleanField(
        default=False,
        verbose_name="Bosi Mkuu (Admin)",
    )
    ni_cashier = models.BooleanField(
        default=True,
        verbose_name="Mhudumu wa Kaunta",
    )
    ni_stoo = models.BooleanField(
        default=False,
        verbose_name="Msimamizi wa Stoo",
    )

    # SURGERY: DYNAMIC PERMISSIONS (Ruhusa Maalum zinazochaguliwa kwa Checkbox)
    ruhusa_mauzo = models.BooleanField(default=False, verbose_name="Ruhusa ya Mauzo (POS)")
    ruhusa_stoo = models.BooleanField(default=False, verbose_name="Ruhusa ya Stoo na Bidhaa")
    ruhusa_wateja = models.BooleanField(default=False, verbose_name="Ruhusa ya Wateja")
    ruhusa_matumizi = models.BooleanField(default=False, verbose_name="Ruhusa ya Matumizi")
    ruhusa_ripoti = models.BooleanField(default=False, verbose_name="Ruhusa ya Ripoti")
    ruhusa_mawasiliano = models.BooleanField(default=False, verbose_name="Ruhusa ya Mawasiliano")

    picha = models.ImageField(
        upload_to="wafanyakazi/",
        null=True,
        blank=True,
    )
    muda_wa_mwisho = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Profile"
        verbose_name_plural = "Profiles"

    def __str__(self):
        if self.ni_admin:
            return f"{self.user.username} - [Bosi Mkuu / Admin]"
        
        # Orodha ya ruhusa zinazofanya kazi (Kama si admin)
        active_perms = []
        if self.ruhusa_mauzo: active_perms.append("Mauzo")
        if self.ruhusa_stoo: active_perms.append("Stoo")
        if self.ruhusa_wateja: active_perms.append("Wateja")
        if self.ruhusa_matumizi: active_perms.append("Matumizi")
        if self.ruhusa_ripoti: active_perms.append("Ripoti")
        if self.ruhusa_mawasiliano: active_perms.append("Mawasiliano")
        
        vyeo = ", ".join(active_perms) if active_perms else "Hana Ruhusa Maalum"
        return f"{self.user.username} - [{vyeo}]"

    @property
    def jukumu(self):
        """
        Backward-compatible role property.
        """
        if self.ni_admin:
            return "admin"
        if self.ruhusa_mauzo:
            return "cashier"
        if self.ruhusa_stoo:
            return "stoo"

        # Legacy fallback if checkboxes are not used
        if self.ni_stoo:
            return "stoo"
        if self.ni_cashier:
            return "cashier"
        return None

    @property
    def yuko_online(self):
        if not self.muda_wa_mwisho:
            return False

        tofauti = timezone.now() - self.muda_wa_mwisho
        return tofauti.total_seconds() < 300


@receiver(post_save, sender=User)
def tengeneza_profile_ya_mtumiaji(sender, instance, created, **kwargs):
    if created:
        defaults = {
            "ni_admin": bool(instance.is_superuser),
            "ni_cashier": not instance.is_superuser,
            "ni_stoo": False,
        }
        Profile.objects.get_or_create(user=instance, defaults=defaults)
    else:
        Profile.objects.get_or_create(user=instance)

    # Keep one User post_save hook for both related records. This preserves the
    # existing behavior while avoiding duplicate receivers/queries on every User save.
    BusinessSubscription.objects.get_or_create(user=instance)
        



# =========================================================
# 2. VOCHA YA DUKA
# =========================================================
class VochaYaDuka(models.Model):
    objects = DukaTenantManager()
    all_objects = models.Manager()
    
    # SURGERY: Tumeongeza kiunganishi cha duka ili TenantManager isichanganyikiwe
    duka = models.ForeignKey(
        "Duka",
        on_delete=models.CASCADE,
        related_name="vocha",
        null=True,
        blank=True,
    )
    
    jina_la_duka = models.CharField(
        max_length=100,
        default="TradeCore Main Store",
    )
    salio_la_sms = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Vocha ya Duka"
        verbose_name_plural = "Vocha za Duka"

    def save(self, *args, **kwargs):
        tenant_id = _tenant_id_from_context()
        if self.duka_id is None and tenant_id is not None:
            self.duka_id = tenant_id
        _assert_current_tenant(self.duka_id, "Vocha hii ni ya biashara nyingine.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.jina_la_duka} - Salio SMS: {self.salio_la_sms}"


# =========================================================
# 3. MTEJA
# =========================================================
class Mteja(models.Model):
    objects = DukaTenantManager()
    all_objects = models.Manager()
    duka = models.ForeignKey(
        "Duka",
        on_delete=models.CASCADE,
        related_name="wateja",
        db_index=True,
    )

    # SURGERY: Tumeongeza db_index=True ili kuharakisha Search ya wateja
    majina_kamili = models.CharField(max_length=200, db_index=True)

    namba_ya_simu = models.CharField(
        max_length=15, db_index=True
    )

    whatsapp_no = models.CharField(
        max_length=15,
        blank=True,
        null=True,
    )

    tarehe_ya_kusajiliwa = models.DateTimeField(
        auto_now_add=True,
    )

    aina = models.CharField(
        max_length=50,
        default="binafsi",
    )

    pre_order_deposit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(
                Decimal("0.00")
            )
        ],
    )

    outstanding_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(
                Decimal("0.00")
            )
        ],
    )

    email = models.EmailField(
        blank=True,
        null=True,
    )

    anwani = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    eneo = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    marketing_opt_in = models.BooleanField(
        default=True,
    )

    class Meta:
        verbose_name = "Mteja"
        verbose_name_plural = "Wateja"
        ordering = ["majina_kamili"]

    def save(self, *args, **kwargs):
        _assert_current_tenant(self.duka_id, "Mteja huyu ni wa biashara nyingine.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.majina_kamili
    
class BusinessSubscription(models.Model):
    PLAN_CHOICES = (
        ("TRIAL", "30-Day Demo"),
        ("PREMIUM", "Premium Plan"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="subscription")
    is_active = models.BooleanField(default=True)
    trial_start_date = models.DateTimeField(default=timezone.now)
    plan_type = models.CharField(max_length=20, default="TRIAL", choices=PLAN_CHOICES)
    premium_start_date = models.DateTimeField(null=True, blank=True)
    premium_end_date = models.DateTimeField(null=True, blank=True)
    last_payment_at = models.DateTimeField(null=True, blank=True)

    @property
    def trial_end_date(self):
        return self.trial_start_date + timedelta(days=30)

    @property
    def trial_days_left(self):
        delta = self.trial_end_date - timezone.now()
        return max(delta.days, 0)

    @property
    def premium_days_left(self):
        if self.plan_type != "PREMIUM" or not self.premium_end_date:
            return 0
        delta = self.premium_end_date - timezone.now()
        return max(delta.days, 0)

    @property
    def days_left(self):
        if self.plan_type == "PREMIUM":
            return self.premium_days_left
        return self.trial_days_left

    @property
    def is_trial_expired(self):
        return self.plan_type == "TRIAL" and timezone.now() >= self.trial_end_date

    @property
    def is_premium_expired(self):
        return self.plan_type == "PREMIUM" and (
            not self.premium_end_date or timezone.now() >= self.premium_end_date
        )

    @property
    def access_expired(self):
        return (
            not self.is_active
            or self.is_trial_expired
            or self.is_premium_expired
        )

    def activate_premium(self, payment_time=None, months=1):
        """Activate or extend Premium for the purchased number of calendar months."""
        now = payment_time or timezone.now()
        try:
            months = int(months)
        except (TypeError, ValueError):
            raise ValueError("Idadi ya miezi lazima iwe zaidi ya sifuri.")
        if months <= 0:
            raise ValueError("Idadi ya miezi lazima iwe zaidi ya sifuri.")

        base = (
            self.premium_end_date
            if self.plan_type == "PREMIUM"
            and self.premium_end_date
            and self.premium_end_date > now
            else now
        )
        self.plan_type = "PREMIUM"
        self.is_active = True
        self.premium_start_date = now
        month_index = (base.month - 1) + months
        target_year = base.year + (month_index // 12)
        target_month = (month_index % 12) + 1
        target_day = min(base.day, monthrange(target_year, target_month)[1])
        self.premium_end_date = base.replace(
            year=target_year,
            month=target_month,
            day=target_day,
        )
        self.last_payment_at = now

    def __str__(self):
        return f"{self.user.username} - {self.plan_type}"


class PaymentTransaction(models.Model):
    STATUS_CHOICES = (
        ("INITIATED", "Initiated"),
        ("PENDING", "Pending"),
        ("SUCCESSFUL", "Successful"),
        ("FAILED", "Failed"),
        ("CANCELLED", "Cancelled"),
        ("PENDING_BANK", "Pending Bank Verification"),
    )
    METHOD_CHOICES = (
        ("MOBILE_MONEY", "Mobile Money"),
        ("BANK_TRANSFER", "Bank Transfer"),
    )
    NETWORK_CHOICES = (
        ("AIRTEL", "Airtel Money"),
        ("TIGO", "Tigo / Mixx by Yas"),
        ("HALOPESA", "HaloPesa"),
        ("VODAFONE", "Vodacom M-Pesa"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="payment_transactions",
    )
    subscription = models.ForeignKey(
        BusinessSubscription,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    tx_ref = models.CharField(max_length=100, unique=True, db_index=True)
    gateway_transaction_id = models.CharField(max_length=100, blank=True, default="", db_index=True)
    gateway_reference = models.CharField(max_length=150, blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="TZS")
    method = models.CharField(max_length=30, choices=METHOD_CHOICES)
    network = models.CharField(max_length=30, choices=NETWORK_CHOICES, blank=True, default="")
    phone_number = models.CharField(max_length=20, blank=True, default="")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="INITIATED", db_index=True)
    gateway_status = models.CharField(max_length=50, blank=True, default="")
    failure_reason = models.CharField(max_length=255, blank=True, default="")
    gateway_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "created_at"]),
            models.Index(fields=["gateway_transaction_id"]),
        ]

    def __str__(self):
        return f"{self.tx_ref} - {self.user.username} - {self.status}"


# =========================================================
# 4. KATEGORIA NA BIDHAA
# =========================================================
class Kategoria(models.Model):
    jina = models.CharField(max_length=100)
    business_type = models.CharField(
        max_length=30,
        choices=BUSINESS_TYPE_CHOICES,
        default="GENERAL",
        db_index=True,
        verbose_name="Aina ya Biashara",
    )

    is_custom = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Kategoria"
        verbose_name_plural = "Makategoria"
        ordering = ["jina"]
        constraints = [
            models.UniqueConstraint(
                fields=["business_type", "jina"],
                name="uniq_tradecore_category_type_name",
            )
        ]

    def __str__(self):
        return self.jina


class Bidhaa(models.Model):
    objects = DukaTenantManager()
    all_objects = models.Manager()

    duka = models.ForeignKey(
        "Duka",
        on_delete=models.CASCADE,
        related_name="bidhaa",
        db_index=True,
    )
    kategoria = models.ForeignKey(
        Kategoria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bidhaa",
    )
    picha = models.ImageField(
        upload_to="bidhaa/",
        null=True,
        blank=True,
    )
    # SURGERY: Tumeongeza db_index=True kuharakisha Search ya bidhaa kwenye POS
    jina_la_bidhaa = models.CharField(max_length=200, db_index=True)
    qr_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=False,
    )
    bei_ya_kununulia = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    bei_ya_kuuzia = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    idadi_stoo = models.PositiveIntegerField(default=0)
    maelekezo_maalum = models.TextField(
        blank=True,
        null=True,
    )
    tarehe_iliyoingia = models.DateTimeField(auto_now_add=True)
    
    barcode = models.CharField(max_length=255, blank=True, null=True, unique=False, verbose_name="Barcode ya Bidhaa")

    class Meta:
        verbose_name = "Bidhaa"
        verbose_name_plural = "Bidhaa"
        ordering = ["jina_la_bidhaa"]
        constraints = [
            models.UniqueConstraint(
                fields=["duka", "qr_code"],
                condition=Q(qr_code__isnull=False) & ~Q(qr_code=""),
                name="uniq_bidhaa_duka_qr_code",
            ),
            models.UniqueConstraint(
                fields=["duka", "barcode"],
                condition=Q(barcode__isnull=False) & ~Q(barcode=""),
                name="uniq_bidhaa_duka_barcode",
            ),
        ]

    def save(self, *args, **kwargs):
        _assert_current_tenant(self.duka_id, "Bidhaa hii ni ya biashara nyingine.")
        return super().save(*args, **kwargs)

    @property
    def faida_kwa_bidhaa(self):
        return self.bei_ya_kuuzia - self.bei_ya_kununulia

    def __str__(self):
        # Location-aware inventory uses ProductStock as the stock source of truth;
        # idadi_stoo can be a legacy aggregate and should not be shown as live stock.
        return self.jina_la_bidhaa


# =========================================================
# 5. MZIGO ULIOINGIA (GRN)
# =========================================================
class MzigoUlioingia(models.Model):
    objects = DukaTenantManager()
    all_objects = models.Manager()
    bidhaa = models.ForeignKey(
        Bidhaa,
        on_delete=models.CASCADE,
        related_name="mizigo_iliyoingia",
    )
    supplier = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    duka = models.ForeignKey(
        "Duka",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mizigo_iliyoingia",
    )
    location = models.ForeignKey(
        "StockLocation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mizigo",
    )
    received_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mizigo_iliyopokelewa",
    )
    reference = models.CharField(max_length=100, blank=True, default="")
    notes = models.TextField(blank=True, null=True)
    buying_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    tarehe = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mzigo Uliingia (GRN)"
        verbose_name_plural = "Mizigo Iliyoingia (GRN)"
        ordering = ["-tarehe"]

    def save(self, *args, **kwargs):
        if not self.bidhaa_id:
            raise ValueError("Bidhaa lazima ichaguliwe kwenye mzigo unaoingia.")
        if int(self.quantity or 0) <= 0:
            raise ValueError("Quantity ya mzigo lazima iwe zaidi ya sifuri.")

        bidhaa = Bidhaa.all_objects.only("duka_id").get(pk=self.bidhaa_id)
        if self.duka_id is None:
            self.duka_id = bidhaa.duka_id
        if self.duka_id != bidhaa.duka_id:
            raise ValueError("Mzigo na bidhaa lazima viwe vya biashara moja.")
        _assert_current_tenant(self.duka_id, "Mzigo huu ni wa biashara nyingine.")

        if self.location_id:
            location = StockLocation.all_objects.only("duka_id").get(pk=self.location_id)
            if location.duka_id != self.duka_id:
                raise ValueError("Stock location si ya biashara ya mzigo huu.")

        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.bidhaa.jina_la_bidhaa} ({self.quantity})"


# =========================================================
# 6. DUKA
# =========================================================
class Duka(models.Model):
    mwenye_duka = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="duka",
    )

    jina_la_duka = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    anwani_au_mahali = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    simu = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )

    tin = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    email = models.EmailField(
        blank=True,
        null=True,
    )

    logo = models.ImageField(
        upload_to="maduka/logos/",
        blank=True,
        null=True,
    )

    tagline = models.CharField(
        max_length=200,
        blank=True,
        null=True,
    )

    receipt_footer = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        default="Asante kwa kufanya manunuzi nasi!",
    )

    terminal_name = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    currency = models.CharField(
        max_length=10,
        default="TZS",
    )

    # Additive inventory switch: legacy aggregate stock remains supported.
    inventory_location_mode = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Tumia stock kwa Locations",
    )

    business_type = models.CharField(
        max_length=30,
        choices=BUSINESS_TYPE_CHOICES,
        default="GENERAL",
        db_index=True,
        verbose_name="Aina ya Biashara",
    )

    class Meta:
        verbose_name = "Duka"
        verbose_name_plural = "Maduka"

    def __str__(self):
        return (
            f"{self.jina_la_duka or 'TradeCore'} "
            f"- ({self.mwenye_duka.username})"
        )


# =========================================================
# 7. INVENTORY LOCATIONS + STOCK LEDGER
# =========================================================
class StockLocation(models.Model):
    objects = DukaTenantManager()
    all_objects = models.Manager()
    KIND_CHOICES = (
        ("STORE", "Store / Chumba cha Stoo"),
        ("SHOP", "Duka / POS"),
        ("WAREHOUSE", "Warehouse"),
        ("OTHER", "Other"),
    )

    duka = models.ForeignKey(
        Duka,
        on_delete=models.CASCADE,
        related_name="stock_locations",
    )
    jina = models.CharField(max_length=120)
    code = models.SlugField(max_length=80)
    aina = models.CharField(max_length=20, choices=KIND_CHOICES, default="OTHER")
    is_sales_location = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Stock Location"
        verbose_name_plural = "Stock Locations"
        constraints = [
            models.UniqueConstraint(fields=["duka", "code"], name="uniq_stock_location_duka_code"),
        ]
        ordering = ["jina"]

    def __str__(self):
        return f"{self.duka.jina_la_duka or 'TradeCore'} — {self.jina}"


class ProductStock(models.Model):
    objects = ProductStockTenantManager()
    all_objects = models.Manager()
    bidhaa = models.ForeignKey(
        Bidhaa,
        on_delete=models.CASCADE,
        related_name="location_stocks",
    )
    location = models.ForeignKey(
        StockLocation,
        on_delete=models.CASCADE,
        related_name="product_stocks",
    )
    quantity = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product Stock"
        verbose_name_plural = "Product Stocks"
        constraints = [
            models.UniqueConstraint(fields=["bidhaa", "location"], name="uniq_product_stock_location"),
        ]
        ordering = ["bidhaa__jina_la_bidhaa"]

    def save(self, *args, **kwargs):
        bidhaa = self._state.fields_cache.get("bidhaa")
        if bidhaa is None:
            bidhaa = Bidhaa.all_objects.only("duka_id").get(pk=self.bidhaa_id)
        location = self._state.fields_cache.get("location")
        if location is None:
            location = StockLocation.all_objects.only("duka_id").get(pk=self.location_id)
        if bidhaa.duka_id != location.duka_id:
            raise ValueError("Bidhaa na stock location lazima viwe vya biashara moja.")
        _assert_current_tenant(location.duka_id, "Stock hii ni ya biashara nyingine.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.bidhaa.jina_la_bidhaa} @ {self.location.jina}: {self.quantity}"


class StockTransfer(models.Model):
    objects = DukaTenantManager()
    all_objects = models.Manager()
    REASON_CHOICES = (
        ("REPLENISHMENT", "Replenishment / Kupeleka Duka"),
        ("RETURN_TO_STORE", "Return to Store"),
        ("DAMAGED", "Damaged Product"),
        ("EXPIRED", "Expired Product"),
        ("CUSTOMER_RETURN", "Customer Return"),
        ("REDISTRIBUTION", "Redistribution"),
        ("OTHER", "Other"),
    )

    duka = models.ForeignKey(Duka, on_delete=models.CASCADE, related_name="stock_transfers")
    source_location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="transfers_out")
    destination_location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="transfers_in")
    reference = models.CharField(max_length=40, unique=True)
    reason_code = models.CharField(max_length=30, choices=REASON_CHOICES, default="OTHER")
    reason_text = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, null=True)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="stock_transfers_performed")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="stock_transfers_received")

    class Meta:
        verbose_name = "Stock Transfer"
        verbose_name_plural = "Stock Transfers"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.source_location_id and self.destination_location_id:
            source = self._state.fields_cache.get("source_location")
            if source is None:
                source = StockLocation.all_objects.only("duka_id").get(pk=self.source_location_id)
            destination = self._state.fields_cache.get("destination_location")
            if destination is None:
                destination = StockLocation.all_objects.only("duka_id").get(pk=self.destination_location_id)
            if source.duka_id != self.duka_id or destination.duka_id != self.duka_id:
                raise ValueError("Transfer na locations lazima viwe vya biashara moja.")
        _assert_current_tenant(self.duka_id, "Transfer hii ni ya biashara nyingine.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference}: {self.source_location.jina} → {self.destination_location.jina}"


class StockTransferItem(models.Model):
    objects = TransferItemTenantManager()
    all_objects = models.Manager()
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name="items")
    bidhaa = models.ForeignKey(Bidhaa, on_delete=models.PROTECT, related_name="stock_transfer_items")
    quantity = models.PositiveIntegerField()
    source_before = models.PositiveIntegerField(default=0)
    source_after = models.PositiveIntegerField(default=0)
    destination_before = models.PositiveIntegerField(default=0)
    destination_after = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Stock Transfer Item"
        verbose_name_plural = "Stock Transfer Items"
        constraints = [
            models.UniqueConstraint(fields=["transfer", "bidhaa"], name="uniq_transfer_product"),
        ]

    def save(self, *args, **kwargs):
        if int(self.quantity or 0) <= 0:
            raise ValueError("Quantity ya transfer lazima iwe zaidi ya sifuri.")
        transfer = self._state.fields_cache.get("transfer")
        if transfer is None:
            transfer = StockTransfer.all_objects.only("duka_id").get(pk=self.transfer_id)
        bidhaa = self._state.fields_cache.get("bidhaa")
        if bidhaa is None:
            bidhaa = Bidhaa.all_objects.only("duka_id").get(pk=self.bidhaa_id)
        if bidhaa.duka_id != transfer.duka_id:
            raise ValueError("Bidhaa na transfer lazima viwe vya biashara moja.")
        _assert_current_tenant(transfer.duka_id, "Transfer item hii ni ya biashara nyingine.")
        return super().save(*args, **kwargs)


class StockTake(models.Model):
    objects = DukaTenantManager()
    all_objects = models.Manager()
    STATUS_CHOICES = (
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    )

    duka = models.ForeignKey(Duka, on_delete=models.CASCADE, related_name="stock_takes")
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="stock_takes")
    reference = models.CharField(max_length=40, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="COMPLETED")
    notes = models.TextField(blank=True, null=True)
    started_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="stock_takes_started")
    completed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="stock_takes_completed")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Stock Take"
        verbose_name_plural = "Stock Takes"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        location = self._state.fields_cache.get("location")
        if location is None:
            location = StockLocation.all_objects.only("duka_id").get(pk=self.location_id)
        if location.duka_id != self.duka_id:
            raise ValueError("Stock take na location lazima viwe vya biashara moja.")
        _assert_current_tenant(self.duka_id, "Stock take hii ni ya biashara nyingine.")
        return super().save(*args, **kwargs)


class StockTakeItem(models.Model):
    objects = StockTakeItemTenantManager()
    all_objects = models.Manager()
    stock_take = models.ForeignKey(StockTake, on_delete=models.CASCADE, related_name="items")
    bidhaa = models.ForeignKey(Bidhaa, on_delete=models.PROTECT, related_name="stock_take_items")
    system_quantity = models.PositiveIntegerField(default=0)
    physical_quantity = models.PositiveIntegerField(default=0)
    variance = models.IntegerField(default=0)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Stock Take Item"
        verbose_name_plural = "Stock Take Items"
        constraints = [
            models.UniqueConstraint(fields=["stock_take", "bidhaa"], name="uniq_stock_take_product"),
        ]

    def save(self, *args, **kwargs):
        stock_take = self._state.fields_cache.get("stock_take")
        if stock_take is None:
            stock_take = StockTake.all_objects.only("duka_id").get(pk=self.stock_take_id)
        bidhaa = self._state.fields_cache.get("bidhaa")
        if bidhaa is None:
            bidhaa = Bidhaa.all_objects.only("duka_id").get(pk=self.bidhaa_id)
        if bidhaa.duka_id != stock_take.duka_id:
            raise ValueError("Bidhaa na stock take lazima viwe vya biashara moja.")
        _assert_current_tenant(stock_take.duka_id, "Stock take item hii ni ya biashara nyingine.")
        return super().save(*args, **kwargs)


class StockMovement(models.Model):
    objects = DukaTenantManager()
    all_objects = models.Manager()
    TYPE_CHOICES = (
        ("OPENING", "Opening Stock"),
        ("STOCK_IN", "Stock In"),
        ("SALE", "Sale"),
        ("TRANSFER", "Transfer"),
        ("RETURN", "Return"),
        ("ADJUSTMENT", "Adjustment"),
        ("DAMAGE", "Damage"),
        ("STOCK_TAKE", "Stock Take"),
    )

    duka = models.ForeignKey(Duka, on_delete=models.CASCADE, related_name="stock_movements")
    bidhaa = models.ForeignKey(Bidhaa, on_delete=models.PROTECT, related_name="stock_movements")
    movement_type = models.CharField(max_length=20, choices=TYPE_CHOICES, db_index=True)
    quantity = models.PositiveIntegerField(default=0)
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, null=True, blank=True, related_name="movements")
    from_location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, null=True, blank=True, related_name="movement_from")
    to_location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, null=True, blank=True, related_name="movement_to")
    balance_before = models.PositiveIntegerField(null=True, blank=True)
    balance_after = models.PositiveIntegerField(null=True, blank=True)
    from_balance_before = models.PositiveIntegerField(null=True, blank=True)
    from_balance_after = models.PositiveIntegerField(null=True, blank=True)
    to_balance_before = models.PositiveIntegerField(null=True, blank=True)
    to_balance_after = models.PositiveIntegerField(null=True, blank=True)
    reference = models.CharField(max_length=80, db_index=True)
    reason = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, null=True)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="stock_movements_performed")
    sale = models.ForeignKey("Mauzo", on_delete=models.SET_NULL, null=True, blank=True, related_name="stock_movements")
    transfer = models.ForeignKey(StockTransfer, on_delete=models.SET_NULL, null=True, blank=True, related_name="movements")
    stock_take = models.ForeignKey(StockTake, on_delete=models.SET_NULL, null=True, blank=True, related_name="movements")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Stock Movement"
        verbose_name_plural = "Stock Movements"
        indexes = [
            models.Index(fields=["duka", "bidhaa", "created_at"]),
            models.Index(fields=["duka", "movement_type", "created_at"]),
        ]
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if int(self.quantity or 0) <= 0:
            raise ValueError("Quantity ya stock movement lazima iwe zaidi ya sifuri.")

        bidhaa = self._state.fields_cache.get("bidhaa")
        if bidhaa is None:
            bidhaa = Bidhaa.all_objects.only("duka_id").get(pk=self.bidhaa_id)
        if bidhaa.duka_id != self.duka_id:
            raise ValueError("Stock movement na bidhaa lazima viwe vya biashara moja.")

        location_fields = {
            "location": self.location_id,
            "from_location": self.from_location_id,
            "to_location": self.to_location_id,
        }
        for field_name, location_id in location_fields.items():
            if not location_id:
                continue
            location = self._state.fields_cache.get(field_name)
            if location is None:
                location = StockLocation.all_objects.only("duka_id").get(pk=location_id)
            if location.duka_id != self.duka_id:
                raise ValueError("Stock movement location si ya biashara hii.")

        related_models = {
            "sale": Mauzo,
            "transfer": StockTransfer,
            "stock_take": StockTake,
        }
        for relation_name, model in related_models.items():
            relation_id = getattr(self, f"{relation_name}_id")
            if not relation_id:
                continue
            relation = self._state.fields_cache.get(relation_name)
            if relation is None:
                relation = model.all_objects.only("duka_id").get(pk=relation_id)
            if relation.duka_id != self.duka_id:
                raise ValueError(
                    f"Stock movement {relation_name.replace('_', ' ')} si ya biashara hii."
                )

        _assert_current_tenant(self.duka_id, "Stock movement hii ni ya biashara nyingine.")
        return super().save(*args, **kwargs)


# =========================================================
# 8. MAUZO
# =========================================================
class Mauzo(models.Model):
    objects = DukaTenantManager()
    all_objects = models.Manager()
    PAYMENT_CHOICES = (
        ("CASH", "Cash (Pesa Mkononi)"),
        ("MPESA", "M-Pesa"),
        ("TIGOPESA", "Tigo Pesa"),
        ("AIRTELMONEY", "Airtel Money"),
        ("BANK", "Bank Transfer / Kadi"),
    )

    DISCOUNT_MARKUP_CHOICES = (
        ("TZS", "TZS (Pesa)"),
        ("PERCENT", "Asilimia (%)"),
    )

    bidhaa = models.ForeignKey(
        Bidhaa,
        on_delete=models.PROTECT,
        related_name="mauzo",
    )
    mteja = models.ForeignKey(
        Mteja,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mauzo",
    )
    muuzaji = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mauzo_aliyofanya",
    )
    duka = models.ForeignKey(
        Duka,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mauzo",
    )
    stock_location = models.ForeignKey(
        StockLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mauzo",
    )
    idadi = models.PositiveIntegerField(default=1)
    bei_ya_kuuzia_stoo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )
    bei_ya_kununulia_stoo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )
    tarehe_ya_mauzo = models.DateTimeField(auto_now_add=True)

    namba_ya_invoice = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )
    njia_ya_malipo = models.CharField(
        max_length=20,
        choices=PAYMENT_CHOICES,
        default="CASH",
    )

    aina_ya_punguzo = models.CharField(
        max_length=10,
        choices=DISCOUNT_MARKUP_CHOICES,
        default="TZS",
    )
    punguzo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    aina_ya_ongezeko = models.CharField(
        max_length=10,
        choices=DISCOUNT_MARKUP_CHOICES,
        default="TZS",
    )
    ongezeko = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    jumla_pesa_iliyopokelewa = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    class Meta:
        verbose_name = "Mauzo"
        verbose_name_plural = "Mauzo"
        ordering = ["-tarehe_ya_mauzo"]

    def _calculate_discount(self, subtotal):
        amount = self.punguzo or Decimal("0.00")
        if self.aina_ya_punguzo == "PERCENT":
            return subtotal * (amount / Decimal("100"))
        return amount

    def _calculate_markup(self, subtotal_after_discount):
        amount = self.ongezeko or Decimal("0.00")
        if self.aina_ya_ongezeko == "PERCENT":
            return subtotal_after_discount * (amount / Decimal("100"))
        return amount

    @property
    def subtotal(self):
        price = self.bei_ya_kuuzia_stoo or Decimal("0.00")
        return price * self.idadi

    @property
    def total_before_save(self):
        subtotal = self.subtotal
        discount = self._calculate_discount(subtotal)
        after_discount = subtotal - discount
        markup = self._calculate_markup(after_discount)
        return max(after_discount + markup, Decimal("0.00"))

    def save(self, *args, **kwargs):
        if not self.bidhaa_id:
            raise ValueError("Bidhaa lazima ichaguliwe kwenye mauzo.")

        # Derive the tenant from the product for legacy callers that did not
        # pass duka explicitly, while still refusing cross-tenant writes.
        bidhaa_ref = Bidhaa.all_objects.only("duka_id").get(pk=self.bidhaa_id)
        if self.duka_id is None:
            self.duka_id = bidhaa_ref.duka_id
        if self.duka_id != bidhaa_ref.duka_id:
            raise ValueError("Mauzo na bidhaa lazima viwe vya biashara moja.")
        _assert_current_tenant(self.duka_id, "Mauzo haya ni ya biashara nyingine.")

        if self.mteja_id:
            mteja = Mteja.all_objects.only("duka_id").get(pk=self.mteja_id)
            if mteja.duka_id != self.duka_id:
                raise ValueError("Mteja si wa biashara ya mauzo haya.")

        if self.stock_location_id:
            location = self._state.fields_cache.get("stock_location")
            if location is None:
                location = StockLocation.all_objects.only(
                    "duka_id", "is_active", "is_sales_location"
                ).get(pk=self.stock_location_id)
            if location.duka_id != self.duka_id:
                raise ValueError("Stock location si ya biashara ya mauzo haya.")
            if not location.is_active:
                raise ValueError("Stock location ya mauzo imezimwa.")
            if not location.is_sales_location:
                raise ValueError("Mauzo lazima yatoke kwenye selling location ya biashara.")

        is_new = self.pk is None

        if not is_new:
            super().save(*args, **kwargs)
            return

        if self.idadi <= 0:
            raise ValueError("Idadi ya bidhaa lazima iwe zaidi ya sifuri.")

        with transaction.atomic():
            bidhaa = (
                Bidhaa.objects
                .select_for_update()
                .get(pk=self.bidhaa_id)
            )

            if self.duka_id and bidhaa.duka_id != self.duka_id:
                raise ValueError("Bidhaa hii si ya biashara iliyochaguliwa.")
            if self.duka_id and self.stock_location_id and self.stock_location.duka_id != self.duka_id:
                raise ValueError("Stock location si ya biashara hii.")

            # SURGERY FIX: Kamata Cost na Selling price za wakati huu kuzilinda zisibadilike
            self.bei_ya_kuuzia_stoo = bidhaa.bei_ya_kuuzia
            self.bei_ya_kununulia_stoo = bidhaa.bei_ya_kununulia 
            self.jumla_pesa_iliyopokelewa = self.total_before_save

            if self.stock_location_id:
                from .inventory_services import deduct_stock
                movement = deduct_stock(
                    duka=self.duka,
                    bidhaa=bidhaa,
                    location=self.stock_location,
                    quantity=self.idadi,
                    actor=self.muuzaji,
                    reference=self.namba_ya_invoice or f"SALE-{uuid.uuid4().hex[:10].upper()}",
                    reason="Mauzo ya POS",
                )
                super().save(*args, **kwargs)
                movement.sale = self
                movement.save(update_fields=["sale"])
            else:
                # Legacy compatibility: old callers without a location still
                # use the original aggregate stock field.
                if bidhaa.idadi_stoo < self.idadi:
                    raise ValueError(
                        f"Samahani, bidhaa '{bidhaa.jina_la_bidhaa}' "
                        f"imebaki stoo idadi {bidhaa.idadi_stoo} tu!"
                    )
                bidhaa.idadi_stoo -= self.idadi
                bidhaa.save(update_fields=["idadi_stoo"])
                super().save(*args, **kwargs)

    def __str__(self):
        return f"Mauzo: {self.bidhaa.jina_la_bidhaa} x {self.idadi}"


# =========================================================
# 8. PURCHASE REQUEST / REORDER
# =========================================================
class PurchaseRequest(models.Model):
    objects = DukaTenantManager()
    all_objects = models.Manager()

    duka = models.ForeignKey(
        "Duka",
        on_delete=models.CASCADE,
        related_name="purchase_requests",
        db_index=True,
    )
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("CANCELLED", "Cancelled"),
    )

    request_number = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_requests_created",
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_requests_reviewed",
    )
    source_department = models.CharField(
        max_length=100,
        default="Stoo",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        db_index=True,
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Purchase Request"
        verbose_name_plural = "Purchase Requests"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        _assert_current_tenant(self.duka_id, "Purchase request hii ni ya biashara nyingine.")
        return super().save(*args, **kwargs)

    @property
    def display_number(self):
        return f"REQ-{str(self.request_number).split('-')[0].upper()}"

    @property
    def total_amount(self):
        return sum(
            (item.total_amount for item in self.items.all()),
            Decimal("0.00"),
        )

    def __str__(self):
        return self.display_number


class PurchaseRequestItem(models.Model):
    objects = PurchaseRequestItemTenantManager()
    all_objects = models.Manager()
    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.CASCADE,
        related_name="items",
    )
    bidhaa = models.ForeignKey(
        Bidhaa,
        on_delete=models.PROTECT,
        related_name="purchase_request_items",
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    current_stock = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Purchase Request Item"
        verbose_name_plural = "Purchase Request Items"

    def save(self, *args, **kwargs):
        if int(self.quantity or 0) <= 0:
            raise ValueError("Quantity ya purchase request lazima iwe zaidi ya sifuri.")
        purchase_request = PurchaseRequest.all_objects.only("duka_id").get(pk=self.purchase_request_id)
        bidhaa = Bidhaa.all_objects.only("duka_id").get(pk=self.bidhaa_id)
        if bidhaa.duka_id != purchase_request.duka_id:
            raise ValueError("Bidhaa na purchase request lazima viwe vya biashara moja.")
        _assert_current_tenant(purchase_request.duka_id, "Purchase request item hii ni ya biashara nyingine.")
        return super().save(*args, **kwargs)

    @property
    def total_amount(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.purchase_request.display_number} - {self.bidhaa.jina_la_bidhaa}"


# =========================================================
# 9. NOTIFICATIONS
# =========================================================
class Notification(models.Model):
    objects = models.Manager()
    all_objects = models.Manager()
    TYPE_CHOICES = (
        ("PURCHASE_REQUEST", "Purchase Request"),
        ("LOW_STOCK", "Low Stock"),
        ("SALE", "Sale"),
        ("STOCK", "Stock"),
        ("SYSTEM", "System"),
    )

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=150)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES,
        default="SYSTEM",
        db_index=True,
    )
    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    link_url = models.CharField(
        max_length=500,
        blank=True,
        null=True,
    )
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]

    def __str__(self):
        state = "Read" if self.is_read else "Unread"
        return f"{self.recipient.username} - {self.title} ({state})"


# =========================================================
# 8. ACTIVITY LOG
# =========================================================
class ActivityLog(models.Model):
    objects = ActivityTenantManager()
    all_objects = models.Manager()

    duka = models.ForeignKey(
        "Duka",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duka_activity_logs",
        db_index=True,
    )
    mhusika = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    kitendo = models.CharField(max_length=255)
    aina = models.CharField(max_length=50, default="kawaida")
    muda = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Activity Log"
        verbose_name_plural = "Activity Logs"
        ordering = ["-muda"]

    def save(self, *args, **kwargs):
        tenant_id = _tenant_id_from_context()
        if self.duka_id is None and tenant_id is not None:
            self.duka_id = tenant_id
        _assert_current_tenant(self.duka_id, "Activity hii ni ya biashara nyingine.")
        return super().save(*args, **kwargs)

    def __str__(self):
        mhusika_jina = self.mhusika.username if self.mhusika else "Mfumo"
        return f"{mhusika_jina} {self.kitendo} - {self.muda:%H:%M}"


# =========================================================
# 9. LOGIN HISTORY
# =========================================================
class LoginHistory(models.Model):
    STATUS_CHOICES = (
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
        ("LOCKED", "Locked Out"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="login_history",
    )
    username_attempt = models.CharField(
        max_length=150,
        null=True,
        blank=True,
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )
    user_agent = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Login History"
        verbose_name_plural = "Login Histories"

    def __str__(self):
        return (
            f"{self.username_attempt or '-'} - "
            f"{self.status} - "
            f"{self.timestamp:%Y-%m-%d %H:%M}"
        )
        
        # =========================================================
# MATUMIZI / EXPENSES
# =========================================================
class Matumizi(models.Model):
    objects = DukaTenantManager()
    all_objects = models.Manager()

    duka = models.ForeignKey(
        "Duka",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matumizi",
    )

    CATEGORY_CHOICES = (
        ("Fuel", "Fuel"),
        ("Transport", "Transport"),
        ("Salary", "Salary"),
        ("Maintenance", "Maintenance"),
        ("Electricity", "Electricity"),
        ("Internet", "Internet"),
        ("Meal", "Meal"),
        ("Others", "Others"),
    )

    STATUS_CHOICES = (
        ("PAID", "Paid"),
        ("PENDING", "Pending"),
    )

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default="Others",
        db_index=True,
    )

    maelezo = models.TextField(
        max_length=1000,
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
    )

    kiasi = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="PAID",
        db_index=True,
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matumizi_aliyosajili",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Matumizi"
        verbose_name_plural = "Matumizi"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        tenant_id = _tenant_id_from_context()
        if self.duka_id is None and tenant_id is not None:
            self.duka_id = tenant_id
        _assert_current_tenant(self.duka_id, "Matumizi haya ni ya biashara nyingine.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.category} - TZS {self.kiasi:,.2f}"

    @property
    def is_pending(self):
        return self.status == "PENDING"
    
    # =========================================================
# RETURNS / REFUNDS
# =========================================================
class SaleReturn(models.Model):
    objects = SaleReturnTenantManager()
    all_objects = models.Manager()

    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    )

    REFUND_METHOD_CHOICES = (
        ("ORIGINAL", "Original Payment Method"),
        ("CASH", "Cash"),
        ("MPESA", "M-Pesa"),
        ("TIGOPESA", "Tigo Pesa"),
        ("AIRTELMONEY", "Airtel Money"),
        ("BANK", "Bank Transfer"),
    )

    sale = models.ForeignKey(
        Mauzo,
        on_delete=models.PROTECT,
        related_name="returns",
    )

    quantity_returned = models.PositiveIntegerField(
        validators=[
            MinValueValidator(1)
        ],
    )

    reason = models.TextField(
        max_length=1000,
    )

    refund_method = models.CharField(
        max_length=20,
        choices=REFUND_METHOD_CHOICES,
        default="ORIGINAL",
    )

    refund_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="PENDING",
        db_index=True,
    )

    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sale_returns_requested",
    )

    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sale_returns_approved",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Sale Return / Refund"
        verbose_name_plural = "Sale Returns / Refunds"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        sale = self._state.fields_cache.get("sale")
        if sale is None:
            sale = Mauzo.all_objects.only("duka_id", "idadi").get(pk=self.sale_id)
        if sale.duka_id is None:
            raise ValueError("Mauzo ya return hayana biashara iliyowekwa.")
        if int(self.quantity_returned or 0) <= 0:
            raise ValueError("Quantity ya return lazima iwe zaidi ya sifuri.")
        if self.refund_amount is None or self.refund_amount < Decimal("0.00"):
            raise ValueError("Refund amount haiwezi kuwa chini ya sifuri.")
        if int(self.quantity_returned) > int(sale.idadi):
            raise ValueError("Quantity ya return haiwezi kuzidi quantity ya mauzo haya.")
        _assert_current_tenant(sale.duka_id, "Return hii ni ya biashara nyingine.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"Return #{self.id} - "
            f"Sale #{self.sale_id} - "
            f"{self.quantity_returned} pcs"
        )

    @property
    def total_sale_quantity(self):
        return self.sale.idadi

    @property
    def remaining_returnable_quantity(self):
        approved_and_pending = (
            self.sale.returns
            .exclude(pk=self.pk)
            .filter(
                status__in=["PENDING", "APPROVED"]
            )
            .aggregate(
                total=Sum("quantity_returned")
            )["total"]
            or 0
        )

        return max(
            self.sale.idadi - approved_and_pending,
            0,
        )
        
class CustomerCampaign(models.Model):
    objects = DukaTenantManager()
    all_objects = models.Manager()

    duka = models.ForeignKey(
        "Duka",
        on_delete=models.CASCADE,
        related_name="duka_customer_campaigns",
        db_index=True,
    )

    CHANNEL_CHOICES = (
        ("WHATSAPP", "WhatsApp"),
        ("SMS", "SMS"),
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_campaigns",
    )

    name = models.CharField(
        max_length=150,
    )

    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
    )

    message = models.TextField()

    recipient_count = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        _assert_current_tenant(self.duka_id, "Campaign hii ni ya biashara nyingine.")
        return super().save(*args, **kwargs)

# =========================================================
# 6B. DAILY BUSINESS REPORT SETTINGS
# =========================================================
class DailyReportSettings(models.Model):
    """Tenant-scoped configuration for the Daily Business Report."""
    objects = DukaTenantManager()
    all_objects = models.Manager()

    duka = models.OneToOneField(
        "Duka",
        on_delete=models.CASCADE,
        related_name="daily_report_settings",
    )

    enabled = models.BooleanField(default=True)
    report_time = models.TimeField(default=dt_time(22, 0))

    recipient_boss = models.BooleanField(default=True)
    recipient_manager = models.BooleanField(default=True)

    include_sales_summary = models.BooleanField(default=True)
    include_payment_breakdown = models.BooleanField(default=True)
    include_staff_performance = models.BooleanField(default=True)
    include_products_sold = models.BooleanField(default=True)
    include_discounts = models.BooleanField(default=True)
    include_markups = models.BooleanField(default=True)
    include_debts = models.BooleanField(default=True)
    include_transaction_details = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Daily Report Setting"
        verbose_name_plural = "Daily Report Settings"

    def save(self, *args, **kwargs):
        _assert_current_tenant(
            self.duka_id,
            "Mipangilio ya ripoti hii ni ya biashara nyingine.",
        )
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Daily Report Settings - {self.duka_id}"


class CommunicationLog(models.Model):
    objects = DukaTenantManager()
    all_objects = models.Manager()

    duka = models.ForeignKey(
        "Duka",
        on_delete=models.CASCADE,
        related_name="duka_communication_logs",
        db_index=True,
    )

    CHANNEL_CHOICES = (
        ("SMS", "SMS"),
        ("WHATSAPP", "WhatsApp"),
    )

    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("SENT", "Sent"),
        ("DELIVERED", "Delivered"),
        ("FAILED", "Failed"),
    )
    
    MESSAGE_TYPE_CHOICES = (
        ("MANUAL", "Manual Message"),
        ("AFTER_SALE", "After Sale"),
        ("PAYMENT", "Payment Confirmation"),
        ("DEBT_REMINDER", "Debt Reminder"),
        ("DAILY_REPORT", "Daily Report"),
        ("LOW_STOCK", "Low Stock"),
        ("FOLLOW_UP", "Customer Follow-up"),
        ("AI_PRODUCT_CARE", "AI Product Care"),
    )

    customer = models.ForeignKey(
        Mteja,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communication_logs",
    )

    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
    )

    message_type = models.CharField(
        max_length=50,
        choices=MESSAGE_TYPE_CHOICES,
        default="MANUAL"
    )

    recipient = models.CharField(
        max_length=30,
    )

    message = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )

    provider_message_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    provider_response = models.JSONField(
        blank=True,
        null=True,
    )

    error_message = models.TextField(
        blank=True,
        null=True,
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communication_logs_created",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )

    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Communication Log"
        verbose_name_plural = "Communication Logs"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        _assert_current_tenant(self.duka_id, "Communication log hii ni ya biashara nyingine.")
        if self.customer_id:
            customer = Mteja.all_objects.only("duka_id").get(pk=self.customer_id)
            if customer.duka_id != self.duka_id:
                raise ValueError("Customer wa ujumbe si wa biashara hii.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.channel} - {self.recipient} - {self.status}"
    
