"""Tests for the landlord dashboard API."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from properties.models import Property
from reviews.models import Review

User = get_user_model()


class LandlordDashboardTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("landlords:dashboard")
        self.landlord = User.objects.create_user(
            username="boss",
            email="boss@example.com",
            password="strongpass123",
            role=User.Role.LANDLORD,
            business_name="Boss Properties",
        )
        self.tenant = User.objects.create_user(
            username="renter",
            email="renter@example.com",
            password="strongpass123",
        )
        self.admin = User.objects.create_superuser(
            username="superadmin",
            email="super@example.com",
            password="strongpass123",
        )
        self.property = Property.objects.create(
            owner=self.landlord,
            title="Boss Towers 1BR",
            description="One bedroom apartment in Boss Towers.",
            county="Nairobi",
            estate="Westlands",
            rent=22000,
            bedrooms=1,
            bathrooms=1.0,
        )
        self.property2 = Property.objects.create(
            owner=self.landlord,
            title="Boss Studios",
            description="Affordable studios near the campus.",
            county="Kiambu",
            town="Ruiru",
            rent=8000,
            bedrooms=0,
            bathrooms=1.0,
            available=False,
        )
        Review.objects.create(
            property=self.property,
            tenant=self.tenant,
            overall=5,
            condition=5,
            location=4,
            water=4,
            security=5,
            value_for_money=4,
            landlord_rating=5,
            comment="Excellent landlord and well kept building.",
        )

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_landlord_sees_own_stats(self):
        token = Token.objects.create(user=self.landlord)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stats = response.data["stats"]
        self.assertEqual(stats["total_properties"], 2)
        self.assertEqual(stats["available_properties"], 1)
        self.assertEqual(stats["total_reviews"], 1)
        self.assertEqual(stats["average_rating"], 5.0)
        self.assertEqual(stats["average_rent"], 15000)
        self.assertEqual(len(response.data["properties"]), 2)
        self.assertFalse(response.data["is_admin_view"])

    def test_tenant_is_forbidden(self):
        token = Token.objects.create(user=self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_sees_all_properties(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_admin_view"])
        self.assertEqual(response.data["stats"]["total_properties"], 2)

    def test_property_summaries_include_ratings(self):
        token = Token.objects.create(user=self.landlord)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        response = self.client.get(self.url)
        first = response.data["properties"][0]
        self.assertIn("average_rating", first)
        self.assertIn("review_count", first)
