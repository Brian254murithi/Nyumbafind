from rest_framework.permissions import BasePermission


class IsLandlordOrAdmin(BasePermission):
    """Only landlords (or admins) may create/manage listings."""

    message = "You must be a landlord to manage property listings."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_landlord or request.user.is_superuser)
        )


class IsOwnerOrAdmin(BasePermission):
    """Object-level: landlords manage only their own properties."""

    message = "You can only manage properties you own."

    def has_object_permission(self, request, view, obj):
        return request.user.is_admin_role or obj.owner_id == request.user.id
