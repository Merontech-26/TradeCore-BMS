from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pos_app", "0029_premium_billing_months_pricing"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="ui_preferences",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
