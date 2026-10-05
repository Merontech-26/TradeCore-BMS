from decimal import Decimal
from datetime import timedelta
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.utils import timezone

from .inventory_services import (
    add_stock,
    current_quantity,
    ensure_inventory_locations,
    perform_adjustments,
    perform_stock_take,
    perform_transfer,
    receive_transfer,
    reject_transfer,
)
from .models import (
    Bidhaa,
    BusinessSubscription,
    PaymentTransaction,
    Duka,
    Kategoria,
    Mauzo,
    ProductStock,
    StockLocation,
    StockMovement,
    StockTakeItem,
    StockTransferItem,
)
from .tenant import tenant_scope


class TradeCoreInventoryServiceTests(TestCase):
    """Regression tests for the critical stock/tenant workflows."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner_test",
            password="test-password",
        )
        self.duka = Duka.objects.create(
            mwenye_duka=self.owner,
            jina_la_duka="Test Shop",
            inventory_location_mode=True,
        )
        self.category = Kategoria.objects.create(
            jina="Test Category",
            business_type="GENERAL",
        )
        self.product = Bidhaa.objects.create(
            duka=self.duka,
            kategoria=self.category,
            jina_la_bidhaa="Test Product",
            bei_ya_kununulia=Decimal("1000.00"),
            bei_ya_kuuzia=Decimal("1500.00"),
            idadi_stoo=0,
        )

        with tenant_scope(self.duka.id):
            self.store, self.shop = ensure_inventory_locations(self.duka)

    def test_location_bootstrap_copies_legacy_stock_once(self):
        """Legacy aggregate stock is bootstrapped into Store and not duplicated."""
        self.product.idadi_stoo = 12
        self.product.save(update_fields=["idadi_stoo"])

        # Existing location rows mean a second ensure call must not add stock.
        with tenant_scope(self.duka.id):
            ensure_inventory_locations(self.duka)

        # Bootstrap already happened with zero, so changing legacy stock later
        # must not silently create another ProductStock row.
        ps_rows = ProductStock.all_objects.filter(
            bidhaa=self.product,
            location=self.store,
        )
        self.assertEqual(ps_rows.count(), 1)
        self.assertEqual(ps_rows.get().quantity, 0)

    def test_add_stock_updates_location_and_creates_ledger(self):
        with tenant_scope(self.duka.id):
            movement, location_after, total = add_stock(
                duka=self.duka,
                bidhaa=self.product,
                location=self.store,
                quantity=8,
                actor=self.owner,
                reference="TEST-STOCK-IN-001",
                reason="Test stock in",
                supplier="Supplier A",
                source_ref="GRN-001",
            )

        self.assertEqual(location_after, 8)
        self.assertEqual(total, 8)
        self.assertEqual(current_quantity(self.product, self.store), 8)
        self.assertEqual(
            StockMovement.all_objects.filter(
                duka=self.duka,
                bidhaa=self.product,
                reference="TEST-STOCK-IN-001",
            ).count(),
            1,
        )
        self.assertEqual(
            self.product.mizigo_iliyoingia.filter(reference="GRN-001").count(),
            1,
        )

    def test_adjustment_rejects_invalid_direction_and_zero_quantity(self):
        with tenant_scope(self.duka.id):
            with self.assertRaises(ValueError):
                perform_adjustments(
                    duka=self.duka,
                    location=self.store,
                    items=[{"id": self.product.id, "qty": 2, "direction": "BAD"}],
                    actor=self.owner,
                )

            with self.assertRaises(ValueError):
                perform_adjustments(
                    duka=self.duka,
                    location=self.store,
                    items=[{"id": self.product.id, "qty": 0, "direction": "ADD"}],
                    actor=self.owner,
                )

        self.assertFalse(
            StockMovement.all_objects.filter(
                duka=self.duka,
                bidhaa=self.product,
                movement_type__in=["ADJUSTMENT", "DAMAGE"],
            ).exists()
        )

    def test_stock_take_allows_zero_and_records_variance(self):
        with tenant_scope(self.duka.id):
            add_stock(
                duka=self.duka,
                bidhaa=self.product,
                location=self.store,
                quantity=10,
                actor=self.owner,
                reference="TEST-STOCK-IN-002",
            )
            take = perform_stock_take(
                duka=self.duka,
                location=self.store,
                items=[{"id": self.product.id, "physical": 6}],
                actor=self.owner,
                notes="Cycle count",
            )

        ps = ProductStock.all_objects.get(
            bidhaa=self.product,
            location=self.store,
        )
        item = StockTakeItem.objects.get(stock_take=take, bidhaa=self.product)

        self.assertEqual(ps.quantity, 6)
        self.assertEqual(item.system_quantity, 10)
        self.assertEqual(item.physical_quantity, 6)
        self.assertEqual(item.variance, -4)

    def test_stock_take_rejects_duplicate_product_in_one_take(self):
        with tenant_scope(self.duka.id):
            with self.assertRaises(ValueError):
                perform_stock_take(
                    duka=self.duka,
                    location=self.store,
                    items=[
                        {"id": self.product.id, "physical": 2},
                        {"id": self.product.id, "physical": 3},
                    ],
                    actor=self.owner,
                )

        self.assertEqual(StockTakeItem.objects.count(), 0)

    def test_transfer_is_pending_then_receive_moves_destination_stock(self):
        with tenant_scope(self.duka.id):
            add_stock(
                duka=self.duka,
                bidhaa=self.product,
                location=self.store,
                quantity=10,
                actor=self.owner,
                reference="TEST-STOCK-IN-003",
            )
            transfer = perform_transfer(
                duka=self.duka,
                source=self.store,
                destination=self.shop,
                items=[{"id": self.product.id, "qty": 4}],
                actor=self.owner,
                reason_code="RESTOCK",
                reason_text="Restock shop",
            )

        self.assertIsNone(transfer.completed_at)
        self.assertEqual(
            ProductStock.all_objects.get(
                bidhaa=self.product,
                location=self.store,
            ).quantity,
            6,
        )
        self.assertEqual(
            ProductStock.all_objects.get(
                bidhaa=self.product,
                location=self.shop,
            ).quantity,
            0,
        )

        with tenant_scope(self.duka.id):
            received = receive_transfer(transfer.id, self.owner)

        self.assertIsNotNone(received.completed_at)
        self.assertEqual(
            ProductStock.all_objects.get(
                bidhaa=self.product,
                location=self.shop,
            ).quantity,
            4,
        )

    def test_transfer_normalizes_duplicate_product_entries(self):
        with tenant_scope(self.duka.id):
            add_stock(
                duka=self.duka,
                bidhaa=self.product,
                location=self.store,
                quantity=10,
                actor=self.owner,
                reference="TEST-STOCK-IN-004",
            )
            transfer = perform_transfer(
                duka=self.duka,
                source=self.store,
                destination=self.shop,
                items=[
                    {"id": self.product.id, "qty": 2},
                    {"id": self.product.id, "qty": 3},
                ],
                actor=self.owner,
            )

        self.assertEqual(
            StockTransferItem.objects.filter(transfer=transfer).count(),
            1,
        )
        transfer_item = StockTransferItem.objects.get(transfer=transfer)
        self.assertEqual(transfer_item.quantity, 5)

    def test_transfer_rolls_back_when_one_item_cannot_be_fulfilled(self):
        second = Bidhaa.objects.create(
            duka=self.duka,
            kategoria=self.category,
            jina_la_bidhaa="Second Product",
            bei_ya_kununulia=Decimal("2000.00"),
            bei_ya_kuuzia=Decimal("3000.00"),
            idadi_stoo=0,
        )

        with tenant_scope(self.duka.id):
            add_stock(
                duka=self.duka,
                bidhaa=self.product,
                location=self.store,
                quantity=5,
                actor=self.owner,
                reference="TEST-STOCK-IN-005",
            )

            with self.assertRaises(ValueError):
                perform_transfer(
                    duka=self.duka,
                    source=self.store,
                    destination=self.shop,
                    items=[
                        {"id": self.product.id, "qty": 2},
                        {"id": second.id, "qty": 99},
                    ],
                    actor=self.owner,
                )

        self.assertEqual(
            ProductStock.all_objects.get(
                bidhaa=self.product,
                location=self.store,
            ).quantity,
            5,
        )
        self.assertFalse(
            StockTransferItem.objects.filter(bidhaa=self.product).exists()
        )

    def test_reject_transfer_restores_source_stock(self):
        with tenant_scope(self.duka.id):
            add_stock(
                duka=self.duka,
                bidhaa=self.product,
                location=self.store,
                quantity=9,
                actor=self.owner,
                reference="TEST-STOCK-IN-006",
            )
            transfer = perform_transfer(
                duka=self.duka,
                source=self.store,
                destination=self.shop,
                items=[{"id": self.product.id, "qty": 4}],
                actor=self.owner,
            )
            rejected, restored = reject_transfer(
                transfer.id,
                self.owner,
                reason="Destination imekataa mzigo",
            )

        self.assertIsNotNone(rejected.completed_at)
        self.assertEqual(restored[0]["quantity"], 4)
        self.assertEqual(
            ProductStock.all_objects.get(
                bidhaa=self.product,
                location=self.store,
            ).quantity,
            9,
        )

    def test_sale_deducts_stock_and_preserves_historical_prices(self):
        with tenant_scope(self.duka.id):
            add_stock(
                duka=self.duka,
                bidhaa=self.product,
                location=self.store,
                quantity=7,
                actor=self.owner,
                reference="TEST-STOCK-IN-007",
            )

            with self.assertRaises(ValueError):
                Mauzo.objects.create(
                    bidhaa=self.product,
                    duka=self.duka,
                    stock_location=self.shop,
                    muuzaji=self.owner,
                    idadi=2,
                )

        # Re-seed shop stock through the service, then create the valid sale.
        with tenant_scope(self.duka.id):
            add_stock(
                duka=self.duka,
                bidhaa=self.product,
                location=self.shop,
                quantity=3,
                actor=self.owner,
                reference="TEST-STOCK-IN-008",
            )
            sale = Mauzo.objects.create(
                bidhaa=self.product,
                duka=self.duka,
                stock_location=self.shop,
                muuzaji=self.owner,
                idadi=2,
            )

        sale.refresh_from_db()
        self.assertEqual(sale.bei_ya_kuuzia_stoo, Decimal("1500.00"))
        self.assertEqual(sale.bei_ya_kununulia_stoo, Decimal("1000.00"))
        self.assertEqual(
            ProductStock.all_objects.get(
                bidhaa=self.product,
                location=self.shop,
            ).quantity,
            1,
        )

    def test_cross_tenant_service_access_is_rejected(self):
        other_owner = User.objects.create_user(
            username="other_owner_test",
            password="test-password",
        )
        other_duka = Duka.objects.create(
            mwenye_duka=other_owner,
            jina_la_duka="Other Shop",
            inventory_location_mode=True,
        )

        with self.assertRaises(ValueError):
            with tenant_scope(other_duka.id):
                ensure_inventory_locations(self.duka)


class TradeCoreModelIntegrityTests(TestCase):
    """Regression tests for model-level tenant and data integrity guards."""

    def setUp(self):
        owner = User.objects.create_user(username="model_owner", password="test-password")
        self.duka = Duka.objects.create(
            mwenye_duka=owner,
            jina_la_duka="Model Shop",
            inventory_location_mode=True,
        )
        self.owner = owner

        category = Kategoria.objects.create(
            jina="Model Category",
            business_type="GENERAL",
        )
        self.product = Bidhaa.objects.create(
            duka=self.duka,
            kategoria=category,
            jina_la_bidhaa="Model Product",
            bei_ya_kununulia=Decimal("500.00"),
            bei_ya_kuuzia=Decimal("900.00"),
        )

    def test_product_barcode_is_unique_per_business(self):
        Bidhaa.objects.create(
            duka=self.duka,
            jina_la_bidhaa="Another Product",
            bei_ya_kununulia=Decimal("300.00"),
            bei_ya_kuuzia=Decimal("600.00"),
            barcode="123456789",
        )
        with self.assertRaises(IntegrityError):
            Bidhaa.objects.create(
                duka=self.duka,
                jina_la_bidhaa="Duplicate Barcode",
                bei_ya_kununulia=Decimal("400.00"),
                bei_ya_kuuzia=Decimal("700.00"),
                barcode="123456789",
            )

    def test_product_stock_cannot_mix_businesses(self):
        other_owner = User.objects.create_user(
            username="model_other_owner",
            password="test-password",
        )
        other_duka = Duka.objects.create(
            mwenye_duka=other_owner,
            jina_la_duka="Other Model Shop",
            inventory_location_mode=True,
        )
        foreign_location = StockLocation.objects.create(
            duka=other_duka,
            jina="Other Shop",
            code="other-shop",
            aina="SHOP",
            is_sales_location=True,
        )

        with self.assertRaises(ValueError):
            ProductStock.objects.create(
                bidhaa=self.product,
                location=foreign_location,
                quantity=1,
            )


class TradeCorePaymentTests(TestCase):
    """Regression coverage for Premium payment initiation and activation."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username="payment_owner",
            email="payment@example.com",
            password="test-password",
        )
        self.subscription = BusinessSubscription.objects.get(user=self.owner)

    def test_premium_activation_creates_one_calendar_month_entitlement(self):
        started = timezone.now().replace(microsecond=0)
        self.subscription.activate_premium(payment_time=started, months=1)
        self.subscription.save()
        self.subscription.refresh_from_db()

        self.assertEqual(self.subscription.plan_type, "PREMIUM")
        self.assertTrue(self.subscription.is_active)
        self.assertEqual(self.subscription.premium_start_date, started)
        self.assertIsNotNone(self.subscription.premium_end_date)
        self.assertGreater(self.subscription.premium_end_date, self.subscription.premium_start_date)

        expected_month_index = started.month  # 0-based next-month offset from the model algorithm
        expected_year = started.year + (expected_month_index // 12)
        expected_month = (expected_month_index % 12) + 1
        self.assertEqual(self.subscription.premium_end_date.year, expected_year)
        self.assertEqual(self.subscription.premium_end_date.month, expected_month)

    @override_settings(FLW_SECRET_KEY="test-secret")
    @patch("pos_app.views.requests.post")
    def test_mobile_payment_initiation_creates_pending_transaction(self, mock_post):
        class FakeResponse:
            status_code = 200

            def json(self):
                return {
                    "status": "success",
                    "message": "Charge initiated",
                    "data": {"id": 12345, "tx_ref": self.tx_ref, "status": "pending"},
                }

        def fake_post(url, headers=None, json=None, timeout=None):
            response = FakeResponse()
            response.tx_ref = json["tx_ref"]
            return response

        mock_post.side_effect = fake_post
        self.client.login(username="payment_owner", password="test-password")
        response = self.client.post(
            "/billing/mobile/initiate/",
            {"network": "VODAFONE", "phone_number": "0712345678"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["state"], "pending")
        payment = PaymentTransaction.objects.get(user=self.owner)
        self.assertEqual(payment.status, "PENDING")
        self.assertEqual(payment.phone_number, "255712345678")
        self.assertEqual(payment.network, "VODAFONE")
        self.assertEqual(payment.gateway_transaction_id, "12345")

    @override_settings(FLW_SECRET_HASH="test-hash")
    @patch("pos_app.views._verify_flutterwave_transaction")
    def test_webhook_verification_activates_premium_once(self, mock_verify):
        payment = PaymentTransaction.objects.create(
            user=self.owner,
            subscription=self.subscription,
            tx_ref="TC-PREM-TEST-001",
            amount=Decimal("20000.00"),
            currency="TZS",
            method="MOBILE_MONEY",
            network="VODAFONE",
            phone_number="255712345678",
            status="PENDING",
            gateway_transaction_id="12345",
        )
        successful = {
            "status": "success",
            "data": {
                "id": 12345,
                "tx_ref": "TC-PREM-TEST-001",
                "amount": 20000,
                "currency": "TZS",
                "status": "successful",
                "flw_ref": "FLW-TEST-001",
            },
        }
        mock_verify.return_value = successful

        body = json.dumps({
            "event": "charge.completed",
            "data": {
                "id": 12345,
                "tx_ref": payment.tx_ref,
                "amount": 20000,
                "currency": "TZS",
                "status": "successful",
            },
        })
        response = self.client.post(
            "/billing/flutterwave/webhook/",
            data=body,
            content_type="application/json",
            HTTP_VERIF_HASH="test-hash",
        )
        self.assertEqual(response.status_code, 200)

        payment.refresh_from_db()
        self.subscription.refresh_from_db()
        self.assertEqual(payment.status, "SUCCESSFUL")
        self.assertEqual(self.subscription.plan_type, "PREMIUM")
        self.assertTrue(self.subscription.is_active)

        response = self.client.post(
            "/billing/flutterwave/webhook/",
            data=body,
            content_type="application/json",
            HTTP_VERIF_HASH="test-hash",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PaymentTransaction.objects.get(pk=payment.pk).status, "SUCCESSFUL")

    @override_settings(FLW_SECRET_HASH="test-hash")
    @patch("pos_app.views._verify_flutterwave_transaction")
    def test_webhook_does_not_activate_when_amount_is_wrong(self, mock_verify):
        payment = PaymentTransaction.objects.create(
            user=self.owner,
            subscription=self.subscription,
            tx_ref="TC-PREM-TEST-002",
            amount=Decimal("20000.00"),
            currency="TZS",
            method="MOBILE_MONEY",
            network="TIGO",
            phone_number="255712345678",
            status="PENDING",
            gateway_transaction_id="12346",
        )
        mock_verify.return_value = {
            "status": "success",
            "data": {
                "id": 12346,
                "tx_ref": payment.tx_ref,
                "amount": 5000,
                "currency": "TZS",
                "status": "successful",
            },
        }
        body = json.dumps({"event": "charge.completed", "data": {"id": 12346, "tx_ref": payment.tx_ref}})
        response = self.client.post(
            "/billing/flutterwave/webhook/",
            data=body,
            content_type="application/json",
            HTTP_VERIF_HASH="test-hash",
        )
        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.subscription.refresh_from_db()
        self.assertEqual(payment.status, "FAILED")
        self.assertEqual(self.subscription.plan_type, "TRIAL")


class TradeCorePremiumCommercialBillingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="commercial_owner",
            email="commercial@example.com",
            password="test-password",
        )
        self.subscription = BusinessSubscription.objects.get(user=self.owner)

    def test_pricing_is_20k_until_six_months(self):
        from .views import calculate_premium_pricing

        self.assertEqual(calculate_premium_pricing(1)["total"], Decimal("20000.00"))
        self.assertEqual(calculate_premium_pricing(3)["total"], Decimal("60000.00"))
        self.assertEqual(calculate_premium_pricing(6)["total"], Decimal("120000.00"))

    def test_pricing_is_15k_per_month_after_six_months(self):
        from .views import calculate_premium_pricing

        pricing = calculate_premium_pricing(12)
        self.assertEqual(pricing["unit_price"], Decimal("15000.00"))
        self.assertEqual(pricing["total"], Decimal("180000.00"))
        self.assertEqual(pricing["discount"], Decimal("60000.00"))

    def test_pricing_rejects_invalid_duration(self):
        from .views import calculate_premium_pricing

        with self.assertRaises(ValueError):
            calculate_premium_pricing(0)

        with self.assertRaises(ValueError):
            calculate_premium_pricing(61)

    def test_premium_can_be_renewed_for_twelve_calendar_months(self):
        started = timezone.now()
        self.subscription.activate_premium(payment_time=started, months=12)
        self.subscription.save()
        self.subscription.refresh_from_db()

        self.assertEqual(self.subscription.plan_type, "PREMIUM")
        self.assertEqual(
            self.subscription.premium_end_date.year,
            self.subscription.premium_start_date.year + 1,
        )
        self.assertEqual(
            self.subscription.premium_end_date.month,
            self.subscription.premium_start_date.month,
        )

    @override_settings(FLW_SECRET_KEY="test-secret")
    @patch("pos_app.views.requests.post")
    def test_mobile_payment_uses_server_calculated_long_term_amount(self, mock_post):
        class FakeResponse:
            status_code = 200

            def json(self):
                return {
                    "status": "success",
                    "message": "Charge initiated",
                    "data": {"id": 67890, "tx_ref": self.tx_ref, "status": "pending"},
                }

        def fake_post(url, headers=None, json=None, timeout=None):
            response = FakeResponse()
            response.tx_ref = json["tx_ref"]
            self.assertEqual(json["amount"], "180000.00")
            self.assertEqual(json["meta"]["billing_months"], 12)
            self.assertEqual(json["meta"]["unit_price"], "15000.00")
            return response

        mock_post.side_effect = fake_post
        self.client.login(username="commercial_owner", password="test-password")

        response = self.client.post(
            "/billing/mobile/initiate/",
            {
                "network": "VODAFONE",
                "phone_number": "0712345678",
                "months": "12",
            },
        )

        self.assertEqual(response.status_code, 200)
        payment = PaymentTransaction.objects.get(user=self.owner)
        self.assertEqual(payment.amount, Decimal("180000.00"))
        self.assertEqual(payment.gateway_payload["_tradecore"]["billing_months"], 12)

    def test_expired_trial_keeps_data_and_blocks_write_requests(self):
        self.subscription.trial_start_date = timezone.now() - timedelta(days=31)
        self.subscription.plan_type = "TRIAL"
        self.subscription.is_active = True
        self.subscription.save()

        self.client.login(username="commercial_owner", password="test-password")

        read_response = self.client.get("/")
        self.assertEqual(read_response.status_code, 200)

        write_response = self.client.post("/", {})
        self.assertEqual(write_response.status_code, 302)
        self.assertIn("/billing/", write_response.url)

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan_type, "TRIAL")
        self.assertTrue(self.subscription.is_active)
