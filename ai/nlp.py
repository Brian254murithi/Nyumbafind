"""
Natural-language understanding for the NyumbaFind AI assistant.

The rule-based engine extracts structured rental-search intent from a
message: budget, location, property type, bedroom count and intent.
It never invents listings — every result comes from the database.
"""

import re

from properties.models import Property


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------
COUNTIES = [
    "mombasa", "kwale", "kilifi", "tana river", "lamu", "taita taveta",
    "garissa", "wajir", "mandera", "marsabit", "isiolo", "meru", "tharaka",
    "embu", "kitui", "machakos", "makueni", "nyandarua", "nyeri", "kirinyaga",
    "murang'a", "kiambu", "turkana", "west pokot", "samburu", "trans nzoia",
    "uasin gishu", "elgeyo marakwet", "nandi", "baringo", "laikipia",
    "nakuru", "narok", "kajiado", "kericho", "bomet", "kakamega", "vihiga",
    "bungoma", "busia", "siaya", "kisumu", "homabay", "migori", "kisii",
    "nyamira", "nairobi",
]

# Common towns mapped to their counties (helps match town names).
TOWN_TO_COUNTY = {
    "roysambu": "nairobi", "westlands": "nairobi", "kilimani": "nairobi",
    "lavington": "nairobi", "karen": "nairobi", "langata": "nairobi",
    "south b": "nairobi", "south c": "nairobi", "eastleigh": "nairobi",
    "embakasi": "nairobi", "ruaraka": "nairobi", "kahawa": "nairobi",
    "donholm": "nairobi", "ngong": "nairobi", "syokimau": "nairobi",
    "githurai": "kiambu", "ruaka": "kiambu", "ruiru": "kiambu",
    "thika": "kiambu", "juja": "kiambu", "kitengela": "kajiado",
    "machakos": "machakos", "thika road": "nairobi",
    "nyali": "mombasa", "bamburi": "mombasa", "likoni": "mombasa",
    "mombasa": "mombasa", "nakuru": "nakuru", "eldoret": "uasin gishu",
    "kisumu": "kisumu", "kericho": "kericho", "limuru": "kiambu",
}

PROPERTY_TYPE_KEYWORDS = {
    "bedsitter": ["bedsitter", "bed sitter", "bed-sitter"],
    "studio": ["studio"],
    "apartment": ["apartment", "apartments", "flat", "flats"],
    "house": ["house", "standalone", "family home", "family house"],
    "maisonette": ["maisonette", "maisonettes"],
    "duplex": ["duplex", "duplexes"],
    "townhouse": ["townhouse", "townhouses", "town house"],
    "bungalow": ["bungalow", "bungalows"],
    "condo": ["condo", "condominium", "condos"],
}

AMENITY_KEYWORDS = {
    "wifi": ["wifi", "wi-fi", "internet"],
    "water": ["water"],
    "security": ["security", "guarded", "gated"],
    "parking": ["parking", "garage"],
    "generator": ["generator", "backup power"],
    "furnished": ["furnished"],
    "pet friendly": ["pet friendly", "pets allowed"],
    "balcony": ["balcony"],
    "pool": ["pool", "swimming"],
}

INTENTS = {
    "search": "search",
    "compare": "compare",
    "checklist": "checklist",
    "how_reviews": "how_reviews",
    "greeting": "greeting",
    "help": "help",
    "thanks": "thanks",
    "general": "general",
}


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------
def parse_budget(text):
    """Extract min/max rent from phrases like 'under 15,000', '5k to 12k'."""
    cleaned = text.lower().replace(",", "")
    amounts = []
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(k\b|thousand|ksh|/=)?", cleaned):
        raw = float(match.group(1))
        suffix = (match.group(2) or "").strip()
        if suffix.startswith("k") or suffix == "thousand":
            raw *= 1000
        if raw >= 100:  # ignore tiny numbers (bedrooms etc.)
            amounts.append(int(raw))

    if not amounts:
        return None, None

    min_rent = max_rent = None
    between = re.search(r"between\s+(\d[\d,]*)\s*(?:k)?\s*(?:and|to|-)\s*(\d[\d,]*)\s*(k)?", cleaned)
    if between:
        low = float(between.group(1).replace(",", ""))
        high = float(between.group(2).replace(",", ""))
        if between.group(3):
            low *= 1000
            high *= 1000
        if high < low:
            low, high = high, low
        return int(low), int(high)

    if re.search(r"(under|less than|below|at most|up to|max|maximum|within|budget of)\s", cleaned):
        max_rent = max(amounts)
    elif re.search(r"(over|above|more than|at least|min|minimum|from)\s", cleaned):
        min_rent = min(amounts)
    elif len(amounts) >= 2:
        min_rent, max_rent = min(amounts[:2]), max(amounts[:2])
    else:
        # A single amount is treated as a maximum budget.
        max_rent = amounts[0]

    return min_rent, max_rent


