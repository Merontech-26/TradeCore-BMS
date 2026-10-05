from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

import uuid

from .models import (
    Bidhaa,
    Duka,
    MzigoUlioingia,
    ProductStock,
    StockLocation,
    StockMovement,
    StockTake,
    StockTakeItem,
    StockTransfer,
    StockTransferItem,
)


LOCATION_STORE = "STORE"
LOCATION_SHOP = "SHOP"


def _validate_duka_scope(duka):
    """Reject service calls that attempt to operate outside the active tenant."""
    if not duka or not getattr(duka, "pk", None):
        raise ValueError("Duka haijapatikana.")
    from .tenant import get_current_duka_id
    current_duka_id = get_current_duka_id()
    # None is intentionally allowed for shell/admin/maintenance callers that
    # explicitly provide a Duka. The web middleware uses a real tenant id or 0;
    # zero therefore acts as a fail-closed tenant and must not match any Duka.
    if current_duka_id is not None and int(current_duka_id) != int(duka.pk):
        raise ValueError("Operesheni hii si ya biashara iliyopo kwenye request.")
    return duka


def _validate_actor_scope(actor, duka):
    """Ensure an authenticated actor belongs to the same business when known."""
    if actor is None:
        return
    if getattr(actor, "is_superuser", False):
        return
    actor_duka = getattr(actor, "duka", None)
    if actor_duka is None:
        profile = getattr(actor, "profile", None)
        actor_duka = getattr(profile, "duka", None) if profile else None
    if actor_duka is not None and actor_duka.pk != duka.pk:
        raise ValueError("Mtumiaji huyu si wa biashara hii.")


def ensure_inventory_locations(duka):
    """Return the Store and Duka/POS locations for a business.

    This is intentionally additive to the existing schema. Legacy businesses
    are enabled the first time a location-aware inventory action is used, and
    the old aggregate stock is copied into Store exactly once when no
    ProductStock rows exist yet.
    """
    _validate_duka_scope(duka)
    if not duka:
        return None, None

    store, _ = StockLocation.objects.get_or_create(
        duka=duka,
        code="store",
        defaults={"jina": "Store", "aina": LOCATION_STORE, "is_sales_location": False},
    )
    shop, _ = StockLocation.objects.get_or_create(
        duka=duka,
        code="duka",
        defaults={"jina": "Duka", "aina": LOCATION_SHOP, "is_sales_location": True},
    )

    if not getattr(duka, "inventory_location_mode", True):
        duka.inventory_location_mode = True
        duka.save(update_fields=["inventory_location_mode"])

    # One-time bootstrap. Lock the business row so two first-time requests
    # cannot both decide that the inventory has not been bootstrapped yet.
    if not ProductStock.objects.filter(location__duka=duka).exists():
        with transaction.atomic():
            locked_duka = Duka.objects.select_for_update().get(pk=duka.pk)
            store = StockLocation.objects.get(duka=locked_duka, code="store")
            shop = StockLocation.objects.get(duka=locked_duka, code="duka")
            if not ProductStock.objects.filter(location__duka=locked_duka).exists():
                # Only bootstrap products that actually belong to this tenant.
                # A new store must NEVER inherit products from another store.
                for product in (
                    Bidhaa.objects
                    .filter(duka=locked_duka)
                    .only("id", "idadi_stoo")
                    .order_by("id")
                    .iterator()
                ):
                    ProductStock.objects.get_or_create(
                        bidhaa=product,
                        location=store,
                        defaults={"quantity": max(int(product.idadi_stoo or 0), 0)},
                    )

    return store, shop


def ensure_product_stock(bidhaa, location):
    if not bidhaa or not location:
        raise ValueError("Bidhaa na location vinahitajika.")
    _validate_duka_scope(location.duka)
    if bidhaa.duka_id != location.duka_id:
        raise ValueError("Bidhaa na location lazima viwe vya biashara hii.")
    obj, _ = ProductStock.objects.get_or_create(
        bidhaa=bidhaa,
        location=location,
        defaults={"quantity": 0},
    )
    return obj


