from django.db import migrations, models
from decimal import Decimal


class Migration(migrations.Migration):
    dependencies = [
        ("pos_app", "0028_payment_transactions_and_premium_expiry"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymenttransaction",
            name="billing_months",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="paymenttransaction",
            name="unit_price",
            field=models.DecimalField(decimal_places=2, default=Decimal("20000.00"), max_digits=12),
        ),
        migrations.AddField(
            model_name="paymenttransaction",
            name="discount_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12),
        ),
    ]
