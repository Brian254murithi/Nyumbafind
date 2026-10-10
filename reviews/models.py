from django.conf import settings
from django.db import models


class Review(models.Model):
    """A tenant review for a property.

    One review per tenant per property (enforced by a database constraint).
    Verification and moderation status are controlled server-side by admins.
    """

    class Status(models.TextChoices):
        APPROVED = "approved", "Approved"
        PENDING = "pending", "Pending"
        UNDER_REVIEW = "under_review", "Under review"
        REJECTED = "rejected", "Rejected"

    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    property = models.ForeignKey(
        "properties.Property", on_delete=models.CASCADE, related_name="reviews"
    )
    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_given",
    )

    overall = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    condition = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    location = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    water = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES, verbose_name="Water reliability"
    )
    security = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    value_for_money = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    landlord_rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)

    comment = models.TextField()
    recommends = models.BooleanField(default=True)

    # Moderation: only admins may change status or verification.
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.APPROVED
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Admin-only flag confirming the reviewer actually stayed here.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "tenant"], name="unique_review_per_tenant"
            ),
        ]
        indexes = [
            models.Index(
                fields=["property", "status"], name="reviews_review_prop_status"
            ),
        ]

    def __str__(self):
        return f"{self.tenant} on {self.property} ({self.overall}/5)"


class ReviewReport(models.Model):
    """A user report about a review, queued for admin moderation."""

    class Reason(models.TextChoices):
        INACCURATE = "inaccurate", "Inaccurate information"
        OFFENSIVE = "offensive", "Offensive content"
        SPAM = "spam", "Spam or advertising"
        SUSPICIOUS = "suspicious", "Suspicious or fake review"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    review = models.ForeignKey(
        Review, on_delete=models.CASCADE, related_name="reports"
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_reports",
    )
    reason = models.CharField(max_length=20, choices=Reason.choices)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["review", "reporter"], name="unique_report_per_user"
            )
        ]

    def __str__(self):
        return f"Report ({self.reason}) on review #{self.review_id}"


class LandlordResponse(models.Model):
    """A response written by the landlord who owns the reviewed property."""

    review = models.OneToOneField(
        Review, on_delete=models.CASCADE, related_name="response"
    )
    landlord = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="landlord_responses",
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Response by {self.landlord} on review #{self.review_id}"