def current_quantity(bidhaa, location):
    if not bidhaa:
        return 0
    if not location:
        return int(bidhaa.idadi_stoo or 0)
    _validate_duka_scope(location.duka)
    if bidhaa.duka_id != location.duka_id:
        raise ValueError("Bidhaa na location lazima viwe vya biashara hii.")
    return int(
        ProductStock.objects.filter(
            bidhaa=bidhaa,
            location=location,
        ).values_list("quantity", flat=True).first()
        or 0
    )


def sync_legacy_total(bidhaa, duka=None):
    if not bidhaa or not getattr(bidhaa, "duka_id", None):
        raise ValueError("Bidhaa yenye biashara inahitajika.")
    if duka is None:
        raise ValueError("Duka lazima litajwe wakati wa kusawazisha stock.")
    _validate_duka_scope(duka)
    if bidhaa.duka_id != duka.pk:
        raise ValueError("Bidhaa si ya biashara hii.")

    qs = ProductStock.objects.filter(
        bidhaa=bidhaa,
        location__is_active=True,
        location__duka=duka,
    )
    total = qs.aggregate(v=Sum("quantity"))["v"] or 0

    # Location-mode businesses use ProductStock as source of truth. Do not
    # overwrite the shared legacy field and accidentally mix businesses.
    if not getattr(duka, "inventory_location_mode", False):
        bidhaa.idadi_stoo = max(int(total), 0)
        bidhaa.save(update_fields=["idadi_stoo"])
    return int(total)


def unique_reference(prefix):
    """Generate a compact, collision-resistant reference without a pre-check query."""
    stamp = timezone.now().strftime("%Y%m%d%H%M%S%f")
    token = uuid.uuid4().hex[:8].upper()
    return f"{prefix}-{stamp}-{token}"


def add_stock(*, duka, bidhaa, location, quantity, actor, reference, reason="", notes=None, movement_type="STOCK_IN", supplier="", source_ref=""):
    _validate_duka_scope(duka)
    _validate_actor_scope(actor, duka)
    quantity = int(quantity or 0)
    if quantity <= 0:
        raise ValueError("Quantity lazima iwe zaidi ya sifuri.")
    if not duka or not location:
        raise ValueError("Duka na location vinahitajika.")
    if location.duka_id != duka.id:
        raise ValueError("Location si ya biashara hii.")
    if bidhaa.duka_id != duka.id:
        raise ValueError("Bidhaa si ya biashara hii.")
    with transaction.atomic():
        # SURGERY FIX: Lock 'Bidhaa' kwanza (Parent Lock) kuepuka deadlocks na race conditions
        locked_bidhaa = Bidhaa.objects.select_for_update().get(pk=bidhaa.pk)
        ps, _ = ProductStock.objects.select_for_update().get_or_create(bidhaa=locked_bidhaa, location=location, defaults={"quantity": 0})
        before = int(ps.quantity or 0)
        ps.quantity = before + quantity
        ps.save(update_fields=["quantity", "updated_at"])
        total = sync_legacy_total(locked_bidhaa, duka)
        movement = StockMovement.objects.create(
            duka=duka,
            bidhaa=locked_bidhaa,
            movement_type=movement_type,
            quantity=quantity,
            location=location,
            balance_before=before,
            balance_after=int(ps.quantity),
            reference=reference,
            reason=reason or "Stock In",
            notes=notes,
            actor=actor,
        )
        if supplier or source_ref:
            MzigoUlioingia.objects.create(
                bidhaa=locked_bidhaa,
                supplier=supplier or "—",
                quantity=quantity,
                duka=duka,
                location=location,
                received_by=actor,
                reference=source_ref or reference,
                notes=notes,
                buying_price=locked_bidhaa.bei_ya_kununulia,
            )
        return movement, int(ps.quantity), total


