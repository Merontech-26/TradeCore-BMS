from datetime import time as dt_time

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("pos_app", "0026_mauzo_bei_ya_kununulia_stoo"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyReportSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("enabled", models.BooleanField(default=True)),
                ("report_time", models.TimeField(default=dt_time(22, 0))),
                ("recipient_boss", models.BooleanField(default=True)),
                ("recipient_manager", models.BooleanField(default=True)),
                ("include_sales_summary", models.BooleanField(default=True)),
                ("include_payment_breakdown", models.BooleanField(default=True)),
                ("include_staff_performance", models.BooleanField(default=True)),
                ("include_products_sold", models.BooleanField(default=True)),
                ("include_discounts", models.BooleanField(default=True)),
                ("include_markups", models.BooleanField(default=True)),
                ("include_debts", models.BooleanField(default=True)),
                ("include_transaction_details", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("duka", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="daily_report_settings", to="pos_app.duka")),
            ],
            options={
                "verbose_name": "Daily Report Setting",
                "verbose_name_plural": "Daily Report Settings",
            },
        ),
    ]
