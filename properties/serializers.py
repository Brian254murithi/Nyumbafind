from django.conf import settings
from rest_framework import serializers

from properties.models import Property, PropertyImage
from properties.validators import validate_amenities, validate_upload


class PropertyImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = PropertyImage
        fields = [
            "id",
            "image",
            "image_url",
            "remote_url",
            "alt_text",
            "is_primary",
            "order",
        ]
        read_only_fields = [
            "id",
            "image_url",
            "remote_url",
            "is_primary",
            "order",
        ]

    def get_image_url(self, obj):
        if obj.remote_url:
            return obj.remote_url
        request = self.context.get("request")
        if obj.image and hasattr(obj.image, "url"):
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None


class RatingSummaryField(serializers.SerializerMethodField):
    """Average rating and review count for a property."""

    def to_representation(self, value):
        from reviews.utils import get_rating_summary

        return get_rating_summary(value)


class PropertyListSerializer(serializers.ModelSerializer):
    main_image_url = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()
    rating = RatingSummaryField(source="*")

    class Meta:
        model = Property
        fields = [
            "id",
            "title",
            "property_type",
            "county",
            "town",
            "estate",
            "rent",
            "bedrooms",
            "bathrooms",
            "amenities",
            "available",
            "is_featured",
            "is_sample",
            "main_image",
            "main_image_url",
            "owner_name",
            "rating",
            "latitude",
            "longitude",
            "created_at",
        ]

    def get_main_image_url(self, obj):
        request = self.context.get("request")
        if obj.main_image and hasattr(obj.main_image, "url"):
            url = obj.main_image.url
            return request.build_absolute_uri(url) if request else url
        # Fall back to the first gallery photo (e.g. sample listings).
        first_image = obj.images.filter().first()
        if first_image and first_image.remote_url:
            return first_image.remote_url
        return None

    def get_owner_name(self, obj):
        owner = obj.owner
        return owner.business_name or owner.get_full_name() or owner.username


class PropertyDetailSerializer(PropertyListSerializer):
    images = PropertyImageSerializer(many=True, read_only=True)
    description = serializers.CharField()
    address = serializers.CharField()
    is_owner = serializers.SerializerMethodField()
    rating = RatingSummaryField(source="*")

    class Meta(PropertyListSerializer.Meta):
        fields = PropertyListSerializer.Meta.fields + [
            "description",
            "address",
            "images",
            "latitude",
            "longitude",
            "is_owner",
            "owner_accepts_payments",
            "updated_at",
        ]

    def get_is_owner(self, obj):
        request = self.context.get("request")
        return bool(
            request and request.user.is_authenticated and obj.owner_id == request.user.id
        )

    owner_accepts_payments = serializers.BooleanField(
        source="owner.accepts_payments", read_only=True
    )


class PropertyCreateUpdateSerializer(serializers.ModelSerializer):
    amenities = serializers.ListField(
        child=serializers.CharField(max_length=60),
        required=False,
        validators=[validate_amenities],
    )
    main_image = serializers.ImageField(
        required=False, allow_null=True, validators=[validate_upload]
    )

    class Meta:
        model = Property
        fields = [
            "title",
            "description",
            "property_type",
            "county",
            "town",
            "estate",
            "address",
            "rent",
            "bedrooms",
            "bathrooms",
            "amenities",
            "available",
            "is_featured",
            "main_image",
            "latitude",
            "longitude",
        ]

    def validate_title(self, value):
        if len(value.strip()) < 5:
            raise serializers.ValidationError("Title must be at least 5 characters.")
        return value.strip()

    def validate_rent(self, value):
        if value <= 0:
            raise serializers.ValidationError("Rent must be greater than zero.")
        if value > 10_000_000:
            raise serializers.ValidationError("Please enter a realistic rent amount.")
        return value

    def validate_bedrooms(self, value):
        if value > 20:
            raise serializers.ValidationError("Bedrooms must be 20 or fewer.")
        return value

    def validate_bathrooms(self, value):
        if value < 0 or value > 20:
            raise serializers.ValidationError("Bathrooms must be between 0 and 20.")
        return value

    def validate_description(self, value):
        if len(value.strip()) < 20:
            raise serializers.ValidationError("Description must be at least 20 characters.")
        return value.strip()

    def validate(self, attrs):
        if attrs.get("property_type") in ("bedsitter", "studio"):
            attrs["bedrooms"] = 0
        return attrs


class PropertyImageUploadSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(validators=[validate_upload])

    class Meta:
        model = PropertyImage
        fields = ["image", "alt_text", "order"]