def deduct_stock(*, duka, bidhaa, location, quantity, actor, reference, reason="", notes=None):
    _validate_duka_scope(duka)
    _validate_actor_scope(actor, duka)
    quantity = int(quantity or 0)
    if quantity <= 0:
        raise ValueError("Quantity lazima iwe zaidi ya sifuri.")
    if not duka or not location:
        raise ValueError("Duka na location vinahitajika.")
    if location.duka_id != duka.id:
        raise ValueError("Location si ya biashara hii.")
    if bidhaa.duka_id != duka.id:
        raise ValueError("Bidhaa si ya biashara hii.")
    with transaction.atomic():
        # SURGERY FIX: Funga Bidhaa kwanza kuhakikisha muamala mmoja tu unagusa hii bidhaa kwa wakati mmoja
        locked_bidhaa = Bidhaa.objects.select_for_update().get(pk=bidhaa.pk)
        ps = ProductStock.objects.select_for_update().filter(
            bidhaa=locked_bidhaa,
            location=location,
        ).first()
        if ps is None:
            raise ValueError(
                f"{locked_bidhaa.jina_la_bidhaa} haina stock iliyosajiliwa "
                f"kwenye {location.jina}."
            )
        before = int(ps.quantity or 0)
        if before < quantity:
            raise ValueError(
                f"Samahani, bidhaa '{locked_bidhaa.jina_la_bidhaa}' "
                f"imebaki {before} tu kwenye {location.jina}!"
            )
        ps.quantity = before - quantity
        ps.save(update_fields=["quantity", "updated_at"])
        total = sync_legacy_total(locked_bidhaa, duka)
        return StockMovement.objects.create(
            duka=duka,
            bidhaa=locked_bidhaa,
            movement_type="SALE",
            quantity=quantity,
            location=location,
            balance_before=before,
            balance_after=int(ps.quantity),
            reference=reference,
            reason=reason or "Mauzo ya POS",
            notes=notes,
            actor=actor,
        )

def perform_transfer(*, duka, source, destination, items, actor, reason_code="OTHER", reason_text="", notes=None):
    _validate_duka_scope(duka)
    _validate_actor_scope(actor, duka)
    if not duka or not source or not destination or source.id == destination.id:
        raise ValueError("Source na destination lazima ziwe sahihi na tofauti.")
    if source.duka_id != duka.id or destination.duka_id != duka.id:
        raise ValueError("Source/destination si za biashara hii.")
    if not source.is_active or not destination.is_active:
        raise ValueError("Source na destination lazima ziwe active.")
    normalized_map = {}
    for item in items or []:
        pid = int(item.get("id"))
        qty = int(item.get("qty"))
        if qty <= 0:
            raise ValueError("Kuna quantity isiyo sahihi.")
        normalized_map[pid] = normalized_map.get(pid, 0) + qty
    normalized = sorted(normalized_map.items())
    if not normalized:
        raise ValueError("Hakuna bidhaa kwenye transfer.")

    with transaction.atomic():
        ref = unique_reference("TR")
        transfer = StockTransfer.objects.create(
            duka=duka,
            source_location=source,
            destination_location=destination,
            reference=ref,
            reason_code=reason_code or "OTHER",
            reason_text=reason_text or "",
            notes=notes,
            performed_by=actor,
            completed_at=None,
        )
        for pid, qty in normalized:
            bidhaa = Bidhaa.objects.select_for_update().get(pk=pid)
            if bidhaa.duka_id != duka.id:
                raise ValueError(f"Bidhaa {pid} si ya biashara hii.")
            src, _ = ProductStock.objects.select_for_update().get_or_create(bidhaa=bidhaa, location=source, defaults={"quantity": 0})
            dst, _ = ProductStock.objects.select_for_update().get_or_create(bidhaa=bidhaa, location=destination, defaults={"quantity": 0})
            src_before = int(src.quantity or 0)
            dst_before = int(dst.quantity or 0)
            if src_before < qty:
                raise ValueError(f"{bidhaa.jina_la_bidhaa}: {source.jina} ina {src_before} tu, umeomba {qty}.")
            
            src.quantity = src_before - qty
            src.save(update_fields=["quantity", "updated_at"])
            sync_legacy_total(bidhaa, duka)

            StockTransferItem.objects.create(
                transfer=transfer,
                bidhaa=bidhaa,
                quantity=qty,
                source_before=src_before,
                source_after=int(src.quantity),
                destination_before=dst_before,
                destination_after=dst_before,
            )
            StockMovement.objects.create(
                duka=duka,
                bidhaa=bidhaa,
                movement_type="TRANSFER",
                quantity=qty,
                from_location=source,
                to_location=destination,
                from_balance_before=src_before,
                from_balance_after=int(src.quantity),
                reference=ref,
                reason=f"Mzigo Uko Njiani kwenda {destination.jina}",
                notes=notes,
                actor=actor,
                transfer=transfer,
            )
        return transfer


