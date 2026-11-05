from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("pos_app", "0027_daily_report_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="businesssubscription",
            name="premium_start_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="businesssubscription",
            name="premium_end_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="businesssubscription",
            name="last_payment_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="PaymentTransaction",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "tx_ref",
                    models.CharField(
                        db_index=True,
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    "gateway_transaction_id",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        default="",
                        max_length=100,
                    ),
                ),
                (
                    "gateway_reference",
                    models.CharField(blank=True, default="", max_length=150),
                ),
                (
                    "amount",
                    models.DecimalField(decimal_places=2, max_digits=12),
                ),
                (
                    "currency",
                    models.CharField(default="TZS", max_length=10),
                ),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("MOBILE_MONEY", "Mobile Money"),
                            ("BANK_TRANSFER", "Bank Transfer"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "network",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("AIRTEL", "Airtel Money"),
                            ("TIGO", "Tigo / Mixx by Yas"),
                            ("HALOPESA", "HaloPesa"),
                            ("VODAFONE", "Vodacom M-Pesa"),
                        ],
                        default="",
                        max_length=30,
                    ),
                ),
                (
                    "phone_number",
                    models.CharField(blank=True, default="", max_length=20),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("INITIATED", "Initiated"),
                            ("PENDING", "Pending"),
                            ("SUCCESSFUL", "Successful"),
                            ("FAILED", "Failed"),
                            ("CANCELLED", "Cancelled"),
                            ("PENDING_BANK", "Pending Bank Verification"),
                        ],
                        db_index=True,
                        default="INITIATED",
                        max_length=30,
                    ),
                ),
                (
                    "gateway_status",
                    models.CharField(blank=True, default="", max_length=50),
                ),
                (
                    "failure_reason",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "gateway_payload",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "completed_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payments",
                        to="pos_app.businesssubscription",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_transactions",
                        to="auth.user",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["user", "status", "created_at"],
                        name="pos_app_pay_user_id_2d5f4b_idx",
                    ),
                    models.Index(
                        fields=["gateway_transaction_id"],
                        name="pos_app_pay_gate_4e3f3b_idx",
                    ),
                ],
            },
        ),
    ]
