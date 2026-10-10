"""Tests for the NyumbaFind AI assistant."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from ai import nlp
from ai.providers import RuleBasedProvider, apply_filters, get_provider
from ai.views import ChatView

from properties.models import Property


class NLPTests(TestCase):
    def test_parse_budget_under(self):
        self.assertEqual(nlp.parse_budget("bedsitter under 12,000"), (None, 12000))
        self.assertEqual(nlp.parse_budget("under 12k"), (None, 12000))
        self.assertEqual(nlp.parse_budget("less than 15000"), (None, 15000))

    def test_parse_budget_between(self):
        self.assertEqual(nlp.parse_budget("between 5,000 and 10,000"), (5000, 10000))
        self.assertEqual(nlp.parse_budget("between 5k and 10k"), (5000, 10000))

    def test_parse_budget_single_amount(self):
        self.assertEqual(nlp.parse_budget("15000"), (None, 15000))
        self.assertEqual(nlp.parse_budget("ksh 20k"), (None, 20000))

    def test_parse_budget_none(self):
        self.assertEqual(nlp.parse_budget("hello there"), (None, None))

    def test_parse_bedrooms(self):
        self.assertEqual(nlp.parse_bedrooms("2 bedroom apartment"), 2)
        self.assertEqual(nlp.parse_bedrooms("1-bed"), 1)
        self.assertEqual(nlp.parse_bedrooms("bedsitter"), 0)
        self.assertEqual(nlp.parse_bedrooms("nice studio flat"), 0)
        self.assertIsNone(nlp.parse_bedrooms("cheap house"))

    def test_detect_property_type(self):
        self.assertEqual(nlp.detect_property_type("apartment in town"), "apartment")
        self.assertEqual(nlp.detect_property_type("maisonette"), "maisonette")
        self.assertEqual(nlp.detect_property_type("family house"), "house")
        self.assertEqual(nlp.detect_property_type("duplex for rent"), "duplex")
        self.assertIsNone(nlp.detect_property_type("random words here"))

    def test_detect_location_county(self):
        self.assertEqual(nlp.detect_location("in Mombasa")["county"], "mombasa")
        self.assertEqual(nlp.detect_location("nakuru county")["county"], "nakuru")

    def test_detect_location_common_town(self):
        result = nlp.detect_location("bedsitter in Roysambu")
        self.assertEqual(result["town"], "roysambu")
        self.assertEqual(result["county"], "nairobi")

    def test_determine_intent(self):
        self.assertEqual(nlp.determine_intent("hello!"), "greeting")
        self.assertEqual(nlp.determine_intent("thank you"), "thanks")
        self.assertEqual(nlp.determine_intent("compare property 1 and 2"), "compare")
        self.assertEqual(
            nlp.determine_intent("what should I check before renting?"), "checklist"
        )
        self.assertEqual(
            nlp.determine_intent("how do property reviews work?"), "how_reviews"
        )
        self.assertEqual(
            nlp.determine_intent("help"), "help"
        )
        self.assertEqual(
            nlp.determine_intent("apartments in Nairobi under 20000"), "search"
        )
        self.assertEqual(nlp.determine_intent("tell me a joke"), "general")

    def test_build_filters(self):
        filters = nlp.build_filters("I need a bedsitter in Roysambu for less than KSh 12,000")
        self.assertEqual(filters["max_rent"], 12000)
        self.assertEqual(filters["bedrooms"], 0)
        self.assertEqual(filters["property_type"], "bedsitter")
        self.assertEqual(filters["town"], "roysambu")


class RuleBasedProviderTests(TestCase):
    def setUp(self):
        self.provider = RuleBasedProvider()
        self.user = get_user_model().objects.create_user(
            username="landlord1", password="strongpass123"
        )
        self.property = Property.objects.create(
            owner=self.user,
            title="Roysambu Bedsitter",
            description="Clean bedsitter with water and security in Roysambu.",
            property_type=Property.PropertyType.BEDSITTER,
            county="Nairobi",
            town="Nairobi",
            estate="Roysambu",
            rent=10000,
            bedrooms=0,
            bathrooms=1.0,
        )

    def test_search_reply_lists_matches(self):
        filters = {"county": "nairobi", "max_rent": 12000, "property_type": "bedsitter"}
        properties = apply_filters(filters)
        reply = self.provider.generate_reply(
            "bedsitter in Roysambu under 12000", filters, properties, "search"
        )
        self.assertIn("Roysambu Bedsitter", reply)
        self.assertIn("KSh 10,000", reply)

    def test_no_matches_suggests_broadening(self):
        filters = {"county": "mombasa", "max_rent": 500}
        properties = apply_filters(filters)
        reply = self.provider.generate_reply(
            "cheap bedsitter in Mombasa", filters, properties, "search"
        )
        self.assertIn("couldn't find", reply.lower())

    def test_checklist_intent(self):
        reply = self.provider.generate_reply(
            "what should I check?", {}, Property.objects.none(), "checklist"
        )
        self.assertIn("water", reply.lower())
        self.assertIn("security", reply.lower())

    def test_compare_with_two_ids(self):
        p2 = Property.objects.create(
            owner=self.user,
            title="Comparison Flat",
            description="Another flat for comparison testing.",
            property_type=Property.PropertyType.APARTMENT,
            county="Nairobi",
            estate="Kilimani",
            rent=25000,
            bedrooms=1,
            bathrooms=1.0,
        )
        reply = self.provider.generate_reply(
            f"compare property {self.property.id} and {p2.id}",
            {},
            Property.objects.none(),
            "compare",
        )
        self.assertIn("Roysambu Bedsitter", reply)
        self.assertIn("Comparison Flat", reply)
        self.assertIn("KSh 10,000", reply)
        self.assertIn("KSh 25,000", reply)

    def test_compare_without_ids_explains_how(self):
        reply = self.provider.generate_reply(
            "compare two properties", {}, Property.objects.none(), "compare"
        )
        self.assertIn("mention both listing numbers", reply.lower())


class ChatViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("ai:chat")
        Property.objects.create(
            owner=get_user_model().objects.create_user(
                username="landlord2", password="strongpass123"
            ),
            title="Westlands Apartment",
            description="Apartment in Westlands with great amenities.",
            property_type=Property.PropertyType.APARTMENT,
            county="Nairobi",
            estate="Westlands",
            rent=30000,
            bedrooms=2,
            bathrooms=2.0,
        )

    def test_chat_returns_structured_response(self):
        response = self.client.post(
            self.url,
            {"message": "Show apartments in Nairobi under 40000"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("reply", response.data)
        self.assertEqual(response.data["provider"], "rule_based")
        self.assertEqual(response.data["intent"], "search")
        self.assertTrue(len(response.data["properties"]) >= 1)
        self.assertEqual(response.data["properties"][0]["title"], "Westlands Apartment")

    def test_chat_never_includes_private_fields(self):
        response = self.client.post(
            self.url, {"message": "show all properties"}, format="json"
        )
        for prop in response.data["properties"]:
            self.assertNotIn("address", prop)
            self.assertNotIn("owner", prop)

    def test_chat_requires_message(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_chat_rejects_oversized_message(self):
        response = self.client.post(
            self.url, {"message": "x" * 600}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_chat_greets(self):
        response = self.client.post(self.url, {"message": "hello"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["intent"], "greeting")
        self.assertIn("NyumbaFind AI", response.data["reply"])

    def test_rule_based_fallback_when_no_key(self):
        provider = get_provider()
        self.assertIsInstance(provider, RuleBasedProvider)
        self.assertEqual(provider.name, "rule_based")

    def test_rate_limit_is_configured(self):
        from django.conf import settings

        self.assertEqual(ChatView.throttle_scope, "ai")
        self.assertIn("ai", settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])
        self.assertTrue(ChatView.throttle_classes)
