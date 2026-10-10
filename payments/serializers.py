from django.contrib.auth import get_user_model
from rest_framework import serializers

from payments.models import PaymentConfiguration, PaymentTransaction

User = get_user_model()


class PaymentTransactionSerializer(serializers.ModelSerializer):
    """Safe, public representation of a transaction.

    Never includes Daraja credentials or internal identifiers
    beyond what the user needs to reference the payment.
    """

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    purpose_display = serializers.CharField(source="get_purpose_display", read_only=True)
    property_title = serializers.CharField(source="property.title", read_only=True)
    created = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            "reference",
            "purpose",
            "purpose_display",
            "amount",
            "phone_number",
            "description",
            "property",
            "property_title",
            "checkout_request_id",
            "merchant_request_id",
            "mpesa_receipt_number",
            "mpesa_transaction_date",
            "status",
            "status_display",
            "failure_message",
            "created",
            "updated_at",
        ]
        read_only_fields = fields


class StkPushRequestSerializer(serializers.Serializer):
    """Validation for initiating an STK Push."""

    PURPOSE_CHOICES = [choice[0] for choice in PaymentTransaction.Purpose.choices]

    purpose = serializers.ChoiceField(choices=PURPOSE_CHOICES)
    amount = serializers.IntegerField(min_value=1, max_value=150000)
    phone_number = serializers.CharField(max_length=16)
    property_id = serializers.IntegerField(required=False, allow_null=True)
    description = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate_purpose(self, value):
        config = PaymentConfiguration.get_solo()
        if not config.is_purpose_enabled(value):
            raise serializers.ValidationError(
                f"The payment purpose '{value}' is not enabled by the administrator."
            )
        return value

    def validate_amount(self, value):
        if value < 1:
            raise serializers.ValidationError("Amount must be at least KSh 1.")
        if value > 150000:
            raise serializers.ValidationError(
                "A single M-Pesa transaction cannot exceed KSh 150,000."
            )
        return value

    def validate_phone_number(self, value):
        normalized = normalize_phone(value)
        return normalized


def normalize_phone(value):
    """Normalize a Kenyan mobile number to 254XXXXXXXXX."""
    import re

    if not isinstance(value, str):
        raise serializers.ValidationError("Phone number must be text.")

    digits = re.sub(r"\D", "", value.strip())

    if len(digits) == 12 and digits.startswith("254"):
        phone = digits
    elif len(digits) == 10 and digits.startswith("0"):
        phone = "254" + digits[1:]
    elif len(digits) == 9 and digits.startswith("7"):
        phone = "254" + digits
    else:
        raise serializers.ValidationError(
            "Enter a valid Kenyan mobile number, e.g. 0712 345 678 or +254712345678."
        )

    if not re.fullmatch(r"2547\d{8}", phone):
        raise serializers.ValidationError(
            "Enter a valid Kenyan mobile number, e.g. 0712 345 678 or +254712345678."
        )
    return phone


class PaymentConfigSerializer(serializers.ModelSerializer):
    """Public payment configuration (no secrets)."""

    class Meta:
        model = PaymentConfiguration
        fields = [
            "enabled_purposes",
            "listing_fee_amount",
            "viewing_fee_amount",
            "rental_payments_enabled",
        ]
        read_only_fields = fields
