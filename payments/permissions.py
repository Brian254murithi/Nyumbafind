"""Permissions for the payments API."""

from rest_framework.permissions import BasePermission


class IsPaymentOwnerOrAdmin(BasePermission):
    """Users see their own transactions; admins see all."""

    message = "You can only access your own payment transactions."

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        return request.user.is_admin_role or obj.user_id == request.user.id


class IsAdminUser(BasePermission):
    """Admin-only actions such as reconciliation."""

    message = "Only administrators can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_admin_role
        )