def reject_transfer(transfer_id, actor, reason=""):
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("Andika sababu ya kukataa mzigo.")
    with transaction.atomic():
        transfer = (
            StockTransfer.objects
            .select_for_update()
            .select_related("source_location", "destination_location", "duka")
            .get(pk=transfer_id)
        )

        _validate_duka_scope(transfer.duka)
        _validate_actor_scope(actor, transfer.duka)
        if transfer.completed_at is not None:
            raise ValueError("Mzigo huu tayari umeshashughulikiwa.")
        if (
            not transfer.source_location
            or not transfer.destination_location
            or transfer.source_location.duka_id != transfer.duka_id
            or transfer.destination_location.duka_id != transfer.duka_id
        ):
            raise ValueError("Transfer ina locations zisizo za biashara hii.")

        restored = []
        # SURGERY FIX: Tunatumia order_by('bidhaa_id') kuzuia Deadlock
        for item in transfer.items.order_by('bidhaa_id'):
            bidhaa = Bidhaa.objects.select_for_update().get(pk=item.bidhaa_id)
            if bidhaa.duka_id != transfer.duka_id:
                raise ValueError(
                    f"Bidhaa {bidhaa.id} si ya biashara ya transfer hii."
                )

            src, _ = ProductStock.objects.select_for_update().get_or_create(
                bidhaa=bidhaa,
                location=transfer.source_location,
                defaults={"quantity": 0},
            )
            dst, _ = ProductStock.objects.select_for_update().get_or_create(
                bidhaa=bidhaa,
                location=transfer.destination_location,
                defaults={"quantity": 0},
            )
            before = int(src.quantity or 0)
            after = before + int(item.quantity)
            src.quantity = after
            src.save(update_fields=["quantity", "updated_at"])
            dst_qty = int(dst.quantity or 0)
            sync_legacy_total(bidhaa, transfer.duka)

            StockMovement.objects.create(
                duka=transfer.duka,
                bidhaa=bidhaa,
                movement_type="TRANSFER",
                quantity=item.quantity,
                from_location=transfer.destination_location,
                to_location=transfer.source_location,
                from_balance_before=dst_qty,
                from_balance_after=dst_qty,
                to_balance_before=before,
                to_balance_after=after,
                reference=transfer.reference,
                reason=f"Transfer imekataliwa: {reason}",
                notes=f"Rejected by {actor.get_full_name() or actor.username}",
                actor=actor,
                transfer=transfer,
            )
            restored.append(
                {
                    "product": bidhaa.jina_la_bidhaa,
                    "quantity": item.quantity,
                    "source_after": after,
                }
            )

        transfer.completed_at = timezone.now()
        transfer.notes = (
            (transfer.notes or "").strip()
            + (" | " if transfer.notes else "")
            + f"REJECTED by {actor.get_full_name() or actor.username}: {reason}"
        )
        transfer.save(update_fields=["completed_at", "notes"])
        return transfer, restored


