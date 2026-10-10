from django.db import IntegrityError
from rest_framework import serializers

from reviews.models import LandlordResponse, Review, ReviewReport

RATING_FIELDS = [
    "overall",
    "condition",
    "location",
    "water",
    "security",
    "value_for_money",
    "landlord_rating",
]


class RatingField(serializers.IntegerField):
    def to_representation(self, value):
        return int(value)

    def validate(self, value):
        value = super().validate(value)
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value


class ReviewSerializer(serializers.ModelSerializer):
    """Read representation of a review."""

    tenant_name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    response = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id",
            "overall",
            "condition",
            "location",
            "water",
            "security",
            "value_for_money",
            "landlord_rating",
            "comment",
            "recommends",
            "status",
            "is_verified",
            "tenant_name",
            "avatar",
            "is_owner",
            "response",
            "created_at",
        ]
        read_only_fields = fields

    def get_tenant_name(self, obj):
        return obj.tenant.get_full_name() or obj.tenant.username

    def get_avatar(self, obj):
        request = self.context.get("request")
        if obj.tenant.avatar and hasattr(obj.tenant.avatar, "url"):
            return (
                request.build_absolute_uri(obj.tenant.avatar.url)
                if request
                else obj.tenant.avatar.url
            )
        return None

    def get_response(self, obj):
        response = getattr(obj, "response", None)
        if response is None:
            return None
        try:
            response = LandlordResponse.objects.get(review=obj)
        except LandlordResponse.DoesNotExist:
            return None
        return {
            "landlord_name": response.landlord.business_name
            or response.landlord.get_full_name()
            or response.landlord.username,
            "message": response.message,
            "created_at": response.created_at,
        }

    def get_is_owner(self, obj):
        request = self.context.get("request")
        return bool(
            request
            and request.user.is_authenticated
            and obj.tenant_id == request.user.id
        )


class ReviewCreateSerializer(serializers.ModelSerializer):
    """Validation for submitting a review."""

    class Meta:
        model = Review
        fields = RATING_FIELDS + ["comment", "recommends"]

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        property_obj = self.context["property"]

        if not user.is_authenticated:
            raise serializers.ValidationError("You must be signed in to review.")

        if property_obj.owner_id == user.id:
            raise serializers.ValidationError(
                "Landlords cannot review their own property."
            )

        if Review.objects.filter(property=property_obj, tenant=user).exists():
            raise serializers.ValidationError(
                "You have already reviewed this property. "
                "Each tenant may leave one review per property."
            )

        for field in RATING_FIELDS:
            value = attrs.get(field)
            if value is None or not (1 <= value <= 5):
                raise serializers.ValidationError(
                    {field: "Rating must be between 1 and 5."}
                )

        comment = attrs.get("comment", "").strip()
        if len(comment) < 10:
            raise serializers.ValidationError(
                "Please write a comment of at least 10 characters."
            )
        attrs["comment"] = comment
        return attrs


class ReviewUpdateSerializer(serializers.ModelSerializer):
    """Reviewers may edit their own review (moderation fields excluded)."""

    class Meta:
        model = Review
        fields = RATING_FIELDS + ["comment", "recommends"]

    def validate(self, attrs):
        for field in RATING_FIELDS:
            value = attrs.get(field)
            if value is not None and not (1 <= value <= 5):
                raise serializers.ValidationError(
                    {field: "Rating must be between 1 and 5."}
                )
        comment = attrs.get("comment")
        if comment is not None and len(comment.strip()) < 10:
            raise serializers.ValidationError(
                "Comment must be at least 10 characters."
            )
        return attrs


class AdminReviewSerializer(serializers.ModelSerializer):
    """Admins may moderate status and verification."""

    class Meta:
        model = Review
        fields = ["status", "is_verified"]


class ReviewReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewReport
        fields = ["id", "reason", "description", "status", "created_at"]
        read_only_fields = ["id", "status", "created_at"]

    def validate_reason(self, value):
        valid = dict(ReviewReport.Reason.choices).keys()
        if value not in valid:
            raise serializers.ValidationError("Select a valid report reason.")
        return value

    def validate_description(self, value):
        if len(value) > 1000:
            raise serializers.ValidationError(
                "Please keep the description under 1000 characters."
            )
        return value


class LandlordResponseSerializer(serializers.ModelSerializer):
    landlord_name = serializers.SerializerMethodField()

    class Meta:
        model = LandlordResponse
        fields = ["id", "message", "landlord_name", "created_at"]
        read_only_fields = ["id", "landlord_name", "created_at"]

    def get_landlord_name(self, obj):
        return obj.landlord.business_name or obj.landlord.get_full_name() or obj.landlord.username
