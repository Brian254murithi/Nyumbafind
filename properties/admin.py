from django.contrib import admin

from properties.models import Property, PropertyImage


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "owner",
        "property_type",
        "county",
        "rent",
        "bedrooms",
        "available",
        "is_featured",
        "is_sample",
        "created_at",
    ]
    list_filter = [
        "property_type",
        "county",
        "available",
        "is_featured",
        "is_sample",
        "created_at",
    ]
    search_fields = ["title", "estate", "town", "county", "address", "owner__username"]
    ordering = ["-created_at"]
    autocomplete_fields = ["owner"]


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ["id", "property", "alt_text", "is_primary", "order", "created_at"]
    list_filter = ["is_primary"]
    search_fields = ["property__title", "alt_text"]
    ordering = ["property", "order"]
