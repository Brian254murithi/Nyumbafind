"""
Modular AI provider layer for NyumbaFind.

Providers implement ``generate_reply(message, filters, properties)`` and
return ``(reply_text, provider_name)``. When no API key is configured the
rule-based provider is used and clearly identifies itself as a limited
assistant — the platform never pretends a language model is connected.
"""

import json
import urllib.error
import urllib.request

from django.conf import settings
from django.db.models import Avg

from ai import nlp
from properties.models import Property

MAX_CONTEXT_PROPERTIES = 8


def apply_filters(filters):
    """Apply extracted filters to the property queryset."""
    qs = Property.objects.filter()
    if filters.get("county"):
        qs = qs.filter(county__iexact=filters["county"])
    if filters.get("town"):
        qs = qs.filter(town__icontains=filters["town"])
    if filters.get("estate"):
        qs = qs.filter(estate__icontains=filters["estate"])
    if filters.get("property_type"):
        qs = qs.filter(property_type__iexact=filters["property_type"])
    if filters.get("min_rent"):
        qs = qs.filter(rent__gte=filters["min_rent"])
    if filters.get("max_rent"):
        qs = qs.filter(rent__lte=filters["max_rent"])
    if filters.get("bedrooms") is not None:
        qs = qs.filter(bedrooms=filters["bedrooms"])
    for amenity in filters.get("amenities") or []:
        qs = qs.filter(amenities__contains=[amenity])
    return qs.order_by("-is_featured", "-created_at")


def serialize_property(p):
    """Compact, public-only property representation for AI responses.

    Never includes owner contact details, addresses of private listings,
    or any tenant information.
    """
    return {
        "id": p.id,
        "title": p.title,
        "property_type": p.property_type,
        "county": p.county,
        "town": p.town,
        "estate": p.estate,
        "rent": p.rent,
        "bedrooms": p.bedrooms,
        "bathrooms": float(p.bathrooms),
        "available": p.available,
        "is_sample": p.is_sample,
        "average_rating": round(
            p.reviews.filter(status="approved").aggregate(avg=Avg("overall"))["avg"]
            or 0.0,
            1,
        ),
        "review_count": p.reviews.filter(status="approved").count(),
    }


class BaseProvider:
    name = "base"

    def generate_reply(self, message, filters, properties, intent):
        raise NotImplementedError


