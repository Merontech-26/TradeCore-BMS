from django.conf import settings
from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError
import django.db.models.deletion
from django.db.models import Q


def _first_duka(Duka):
    duka = Duka.objects.order_by("id").first()
    if duka is None:
        raise RuntimeError(
            "TradeCore tenant migration found store data but no Duka exists. "
            "Create/restore the store before applying migration 0022."
        )
    return duka


def backfill_tenants(apps, schema_editor):
    Duka = apps.get_model("pos_app", "Duka")
    User = apps.get_model("auth", "User")
    Profile = apps.get_model("pos_app", "Profile")
    Bidhaa = apps.get_model("pos_app", "Bidhaa")
    Mteja = apps.get_model("pos_app", "Mteja")
    Mauzo = apps.get_model("pos_app", "Mauzo")
    Mzigo = apps.get_model("pos_app", "MzigoUlioingia")
    ProductStock = apps.get_model("pos_app", "ProductStock")
    StockMovement = apps.get_model("pos_app", "StockMovement")
    StockTransferItem = apps.get_model("pos_app", "StockTransferItem")
    StockTakeItem = apps.get_model("pos_app", "StockTakeItem")
    PurchaseRequest = apps.get_model("pos_app", "PurchaseRequest")
    PurchaseRequestItem = apps.get_model("pos_app", "PurchaseRequestItem")
    ActivityLog = apps.get_model("pos_app", "ActivityLog")
    Vocha = apps.get_model("pos_app", "VochaYaDuka")
    Campaign = apps.get_model("pos_app", "CustomerCampaign")
    CommunicationLog = apps.get_model("pos_app", "CommunicationLog")
    StockLocation = apps.get_model("pos_app", "StockLocation")
    StockTake = apps.get_model("pos_app", "StockTake")
    SaleReturn = apps.get_model("pos_app", "SaleReturn")

    stores = list(Duka.objects.order_by("id").values_list("id", flat=True))
    primary_duka_id = stores[0] if stores else None

    # Nothing to migrate in a brand-new installation.
    if not stores:
        has_rows = any(
            model.objects.exists()
            for model in [Bidhaa, Mteja, PurchaseRequest, Vocha, Campaign, CommunicationLog]
        )
        if has_rows:
            raise RuntimeError("Tenant migration cannot assign legacy rows because no Duka exists.")
        return

    # ---------------------------------------------------------
    # PRODUCTS
    # ---------------------------------------------------------
    # Product master data was global in the legacy schema. We turn it into a
    # store-owned catalog. Where the same SKU exists in several stores, keep
    # the original row for the lowest-id store and clone it for every other
    # store. Related sales/stock/movements are then pointed to the correct
    # clone.
    product_store_ids = {}
    products = list(Bidhaa.objects.all().order_by("id"))
    for product in products:
        duka_ids = set()
        for x in Mauzo.objects.filter(bidhaa_id=product.id).exclude(duka_id=None).values_list("duka_id", flat=True):
            duka_ids.add(x)
        for x in Mzigo.objects.filter(bidhaa_id=product.id).exclude(duka_id=None).values_list("duka_id", flat=True):
            duka_ids.add(x)
        for x in StockMovement.objects.filter(bidhaa_id=product.id).exclude(duka_id=None).values_list("duka_id", flat=True):
            duka_ids.add(x)
        for x in ProductStock.objects.filter(bidhaa_id=product.id).values_list("location__duka_id", flat=True):
            if x:
                duka_ids.add(x)
        for x in StockTransferItem.objects.filter(bidhaa_id=product.id).values_list("transfer__duka_id", flat=True):
            if x:
                duka_ids.add(x)
        for x in StockTakeItem.objects.filter(bidhaa_id=product.id).values_list("stock_take__duka_id", flat=True):
            if x:
                duka_ids.add(x)
        for x in PurchaseRequestItem.objects.filter(bidhaa_id=product.id).values_list("purchase_request__duka_id", flat=True):
            if x:
                duka_ids.add(x)

        if not duka_ids:
            duka_ids = {primary_duka_id}

        sorted_duka_ids = sorted(int(x) for x in duka_ids if x)
        owner_id = sorted_duka_ids[0]
        product.duka_id = owner_id
        product.save(update_fields=["duka"])
        product_store_ids[(product.id, owner_id)] = product.id

        for target_id in sorted_duka_ids[1:]:
            clone = Bidhaa.objects.create(
                duka_id=target_id,
                kategoria_id=product.kategoria_id,
                picha=product.picha,
                jina_la_bidhaa=product.jina_la_bidhaa,
                qr_code=product.qr_code,
                bei_ya_kununulia=product.bei_ya_kununulia,
                bei_ya_kuuzia=product.bei_ya_kuuzia,
                idadi_stoo=product.idadi_stoo,
                maelekezo_maalum=product.maelekezo_maalum,
                barcode=product.barcode,
            )
            product_store_ids[(product.id, target_id)] = clone.id

    # Re-point every product relation to the store-specific product row.
    for sale in Mauzo.objects.all().iterator():
        target_duka = sale.duka_id or primary_duka_id
        new_pid = product_store_ids.get((sale.bidhaa_id, target_duka))
        if new_pid and new_pid != sale.bidhaa_id:
            sale.bidhaa_id = new_pid
            sale.save(update_fields=["bidhaa"])

    for row in Mzigo.objects.all().iterator():
        target_duka = row.duka_id or primary_duka_id
        new_pid = product_store_ids.get((row.bidhaa_id, target_duka))
        if new_pid and new_pid != row.bidhaa_id:
            row.bidhaa_id = new_pid
            row.save(update_fields=["bidhaa"])

    for row in ProductStock.objects.all().iterator():
        target_duka = row.location.duka_id if row.location_id else primary_duka_id
        new_pid = product_store_ids.get((row.bidhaa_id, target_duka))
        if new_pid and new_pid != row.bidhaa_id:
            row.bidhaa_id = new_pid
            row.save(update_fields=["bidhaa"])

    for row in StockMovement.objects.all().iterator():
        new_pid = product_store_ids.get((row.bidhaa_id, row.duka_id or primary_duka_id))
        if new_pid and new_pid != row.bidhaa_id:
            row.bidhaa_id = new_pid
            row.save(update_fields=["bidhaa"])

    for row in StockTransferItem.objects.select_related("transfer").all().iterator():
        transfer_duka = row.transfer.duka_id if row.transfer_id else primary_duka_id
        new_pid = product_store_ids.get((row.bidhaa_id, transfer_duka))
        if new_pid and new_pid != row.bidhaa_id:
            row.bidhaa_id = new_pid
            row.save(update_fields=["bidhaa"])

    for row in StockTakeItem.objects.select_related("stock_take").all().iterator():
        take_duka = row.stock_take.duka_id if row.stock_take_id else primary_duka_id
        new_pid = product_store_ids.get((row.bidhaa_id, take_duka))
        if new_pid and new_pid != row.bidhaa_id:
            row.bidhaa_id = new_pid
            row.save(update_fields=["bidhaa"])

    for row in PurchaseRequestItem.objects.select_related("purchase_request").all().iterator():
        req_duka = row.purchase_request.duka_id if row.purchase_request_id else primary_duka_id
        new_pid = product_store_ids.get((row.bidhaa_id, req_duka))
        if new_pid and new_pid != row.bidhaa_id:
            row.bidhaa_id = new_pid
            row.save(update_fields=["bidhaa"])

    # ---------------------------------------------------------
    # CUSTOMERS
    # ---------------------------------------------------------
    customer_store_ids = {}
    customers = list(Mteja.objects.all().order_by("id"))
    for customer in customers:
        duka_ids = set(
            int(x)
            for x in Mauzo.objects.filter(mteja_id=customer.id).exclude(duka_id=None).values_list("duka_id", flat=True)
            if x
        )
        if not duka_ids:
            duka_ids = {primary_duka_id}

        sorted_duka_ids = sorted(duka_ids)
        owner_id = sorted_duka_ids[0]
        customer.duka_id = owner_id
        customer.save(update_fields=["duka"])
        customer_store_ids[(customer.id, owner_id)] = customer.id

        for target_id in sorted_duka_ids[1:]:
            clone = Mteja.objects.create(
                duka_id=target_id,
                majina_kamili=customer.majina_kamili,
                namba_ya_simu=customer.namba_ya_simu,
                whatsapp_no=customer.whatsapp_no,
                aina=customer.aina,
                pre_order_deposit=customer.pre_order_deposit,
                outstanding_balance=customer.outstanding_balance,
                email=customer.email,
                anwani=customer.anwani,
                eneo=customer.eneo,
                marketing_opt_in=customer.marketing_opt_in,
            )
            customer_store_ids[(customer.id, target_id)] = clone.id

    for sale in Mauzo.objects.all().iterator():
        if not sale.mteja_id:
            continue
        new_cid = customer_store_ids.get((sale.mteja_id, sale.duka_id or primary_duka_id))
        if new_cid and new_cid != sale.mteja_id:
            sale.mteja_id = new_cid
            sale.save(update_fields=["mteja"])

    # ---------------------------------------------------------
    # PURCHASE REQUESTS + COMMUNICATION / AUDIT DATA
    # ---------------------------------------------------------
    user_store = {
        p.user_id: p.duka_id
        for p in Profile.objects.exclude(duka_id=None).only("user_id", "duka_id")
    }
    for duka_id, owner_id in Duka.objects.values_list("id", "mwenye_duka_id"):
        user_store.setdefault(owner_id, duka_id)

    for request_row in PurchaseRequest.objects.all().iterator():
        duka_id = request_row.duka_id or user_store.get(request_row.requested_by_id) or user_store.get(request_row.reviewed_by_id) or primary_duka_id
        request_row.duka_id = duka_id
        request_row.save(update_fields=["duka"])

    for log in ActivityLog.objects.all().iterator():
        if log.duka_id is None:
            log.duka_id = user_store.get(log.mhusika_id)
            if log.duka_id:
                log.save(update_fields=["duka"])

    for campaign in Campaign.objects.all().iterator():
        if campaign.duka_id is None:
            campaign.duka_id = user_store.get(campaign.created_by_id) or primary_duka_id
            campaign.save(update_fields=["duka"])

    for comm in CommunicationLog.objects.all().iterator():
        if comm.duka_id is None:
            comm.duka_id = user_store.get(comm.created_by_id) or (comm.customer.duka_id if comm.customer_id else None) or primary_duka_id
            comm.save(update_fields=["duka"])

    for vocha in Vocha.objects.all().iterator():
        if vocha.duka_id is None:
            # Legacy voucher rows were store-global. Match an exact store name
            # first; otherwise assign the primary legacy store rather than
            # duplicating a balance across tenants.
            match = Duka.objects.filter(jina_la_duka=vocha.jina_la_duka).values_list("id", flat=True).first()
            vocha.duka_id = match or primary_duka_id
            vocha.save(update_fields=["duka"])


