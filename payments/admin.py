from django.contrib import admin

from payments.models import (
    PaymentConfiguration,
    PaymentStatusLog,
    PaymentTransaction,
)


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "user",
        "purpose",
        "amount",
        "phone_number",
        "status",
        "mpesa_receipt_number",
        "created_at",
    ]
    list_filter = [
        "purpose",
        "status",
        "created_at",
    ]
    search_fields = [
        "reference",
        "user__username",
        "checkout_request_id",
        "merchant_request_id",
        "mpesa_receipt_number",
        "phone_number",
    ]
    ordering = ["-created_at"]
    readonly_fields = [
        "reference",
        "checkout_request_id",
        "merchant_request_id",
        "mpesa_receipt_number",
        "mpesa_transaction_date",
        "created_at",
        "updated_at",
    ]
    autocomplete_fields = ["user", "property"]
    list_editable = ["status"]


@admin.register(PaymentStatusLog)
class PaymentStatusLogAdmin(admin.ModelAdmin):
    list_display = ["transaction", "from_status", "to_status", "created_at"]
    list_filter = ["to_status", "created_at"]
    search_fields = ["transaction__reference", "note"]
    ordering = ["-created_at"]
    autocomplete_fields = ["transaction"]


@admin.register(PaymentConfiguration)
class PaymentConfigurationAdmin(admin.ModelAdmin):
    list_display = [
        "listing_fee_amount",
        "viewing_fee_amount",
        "rental_payments_enabled",
        "payment_validity_minutes",
        "updated_at",
    ]

    def has_add_permission(self, request):
        # Singleton configuration.
        return False
