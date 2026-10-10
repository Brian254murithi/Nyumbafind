"""
Payment models for NyumbaFind M-Pesa (Daraja) integration.

A payment is never marked successful by a browser request. Only the
Safaricom callback (server-to-server) — or an administrator via
reconciliation — can move a transaction to ``successful``.
"""

import secrets
import string

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


def generate_reference():
    """Internal reference like ``NF-7QK2-9X4P``."""
    alphabet = string.ascii_uppercase + string.digits
    return "NF-" + "".join(secrets.choice(alphabet) for _ in range(4)) + "-" + "".join(
        secrets.choice(alphabet) for _ in range(4)
    )


class PaymentTransaction(models.Model):
    """A single M-Pesa payment attempt initiated through Daraja."""

    class Purpose(models.TextChoices):
        LISTING_FEE = "listing_fee", "Property listing fee"
        VIEWING_FEE = "viewing_fee", "Property viewing / booking fee"
        RENTAL_PAYMENT = "rental_payment", "Rental payment"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SUCCESSFUL = "successful", "Successful"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    # Terminal states — payments may not move backwards out of these.
    TERMINAL_STATUSES = (Status.SUCCESSFUL, Status.FAILED, Status.CANCELLED, Status.EXPIRED)

    reference = models.CharField(
        max_length=14, unique=True, default=generate_reference
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    amount = models.PositiveIntegerField(help_text="Amount in Kenyan Shillings")
    phone_number = models.CharField(
        max_length=16, help_text="Normalized payer phone, e.g. 254712345678"
    )
    description = models.CharField(max_length=200, blank=True)

    # Daraja identifiers
    checkout_request_id = models.CharField(
        max_length=120, unique=True, null=True, blank=True
    )
    merchant_request_id = models.CharField(max_length=120, null=True, blank=True)
    mpesa_receipt_number = models.CharField(max_length=40, null=True, blank=True)
    mpesa_transaction_date = models.CharField(max_length=20, null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    failure_message = models.CharField(
        max_length=255, blank=True,
        help_text="Sanitized failure description safe for display",
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Prevents duplicate active payments for the same
            # user + purpose + property + amount combination.
            # (Status values are literals because the enclosing
            # class is still being defined at this point.)
            models.UniqueConstraint(
                fields=["user", "purpose", "property", "amount"],
                condition=models.Q(status__in=["pending", "processing"]),
                name="unique_active_payment",
            ),
        ]
        indexes = [
            models.Index(fields=["checkout_request_id"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.reference} — {self.purpose} KSh {self.amount} ({self.status})"

    def is_terminal(self):
        return self.status in self.TERMINAL_STATUSES


class PaymentStatusLog(models.Model):
    """Auditable history of every payment status change."""

    transaction = models.ForeignKey(
        PaymentTransaction,
        on_delete=models.CASCADE,
        related_name="status_logs",
    )
    from_status = models.CharField(max_length=20, null=True, blank=True)
    to_status = models.CharField(max_length=20)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Payment status logs"

    def __str__(self):
        return f"{self.transaction.reference}: {self.from_status} → {self.to_status}"


class PaymentConfiguration(models.Model):
    """Administrator-controlled payment settings (singleton, id=1)."""

    id = models.PositiveSmallIntegerField(primary_key=True)
    enabled_purposes = models.JSONField(
        default=list,
        help_text="Purposes admins have enabled, e.g. [\"listing_fee\", \"viewing_fee\"]",
    )
    listing_fee_amount = models.PositiveIntegerField(
        default=1000, help_text="Standard listing fee in KSh"
    )
    viewing_fee_amount = models.PositiveIntegerField(
        default=500, help_text="Standard viewing/booking fee in KSh"
    )
    rental_payments_enabled = models.BooleanField(
        default=False,
        help_text="Master switch for rent collection via NyumbaFind",
    )
    payment_validity_minutes = models.PositiveIntegerField(
        default=15,
        help_text="Minutes before an unfinished processing payment expires",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Payment configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        valid = {choice[0] for choice in PaymentTransaction.Purpose.choices}
        self.enabled_purposes = [
            p for p in (self.enabled_purposes or []) if p in valid
        ]
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        config, _ = cls.objects.get_or_create(pk=1)
        return config

    def is_purpose_enabled(self, purpose):
        return purpose in (self.enabled_purposes or [])

    def __str__(self):
        return "Payment configuration"
