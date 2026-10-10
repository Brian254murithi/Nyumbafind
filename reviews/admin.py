from django.contrib import admin

from reviews.models import LandlordResponse, Review, ReviewReport


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "property",
        "tenant",
        "overall",
        "status",
        "is_verified",
        "created_at",
    ]
    list_filter = ["status", "is_verified", "overall", "property__county", "created_at"]
    search_fields = [
        "property__title",
        "tenant__username",
        "tenant__email",
        "comment",
    ]
    ordering = ["-created_at"]
    autocomplete_fields = ["property", "tenant"]
    list_editable = ["status", "is_verified"]


@admin.register(ReviewReport)
class ReviewReportAdmin(admin.ModelAdmin):
    list_display = ["id", "review", "reporter", "reason", "status", "created_at"]
    list_filter = ["reason", "status", "created_at"]
    search_fields = ["review__comment", "reporter__username", "description"]
    ordering = ["-created_at"]
    autocomplete_fields = ["review", "reporter"]
    list_editable = ["status"]


@admin.register(LandlordResponse)
class LandlordResponseAdmin(admin.ModelAdmin):
    list_display = ["id", "review", "landlord", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["review__property__title", "landlord__username", "message"]
    ordering = ["-created_at"]
    autocomplete_fields = ["review", "landlord"]