class RuleBasedProvider(BaseProvider):
    """Deterministic rental assistant. Works without any API key."""

    name = "rule_based"

    def _format_property_line(self, p):
        data = serialize_property(p)
        location = ", ".join(
            part for part in (data["estate"], data["town"], data["county"]) if part
        )
        beds = (
            "Bedsitter" if data["property_type"] in ("bedsitter", "studio")
            else f"{data['bedrooms']} bed"
        )
        rating = (
            f"rated {data['average_rating']}/5 ({data['review_count']} reviews)"
            if data["review_count"]
            else "not yet reviewed"
        )
        availability = "Available" if data["available"] else "Currently unavailable"
        sample = " (sample listing)" if data["is_sample"] else ""
        return (
            f"• {data['title']} — KSh {data['rent']:,}/month, {beds}, "
            f"{location}. {rating}; {availability}.{sample} "
            f"View it with: \"show property {data['id']}\" or open listing #{data['id']}."
        )

    def _describe_filters(self, filters):
        parts = []
        location_parts = []
        if filters.get("estate"):
            location_parts.append(f"in {filters['estate']}")
        if filters.get("town") and filters.get("town") != (filters.get("county") or "").lower():
            location_parts.append(f"in {filters['town'].title()}")
        if filters.get("county") and not (
            filters.get("town") and filters["town"] == filters["county"].lower()
        ):
            location_parts.append(f"in {filters['county'].title()}")
        if location_parts:
            parts.append(" ".join(location_parts))
        if filters.get("property_type"):
            parts.append(f"({filters['property_type']}s)")
        if filters.get("min_rent") and filters.get("max_rent"):
            parts.append(
                f"between KSh {filters['min_rent']:,} and KSh {filters['max_rent']:,}"
            )
        elif filters.get("max_rent"):
            parts.append(f"under KSh {filters['max_rent']:,}")
        elif filters.get("min_rent"):
            parts.append(f"above KSh {filters['min_rent']:,}")
        if filters.get("bedrooms") == 0:
            parts.append("with 0 bedrooms (bedsitter/studio)")
        elif filters.get("bedrooms"):
            parts.append(f"with {filters['bedrooms']} bedrooms")
        return " ".join(parts)

    def generate_reply(self, message, filters, properties, intent):
        cleaned = message.lower().strip()

        if intent == "greeting":
            return (
                "Hi there! I'm NyumbaFind AI. I can search rental homes across Kenya, "
                "compare prices and ratings, and explain how tenant reviews work. "
                "What kind of home are you looking for?"
            )

        if intent == "thanks":
            return "You're welcome! Happy house hunting — and feel free to ask if you need help comparing options."

        if intent == "help":
            return (
                "Here's what I can do:\n"
                "• Search rentals by county, estate, price, property type and bedrooms "
                "(e.g. \"bedsitter in Roysambu under KSh 12,000\").\n"
                "• Compare two properties side by side (e.g. \"compare property 3 and 7\").\n"
                "• Share a viewing checklist and explain how tenant reviews work.\n"
                "Just describe what you need in plain words."
            )

        if intent == "how_reviews":
            return (
                "NyumbaFind reviews are written by verified tenants and cover seven areas: "
                "overall, property condition, location, water reliability, security, "
                "value for money and the landlord. Each review is rated 1–5 stars. "
                "Reviews flagged by the community are moderated by our team, and landlords "
                "can publicly respond to reviews on their properties. Look for the "
                "verified badge on confirmed tenant reviews."
            )

        if intent == "checklist":
            return (
                "Before signing a lease in Kenya, check:\n"
                "1. Water reliability — run taps and ask neighbours about supply.\n"
                "2. Power backup — ask whether there's a generator or solar.\n"
                "3. Security — gated access, night guards, locks and lighting.\n"
                "4. Rent inclusions — is water, electricity or internet included?\n"
                "5. Deposit & lease terms — amount, notice period, who handles repairs.\n"
                "6. The landlord — verify identity and check the property's reviews here.\n"
                "7. Photos vs reality — visit in person before paying anything."
            )

        if intent == "compare":
            ids = nlp.extract_property_ids(cleaned)
            if len(ids) >= 2:
                selected = list(Property.objects.filter(id__in=ids[:2]))
                if len(selected) == 2:
                    return self._compare(selected[0], selected[1])
            return (
                "To compare two properties, mention both listing numbers — for example "
                "\"compare property 3 and 7\". You can also tell me your budget and "
                "location and I'll shortlist options for you to compare."
            )

        # Default: search intent or general.
        if intent == "search" or filters:
            active = {
                k: v
                for k, v in filters.items()
                if v not in (None, [], "")
            }
            results = list(properties)

            if not results:
                # Suggest one broadened search as a helpful fallback.
                broadened = dict(filters)
                broadened.pop("property_type", None)
                broadened.pop("bedrooms", None)
                alternatives = list(apply_filters(broadened)[:3])
                reply = (
                    f"I couldn't find any matching listings "
                    f"{self._describe_filters(filters)}. "
                )
                if alternatives:
                    reply += (
                        "If you're flexible on the property type or size, you might "
                        "consider these instead:\n"
                        + "\n".join(self._format_property_line(p) for p in alternatives)
                    )
                else:
                    reply += (
                        "Try a higher budget, a nearby estate, or fewer filters — "
                        "new homes are listed every day."
                    )
                return reply

            head = f"I found {len(results)} listing(s) {self._describe_filters(filters)}:"
            lines = [self._format_property_line(p) for p in results[:5]]
            shown = min(5, len(results))
            if len(results) > shown:
                lines.append(
                    f"…and {len(results) - shown} more. Refine with a county, "
                    "property type or budget to narrow it down."
                )
            return head + "\n" + "\n".join(lines)

        return (
            "I'm a rental-search assistant. Tell me your budget, preferred county or "
            "estate, property type and bedroom count — for example "
            "\"I need a 2-bedroom apartment in Kilimani under KSh 45,000\" — and I'll "
            "search real NyumbaFind listings for you."
        )

    def _compare(self, a, b):
        da, db = serialize_property(a), serialize_property(b)

        def line(label, va, vb, fmt=lambda v: v):
            return f"• {label}: {fmt(va)} vs {fmt(vb)}"

        return (
            f"Here's how the two listings compare:\n"
            f"• {da['title']} (#{da['id']}) vs {db['title']} (#{db['id']})\n"
            + line("Rent", da["rent"], db["rent"], lambda v: f"KSh {v:,}/mo")
            + "\n"
            + line("Bedrooms", da["bedrooms"], db["bedrooms"])
            + "\n"
            + line("Bathrooms", da["bathrooms"], db["bathrooms"])
            + "\n"
            + line("Location", f"{da['estate'] or da['town'] or da['county']}", f"{db['estate'] or db['town'] or db['county']}")
            + "\n"
            + line("Rating", da["average_rating"], db["average_rating"], lambda v: f"{v}/5")
            + "\n"
            + line("Reviews", da["review_count"], db["review_count"])
            + "\n"
            + line("Availability", da["available"], db["available"])
            + "\nTip: the listing with the higher value-for-money rating usually "
            "balances rent against quality — check individual tenant comments before deciding."
        )


