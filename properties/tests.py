"""Tests for the properties API."""

import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from properties.models import Property, PropertyImage

User = get_user_model()


def make_image(name="test.png", size=(120, 80)):
    """Generate a small valid PNG for upload tests."""
    image = Image.new("RGB", size, color=(70, 130, 180))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return SimpleUploadedFile(
        name, buffer.getvalue(), content_type="image/png"
    )


class PropertyTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.landlord = User.objects.create_user(
            username="owner1",
            email="owner1@example.com",
            password="strongpass123",
            role=User.Role.LANDLORD,
            business_name="Test Homes",
        )
        self.landlord_token = Token.objects.create(user=self.landlord)
        self.tenant = User.objects.create_user(
            username="tenant1",
            email="tenant1@example.com",
            password="strongpass123",
            role=User.Role.TENANT,
        )
        self.admin = User.objects.create_superuser(
            username="admin1",
            email="admin1@example.com",
            password="strongpass123",
        )
        self.property = Property.objects.create(
            owner=self.landlord,
            title="Sunny 2BR Apartment in Roysambu",
            description="A bright two-bedroom apartment near Roysambu tarmac.",
            property_type=Property.PropertyType.APARTMENT,
            county="Nairobi",
            town="Nairobi",
            estate="Roysambu",
            rent=18000,
            bedrooms=2,
            bathrooms=1.0,
            amenities=["WiFi", "Generator", "Security"],
        )
        self.property2 = Property.objects.create(
            owner=self.landlord,
            title="Cozy Bedsitter in Kilimani",
            description="Compact bedsitter with own bathroom in Kilimani.",
            property_type=Property.PropertyType.BEDSITTER,
            county="Nairobi",
            town="Nairobi",
            estate="Kilimani",
            rent=6500,
            bedrooms=0,
            bathrooms=1.0,
        )
        self.list_url = reverse("properties:property-list")
        self.detail_url = reverse(
            "properties:property-detail", kwargs={"pk": self.property.pk}
        )


