from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ["username", "email", "first_name", "last_name", "role", "is_staff", "is_active"]
    list_filter = ["role", "is_staff", "is_active", "date_joined"]
    search_fields = ["username", "email", "first_name", "last_name", "phone"]
    ordering = ["-date_joined"]
    fieldsets = UserAdmin.fieldsets + (
        (
            "NyumbaFind profile",
            {
                "fields": (
                    "role",
                    "phone",
                    "business_name",
                    "avatar",
                    "email_verified",
                    "phone_verified",
                )
            },
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {"fields": ("role", "phone", "business_name")}),
    )
