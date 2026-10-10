from django.db.models import Avg, Count, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from properties.models import Property
from reviews.models import Review
from reviews.serializers import ReviewSerializer


class LandlordDashboardView(APIView):
    """
    GET /api/landlord/dashboard/

    Returns portfolio statistics for the signed-in landlord:
    property counts, average rent, review metrics and recent activity.
    Admins see platform-wide numbers.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        is_admin = user.is_admin_role

        if is_admin:
            properties = Property.objects.all()
        elif user.is_landlord:
            properties = Property.objects.filter(owner=user)
        else:
            return Response(
                {"errors": {"detail": "Only landlords can access the dashboard."}},
                status=403,
            )

        properties = properties.select_related("owner").prefetch_related("images")

        total_properties = properties.count()
        available = properties.filter(available=True).count()
        avg_rent = properties.aggregate(avg=Avg("rent"))["avg"] or 0

        review_qs = Review.objects.filter(
            property__in=properties, status=Review.Status.APPROVED
        )
        review_stats = review_qs.aggregate(
            total_reviews=Count("id"), average_rating=Avg("overall")
        )

        # Rating distribution across the portfolio.
        distribution = {str(i): 0 for i in range(1, 6)}
        for star, count in (
            review_qs.values("overall")
            .annotate(count=Count("id"))
            .order_by("overall")
            .values_list("overall", "count")
        ):
            distribution[str(star)] = count

        recent_properties = list(properties.order_by("-created_at")[:5])
        property_summaries = [
            {
                "id": p.id,
                "title": p.title,
                "property_type": p.property_type,
                "county": p.county,
                "town": p.town,
                "estate": p.estate,
                "rent": p.rent,
                "bedrooms": p.bedrooms,
                "available": p.available,
                "is_sample": p.is_sample,
                "created_at": p.created_at,
                "review_count": p.reviews.filter(status=Review.Status.APPROVED).count(),
                "average_rating": (
                    round(
                        p.reviews.filter(status=Review.Status.APPROVED).aggregate(
                            avg=Avg("overall")
                        )["avg"]
                        or 0.0,
                        1,
                    )
                ),
                "main_image_url": (
                    request.build_absolute_uri(p.main_image.url)
                    if p.main_image
                    else None
                ),
            }
            for p in recent_properties
        ]

        recent_reviews = (
            review_qs.select_related("property", "tenant")
            .order_by("-created_at")[:5]
        )

        return Response(
            {
                "stats": {
                    "total_properties": total_properties,
                    "available_properties": available,
                    "average_rent": round(avg_rent, 2),
                    "total_reviews": review_stats["total_reviews"],
                    "average_rating": round(review_stats["average_rating"] or 0.0, 1),
                    "rating_distribution": distribution,
                },
                "properties": property_summaries,
                "recent_reviews": ReviewSerializer(
                    recent_reviews, many=True, context={"request": request}
                ).data,
                "is_admin_view": is_admin,
            },
            status=200,
        )