def reverse_backfill(apps, schema_editor):
    raise IrreversibleError(
        "TradeCore tenant isolation migration 0022 intentionally has no data-safe reverse. Restore a database backup to roll it back."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("pos_app", "0021_rename_stockmov_duka_prod_created_pos_app_sto_duka_id_351541_idx_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="mteja",
            name="duka",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="wateja",
                to="pos_app.duka",
                null=True,
                blank=True,
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name="bidhaa",
            name="duka",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="bidhaa",
                to="pos_app.duka",
                null=True,
                blank=True,
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name="vochayaduka",
            name="duka",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="vocha",
                to="pos_app.duka",
                null=True,
                blank=True,
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name="purchaserequest",
            name="duka",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="purchase_requests",
                to="pos_app.duka",
                null=True,
                blank=True,
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name="activitylog",
            name="duka",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="duka_activity_logs",
                to="pos_app.duka",
                null=True,
                blank=True,
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name="customercampaign",
            name="duka",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="duka_customer_campaigns",
                to="pos_app.duka",
                null=True,
                blank=True,
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name="communicationlog",
            name="duka",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="duka_communication_logs",
                to="pos_app.duka",
                null=True,
                blank=True,
                db_index=True,
            ),
        ),
        migrations.AlterField(
            model_name="bidhaa",
            name="qr_code",
            field=models.CharField(blank=True, max_length=100, null=True, unique=False),
        ),
        migrations.AlterField(
            model_name="bidhaa",
            name="barcode",
            field=models.CharField(blank=True, max_length=255, null=True, unique=False, verbose_name="Barcode ya Bidhaa"),
        ),
        migrations.RunPython(backfill_tenants, reverse_backfill),
        migrations.AlterField(
            model_name="mteja",
            name="duka",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="wateja",
                to="pos_app.duka",
                db_index=True,
            ),
        ),
        migrations.AlterField(
            model_name="bidhaa",
            name="duka",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="bidhaa",
                to="pos_app.duka",
                db_index=True,
            ),
        ),
        migrations.AlterField(
            model_name="vochayaduka",
            name="duka",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="vocha",
                to="pos_app.duka",
                db_index=True,
            ),
        ),
        migrations.AlterField(
            model_name="purchaserequest",
            name="duka",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="purchase_requests",
                to="pos_app.duka",
                db_index=True,
            ),
        ),
        migrations.AlterField(
            model_name="customercampaign",
            name="duka",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="duka_customer_campaigns",
                to="pos_app.duka",
                db_index=True,
            ),
        ),
        migrations.AlterField(
            model_name="communicationlog",
            name="duka",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="duka_communication_logs",
                to="pos_app.duka",
                db_index=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="bidhaa",
            constraint=models.UniqueConstraint(
                condition=Q(qr_code__isnull=False) & ~Q(qr_code=""),
                fields=("duka", "qr_code"),
                name="uniq_bidhaa_duka_qr_code",
            ),
        ),
        migrations.AddConstraint(
            model_name="bidhaa",
            constraint=models.UniqueConstraint(
                condition=Q(barcode__isnull=False) & ~Q(barcode=""),
                fields=("duka", "barcode"),
                name="uniq_bidhaa_duka_barcode",
            ),
        ),
    ]
