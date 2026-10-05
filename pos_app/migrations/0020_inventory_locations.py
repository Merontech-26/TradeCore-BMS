from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def migrate_legacy_inventory(apps, schema_editor):
    Duka = apps.get_model("pos_app", "Duka")
    Profile = apps.get_model("pos_app", "Profile")
    Bidhaa = apps.get_model("pos_app", "Bidhaa")
    Mauzo = apps.get_model("pos_app", "Mauzo")
    Matumizi = apps.get_model("pos_app", "Matumizi")
    StockLocation = apps.get_model("pos_app", "StockLocation")
    ProductStock = apps.get_model("pos_app", "ProductStock")
    StockMovement = apps.get_model("pos_app", "StockMovement")

    # Select the existing business with the most historical sales using the
    # already-existing Profile -> Duka relationship. The new Mauzo.duka field
    # is still empty at this point, so counting Duka.mauzo here would always
    # produce zero.
    profiles = {
        p.user_id: p.duka_id
        for p in Profile.objects.exclude(duka_id=None).only("user_id", "duka_id")
    }
    sales_counts = {}
    for user_id, duka_id in profiles.items():
        if duka_id:
            sales_counts[duka_id] = Mauzo.objects.filter(muuzaji_id=user_id).count()
    primary_id = max(
        sales_counts,
        key=lambda duka_id: (sales_counts[duka_id], -int(duka_id)),
        default=None,
    )
    primary_duka = Duka.objects.filter(pk=primary_id).first() if primary_id else Duka.objects.order_by("id").first()

    # Existing businesses stay on the legacy aggregate path unless they are
    # the active business whose existing stock can be migrated safely.
    Duka.objects.update(inventory_location_mode=False)

    if primary_duka is None:
        return

    primary_duka.inventory_location_mode = True
    primary_duka.save(update_fields=["inventory_location_mode"])

    store, _ = StockLocation.objects.get_or_create(
        duka_id=primary_duka.pk,
        code="store",
        defaults={
            "jina": "Store",
            "aina": "STORE",
            "is_sales_location": False,
            "is_active": True,
        },
    )
    shop, _ = StockLocation.objects.get_or_create(
        duka_id=primary_duka.pk,
        code="duka",
        defaults={
            "jina": "Duka",
            "aina": "SHOP",
            "is_sales_location": True,
            "is_active": True,
        },
    )

    # idadi_stoo already contains the current aggregate. Seed that current
    # balance into Store once. Do not replay historical sales into ProductStock
    # because that would deduct the same units twice.
    for product in Bidhaa.objects.all().iterator():
        qty = int(product.idadi_stoo or 0)
        ProductStock.objects.update_or_create(
            bidhaa_id=product.pk,
            location_id=store.pk,
            defaults={"quantity": qty},
        )
        if qty > 0:
            exists = StockMovement.objects.filter(
                duka_id=primary_duka.pk,
                bidhaa_id=product.pk,
                reference="MIGRATION-0019",
                location_id=store.pk,
            ).exists()
            if not exists:
                StockMovement.objects.create(
                    duka_id=primary_duka.pk,
                    bidhaa_id=product.pk,
                    movement_type="OPENING",
                    quantity=qty,
                    location_id=store.pk,
                    balance_before=0,
                    balance_after=qty,
                    reference="MIGRATION-0019",
                    reason="Legacy aggregate stock migrated to Store",
                    actor_id=primary_duka.mwenye_duka_id,
                )

    # Preserve known ownership for historical transactions. Sales made by a
    # user whose Profile already points to a Duka keep that relationship. Any
    # remaining legacy sale is attached to the primary business so reporting
    # can read it without inventing historic stock movements.
    for sale in Mauzo.objects.filter(duka_id=None).only("id", "muuzaji_id"):
        duka_id = profiles.get(sale.muuzaji_id) or primary_duka.pk
        sale.duka_id = duka_id
        update_fields = ["duka"]
        if duka_id == primary_duka.pk:
            sale.stock_location_id = shop.pk
            update_fields.append("stock_location")
        sale.save(update_fields=update_fields)

    for expense in Matumizi.objects.filter(duka_id=None).only("id", "created_by_id"):
        duka_id = profiles.get(expense.created_by_id) or primary_duka.pk
        expense.duka_id = duka_id
        expense.save(update_fields=["duka"])


