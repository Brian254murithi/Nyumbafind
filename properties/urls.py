from django.urls import path

from . import views

app_name = "properties"

urlpatterns = [
    path(
        "properties/",
        views.PropertyListCreateView.as_view(),
        name="property-list",
    ),
    path(
        "properties/<int:pk>/",
        views.PropertyDetailView.as_view(),
        name="property-detail",
    ),
    path(
        "properties/<int:pk>/images/",
        views.PropertyImagesView.as_view(),
        name="property-images",
    ),
    path(
        "locations/search/",
        views.LocationSearchView.as_view(),
        name="location-search",
    ),
]
