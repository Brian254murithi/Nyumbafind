from django.conf import settings
from django.db import models


class Property(models.Model):
    """A rental property listing owned by a landlord."""

    class PropertyType(models.TextChoices):
        APARTMENT = "apartment", "Apartment"
        BEDSITTER = "bedsitter", "Bedsitter"
        STUDIO = "studio", "Studio"
        HOUSE = "house", "House"
        MAISONETTE = "maisonette", "Maisonette"
        DUPLEX = "duplex", "Duplex"
        TOWNHOUSE = "townhouse", "Townhouse"
        BUNGALOW = "bungalow", "Bungalow"
        CONDO = "condo", "Condominium"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="properties",
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    property_type = models.CharField(
        max_length=20, choices=PropertyType.choices, default=PropertyType.APARTMENT
    )
    county = models.CharField(max_length=100, db_index=True)
    town = models.CharField(max_length=100, blank=True)
    estate = models.CharField(max_length=120, blank=True)
    address = models.CharField(max_length=255, blank=True)
    rent = models.PositiveIntegerField(help_text="Monthly rent in Kenyan Shillings (KSh)")
    bedrooms = models.PositiveSmallIntegerField(
        default=1, help_text="0 for bedsitters and studios"
    )
    bathrooms = models.DecimalField(
        max_digits=3, decimal_places=1, default=1.0
    )
    amenities = models.JSONField(default=list, blank=True)
    available = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    # Marks listings created by the seed command (demo data) so the UI can
    # distinguish sample listings from genuine landlord listings.
    is_sample = models.BooleanField(default=False)
    main_image = models.ImageField(upload_to="properties/", null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["county", "property_type"]),
            models.Index(fields=["rent"]),
        ]

    def __str__(self):
        return f"{self.title} — {self.county} (KSh {self.rent:,})"


class PropertyImage(models.Model):
    """Additional photographs for a property (multiple images supported).

    ``image`` holds an uploaded file; ``remote_url`` optionally
    references an externally hosted photo (used for sample listings).
    """

    property = models.ForeignKey(
        "Property", on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="properties/", null=True, blank=True)
    remote_url = models.URLField(
        blank=True, help_text="Externally hosted photo (sample data only)"
    )
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Image for {self.property.title}"
