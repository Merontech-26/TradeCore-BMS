from django.db import migrations, models


def ean13_checksum(body12):
    digits = [int(ch) for ch in str(body12)]
    total = sum((d if i % 2 == 0 else d * 3) for i, d in enumerate(digits))
    return (10 - (total % 10)) % 10


def populate_barcodes(apps, schema_editor):
    Bidhaa = apps.get_model("pos_app", "Bidhaa")
    used = set(
        Bidhaa.objects.exclude(barcode__isnull=True)
        .exclude(barcode="")
        .values_list("barcode", flat=True)
    )
    for bidhaa in Bidhaa.objects.all().order_by("pk"):
        if bidhaa.barcode:
            continue
        legacy = bidhaa.qr_code
        if legacy and legacy not in used:
            bidhaa.barcode = legacy
            bidhaa.barcode_aina = "FACTORY"
            bidhaa.save(update_fields=["barcode", "barcode_aina"])
            used.add(legacy)
            continue
        body = f"200{bidhaa.pk:09d}"[:12]
        code = body + str(ean13_checksum(body))
        while code in used:
            body = f"201{bidhaa.pk:09d}"[:12]
            code = body + str(ean13_checksum(body))
        bidhaa.barcode = code
        bidhaa.barcode_aina = "GENERATED"
        bidhaa.save(update_fields=["barcode", "barcode_aina"])
        used.add(code)


class Migration(migrations.Migration):
    dependencies = [("pos_app", "0012_alter_mteja_options_duka_currency_duka_email_and_more")]

    operations = [
        migrations.AddField(
            model_name="bidhaa",
            name="barcode",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Barcode ya kiwandani au barcode ya ndani iliyotengenezwa na mfumo.",
                max_length=100,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="bidhaa",
            name="barcode_aina",
            field=models.CharField(
                choices=[("FACTORY", "Factory Barcode"), ("GENERATED", "Generated Barcode")],
                default="GENERATED",
                max_length=20,
            ),
        ),
        migrations.RunPython(populate_barcodes, migrations.RunPython.noop),
    ]
