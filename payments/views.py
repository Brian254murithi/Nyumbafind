import logging

from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from properties.models import Property

from payments.models import PaymentConfiguration, PaymentStatusLog, PaymentTransaction
from payments.permissions import IsAdminUser, IsPaymentOwnerOrAdmin
from payments.serializers import (
    PaymentConfigSerializer,
    PaymentTransactionSerializer,
    StkPushRequestSerializer,
)
from .mpesa_service import MpesaApiError, MpesaConfigurationError, get_mpesa_service

logger = logging.getLogger("nyumbafind.payments")


class PaymentConfigView(APIView):
    """GET /api/payments/config/ — public payment options."""

    permission_classes = [AllowAny]

    def get(self, request):
        config = PaymentConfiguration.get_solo()
        return Response(PaymentConfigSerializer(config).data)


class StkPushView(APIView):
    """
    POST /api/payments/stk-push/

    Creates a pending transaction and initiates an M-Pesa STK Push.
    The payment is NOT successful yet — only the Safaricom callback
    (or admin reconciliation) can confirm success.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = StkPushRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

        purpose = serializer.validated_data["purpose"]
        amount = serializer.validated_data["amount"]
        phone = serializer.validated_data["phone_number"]
        description = serializer.validated_data.get("description", "")
        property_id = serializer.validated_data.get("property_id")

        user = request.user
        config = PaymentConfiguration.get_solo()

        # --- Purpose-specific authorization --------------------------
        if purpose == PaymentTransaction.Purpose.LISTING_FEE:
            if not user.is_landlord:
                return Response(
                    {"errors": {"purpose": "Only landlords can pay listing fees."}},
                    status=status.HTTP_403_FORBIDDEN,
                )
            expected_amount = config.listing_fee_amount
            property_obj = None
        else:
            if property_id is None:
                return Response(
                    {"errors": {"property_id": "A property is required for this payment."}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                property_obj = Property.objects.get(pk=property_id)
            except Property.DoesNotExist:
                return Response(
                    {"errors": {"property_id": "Property not found."}},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if purpose == PaymentTransaction.Purpose.RENTAL_PAYMENT:
                if not config.rental_payments_enabled:
                    return Response(
                        {"errors": {"purpose": "Rental payments are not enabled."}},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                if not property_obj.owner.accepts_payments:
                    return Response(
                        {"errors": {
                            "purpose": "This landlord has not authorized NyumbaFind to collect rent payments."
                        }},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                if property_obj.owner_id == user.id:
                    return Response(
                        {"errors": {"purpose": "You cannot pay rent on your own property."}},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                # Rent payments must match the listed rent.
                expected_amount = property_obj.rent
            else:  # viewing_fee
                expected_amount = config.viewing_fee_amount
                if property_obj.owner_id == user.id:
                    return Response(
                        {"errors": {"purpose": "You cannot book a viewing of your own property."}},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        if amount != expected_amount:
            return Response(
                {"errors": {
                    "amount": f"The {purpose.replace('_', ' ')} is KSh {expected_amount:,}."
                }},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- Create transaction + initiate STK Push ------------------
        try:
            with transaction.atomic():
                # Duplicate prevention: an active transaction for the
                # same user/purpose/property/amount already exists.
                existing = PaymentTransaction.objects.filter(
                    user=user,
                    purpose=purpose,
                    property=property_obj,
                    amount=amount,
                    status__in=[
                        PaymentTransaction.Status.PENDING,
                        PaymentTransaction.Status.PROCESSING,
                    ],
                ).first()
                if existing:
                    return Response(
                        PaymentTransactionSerializer(existing).data,
                        status=status.HTTP_200_OK,
                    )

                payment = PaymentTransaction.objects.create(
                    user=user,
                    property=property_obj,
                    purpose=purpose,
                    amount=amount,
                    phone_number=phone,
                    description=description
                    or f"NyumbaFind {purpose.replace('_', ' ')}",
                )
        except Exception:
            return Response(
                {"errors": {"detail": "A similar payment is already in progress."}},
                status=status.HTTP_409_CONFLICT,
            )

        service = get_mpesa_service()
        try:
            response = service.stk_push(
                amount=amount,
                phone_number=phone,
                account_reference=payment.reference,
                transaction_desc=payment.description,
            )
        except MpesaConfigurationError as exc:
            logger.warning("STK push configuration error: %s", exc)
            payment.status = PaymentTransaction.Status.FAILED
            payment.failure_message = "Mobile payments are not configured. Please contact support."
            payment.save(update_fields=["status", "failure_message"])
            return Response(
                {"errors": {"detail": payment.failure_message}, "transaction": PaymentTransactionSerializer(payment).data},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except MpesaApiError as exc:
            logger.warning("STK push API error for %s: %s", payment.reference, exc)
            payment.status = PaymentTransaction.Status.FAILED
            payment.failure_message = exc.sanitized_message
            payment.save(update_fields=["status", "failure_message"])
            PaymentStatusLog.objects.create(
                transaction=payment,
                from_status=PaymentTransaction.Status.PENDING,
                to_status=PaymentTransaction.Status.FAILED,
                note="STK push initiation failed",
            )
            return Response(
                {"errors": {"detail": exc.sanitized_message}, "transaction": PaymentTransactionSerializer(payment).data},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # The push was accepted for processing — not a success yet.
        payment.checkout_request_id = response.get("CheckoutRequestID")
        payment.merchant_request_id = response.get("MerchantRequestID")
        payment.status = PaymentTransaction.Status.PROCESSING
        payment.save(update_fields=[
            "checkout_request_id", "merchant_request_id", "status"
        ])
        PaymentStatusLog.objects.create(
            transaction=payment,
            from_status=PaymentTransaction.Status.PENDING,
            to_status=PaymentTransaction.Status.PROCESSING,
            note="STK push accepted by Safaricom",
        )

        return Response(
            PaymentTransactionSerializer(payment).data,
            status=status.HTTP_202_ACCEPTED,
        )


class PaymentStatusView(APIView):
    """GET /api/payments/<reference>/status/ — owner or admin only."""

    permission_classes = [IsAuthenticated, IsPaymentOwnerOrAdmin]

    def get_object(self, reference):
        try:
            return PaymentTransaction.objects.get(reference=reference)
        except PaymentTransaction.DoesNotExist:
            return None

    def get(self, request, reference):
        payment = self.get_object(reference)
        if payment is None:
            return Response(
                {"errors": {"detail": "Transaction not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        self.check_object_permissions(request, payment)
        return Response(PaymentTransactionSerializer(payment).data)

    def check_object_permissions(self, request, obj):
        for permission in self.permission_classes:
            if not permission().has_object_permission(request, self, obj):
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied(
                    "You can only access your own payment transactions."
                )


class PaymentHistoryView(APIView):
    """
    GET /api/payments/history/

    Returns the caller's transactions (or all, for admins).
    Supports ?purpose= and ?status= filters.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_admin_role:
            payments = PaymentTransaction.objects.all()
        else:
            payments = PaymentTransaction.objects.filter(user=request.user)

        purpose = request.query_params.get("purpose")
        if purpose:
            payments = payments.filter(purpose=purpose)
        status_filter = request.query_params.get("status")
        if status_filter:
            payments = payments.filter(status=status_filter)

        payments = payments.select_related("user", "property")[:100]
        serializer = PaymentTransactionSerializer(payments, many=True)
        return Response({"results": serializer.data})