def receive_transfer(transfer_id, actor):
    with transaction.atomic():
        transfer = (
            StockTransfer.objects
            .select_for_update()
            .select_related("duka", "source_location", "destination_location")
            .get(pk=transfer_id)
        )
        _validate_duka_scope(transfer.duka)
        _validate_actor_scope(actor, transfer.duka)
        if transfer.completed_at is not None:
            raise ValueError("Mzigo huu tayari umeshapokelewa au ulikataliwa.")
        if not transfer.source_location or not transfer.source_location.is_active:
            raise ValueError("Source ya mzigo haipo au haijawezeshwa.")
        if not transfer.destination_location or not transfer.destination_location.is_active:
            raise ValueError("Destination ya mzigo haipo au haijawezeshwa.")
        if (
            transfer.source_location.duka_id != transfer.duka_id
            or transfer.destination_location.duka_id != transfer.duka_id
        ):
            raise ValueError("Transfer ina locations zisizo za biashara hii.")

        # SURGERY FIX: Tumepanga kwa bidhaa_id kuzuia Deadlocks
        for item in transfer.items.order_by('bidhaa_id'):
            bidhaa = Bidhaa.objects.select_for_update().get(pk=item.bidhaa_id)
            if bidhaa.duka_id != transfer.duka_id:
                raise ValueError(
                    f"Bidhaa {bidhaa.id} si ya biashara ya transfer hii."
                )
            dst, _ = ProductStock.objects.select_for_update().get_or_create(
                bidhaa=bidhaa,
                location=transfer.destination_location,
                defaults={"quantity": 0},
            )
            dst_before = int(dst.quantity or 0)
            received_qty = int(item.quantity or 0)
            if received_qty <= 0:
                raise ValueError(f"{bidhaa.jina_la_bidhaa}: quantity ya mzigo si sahihi.")

            dst.quantity = dst_before + received_qty
            dst.save(update_fields=["quantity", "updated_at"])

            item.destination_before = dst_before
            item.destination_after = int(dst.quantity)
            item.save(update_fields=["destination_before", "destination_after"])

            sync_legacy_total(bidhaa, transfer.duka)

            StockMovement.objects.create(
                duka=transfer.duka,
                bidhaa=bidhaa,
                movement_type="TRANSFER",
                quantity=received_qty,
                from_location=transfer.source_location,
                to_location=transfer.destination_location,
                to_balance_before=dst_before,
                to_balance_after=int(dst.quantity),
                reference=transfer.reference,
                reason=f"Umepokelewa kutoka {transfer.source_location.jina}",
                notes=f"Mzigo umetoka stoo na KUTHIBITISHWA na {actor.username}.",
                actor=actor,
                transfer=transfer,
            )

        transfer.completed_at = timezone.now()
        transfer.received_by = actor
        transfer.save(update_fields=["completed_at", "received_by"])
        return transfer

def perform_adjustments(*, duka, location, items, actor, notes=None):
    _validate_duka_scope(duka)
    _validate_actor_scope(actor, duka)
    if not duka or not location:
        raise ValueError("Location haijapatikana.")
    if location.duka_id != duka.id:
        raise ValueError("Location si ya biashara hii.")
    changed = []
    with transaction.atomic():
        ref = unique_reference("ADJ")
        # SURGERY FIX: Panga (Sort) items kwa ID kuzuia Deadlocks
        sorted_items = sorted(items or [], key=lambda x: int(x.get("id", 0)))
        for item in sorted_items:
            pid = int(item.get("id"))
            qty = int(item.get("qty"))
            if qty <= 0:
                raise ValueError("Adjustment quantity lazima iwe zaidi ya sifuri.")
            direction = (item.get("direction") or "ADD").upper()
            if direction not in {"ADD", "REMOVE"}:
                raise ValueError("Adjustment direction lazima iwe ADD au REMOVE.")
            reason = (item.get("reason") or "").strip()
            bidhaa = Bidhaa.objects.select_for_update().get(pk=pid)
            if bidhaa.duka_id != duka.id:
                raise ValueError(f"Bidhaa {pid} si ya biashara hii.")
            ps, _ = ProductStock.objects.select_for_update().get_or_create(
                bidhaa=bidhaa,
                location=location,
                defaults={"quantity": 0},
            )
            before = int(ps.quantity or 0)
            if direction == "REMOVE":
                if qty > before:
                    raise ValueError(f"{bidhaa.jina_la_bidhaa}: stock {before}, adjustment -{qty} haiwezekani.")
                after = before - qty
                mtype = "DAMAGE" if ("harib" in reason.lower() or "damage" in reason.lower()) else "ADJUSTMENT"
            else:
                after = before + qty
                mtype = "ADJUSTMENT"
            ps.quantity = after
            ps.save(update_fields=["quantity", "updated_at"])
            sync_legacy_total(bidhaa, duka)
            StockMovement.objects.create(
                duka=duka, bidhaa=bidhaa, movement_type=mtype, quantity=qty,
                location=location, balance_before=before, balance_after=after,
                reference=ref, reason=reason or "Stock adjustment", notes=notes, actor=actor,
            )
            changed.append((bidhaa.id, after))
    return ref, changed


