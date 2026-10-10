from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path(
        "properties/<int:pk>/reviews/",
        views.PropertyReviewListCreateView.as_view(),
        name="property-reviews",
    ),
    path("reviews/<int:pk>/", views.ReviewDetailView.as_view(), name="review-detail"),
    path(
        "reviews/<int:pk>/report/",
        views.ReviewReportCreateView.as_view(),
        name="review-report",
    ),
    path(
        "reviews/<int:pk>/response/",
        views.LandlordResponseCreateView.as_view(),
        name="review-response",
    ),
    path("reviews/top/", views.TopReviewsView.as_view(), name="top-reviews"),
    path("reviews/summary/", views.GlobalSummaryView.as_view(), name="global-summary"),
]