class PropertyListTests(PropertyTestCase):
    def test_list_is_public(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_filter_by_county(self):
        response = self.client.get(self.list_url, {"county": "nairobi"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_filter_by_property_type(self):
        response = self.client.get(self.list_url, {"property_type": "bedsitter"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.property2.id)

    def test_filter_by_rent_range(self):
        response = self.client.get(self.list_url, {"min_rent": 10000})
        self.assertEqual(response.data["count"], 1)
        response = self.client.get(
            self.list_url, {"max_rent": 10000}
        )
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.property2.id)

    def test_filter_by_bedrooms(self):
        response = self.client.get(self.list_url, {"bedrooms": 0})
        self.assertEqual(response.data["count"], 1)
        response = self.client.get(self.list_url, {"bedrooms": 2})
        self.assertEqual(response.data["count"], 1)

    def test_filter_by_availability(self):
        self.property.available = False
        self.property.save()
        response = self.client.get(self.list_url, {"available": "true"})
        self.assertEqual(response.data["count"], 1)

    def test_search_query(self):
        response = self.client.get(self.list_url, {"q": "roysambu"})
        self.assertEqual(response.data["count"], 1)
        response = self.client.get(self.list_url, {"q": "bedsitter"})
        self.assertEqual(response.data["count"], 1)

    def test_sort_by_price_asc(self):
        response = self.client.get(self.list_url, {"sort": "price_asc"})
        rents = [item["rent"] for item in response.data["results"]]
        self.assertEqual(rents, sorted(rents))

    def test_invalid_rent_filter_returns_validation_error(self):
        response = self.client.get(self.list_url, {"min_rent": "abc"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PropertyCreateTests(PropertyTestCase):
    def test_landlord_can_create_property(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.landlord_token.key
        )
        data = {
            "title": "Modern 1BR in Westlands",
            "description": "A modern one-bedroom apartment in Westlands.",
            "property_type": "apartment",
            "county": "Nairobi",
            "town": "Nairobi",
            "estate": "Westlands",
            "rent": 25000,
            "bedrooms": 1,
            "bathrooms": 1.0,
            "amenities": ["WiFi"],
        }
        response = self.client.post(self.list_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Property.objects.get(title="Modern 1BR in Westlands")
        self.assertEqual(created.owner, self.landlord)

    def test_tenant_cannot_create_property(self):
        self.client.force_authenticate(user=self.tenant)
        data = {
            "title": "Some house",
            "description": "A house description here.",
            "property_type": "house",
            "county": "Nairobi",
            "rent": 10000,
            "bedrooms": 2,
            "bathrooms": 1.0,
        }
        response = self.client.post(self.list_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_cannot_create_property(self):
        response = self.client.post(
            self.list_url,
            {
                "title": "House",
                "description": "Description long enough.",
                "county": "Nairobi",
                "rent": 1000,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_validation_errors_on_create(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.landlord_token.key
        )
        data = {
            "title": "Hi",  # too short
            "description": "short",  # too short
            "county": "Nairobi",
            "rent": -5,
            "bedrooms": 99,
            "bathrooms": 99,
        }
        response = self.client.post(self.list_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        errors = response.data["errors"]
        self.assertIn("title", errors)
        self.assertIn("description", errors)
        self.assertIn("rent", errors)

    def test_bedsitter_forced_to_zero_bedrooms(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.landlord_token.key
        )
        data = {
            "title": "Nice bedsitter near town",
            "description": "A bedsitter with own bathroom and water.",
            "property_type": "bedsitter",
            "county": "Nairobi",
            "rent": 5000,
            "bedrooms": 2,
            "bathrooms": 1.0,
        }
        response = self.client.post(self.list_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Property.objects.get(pk=response.data["id"]).bedrooms, 0)

    def test_create_with_main_image(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.landlord_token.key
        )
        image = make_image("house.png")
        data = {
            "title": "House with photo",
            "description": "A house with a main photo attached.",
            "property_type": "house",
            "county": "Kiambu",
            "rent": 12000,
            "bedrooms": 2,
            "bathrooms": 1.0,
            "main_image": image,
        }
        response = self.client.post(self.list_url, data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Property.objects.get(pk=response.data["id"]).main_image)

    def test_reject_non_image_upload(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.landlord_token.key
        )
        bad = SimpleUploadedFile(
            "doc.pdf", b"%PDF-1.4 fake", content_type="application/pdf"
        )
        data = {
            "title": "House with bad photo",
            "description": "A house with an invalid photo.",
            "property_type": "house",
            "county": "Kiambu",
            "rent": 12000,
            "bedrooms": 2,
            "bathrooms": 1.0,
            "main_image": bad,
        }
        response = self.client.post(self.list_url, data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PropertyPermissionTests(PropertyTestCase):
    def test_owner_can_update_own_property(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.landlord_token.key
        )
        response = self.client.patch(
            self.detail_url, {"rent": 19000}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.property.refresh_from_db()
        self.assertEqual(self.property.rent, 19000)

    def test_other_landlord_cannot_update(self):
        other = User.objects.create_user(
            username="owner2",
            email="owner2@example.com",
            password="strongpass123",
            role=User.Role.LANDLORD,
        )
        self.client.force_authenticate(user=other)
        response = self.client.patch(
            self.detail_url, {"rent": 99999}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_delete_own_property(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.landlord_token.key
        )
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Property.objects.filter(pk=self.property.pk).exists())

    def test_admin_can_delete_any_property(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_detail_is_public(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("rating", response.data)
        self.assertIn("images", response.data)


class PropertyImageTests(PropertyTestCase):
    def test_owner_can_upload_images(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.landlord_token.key
        )
        url = reverse("properties:property-images", kwargs={"pk": self.property.pk})
        image = make_image("interior.png")
        response = self.client.post(
            url, {"images": [image], "alt_text": "Living room"}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.property.images.count(), 1)

    def test_other_landlord_cannot_upload_images(self):
        other = User.objects.create_user(
            username="owner3",
            email="owner3@example.com",
            password="strongpass123",
            role=User.Role.LANDLORD,
        )
        self.client.force_authenticate(user=other)
        url = reverse("properties:property-images", kwargs={"pk": self.property.pk})
        image = make_image("interior.png")
        response = self.client.post(url, {"images": [image]}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_images_are_serialized_with_absolute_urls(self):
        PropertyImage.objects.create(
            property=self.property,
            image=make_image("kitchen.png"),
            alt_text="Kitchen",
        )
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        image_data = response.data["images"][0]
        self.assertTrue(image_data["image_url"].startswith("http"))
        self.assertEqual(image_data["alt_text"], "Kitchen")


class GeoSearchTests(TestCase):
    """Map-based geographic filtering on /api/properties/."""

    def setUp(self):
        self.client = APIClient()
        self.landlord = User.objects.create_user(
            username="geo_landlord",
            email="geo_landlord@example.com",
            password="strongpass123",
            role=User.Role.LANDLORD,
        )

        def prop(title, estate, lat, lng, rent=10000):
            return Property.objects.create(
                owner=self.landlord,
                title=title,
                description=f"Geospatial test listing {title}.",
                property_type=Property.PropertyType.APARTMENT,
                county="Nairobi",
                town="Nairobi",
                estate=estate,
                address=estate,
                rent=rent,
                bedrooms=1,
                bathrooms=1.0,
                latitude=lat,
                longitude=lng,
            )

        # Roysambu anchor.
        self.roysambu = prop(
            "Geo Roysambu Flat", "Roysambu", -1.2186, 36.8911
        )
        # ~2 km away.
        self.nearby = prop(
            "Geo Nearby Flat", "Kasarani", -1.2380, 36.8980
        )
        # ~9 km away (Westlands).
        self.far = prop(
            "Geo Westlands Flat", "Westlands", -1.2624, 36.8067
        )
        # No coordinates — must never appear as a marker.
        self.no_coords = Property.objects.create(
            owner=self.landlord,
            title="Geo Unlocated Flat",
            description="A listing without coordinates.",
            property_type=Property.PropertyType.APARTMENT,
            county="Nairobi",
            town="Nairobi",
            estate="Unknown",
            address="Somewhere",
            rent=9000,
            bedrooms=1,
            bathrooms=1.0,
        )
        self.list_url = reverse("properties:property-list")

    def test_radius_search_returns_only_nearby_properties(self):
        response = self.client.get(
            self.list_url,
            {"latitude": "-1.2186", "longitude": "36.8911", "radius": "5"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = {p["title"] for p in response.data["results"]}
        self.assertIn("Geo Roysambu Flat", titles)
        self.assertIn("Geo Nearby Flat", titles)
        self.assertNotIn("Geo Westlands Flat", titles)
        self.assertNotIn("Geo Unlocated Flat", titles)

    def test_large_radius_includes_distant_properties(self):
        response = self.client.get(
            self.list_url,
            {"latitude": "-1.2186", "longitude": "36.8911", "radius": "50"},
        )
        titles = {p["title"] for p in response.data["results"]}
        self.assertIn("Geo Roysambu Flat", titles)
        self.assertIn("Geo Westlands Flat", titles)

    def test_default_radius_is_10km(self):
        response = self.client.get(
            self.list_url, {"latitude": "-1.2186", "longitude": "36.8911"}
        )
        titles = {p["title"] for p in response.data["results"]}
        self.assertIn("Geo Nearby Flat", titles)
        self.assertNotIn("Geo Westlands Flat", titles)

    def test_invalid_coordinates_rejected(self):
        cases = [
            {"latitude": "91", "longitude": "36.89"},
            {"latitude": "abc", "longitude": "36.89"},
            {"latitude": "-1.21", "longitude": "181"},
            {"latitude": "-1.21", "longitude": "nope"},
        ]
        for params in cases:
            response = self.client.get(self.list_url, params)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_latitude_without_longitude_rejected(self):
        response = self.client.get(
            self.list_url, {"latitude": "-1.2186"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_radius_rejected(self):
        for radius in ("0", "-5", "abc", "99999"):
            response = self.client.get(
                self.list_url,
                {
                    "latitude": "-1.2186",
                    "longitude": "36.8911",
                    "radius": radius,
                },
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bounding_box_search(self):
        # A tight box around Roysambu only.
        response = self.client.get(
            self.list_url,
            {
                "min_lat": "-1.25",
                "max_lat": "-1.19",
                "min_lng": "36.87",
                "max_lng": "36.92",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = {p["title"] for p in response.data["results"]}
        self.assertIn("Geo Roysambu Flat", titles)
        self.assertNotIn("Geo Westlands Flat", titles)

    def test_incomplete_bounding_box_rejected(self):
        response = self.client.get(
            self.list_url, {"min_lat": "-1.25", "max_lat": "-1.19"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_bounding_box_rejected(self):
        response = self.client.get(
            self.list_url,
            {
                "min_lat": "91",
                "max_lat": "-1.19",
                "min_lng": "36.87",
                "max_lng": "36.92",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inverted_bounding_box_rejected(self):
        response = self.client.get(
            self.list_url,
            {
                "min_lat": "-1.19",
                "max_lat": "-1.25",
                "min_lng": "36.87",
                "max_lng": "36.92",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_has_coords_filter(self):
        response = self.client.get(
            self.list_url, {"has_coords": "true", "estate": "Roysambu"}
        )
        titles = {p["title"] for p in response.data["results"]}
        self.assertIn("Geo Roysambu Flat", titles)
        self.assertNotIn("Geo Unlocated Flat", titles)

    def test_radius_search_respects_other_filters(self):
        response = self.client.get(
            self.list_url,
            {
                "latitude": "-1.2186",
                "longitude": "36.8911",
                "radius": "50",
                "min_rent": "9500",
            },
        )
        titles = {p["title"] for p in response.data["results"]}
        self.assertIn("Geo Roysambu Flat", titles)
        self.assertNotIn("Geo Unlocated Flat", titles)

    def test_radius_search_sorted_by_price(self):
        response = self.client.get(
            self.list_url,
            {
                "latitude": "-1.2186",
                "longitude": "36.8911",
                "radius": "50",
                "sort": "price_asc",
            },
        )
        rents = [p["rent"] for p in response.data["results"]]
        self.assertEqual(rents, sorted(rents))

    def test_list_includes_coordinates(self):
        response = self.client.get(self.list_url)
        first = response.data["results"][0]
        self.assertIn("latitude", first)
        self.assertIn("longitude", first)


class LocationSearchTests(TestCase):
    """GET /api/locations/search/ — real locations from the DB."""

    def setUp(self):
        self.client = APIClient()
        self.landlord = User.objects.create_user(
            username="loc_landlord",
            email="loc_landlord@example.com",
            password="strongpass123",
            role=User.Role.LANDLORD,
        )
        Property.objects.create(
            owner=self.landlord,
            title="Loc Roysambu One",
            description="Location search test listing one.",
            property_type=Property.PropertyType.APARTMENT,
            county="Nairobi",
            town="Nairobi",
            estate="Roysambu",
            rent=12000,
            bedrooms=1,
            bathrooms=1.0,
            latitude=-1.2186,
            longitude=36.8911,
        )
        Property.objects.create(
            owner=self.landlord,
            title="Loc Roysambu Two",
            description="Location search test listing two.",
            property_type=Property.PropertyType.BEDSITTER,
            county="Nairobi",
            town="Nairobi",
            estate="Roysambu",
            rent=7000,
            bedrooms=0,
            bathrooms=1.0,
            latitude=-1.2214,
            longitude=36.8956,
        )
        self.url = reverse("properties:location-search")

    def test_short_query_returns_empty(self):
        response = self.client.get(self.url, {"q": "a"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])

    def test_estate_search(self):
        response = self.client.get(self.url, {"q": "roysambu"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        estates = [
            r for r in response.data["results"] if r["type"] == "estate"
        ]
        self.assertTrue(estates)
        self.assertEqual(estates[0]["name"], "Roysambu")
        self.assertEqual(estates[0]["count"], 2)
        self.assertIsNotNone(estates[0]["latitude"])
        self.assertIsNotNone(estates[0]["longitude"])

    def test_county_search(self):
        response = self.client.get(self.url, {"q": "nairobi"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        counties = [
            r for r in response.data["results"] if r["type"] == "county"
        ]
        self.assertTrue(counties)
        self.assertEqual(counties[0]["name"], "Nairobi")

    def test_all_counties_with_centroids(self):
        response = self.client.get(self.url, {"all": "1"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        counties = [
            r for r in response.data["results"] if r["type"] == "county"
        ]
        self.assertTrue(counties)
        self.assertIsNotNone(counties[0]["latitude"])

    def test_no_matches(self):
        response = self.client.get(self.url, {"q": "zzz_nonexistent"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])