def perform_stock_take(*, duka, location, items, actor, notes=None):
    _validate_duka_scope(duka)
    _validate_actor_scope(actor, duka)
    if not duka or not location:
        raise ValueError("Location haijapatikana.")
    if location.duka_id != duka.id:
        raise ValueError("Location si ya biashara hii.")
    with transaction.atomic():
        ref = unique_reference("ST")
        take = StockTake.objects.create(
            duka=duka,
            location=location,
            reference=ref,
            status="COMPLETED",
            notes=notes,
            started_by=actor,
            completed_by=actor,
            completed_at=timezone.now(),
        )
        # SURGERY FIX: Panga (Sort) items kwa ID kuzuia Deadlocks
        sorted_items = sorted(items or [], key=lambda x: int(x.get("id", 0)))
        seen_product_ids = set()
        for item in sorted_items:
            pid = int(item.get("id"))
            if pid in seen_product_ids:
                raise ValueError(f"Bidhaa {pid} imejirudia ndani ya Stock Take moja.")
            seen_product_ids.add(pid)
            raw_physical = item.get("physical")
            try:
                physical = int(raw_physical or 0)
            except (TypeError, ValueError):
                raise ValueError("Physical quantity lazima iwe namba halali.")
            if physical < 0:
                raise ValueError("Physical quantity haiwezi kuwa chini ya sifuri.")
            bidhaa = Bidhaa.objects.select_for_update().get(pk=pid)
            if bidhaa.duka_id != duka.id:
                raise ValueError(f"Bidhaa {pid} si ya biashara hii.")
            ps, _ = ProductStock.objects.select_for_update().get_or_create(
                bidhaa=bidhaa,
                location=location,
                defaults={"quantity": 0},
            )
            before = int(ps.quantity or 0)
            variance = physical - before
            ps.quantity = physical
            ps.save(update_fields=["quantity", "updated_at"])
            sync_legacy_total(bidhaa, duka)
            StockTakeItem.objects.create(
                stock_take=take,
                bidhaa=bidhaa,
                system_quantity=before,
                physical_quantity=physical,
                variance=variance,
                notes=(item.get("notes") or "").strip() or None,
            )
            if variance != 0:
                StockMovement.objects.create(
                    duka=duka, bidhaa=bidhaa, movement_type="STOCK_TAKE", quantity=abs(variance),
                    location=location, balance_before=before, balance_after=physical,
                    reference=ref, reason="Stock Take Variance", notes=notes, actor=actor, stock_take=take,
                )
        return take


def get_last_verified(bidhaa, location):
    item = (
        StockTakeItem.objects
        .filter(stock_take__location=location, stock_take__status="COMPLETED", bidhaa=bidhaa)
        .select_related("stock_take")
        .order_by("-stock_take__completed_at", "-stock_take_id")
        .first()
    )
    if not item:
        return None
    return {
        "quantity": int(item.physical_quantity),
        "date": timezone.localtime(item.stock_take.completed_at or item.stock_take.created_at),
        "reference": item.stock_take.reference,
        "verified_by": item.stock_take.completed_by.username if item.stock_take.completed_by else "Mfumo",
    }