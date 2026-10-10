"""Tests for the reviews API."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from properties.models import Property
from reviews.models import LandlordResponse, Review, ReviewReport

User = get_user_model()


class ReviewTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.landlord = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="strongpass123",
            role=User.Role.LANDLORD,
            business_name="Sunrise Homes",
        )
        self.tenant = User.objects.create_user(
            username="mwanamke",
            email="tenant@example.com",
            password="strongpass123",
        )
        self.tenant2 = User.objects.create_user(
            username="secondtenant",
            email="tenant2@example.com",
            password="strongpass123",
        )
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="strongpass123",
        )
        self.tenant_token = Token.objects.create(user=self.tenant)
        self.property = Property.objects.create(
            owner=self.landlord,
            title="Garden Apartment in Lavington",
            description="Spacious apartment with a garden view in Lavington.",
            property_type=Property.PropertyType.APARTMENT,
            county="Nairobi",
            estate="Lavington",
            rent=35000,
            bedrooms=2,
            bathrooms=2.0,
        )
        self.reviews_url = reverse(
            "reviews:property-reviews", kwargs={"pk": self.property.pk}
        )

    def make_review(self, user=None, overall=4):
        user = user or self.tenant
        return Review.objects.create(
            property=self.property,
            tenant=user,
            overall=overall,
            condition=4,
            location=5,
            water=3,
            security=4,
            value_for_money=4,
            landlord_rating=5,
            comment="Great place to live, water is sometimes low.",
        )


class ReviewSubmissionTests(ReviewTestCase):
    def test_tenant_can_submit_review(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.tenant_token.key
        )
        payload = {
            "overall": 4,
            "condition": 4,
            "location": 5,
            "water": 3,
            "security": 4,
            "value_for_money": 4,
            "landlord_rating": 5,
            "comment": "Great place to live, water is sometimes low.",
            "recommends": True,
        }
        response = self.client.post(self.reviews_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.property.reviews.count(), 1)

    def test_ratings_must_be_between_1_and_5(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.tenant_token.key
        )
        payload = {
            "overall": 9,
            "condition": 0,
            "location": 5,
            "water": 3,
            "security": 4,
            "value_for_money": 4,
            "landlord_rating": 5,
            "comment": "Rating values are out of range.",
        }
        response = self.client.post(self.reviews_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_comment_too_short_is_rejected(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.tenant_token.key
        )
        payload = {
            "overall": 4,
            "condition": 4,
            "location": 4,
            "water": 4,
            "security": 4,
            "value_for_money": 4,
            "landlord_rating": 4,
            "comment": "short",
        }
        response = self.client.post(self.reviews_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_review_prevented(self):
        self.make_review()
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.tenant_token.key
        )
        payload = {
            "overall": 5,
            "condition": 5,
            "location": 5,
            "water": 5,
            "security": 5,
            "value_for_money": 5,
            "landlord_rating": 5,
            "comment": "Second review attempt for the same property.",
        }
        response = self.client.post(self.reviews_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_landlord_cannot_review_own_property(self):
        token = Token.objects.create(user=self.landlord)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        payload = {
            "overall": 5,
            "condition": 5,
            "location": 5,
            "water": 5,
            "security": 5,
            "value_for_money": 5,
            "landlord_rating": 5,
            "comment": "Landlord reviewing their own listing is not allowed.",
        }
        response = self.client.post(self.reviews_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anonymous_cannot_review(self):
        payload = {
            "overall": 4,
            "condition": 4,
            "location": 4,
            "water": 4,
            "security": 4,
            "value_for_money": 4,
            "landlord_rating": 4,
            "comment": "Anonymous review attempt here.",
        }
        response = self.client.post(self.reviews_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_two_tenants_can_review_same_property(self):
        self.make_review(user=self.tenant)
        token2 = Token.objects.create(user=self.tenant2)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token2.key)
        payload = {
            "overall": 3,
            "condition": 3,
            "location": 4,
            "water": 2,
            "security": 4,
            "value_for_money": 3,
            "landlord_rating": 4,
            "comment": "Different tenant, independent review here.",
        }
        response = self.client.post(self.reviews_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.property.reviews.count(), 2)


class ReviewListingTests(ReviewTestCase):
    def test_listing_includes_summary_and_reviews(self):
        self.make_review(overall=5)
        Review.objects.create(
            property=self.property,
            tenant=self.tenant2,
            overall=3,
            condition=3,
            location=4,
            water=2,
            security=3,
            value_for_money=3,
            landlord_rating=4,
            comment="Average experience overall for the price.",
        )
        response = self.client.get(self.reviews_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        summary = response.data["summary"]
        self.assertEqual(summary["review_count"], 2)
        self.assertEqual(summary["average_rating"], 4.0)
        self.assertEqual(summary["distribution"]["5"], 1)
        self.assertEqual(summary["distribution"]["3"], 1)
        self.assertEqual(len(response.data["results"]), 2)

    def test_only_approved_reviews_are_public(self):
        review = self.make_review()
        review.status = Review.Status.UNDER_REVIEW
        review.save()
        response = self.client.get(self.reviews_url)
        self.assertEqual(response.data["summary"]["review_count"], 0)
        self.assertEqual(len(response.data["results"]), 0)


class ReviewManagementTests(ReviewTestCase):
    def test_owner_can_edit_own_review(self):
        review = self.make_review()
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.tenant_token.key
        )
        url = reverse("reviews:review-detail", kwargs={"pk": review.pk})
        response = self.client.patch(
            url, {"overall": 2, "comment": "Updated comment with more detail."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        review.refresh_from_db()
        self.assertEqual(review.overall, 2)

    def test_owner_cannot_moderate_status(self):
        review = self.make_review()
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.tenant_token.key
        )
        url = reverse("reviews:review-detail", kwargs={"pk": review.pk})
        response = self.client.patch(
            url, {"status": "rejected"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_owner_cannot_edit_review(self):
        review = self.make_review()
        token2 = Token.objects.create(user=self.tenant2)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token2.key)
        url = reverse("reviews:review-detail", kwargs={"pk": review.pk})
        response = self.client.patch(
            url, {"overall": 1}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_verify_and_moderate(self):
        review = self.make_review()
        self.client.force_authenticate(user=self.admin)
        url = reverse("reviews:review-detail", kwargs={"pk": review.pk})
        response = self.client.patch(
            url, {"is_verified": True, "status": "approved"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        review.refresh_from_db()
        self.assertTrue(review.is_verified)

    def test_admin_can_delete_review(self):
        review = self.make_review()
        self.client.force_authenticate(user=self.admin)
        url = reverse("reviews:review-detail", kwargs={"pk": review.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Review.objects.filter(pk=review.pk).exists())


class LandlordResponseTests(ReviewTestCase):
    def test_property_owner_can_respond(self):
        review = self.make_review()
        token = Token.objects.create(user=self.landlord)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        url = reverse("reviews:review-response", kwargs={"pk": review.pk})
        response = self.client.post(
            url, {"message": "Thank you for the feedback! We are fixing the water."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            LandlordResponse.objects.filter(review=review).exists()
        )

    def test_response_is_limited_to_property_owner(self):
        review = self.make_review()
        token2 = Token.objects.create(user=self.tenant2)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token2.key)
        url = reverse("reviews:review-response", kwargs={"pk": review.pk})
        response = self.client.post(
            url, {"message": "I should not be able to respond."}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_short_response_rejected(self):
        review = self.make_review()
        token = Token.objects.create(user=self.landlord)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        url = reverse("reviews:review-response", kwargs={"pk": review.pk})
        response = self.client.post(url, {"message": "ok"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_response_included_in_review_payload(self):
        review = self.make_review()
        LandlordResponse.objects.create(
            review=review,
            landlord=self.landlord,
            message="We appreciate the honest feedback.",
        )
        response = self.client.get(self.reviews_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["results"][0]["response"]["message"],
            "We appreciate the honest feedback.",
        )


class ReviewReportTests(ReviewTestCase):
    def test_user_can_report_review(self):
        review = self.make_review()
        token2 = Token.objects.create(user=self.tenant2)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token2.key)
        url = reverse("reviews:review-report", kwargs={"pk": review.pk})
        response = self.client.post(
            url,
            {"reason": "inaccurate", "description": "The rent quoted is wrong."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ReviewReport.objects.count(), 1)
        review.refresh_from_db()
        self.assertEqual(review.status, Review.Status.UNDER_REVIEW)

    def test_cannot_report_own_review(self):
        review = self.make_review()
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.tenant_token.key
        )
        url = reverse("reviews:review-report", kwargs={"pk": review.pk})
        response = self.client.post(url, {"reason": "spam"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_report_prevented(self):
        review = self.make_review()
        token2 = Token.objects.create(user=self.tenant2)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token2.key)
        url = reverse("reviews:review-report", kwargs={"pk": review.pk})
        first = self.client.post(url, {"reason": "spam"}, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.client.post(url, {"reason": "offensive"}, format="json")
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)


class GlobalSummaryTests(ReviewTestCase):
    def test_global_summary_aggregates_across_properties(self):
        self.make_review(overall=4)
        other_property = Property.objects.create(
            owner=self.landlord,
            title="Another place in town",
            description="Another property for summary aggregation.",
            county="Nairobi",
            rent=10000,
        )
        Review.objects.create(
            property=other_property,
            tenant=self.tenant2,
            overall=2,
            condition=2,
            location=3,
            water=1,
            security=3,
            value_for_money=2,
            landlord_rating=3,
            comment="Second property review for the global summary.",
        )
        response = self.client.get(reverse("reviews:global-summary"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["review_count"], 2)
        self.assertEqual(response.data["properties_reviewed"], 2)
        self.assertAlmostEqual(response.data["average_rating"], 3.0)


class TopReviewsTests(ReviewTestCase):
    def test_top_reviews_are_public_and_approved(self):
        self.make_review()
        response = self.client.get(reverse("reviews:top-reviews"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertIn("tenant_name", response.data["results"][0])
