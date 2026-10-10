"""Tests for the M-Pesa Daraja payment integration.

Daraja HTTP calls are mocked — no real money, no network.
"""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from payments.models import (
    PaymentConfiguration,
    PaymentStatusLog,
    PaymentTransaction,
)
from payments.mpesa_service import MpesaApiError, MpesaService
from properties.models import Property

User = get_user_model()

STK_OK = {
    "MerchantRequestID": "mr_test_1",
    "CheckoutRequestID": "wsq_test_1",
    "ResponseCode": "0",
    "ResponseDescription": "Success. Request accepted for processing",
    "CustomerMessage": "Success. Request accepted for processing",
}


def callback_payload(checkout_id, result_code=0, amount=500,
                     receipt="QGH12345CD", desc="Success"):
    items = []
    if amount is not None:
        items.append({"Name": "Amount", "Value": amount})
    if receipt is not None:
        items.append({"Name": "MpesaReceiptNumber", "Value": receipt})
    items.append({"Name": "TransactionDate", "Value": 20260101120000})
    return {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "mr_test_1",
                "CheckoutRequestID": checkout_id,
                "ResultCode": result_code,
                "ResultDesc": desc,
                "CallbackMetadata": {"Item": items},
            }
        }
    }


class PaymentTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.landlord = User.objects.create_user(
            username="mp_landlord",
            email="mp_landlord@example.com",
            password="strongpass123",
            role=User.Role.LANDLORD,
            business_name="M-Pesa Test Homes",
        )
        self.landlord.accepts_payments = True
        self.landlord.save()
        self.tenant = User.objects.create_user(
            username="mp_tenant",
            email="mp_tenant@example.com",
            password="strongpass123",
        )
        self.admin = User.objects.create_superuser(
            username="mp_admin",
            email="mp_admin@example.com",
            password="strongpass123",
        )

        self.property = Property.objects.create(
            owner=self.landlord,
            title="M-Pesa Test Apartment",
            description="An apartment used for payment integration tests.",
            property_type=Property.PropertyType.APARTMENT,
            county="Nairobi",
            estate="Roysambu",
            rent=18000,
            bedrooms=2,
            bathrooms=1.0,
        )

        self.config = PaymentConfiguration.get_solo()
        self.config.enabled_purposes = [
            "listing_fee",
            "viewing_fee",
            "rental_payment",
        ]
        self.config.rental_payments_enabled = True
        self.config.save()

        self.landlord_token = Token.objects.create(user=self.landlord)
        self.tenant_token = Token.objects.create(user=self.tenant)
        self.admin_token = Token.objects.create(user=self.admin)

        self.stk_url = reverse("payments:stk-push")
        self.callback_url = reverse("payments:payment-callback")
        self.history_url = reverse("payments:payment-history")
        self.config_url = reverse("payments:payment-config")

    def auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def clear_auth(self):
        self.client.credentials()