def reverse_legacy_inventory(apps, schema_editor):
    Duka = apps.get_model("pos_app", "Duka")
    ProductStock = apps.get_model("pos_app", "ProductStock")
    StockLocation = apps.get_model("pos_app", "StockLocation")
    StockMovement = apps.get_model("pos_app", "StockMovement")

    StockMovement.objects.filter(reference="MIGRATION-0019").delete()
    ProductStock.objects.filter(
        location__code__in=["store", "duka"],
        location__duka__inventory_location_mode=True,
    ).delete()
    StockLocation.objects.filter(
        code__in=["store", "duka"],
        duka__inventory_location_mode=True,
    ).delete()
    Duka.objects.update(inventory_location_mode=False)


class Migration(migrations.Migration):
    dependencies = [
        ("pos_app", "0019_profile_duka"),
    ]

    operations = [
        migrations.AddField(
            model_name="duka",
            name="inventory_location_mode",
            field=models.BooleanField(
                default=True,
                db_index=True,
                verbose_name="Tumia stock kwa Locations",
            ),
        ),
        migrations.AddField(
            model_name="mzigoulioingia",
            name="duka",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="mizigo_iliyoingia",
                to="pos_app.duka",
            ),
        ),
        migrations.AddField(
            model_name="mzigoulioingia",
            name="received_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="mizigo_iliyopokelewa",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="mzigoulioingia",
            name="reference",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="mzigoulioingia",
            name="notes",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="StockLocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("jina", models.CharField(max_length=120)),
                ("code", models.SlugField(max_length=80)),
                ("aina", models.CharField(choices=[("STORE", "Store / Chumba cha Stoo"), ("SHOP", "Duka / POS"), ("WAREHOUSE", "Warehouse"), ("OTHER", "Other")], default="OTHER", max_length=20)),
                ("is_sales_location", models.BooleanField(db_index=True, default=False)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("duka", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stock_locations", to="pos_app.duka")),
            ],
            options={
                "verbose_name": "Stock Location",
                "verbose_name_plural": "Stock Locations",
                "ordering": ["jina"],
            },
        ),
        migrations.AddConstraint(
            model_name="stocklocation",
            constraint=models.UniqueConstraint(fields=("duka", "code"), name="uniq_stock_location_duka_code"),
        ),
        migrations.AddField(
            model_name="mzigoulioingia",
            name="location",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="mizigo",
                to="pos_app.stocklocation",
            ),
        ),
        migrations.CreateModel(
            name="ProductStock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("bidhaa", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="location_stocks", to="pos_app.bidhaa")),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="product_stocks", to="pos_app.stocklocation")),
            ],
            options={
                "verbose_name": "Product Stock",
                "verbose_name_plural": "Product Stocks",
                "ordering": ["bidhaa__jina_la_bidhaa"],
            },
        ),
        migrations.AddConstraint(
            model_name="productstock",
            constraint=models.UniqueConstraint(fields=("bidhaa", "location"), name="uniq_product_stock_location"),
        ),
        migrations.CreateModel(
            name="StockTransfer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=40, unique=True)),
                ("reason_code", models.CharField(choices=[("REPLENISHMENT", "Replenishment / Kupeleka Duka"), ("RETURN_TO_STORE", "Return to Store"), ("DAMAGED", "Damaged Product"), ("EXPIRED", "Expired Product"), ("CUSTOMER_RETURN", "Customer Return"), ("REDISTRIBUTION", "Redistribution"), ("OTHER", "Other")], default="OTHER", max_length=30)),
                ("reason_text", models.TextField(blank=True, default="")),
                ("notes", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("destination_location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transfers_in", to="pos_app.stocklocation")),
                ("duka", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stock_transfers", to="pos_app.duka")),
                ("performed_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_transfers_performed", to=settings.AUTH_USER_MODEL)),
                ("source_location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transfers_out", to="pos_app.stocklocation")),
            ],
            options={"verbose_name": "Stock Transfer", "verbose_name_plural": "Stock Transfers", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="StockTransferItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField()),
                ("source_before", models.PositiveIntegerField(default=0)),
                ("source_after", models.PositiveIntegerField(default=0)),
                ("destination_before", models.PositiveIntegerField(default=0)),
                ("destination_after", models.PositiveIntegerField(default=0)),
                ("bidhaa", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_transfer_items", to="pos_app.bidhaa")),
                ("transfer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="pos_app.stocktransfer")),
            ],
            options={"verbose_name": "Stock Transfer Item", "verbose_name_plural": "Stock Transfer Items"},
        ),
        migrations.AddConstraint(
            model_name="stocktransferitem",
            constraint=models.UniqueConstraint(fields=("transfer", "bidhaa"), name="uniq_transfer_product"),
        ),
        migrations.CreateModel(
            name="StockTake",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=40, unique=True)),
                ("status", models.CharField(choices=[("COMPLETED", "Completed"), ("CANCELLED", "Cancelled")], default="COMPLETED", max_length=20)),
                ("notes", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("completed_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_takes_completed", to=settings.AUTH_USER_MODEL)),
                ("duka", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stock_takes", to="pos_app.duka")),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_takes", to="pos_app.stocklocation")),
                ("started_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_takes_started", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Stock Take", "verbose_name_plural": "Stock Takes", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="StockTakeItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("system_quantity", models.PositiveIntegerField(default=0)),
                ("physical_quantity", models.PositiveIntegerField(default=0)),
                ("variance", models.IntegerField(default=0)),
                ("notes", models.TextField(blank=True, null=True)),
                ("bidhaa", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_take_items", to="pos_app.bidhaa")),
                ("stock_take", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="pos_app.stocktake")),
            ],
            options={"verbose_name": "Stock Take Item", "verbose_name_plural": "Stock Take Items"},
        ),
        migrations.AddConstraint(
            model_name="stocktakeitem",
            constraint=models.UniqueConstraint(fields=("stock_take", "bidhaa"), name="uniq_stock_take_product"),
        ),
        migrations.AddField(
            model_name="mauzo",
            name="duka",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="mauzo",
                to="pos_app.duka",
            ),
        ),
        migrations.AddField(
            model_name="mauzo",
            name="stock_location",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="mauzo",
                to="pos_app.stocklocation",
            ),
        ),
        migrations.CreateModel(
            name="StockMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("movement_type", models.CharField(choices=[("OPENING", "Opening Stock"), ("STOCK_IN", "Stock In"), ("SALE", "Sale"), ("TRANSFER", "Transfer"), ("RETURN", "Return"), ("ADJUSTMENT", "Adjustment"), ("DAMAGE", "Damage"), ("STOCK_TAKE", "Stock Take")], db_index=True, max_length=20)),
                ("quantity", models.PositiveIntegerField(default=0)),
                ("balance_before", models.PositiveIntegerField(blank=True, null=True)),
                ("balance_after", models.PositiveIntegerField(blank=True, null=True)),
                ("from_balance_before", models.PositiveIntegerField(blank=True, null=True)),
                ("from_balance_after", models.PositiveIntegerField(blank=True, null=True)),
                ("to_balance_before", models.PositiveIntegerField(blank=True, null=True)),
                ("to_balance_after", models.PositiveIntegerField(blank=True, null=True)),
                ("reference", models.CharField(db_index=True, max_length=80)),
                ("reason", models.TextField(blank=True, default="")),
                ("notes", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("actor", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_movements_performed", to=settings.AUTH_USER_MODEL)),
                ("bidhaa", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_movements", to="pos_app.bidhaa")),
                ("duka", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stock_movements", to="pos_app.duka")),
                ("from_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="movement_from", to="pos_app.stocklocation")),
                ("location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="movements", to="pos_app.stocklocation")),
                ("sale", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_movements", to="pos_app.mauzo")),
                ("stock_take", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="movements", to="pos_app.stocktake")),
                ("to_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="movement_to", to="pos_app.stocklocation")),
                ("transfer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="movements", to="pos_app.stocktransfer")),
            ],
            options={
                "verbose_name": "Stock Movement",
                "verbose_name_plural": "Stock Movements",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["duka", "bidhaa", "created_at"], name="stockmov_duka_prod_created"),
                    models.Index(fields=["duka", "movement_type", "created_at"], name="stockmov_duka_type_created"),
                ],
            },
        ),
        migrations.AddField(
            model_name="matumizi",
            name="duka",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="matumizi",
                to="pos_app.duka",
            ),
        ),
        migrations.RunPython(migrate_legacy_inventory, reverse_legacy_inventory),
    ]