def parse_bedrooms(text):
    """Extract bedroom count ('2 bedroom', '2-bed', bedsitter/studio -> 0)."""
    cleaned = text.lower()
    match = re.search(r"(\d)\s*[-\s]?\s*(bed|bedroom|br\b)", cleaned)
    if match:
        return int(match.group(1))
    if any(word in cleaned for word in ("bedsitter", "bed sitter", "bed-sitter", "studio")):
        return 0
    return None


def detect_property_type(text):
    cleaned = text.lower()
    best_type, best_score = None, 0
    for ptype, keywords in PROPERTY_TYPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in cleaned:
                score = len(keyword)
                if score > best_score:
                    best_type, best_score = ptype, score
    return best_type


def detect_amenities(text):
    cleaned = text.lower()
    found = []
    for amenity, keywords in AMENITY_KEYWORDS.items():
        if any(keyword in cleaned for keyword in keywords):
            found.append(amenity)
    return found


def detect_location(text):
    """Match counties, common towns and estates mentioned in the message."""
    cleaned = f" {text.lower()} "
    county = None

    # Estates are matched against actual database values (most precise).
    estates = list(
        Property.objects.exclude(estate__exact="")
        .order_by("estate")
        .values_list("estate", flat=True)
        .distinct()[:500]
    )
    for estate in sorted(estates, key=len, reverse=True):
        if f" {estate.lower()} " in cleaned or estate.lower() in cleaned:
            return {"estate": estate}

    for town, mapped_county in TOWN_TO_COUNTY.items():
        if re.search(rf"\b{re.escape(town)}\b", cleaned):
            return {"town": town, "county": mapped_county}

    for name in sorted(COUNTIES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", cleaned):
            county = name
            break

    return {"county": county} if county else {}


def determine_intent(text):
    cleaned = text.lower().strip()

    if re.search(r"\b(hi|hello|hey|jambo|mambo|good (morning|afternoon|evening))\b", cleaned):
        return INTENTS["greeting"]
    if "thank" in cleaned:
        return INTENTS["thanks"]
    if "compare" in cleaned:
        return INTENTS["compare"]
    if re.search(r"(what should i check|before renting|viewing|checklist|inspect|look out for)", cleaned):
        return INTENTS["checklist"]
    if re.search(r"(how do(es)? .*review|review.*work|how are ratings|tenant review)", cleaned):
        return INTENTS["how_reviews"]
    if re.search(r"\b(help|what can you do|capabilities)\b", cleaned):
        return INTENTS["help"]

    has_filters = (
        parse_budget(text) != (None, None)
        or parse_bedrooms(text) is not None
        or detect_property_type(text) is not None
        or bool(detect_location(text))
    )
    if has_filters:
        return INTENTS["search"]
    return INTENTS["general"]


def build_filters(text):
    """Return a dict of API-style filters extracted from free text."""
    min_rent, max_rent = parse_budget(text)
    location = detect_location(text)
    return {
        "min_rent": min_rent,
        "max_rent": max_rent,
        "bedrooms": parse_bedrooms(text),
        "property_type": detect_property_type(text),
        "amenities": detect_amenities(text),
        **location,
    }


def extract_property_ids(text):
    """Extract property references such as '#12', 'property 12', 'listing 12'."""
    ids = set()
    for match in re.finditer(
        r"(?:#|property|listing|id|and)\s*(\d+)", text.lower()
    ):
        ids.add(int(match.group(1)))
    return sorted(ids)
