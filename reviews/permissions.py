from rest_framework.permissions import BasePermission


class IsReviewOwnerOrAdmin(BasePermission):
    """Reviewers manage their own reviews; admins moderate any review."""

    message = "You can only manage your own reviews."

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        return request.user.is_admin_role or obj.tenant_id == request.user.id


class IsPropertyOwner(BasePermission):
    """Only the landlord who owns the reviewed property may respond."""

    message = "Only the property owner can respond to this review."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        from reviews.models import Review

        try:
            review = Review.objects.get(pk=view.kwargs.get("pk"))
        except Review.DoesNotExist:
            return True  # Let the view return a 404.
        return request.user.is_admin_role or review.property.owner_id == request.user.id
