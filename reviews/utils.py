"""Rating aggregation utilities shared across apps."""

from django.db.models import Avg, Count, Q

CATEGORY_FIELDS = {
    "condition": "condition",
    "location": "location",
    "water": "water",
    "security": "security",
    "value_for_money": "value_for_money",
    "landlord": "landlord_rating",
}


def get_rating_summary(property_obj):
    """Return average rating, review count, star distribution and category averages."""
    from reviews.models import Review as ReviewModel  # local import avoids circulars

    approved = property_obj.reviews.filter(status=ReviewModel.Status.APPROVED)
    total = approved.count()

    if total == 0:
        return {
            "average_rating": 0.0,
            "review_count": 0,
            "distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
            "category_averages": {
                "condition": 0.0,
                "location": 0.0,
                "water": 0.0,
                "security": 0.0,
                "value_for_money": 0.0,
                "landlord": 0.0,
            },
        }

    distribution = {str(i): 0 for i in range(1, 6)}
    for star, count in (
        approved.values("overall")
        .annotate(count=Count("id"))
        .order_by("overall")
        .values_list("overall", "count")
    ):
        distribution[str(star)] = count

    aggregates = approved.aggregate(
        average_rating=Avg("overall"),
        **{f"avg_{key}": Avg(field) for key, field in CATEGORY_FIELDS.items()},
    )

    category_averages = {}
    for key in CATEGORY_FIELDS:
        value = aggregates.get(f"avg_{key}")
        category_averages[key] = round(value, 1) if value is not None else 0.0

    return {
        "average_rating": round(aggregates["average_rating"] or 0.0, 1),
        "review_count": total,
        "distribution": distribution,
        "category_averages": category_averages,
    }


def get_global_summary():
    """Platform-wide review summary (homepage rating panel)."""
    from reviews.models import Review as ReviewModel

    approved = ReviewModel.objects.filter(status=ReviewModel.Status.APPROVED)
    total = approved.count()

    if total == 0:
        return {
            "average_rating": 0.0,
            "review_count": 0,
            "distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
            "category_averages": {key: 0.0 for key in CATEGORY_FIELDS},
            "properties_reviewed": 0,
        }

    distribution = {str(i): 0 for i in range(1, 6)}
    for star, count in (
        approved.values("overall")
        .annotate(count=Count("id"))
        .order_by("overall")
        .values_list("overall", "count")
    ):
        distribution[str(star)] = count

    aggregates = approved.aggregate(
        average_rating=Avg("overall"),
        properties_reviewed=Count("property", distinct=True),
        **{f"avg_{key}": Avg(field) for key, field in CATEGORY_FIELDS.items()},
    )

    category_averages = {}
    for key in CATEGORY_FIELDS:
        value = aggregates.get(f"avg_{key}")
        category_averages[key] = round(value, 1) if value is not None else 0.0

    return {
        "average_rating": round(aggregates["average_rating"] or 0.0, 1),
        "review_count": total,
        "distribution": distribution,
        "category_averages": category_averages,
        "properties_reviewed": aggregates["properties_reviewed"],
    }
