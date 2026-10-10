"""
Reconcile stuck M-Pesa payments.

Usage:
    python manage.py reconcile_payments

Expires payments stuck in processing beyond the configured
validity window, or queries Daraja's TransactionStatus API
when initiator credentials are configured.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from payments.models import PaymentConfiguration, PaymentStatusLog, PaymentTransaction
from payments.mpesa_service import MpesaApiError, MpesaConfigurationError, get_mpesa_service


class Command(BaseCommand):
    help = "Reconcile payments stuck in processing"

    def handle(self, *args, **options):
        config = PaymentConfiguration.get_solo()
        cutoff = timezone.now() - timezone.timedelta(
            minutes=config.payment_validity_minutes
        )
        stuck = list(
            PaymentTransaction.objects.filter(
                status=PaymentTransaction.Status.PROCESSING,
                updated_at__lt=cutoff,
            )
        )

        service = get_mpesa_service()
        can_query = bool(service.initiator and service.security_credential)

        reconciled = 0
        for payment in stuck:
            if can_query:
                try:
                    _, data = service.query_transaction_status(
                        payment.checkout_request_id
                    )
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
                            note="Reconciled via reconcile_payments command",
                        )
                        reconciled += 1
                        continue
                except (MpesaApiError, MpesaConfigurationError) as exc:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Query failed for {payment.reference}: {exc}"
                        )
                    )

            payment.status = PaymentTransaction.Status.EXPIRED
            payment.failure_message = "Payment was not completed in time and has expired."
            payment.save(update_fields=["status", "failure_message"])
            PaymentStatusLog.objects.create(
                transaction=payment,
                from_status=PaymentTransaction.Status.PROCESSING,
                to_status=PaymentTransaction.Status.EXPIRED,
                note="Expired during reconciliation",
            )
            reconciled += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Reconciled {reconciled} of {len(stuck)} stuck payments."
            )
        )
