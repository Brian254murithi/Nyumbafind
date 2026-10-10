from django.urls import path

from . import views

app_name = "landlords"

urlpatterns = [
    path("landlord/dashboard/", views.LandlordDashboardView.as_view(), name="dashboard"),
]
