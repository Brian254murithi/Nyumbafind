from django.core.paginator import Paginator
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from properties.models import Property
from reviews.models import LandlordResponse, Review, ReviewReport
from reviews.permissions import IsPropertyOwner, IsReviewOwnerOrAdmin
from reviews.serializers import (
    AdminReviewSerializer,
    LandlordResponseSerializer,
    ReviewCreateSerializer,
    ReviewReportSerializer,
    ReviewSerializer,
    ReviewUpdateSerializer,
)
from reviews.utils import get_global_summary, get_rating_summary


class ReviewPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


class PropertyReviewListCreateView(APIView):
    """
    GET  /api/properties/<id>/reviews/ — approved reviews + rating summary
    POST /api/properties/<id>/reviews/ — submit a review (tenants only, once)
    """

    permission_classes = [AllowAny]
    pagination_class = ReviewPagination

    def get_property(self, pk):
        return get_object_or_404(Property.objects.select_related("owner"), pk=pk)

    def get(self, request, pk):
        property_obj = self.get_property(pk)
        reviews = Review.objects.filter(
            property=property_obj, status=Review.Status.APPROVED
        ).select_related("tenant")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(reviews, request, self)
        serializer = ReviewSerializer(
            page, many=True, context={"request": request}
        )
        return Response(
            {
                "count": paginator.page.paginator.count,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
                "summary": get_rating_summary(property_obj),
                "results": serializer.data,
            }
        )

    def post(self, request, pk):
        property_obj = self.get_property(pk)
        if not request.user.is_authenticated:
            return Response(
                {"errors": {"detail": "Sign in to leave a review."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = ReviewCreateSerializer(
            data=request.data,
            context={"request": request, "property": property_obj},
        )
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            review = Review.objects.create(
                property=property_obj, tenant=request.user, **serializer.validated_data
            )
        except IntegrityError:
            return Response(
                {"errors": {"detail": "You have already reviewed this property."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            ReviewSerializer(review, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class ReviewDetailView(APIView):
    """
    GET    /api/reviews/<id>/
    PATCH  /api/reviews/<id>/ — owner edits their review; admins moderate
    DELETE /api/reviews/<id>/ — owner or admin
    """

    permission_classes = [AllowAny]

    def get_review(self, pk):
        return get_object_or_404(Review.objects.select_related("tenant"), pk=pk)

    def get(self, request, pk):
        review = self.get_review(pk)
        if review.status != Review.Status.APPROVED and not (
            request.user.is_authenticated
            and (request.user.is_admin_role or review.tenant_id == request.user.id)
        ):
            raise NotFound("Review not found.")
        return Response(
            ReviewSerializer(review, context={"request": request}).data
        )

    def patch(self, request, pk):
        review = self.get_review(pk)
        is_admin = request.user.is_authenticated and request.user.is_admin_role
        is_owner = request.user.is_authenticated and review.tenant_id == request.user.id

        if not (is_admin or is_owner):
            raise PermissionDenied("You can only manage your own reviews.")

        # Owners may edit content only; admins may moderate status/verification.
        if is_admin and any(f in request.data for f in ("status", "is_verified")):
            serializer = AdminReviewSerializer(
                review, data=request.data, partial=True, context={"request": request}
            )
        elif is_owner:
            if any(f in request.data for f in ("status", "is_verified")):
                raise PermissionDenied("Only admins can moderate reviews.")
            serializer = ReviewUpdateSerializer(
                review, data=request.data, partial=True, context={"request": request}
            )
        else:
            raise PermissionDenied("You can only manage your own reviews.")

        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )
        serializer.save()
        return Response(
            ReviewSerializer(review, context={"request": request}).data
        )

    def delete(self, request, pk):
        review = self.get_review(pk)
        is_admin = request.user.is_authenticated and request.user.is_admin_role
        is_owner = request.user.is_authenticated and review.tenant_id == request.user.id
        if not (is_admin or is_owner):
            raise PermissionDenied("You can only delete your own reviews.")
        review.delete()
        return Response(
            {"message": "Review deleted."}, status=status.HTTP_204_NO_CONTENT
        )


class ReviewReportCreateView(APIView):
    """POST /api/reviews/<id>/report/ — report a review for moderation."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            review = Review.objects.get(pk=pk)
        except Review.DoesNotExist:
            raise NotFound("Review not found.")

        if review.tenant_id == request.user.id:
            raise ValidationError({"detail": "You cannot report your own review."})

        serializer = ReviewReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            report = ReviewReport.objects.create(
                review=review, reporter=request.user, **serializer.validated_data
            )
        except IntegrityError:
            return Response(
                {"errors": {"detail": "You have already reported this review."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Move the review into moderation queue.
        if review.status == Review.Status.APPROVED:
            review.status = Review.Status.UNDER_REVIEW
            review.save(update_fields=["status"])

        return Response(
            ReviewReportSerializer(report).data, status=status.HTTP_201_CREATED
        )


class LandlordResponseCreateView(IsPropertyOwner, APIView):
    """POST /api/reviews/<id>/response/ — property owner responds to a review."""

    permission_classes = [IsAuthenticated, IsPropertyOwner]

    def post(self, request, pk):
        try:
            review = Review.objects.select_related("property").get(pk=pk)
        except Review.DoesNotExist:
            raise NotFound("Review not found.")

        if review.property.owner_id != request.user.id and not request.user.is_admin_role:
            raise PermissionDenied("Only the property owner can respond to this review.")

        message = (request.data.get("message") or "").strip()
        if len(message) < 3:
            return Response(
                {"errors": {"message": "Response must be at least 3 characters."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(message) > 2000:
            return Response(
                {"errors": {"message": "Response must be under 2000 characters."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response, created = LandlordResponse.objects.update_or_create(
            review=review,
            defaults={
                "landlord": request.user,
                "message": message,
            },
        )
        return Response(
            LandlordResponseSerializer(response).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class TopReviewsView(APIView):
    """GET /api/reviews/top/ — recent approved reviews across the platform."""

    permission_classes = [AllowAny]

    def get(self, request):
        reviews = (
            Review.objects.filter(status=Review.Status.APPROVED)
            .select_related("tenant", "property")
            .order_by("-created_at")[:50]
        )
        serializer = ReviewSerializer(reviews, many=True, context={"request": request})
        return Response(
            {"results": serializer.data}, status=status.HTTP_200_OK
        )


class GlobalSummaryView(APIView):
    """GET /api/reviews/summary/ — platform-wide rating summary."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(get_global_summary(), status=status.HTTP_200_OK)