class PaymentCallbackView(APIView):
    """
    POST /api/payments/callback/

    Safaricom's STK Push callback. No authentication — the callback
    is correlated by the unique CheckoutRequestID and validated
    against the original transaction, including the expected amount.
    Processing is idempotent: duplicate callbacks are acknowledged
    without re-applying the outcome.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = None

    def post(self, request):
        service = get_mpesa_service()

        try:
            data = service.validate_callback(request.data)
        except ValueError as exc:
            logger.warning("Invalid callback structure: %s", exc)
            return Response(
                {"ResultCode": 1, "ResultDesc": f"Invalid callback: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        checkout_request_id = data["checkout_request_id"]
        result_code = data["result_code"]
        metadata = data["metadata"]

        try:
            payment = PaymentTransaction.objects.get(
                checkout_request_id=checkout_request_id
            )
        except PaymentTransaction.DoesNotExist:
            # Unknown checkout ID: acknowledge so Safaricom stops
            # retrying; the event is logged for investigation.
            logger.warning(
                "Callback for unknown CheckoutRequestID %s",
                checkout_request_id,
            )
            return Response(
                {"ResultCode": 0, "ResultDesc": "Unknown transaction reference"},
                status=status.HTTP_200_OK,
            )

        new_status, failure_message = service.interpret_result(
            result_code, data.get("result_desc", "")
        )

        # Extract receipt metadata for successful payments.
        receipt = metadata.get("MpesaReceiptNumber")
        callback_amount = metadata.get("Amount")
        transaction_date = metadata.get("TransactionDate")

        with transaction.atomic():
            locked = PaymentTransaction.objects.select_for_update().get(
                pk=payment.pk
            )

            if locked.status == PaymentTransaction.Status.SUCCESSFUL:
                # Already processed — idempotent acknowledgment.
                return Response(
                    {"ResultCode": 0, "ResultDesc": "Already processed"},
                    status=status.HTTP_200_OK,
                )

            if new_status == "successful":
                # Validate the paid amount against the expected amount.
                if callback_amount is not None:
                    try:
                        if int(callback_amount) != locked.amount:
                            logger.error(
                                "Callback amount mismatch for %s: paid %s, expected %s",
                                locked.reference, callback_amount, locked.amount,
                            )
                            return Response(
                                {"ResultCode": 1, "ResultDesc": "Amount mismatch"},
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                    except (TypeError, ValueError):
                        logger.warning(
                            "Non-numeric callback amount for %s", locked.reference
                        )

                locked.status = PaymentTransaction.Status.SUCCESSFUL
                locked.mpesa_receipt_number = str(receipt or "")[:40] or None
                locked.mpesa_transaction_date = str(transaction_date or "")[:20] or None
                locked.failure_message = ""
            else:
                valid_statuses = {
                    value for value, _ in PaymentTransaction.Status.choices
                }
                locked.status = (
                    new_status
                    if new_status in valid_statuses
                    else PaymentTransaction.Status.FAILED
                )
                locked.failure_message = failure_message[:255]

            locked.merchant_request_id = (
                data.get("merchant_request_id") or locked.merchant_request_id
            )
            locked.save(
                update_fields=[
                    "status",
                    "failure_message",
                    "mpesa_receipt_number",
                    "mpesa_transaction_date",
                    "merchant_request_id",
                    "updated_at",
                ]
            )

            PaymentStatusLog.objects.create(
                transaction=locked,
                from_status=payment.status,
                to_status=locked.status,
                note=f"Daraja callback result code {result_code}",
            )

        logger.info(
            "Payment %s -> %s via callback", locked.reference, locked.status
        )
        return Response(
            {"ResultCode": 0, "ResultDesc": "Callback processed successfully"},
            status=status.HTTP_200_OK,
        )


class ReconcileView(APIView):
    """
    POST /api/payments/reconcile/ (admin only)

    Expires payments stuck in processing beyond the configured
    validity window, and optionally queries Daraja's
    TransactionStatus API for transactions that have an initiator
    configured. This is the documented reconciliation path for
    ambiguous outcomes (e.g. callback never arrived).
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        config = PaymentConfiguration.get_solo()
        cutoff = timezone.now() - timezone.timedelta(
            minutes=config.payment_validity_minutes
        )
        stuck = PaymentTransaction.objects.filter(
            status=PaymentTransaction.Status.PROCESSING,
            updated_at__lt=cutoff,
        )
        stuck_count = stuck.count()

        reconciled = 0
        queried = 0
        service = get_mpesa_service()
        can_query = bool(service.initiator and service.security_credential)

        for payment in stuck:
            if can_query:
                try:
                    _, data = service.query_transaction_status(
                        payment.checkout_request_id
                    )
                    queried += 1
                    # The TransactionStatus response contains
                    # ResultCode in its payload; apply it if present.
                    result_code = data.get("ResultCode")
                    if result_code is not None:
                        new_status, failure_message = service.interpret_result(
                            int(result_code), data.get("ResultDesc", "")
                        )
                        payment.status = new_status
                        payment.failure_message = failure_message[:255]
                        payment.save(update_fields=["status", "failure_message"])
                        PaymentStatusLog.objects.create(
                            transaction=payment,
                            from_status=PaymentTransaction.Status.PROCESSING,
                            to_status=new_status,
                            note="Reconciled via Daraja TransactionStatusQuery",
                        )
                        reconciled += 1
                        continue
                except (MpesaApiError, MpesaConfigurationError) as exc:
                    logger.warning(
                        "Reconciliation query failed for %s: %s",
                        payment.reference, exc,
                    )
                    # Fall through to expiry handling.

            payment.status = PaymentTransaction.Status.EXPIRED
            payment.failure_message = (
                "Payment was not completed in time and has expired."
            )
            payment.save(update_fields=["status", "failure_message"])
            PaymentStatusLog.objects.create(
                transaction=payment,
                from_status=PaymentTransaction.Status.PROCESSING,
                to_status=PaymentTransaction.Status.EXPIRED,
                note="Expired during reconciliation",
            )
            reconciled += 1

        return Response(
            {
                "stuck_found": stuck_count,
                "reconciled": reconciled,
                "queried_via_daraja": queried,
            },
            status=status.HTTP_200_OK,
        )