class StkPushValidationTests(PaymentTestCase):
    def test_valid_phone_formats(self):
        self.auth(self.tenant_token)
        for phone in ("0712345678", "+254712345678", "254712345678"):
            PaymentTransaction.objects.all().delete()
            with patch.object(MpesaService, "stk_push", return_value=STK_OK):
                response = self.client.post(self.stk_url, {
                    "purpose": "viewing_fee",
                    "amount": 500,
                    "phone_number": phone,
                    "property_id": self.property.id,
                })
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            self.assertEqual(response.data["phone_number"], "254712345678")

    def test_invalid_phone_numbers(self):
        self.auth(self.tenant_token)
        for phone in ("12345", "071234567", "abc", "0800000000", "0112345678"):
            response = self.client.post(self.stk_url, {
                "purpose": "viewing_fee",
                "amount": 500,
                "phone_number": phone,
                "property_id": self.property.id,
            })
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("phone_number", response.data["errors"])

    def test_invalid_amounts(self):
        self.auth(self.tenant_token)
        for amount in (0, -100, 999999999, "abc"):
            response = self.client.post(self.stk_url, {
                "purpose": "viewing_fee",
                "amount": amount,
                "phone_number": "0712345678",
                "property_id": self.property.id,
            })
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("amount", response.data["errors"])

    def test_wrong_amount_for_purpose(self):
        self.auth(self.tenant_token)
        response = self.client.post(self.stk_url, {
            "purpose": "viewing_fee",
            "amount": 999,
            "phone_number": "0712345678",
            "property_id": self.property.id,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("amount", response.data["errors"])

    def test_missing_purpose_or_property(self):
        self.auth(self.tenant_token)
        response = self.client.post(self.stk_url, {
            "purpose": "viewing_fee",
            "amount": 500,
            "phone_number": "0712345678",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_purpose(self):
        self.auth(self.tenant_token)
        response = self.client.post(self.stk_url, {
            "purpose": "donation",
            "amount": 500,
            "phone_number": "0712345678",
            "property_id": self.property.id,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_disabled_purpose_rejected(self):
        self.config.enabled_purposes = ["viewing_fee"]
        self.config.save()
        self.auth(self.landlord_token)
        response = self.client.post(self.stk_url, {
            "purpose": "listing_fee",
            "amount": 1000,
            "phone_number": "0712345678",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("purpose", response.data["errors"])


class StkPushAuthorizationTests(PaymentTestCase):
    def test_anonymous_cannot_pay(self):
        self.clear_auth()
        response = self.client.post(self.stk_url, {
            "purpose": "viewing_fee",
            "amount": 500,
            "phone_number": "0712345678",
            "property_id": self.property.id,
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tenant_cannot_pay_listing_fee(self):
        self.auth(self.tenant_token)
        response = self.client.post(self.stk_url, {
            "purpose": "listing_fee",
            "amount": 1000,
            "phone_number": "0712345678",
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_landlord_cannot_pay_own_rent(self):
        self.auth(self.landlord_token)
        response = self.client.post(self.stk_url, {
            "purpose": "rental_payment",
            "amount": 18000,
            "phone_number": "0712345678",
            "property_id": self.property.id,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_landlord_cannot_book_own_viewing(self):
        self.auth(self.landlord_token)
        response = self.client.post(self.stk_url, {
            "purpose": "viewing_fee",
            "amount": 500,
            "phone_number": "0712345678",
            "property_id": self.property.id,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rental_payment_requires_landlord_authorization(self):
        self.landlord.accepts_payments = False
        self.landlord.save()
        self.auth(self.tenant_token)
        response = self.client.post(self.stk_url, {
            "purpose": "rental_payment",
            "amount": 18000,
            "phone_number": "0712345678",
            "property_id": self.property.id,
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rental_payment_requires_master_switch(self):
        self.config.rental_payments_enabled = False
        self.config.save()
        self.auth(self.tenant_token)
        response = self.client.post(self.stk_url, {
            "purpose": "rental_payment",
            "amount": 18000,
            "phone_number": "0712345678",
            "property_id": self.property.id,
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_nonexistent_property(self):
        self.auth(self.tenant_token)
        response = self.client.post(self.stk_url, {
            "purpose": "viewing_fee",
            "amount": 500,
            "phone_number": "0712345678",
            "property_id": 99999,
        })
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class StkPushFlowTests(PaymentTestCase):
    def test_successful_initiation_is_processing_not_success(self):
        self.auth(self.tenant_token)
        with patch.object(MpesaService, "stk_push", return_value=STK_OK):
            response = self.client.post(self.stk_url, {
                "purpose": "viewing_fee",
                "amount": 500,
                "phone_number": "0712345678",
                "property_id": self.property.id,
            })
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["status"], "processing")
        self.assertEqual(response.data["checkout_request_id"], "wsq_test_1")

        payment = PaymentTransaction.objects.get(
            reference=response.data["reference"]
        )
        self.assertEqual(payment.status, PaymentTransaction.Status.PROCESSING)
        self.assertFalse(payment.mpesa_receipt_number)

    def test_stk_push_api_error_marks_failed(self):
        self.auth(self.tenant_token)
        with patch.object(
            MpesaService, "stk_push",
            side_effect=MpesaApiError("Daraja rejected", "Please try again."),
        ):
            response = self.client.post(self.stk_url, {
                "purpose": "viewing_fee",
                "amount": 500,
                "phone_number": "0712345678",
                "property_id": self.property.id,
            })
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        payment = PaymentTransaction.objects.get(
            reference=response.data["transaction"]["reference"]
        )
        self.assertEqual(payment.status, PaymentTransaction.Status.FAILED)
        self.assertEqual(payment.failure_message, "Please try again.")

    def test_missing_credentials_returns_service_unavailable(self):
        self.auth(self.tenant_token)
        # MPESA_* settings are empty in tests → configuration error.
        response = self.client.post(self.stk_url, {
            "purpose": "viewing_fee",
            "amount": 500,
            "phone_number": "0712345678",
            "property_id": self.property.id,
        })
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("not configured", response.data["errors"]["detail"])

    def test_timeout_marks_failed_with_safe_message(self):
        self.auth(self.tenant_token)
        with patch.object(
            MpesaService, "get_access_token",
            side_effect=MpesaApiError(
                "Daraja network error: timeout",
                "Payment service is temporarily unreachable. Please try again in a few minutes.",
            ),
        ):
            response = self.client.post(self.stk_url, {
                "purpose": "viewing_fee",
                "amount": 500,
                "phone_number": "0712345678",
                "property_id": self.property.id,
            })
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        payment = PaymentTransaction.objects.get(
            reference=response.data["transaction"]["reference"]
        )
        self.assertEqual(payment.status, PaymentTransaction.Status.FAILED)
        # Sanitized message must not leak provider internals.
        self.assertNotIn("Daraja network error", payment.failure_message)

    def test_duplicate_payment_returns_existing_transaction(self):
        self.auth(self.tenant_token)
        payload = {
            "purpose": "viewing_fee",
            "amount": 500,
            "phone_number": "0712345678",
            "property_id": self.property.id,
        }
        with patch.object(MpesaService, "stk_push", return_value=STK_OK):
            first = self.client.post(self.stk_url, payload)
            second = self.client.post(self.stk_url, payload)
        self.assertEqual(first.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["reference"], second.data["reference"])
        self.assertEqual(
            PaymentTransaction.objects.filter(
                user=self.tenant, purpose="viewing_fee"
            ).count(),
            1,
        )

    def test_database_constraint_prevents_duplicate_active_payments(self):
        from django.db import IntegrityError, transaction

        payment = PaymentTransaction.objects.create(
            user=self.tenant,
            property=self.property,
            purpose="viewing_fee",
            amount=500,
            phone_number="254712345678",
            status=PaymentTransaction.Status.PROCESSING,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PaymentTransaction.objects.create(
                    user=self.tenant,
                    property=self.property,
                    purpose="viewing_fee",
                    amount=500,
                    phone_number="254712345678",
                    status=PaymentTransaction.Status.PROCESSING,
                )
        # A terminal previous payment does not block a new one.
        payment.status = PaymentTransaction.Status.FAILED
        payment.save()
        PaymentTransaction.objects.create(
            user=self.tenant,
            property=self.property,
            purpose="viewing_fee",
            amount=500,
            phone_number="254712345678",
            status=PaymentTransaction.Status.PROCESSING,
        )


class CallbackTests(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.payment = PaymentTransaction.objects.create(
            user=self.tenant,
            property=self.property,
            purpose="viewing_fee",
            amount=500,
            phone_number="254712345678",
            checkout_request_id="wsq_callback_1",
            merchant_request_id="mr_callback_1",
            status=PaymentTransaction.Status.PROCESSING,
        )

    def test_successful_callback(self):
        response = self.client.post(self.callback_url, callback_payload(
            "wsq_callback_1", result_code=0, amount=500
        ), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentTransaction.Status.SUCCESSFUL)
        self.assertEqual(self.payment.mpesa_receipt_number, "QGH12345CD")
        self.assertEqual(
            self.payment.status_logs.filter(
                to_status=PaymentTransaction.Status.SUCCESSFUL
            ).count(),
            1,
        )

    def test_failed_callback(self):
        response = self.client.post(self.callback_url, callback_payload(
            "wsq_callback_1", result_code=1, amount=None,
            receipt=None, desc="Insufficient funds",
        ), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentTransaction.Status.FAILED)
        self.assertIn("Insufficient funds", self.payment.failure_message)

    def test_cancelled_callback(self):
        response = self.client.post(self.callback_url, callback_payload(
            "wsq_callback_1", result_code=1032, amount=None, receipt=None
        ), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentTransaction.Status.CANCELLED)

    def test_timeout_callback_expires(self):
        response = self.client.post(self.callback_url, callback_payload(
            "wsq_callback_1", result_code=1037, amount=None, receipt=None
        ), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentTransaction.Status.EXPIRED)

    def test_duplicate_callback_is_idempotent(self):
        payload = callback_payload("wsq_callback_1", result_code=0, amount=500)
        first = self.client.post(self.callback_url, payload, format="json")
        second = self.client.post(self.callback_url, payload, format="json")
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentTransaction.Status.SUCCESSFUL)
        # Only one successful status log — no reprocessing.
        self.assertEqual(
            self.payment.status_logs.filter(
                to_status=PaymentTransaction.Status.SUCCESSFUL
            ).count(),
            1,
        )

    def test_callback_amount_mismatch_rejected(self):
        response = self.client.post(self.callback_url, callback_payload(
            "wsq_callback_1", result_code=0, amount=999
        ), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentTransaction.Status.PROCESSING)

    def test_unknown_checkout_request_id(self):
        response = self.client.post(self.callback_url, callback_payload(
            "wsq_unknown_999", result_code=0, amount=500
        ), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Unknown", response.data["ResultDesc"])

    def test_invalid_callback_structure(self):
        for bad in ({}, {"Body": {}}, {"Body": {"stkCallback": {}}},
                    {"Body": {"stkCallback": {
                        "CheckoutRequestID": "x",
                        "ResultCode": "not-a-number",
                    }}}):
            response = self.client.post(self.callback_url, bad, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_callback_cannot_downgrade_successful_payment(self):
        self.payment.status = PaymentTransaction.Status.SUCCESSFUL
        self.payment.mpesa_receipt_number = "ORIGINAL"
        self.payment.save()
        response = self.client.post(self.callback_url, callback_payload(
            "wsq_callback_1", result_code=1, amount=None, receipt=None
        ), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentTransaction.Status.SUCCESSFUL)
        self.assertEqual(self.payment.mpesa_receipt_number, "ORIGINAL")


class PaymentStatusPermissionTests(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.payment = PaymentTransaction.objects.create(
            user=self.tenant,
            property=self.property,
            purpose="viewing_fee",
            amount=500,
            phone_number="254712345678",
            status=PaymentTransaction.Status.SUCCESSFUL,
            mpesa_receipt_number="QGHOWN123",
        )
        self.status_url = reverse(
            "payments:payment-status", kwargs={"reference": self.payment.reference}
        )

    def test_owner_can_read_status(self):
        self.auth(self.tenant_token)
        response = self.client.get(self.status_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "successful")
        self.assertEqual(response.data["mpesa_receipt_number"], "QGHOWN123")

    def test_other_user_forbidden(self):
        self.auth(self.landlord_token)
        response = self.client.get(self.status_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_forbidden(self):
        self.clear_auth()
        response = self.client.get(self.status_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unknown_reference(self):
        self.auth(self.tenant_token)
        response = self.client.get(
            reverse("payments:payment-status", kwargs={"reference": "NF-ZZZZ-9999"})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_can_read_any_status(self):
        self.auth(self.admin_token)
        response = self.client.get(self.status_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_history_shows_only_own_transactions(self):
        PaymentTransaction.objects.create(
            user=self.landlord,
            purpose="listing_fee",
            amount=1000,
            phone_number="254700000000",
            status=PaymentTransaction.Status.SUCCESSFUL,
        )
        self.auth(self.tenant_token)
        response = self.client.get(self.history_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        references = [p["reference"] for p in response.data["results"]]
        self.assertIn(self.payment.reference, references)
        self.assertEqual(len(response.data["results"]), 1)

    def test_admin_history_shows_all(self):
        self.auth(self.admin_token)
        response = self.client.get(self.history_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 1)


class ReconciliationTests(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.stuck = PaymentTransaction.objects.create(
            user=self.tenant,
            property=self.property,
            purpose="viewing_fee",
            amount=500,
            phone_number="254712345678",
            checkout_request_id="wsq_stuck_1",
            status=PaymentTransaction.Status.PROCESSING,
        )
        # Age it beyond the validity window.
        PaymentTransaction.objects.filter(pk=self.stuck.pk).update(
            updated_at=timezone.now() - timedelta(minutes=60)
        )
        self.reconcile_url = reverse("payments:payment-reconcile")

    def test_reconcile_requires_admin(self):
        self.auth(self.tenant_token)
        response = self.client.post(self.reconcile_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reconcile_expires_stuck_payments_without_initiator(self):
        self.auth(self.admin_token)
        response = self.client.post(self.reconcile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["reconciled"], 1)
        self.assertEqual(response.data["queried_via_daraja"], 0)
        self.stuck.refresh_from_db()
        self.assertEqual(self.stuck.status, PaymentTransaction.Status.EXPIRED)

    def test_reconcile_queries_daraja_when_initiator_configured(self):
        query_response = {
            "ResultCode": 0,
            "ResultDesc": "The service request is processed successfully.",
        }
        with override_settings(
            MPESA_INITIATOR="test_initiator",
            MPESA_SECURITY_CREDENTIAL="test_credential",
        ), patch.object(
            MpesaService, "query_transaction_status",
            return_value=(200, query_response),
        ), patch.object(MpesaService, "get_access_token", return_value="tok"):
            self.auth(self.admin_token)
            response = self.client.post(self.reconcile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["queried_via_daraja"], 1)
        self.stuck.refresh_from_db()
        self.assertEqual(self.stuck.status, PaymentTransaction.Status.SUCCESSFUL)

    def test_reconcile_leaves_fresh_processing_payments(self):
        other_property = Property.objects.create(
            owner=self.landlord,
            title="Second M-Pesa Test Apartment",
            description="Another apartment for payment tests.",
            property_type=Property.PropertyType.APARTMENT,
            county="Nairobi",
            estate="Kilimani",
            rent=25000,
            bedrooms=1,
            bathrooms=1.0,
        )
        fresh = PaymentTransaction.objects.create(
            user=self.tenant,
            property=other_property,
            purpose="viewing_fee",
            amount=500,
            phone_number="254712345678",
            status=PaymentTransaction.Status.PROCESSING,
        )
        self.auth(self.admin_token)
        response = self.client.post(self.reconcile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        fresh.refresh_from_db()
        self.assertEqual(fresh.status, PaymentTransaction.Status.PROCESSING)


class PaymentConfigTests(PaymentTestCase):
    def test_config_endpoint_is_public(self):
        self.clear_auth()
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("enabled_purposes", response.data)
        self.assertIn("listing_fee_amount", response.data)
        # No credentials leak.
        self.assertNotIn("consumer_key", response.data)
        self.assertNotIn("passkey", response.data)


class MpesaServiceUnitTests(TestCase):
    def test_validate_callback_accepts_valid_payload(self):
        data = MpesaService.validate_callback(callback_payload("wsq_x"))
        self.assertEqual(data["checkout_request_id"], "wsq_x")
        self.assertEqual(data["result_code"], 0)
        self.assertEqual(data["metadata"]["Amount"], 500)
        self.assertEqual(data["metadata"]["MpesaReceiptNumber"], "QGH12345CD")

    def test_validate_callback_rejects_bad_payloads(self):
        for bad in (None, [], {}, {"Body": None},
                    {"Body": {"stkCallback": "nope"}},
                    {"Body": {"stkCallback": {"CheckoutRequestID": None,
                                              "MerchantRequestID": "m",
                                              "ResultCode": 0}}}):
            with self.assertRaises(ValueError):
                MpesaService.validate_callback(bad)

    def test_interpret_result_mapping(self):
        self.assertEqual(
            MpesaService.interpret_result(0), ("successful", "")
        )
        self.assertEqual(
            MpesaService.interpret_result(1032)[0], "cancelled"
        )
        self.assertEqual(
            MpesaService.interpret_result(1037)[0], "expired"
        )
        self.assertEqual(
            MpesaService.interpret_result(1, "No funds")[0], "failed"
        )
        self.assertIn("No funds", MpesaService.interpret_result(1, "No funds")[1])

    def test_stk_push_password_construction(self):
        """The STK password must be base64(shortcode + passkey + timestamp)."""
        import base64
        import re

        captured = {}

        def fake_request(method, path, payload=None, token=None):
            captured["payload"] = payload
            return 200, STK_OK

        service = MpesaService()
        service.consumer_key = "key"
        service.consumer_secret = "secret"
        service.shortcode = "123456"
        service.passkey = "passkey123"
        service.callback_url = "https://example.com/callback"

        with patch.object(service, "get_access_token", return_value="tok"), \
                patch.object(service, "_request", side_effect=fake_request):
            service.stk_push(500, "254712345678", "NF-TEST", "Test payment")

        payload = captured["payload"]
        self.assertEqual(payload["BusinessShortCode"], "123456")
        self.assertEqual(payload["Amount"], 500)
        self.assertEqual(payload["PartyA"], "254712345678")
        self.assertEqual(payload["TransactionType"], "CustomerPayBillOnline")
        self.assertEqual(payload["CallBackURL"], "https://example.com/callback")
        self.assertRegex(payload["Timestamp"], r"^\d{14}$")
        expected = base64.b64encode(
            f"123456passkey123{payload['Timestamp']}".encode()
        ).decode()
        self.assertEqual(payload["Password"], expected)

    def test_stk_push_requires_callback_url(self):
        service = MpesaService()
        service.consumer_key = "key"
        service.consumer_secret = "secret"
        service.shortcode = "123456"
        service.passkey = "passkey123"
        service.callback_url = ""
        with patch.object(service, "get_access_token", return_value="tok"):
            from payments.mpesa_service import MpesaConfigurationError
            with self.assertRaises(MpesaConfigurationError):
                service.stk_push(500, "254712345678", "NF-TEST", "Test")