class OpenAIProvider(BaseProvider):
    """
    Optional provider using any OpenAI-compatible chat-completions API.

    Requires OPENAI_API_KEY in the environment. Falls back to the
    rule-based provider on any failure.
    """

    name = "openai"

    SYSTEM_PROMPT = (
        "You are NyumbaFind AI, a helpful Kenyan rental-property assistant. "
        "Answer using ONLY the provided listing data. Never invent prices, "
        "ratings, reviews or availability. Always mention rents in Kenyan "
        "Shillings (KSh). If the user asks for listings, present them as a "
        "short numbered list with title, rent, location, bedrooms and rating. "
        "Keep answers concise and practical. If you don't know, say so."
    )

    def _call_api(self, message, context_properties):
        payload = {
            "model": settings.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Listing data (JSON):\n{json.dumps(context_properties, default=str)}\n\n"
                        f"User message: {message}"
                    ),
                },
            ],
            "temperature": 0.3,
            "max_tokens": 600,
        }
        request = urllib.request.Request(
            f"{settings.OPENAI_BASE_URL}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"].strip()

    def generate_reply(self, message, filters, properties, intent):
        # Fast local handling for intents that shouldn't consume tokens.
        rule = RuleBasedProvider()
        if intent in ("greeting", "thanks", "help", "how_reviews", "checklist"):
            return rule.generate_reply(message, filters, properties, intent)

        context = [serialize_property(p) for p in properties[:MAX_CONTEXT_PROPERTIES]]
        try:
            reply = self._call_api(message, context)
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError):
            # Graceful degradation: fall back to rule-based and say so.
            fallback = rule.generate_reply(message, filters, properties, intent)
            return (
                fallback
                + "\n\n(Note: the AI service was unreachable, so this answer came "
                "from the built-in search assistant.)"
            )
        return reply


def get_provider():
    """Return the configured provider (never fails; falls back to rule-based)."""
    if (
        settings.AI_PROVIDER == "openai"
        and settings.OPENAI_API_KEY
    ):
        return OpenAIProvider()
    return RuleBasedProvider()
