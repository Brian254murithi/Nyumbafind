"""Seed the database with realistic Kenyan sample listings.

Usage:
    python manage.py seed

All seeded listings are flagged ``is_sample=True`` so the frontend can
clearly distinguish development data from genuine landlord listings.
Images are sourced from Unsplash (images.unsplash.com) and are only
used as placeholders for demonstration.
"""

from django.core.management.base import BaseCommand

from accounts.models import User
from properties.models import Property, PropertyImage
from reviews.models import LandlordResponse, Review

# Unsplash photograph IDs (auto=format keeps them lightweight).
IMAGES = {
    "apartment_exterior": [
        "photo-1545324418-cc1a3fa10c00",
        "photo-1460317442991-0ec209397118",
        "photo-1486406146926-c627a92ad1ab",
        "photo-1600047509807-ba8f99d2cdde",
    ],
    "house_exterior": [
        "photo-1568605114967-8130f3a36994",
        "photo-1570129477492-45c003edd2be",
        "photo-1480074568708-e7b720bb3f09",
        "photo-1600585154340-be6161a56a0c",
        "photo-1512917774080-9991f1c4c750",
        "photo-1580587771525-78b9dba3b914",
        "photo-1600596542815-ffad4c1539a9",
        "photo-1523217582562-09d0def993a6",
        "photo-1600573472592-401b489a3cdc",
        "photo-1600121848594-d8644e57abab",
        "photo-1613977257363-707ba9348227",
        "photo-1617098900594-3d97179d5c52",
    ],
    "living_room": [
        "photo-1522708323590-d24dbb6b0267",
        "photo-1493809842364-78817add7ffb",
        "photo-1554995207-c18c203602cb",
        "photo-1600607687939-ce8a6c25118c",
        "photo-1600566753086-00f18fb6b3ea",
        "photo-1600210492486-724fe5c67fb0",
        "photo-1502005229762-cf1b2da7c5d6",
        "photo-1586023492125-27b2c045efd7",
        "photo-1616486338812-3dadae4b4ace",
        "photo-1618221195710-dd6b41faaea6",
        "photo-1512918728675-ed5a9ecdebfd",
        "photo-1631679706909-1844bbd07221",
        "photo-1567496898669-ee935f5f647a",
        "photo-1502672260266-1c1ef2d93688",
        "photo-1560448204-e02f11c3d0e2",
    ],
    "bedroom": [
        "photo-1560185007-cde436f6a4d0",
        "photo-1560185127-6ed189bf02f4",
        "photo-1595526114035-0d45ed16cfbf",
        "photo-1595526051245-4506e0005bd0",
        "photo-1616594039964-ae9021a400a0",
        "photo-1617806118233-18e1de247200",
        "photo-1565182999561-18d7dc61c393",
        "photo-1560185893-a55cbc8c57e8",
    ],
    "kitchen": [
        "photo-1484154218962-a197022b5858",
        "photo-1556912173-3bb406ef7e77",
        "photo-1556911220-bff31c812dba",
        "photo-1556912167-f556f1f39fdf",
        "photo-1556909114-f6e7ad7d3136",
        "photo-1565538810643-b5bdb714032a",
        "photo-1571175443880-49e1d25b2bc5",
    ],
    "bathroom": [
        "photo-1584622650111-993a426fbf0a",
        "photo-1620626011761-996317b8d101",
        "photo-1552321554-5fefe8c9ef14",
        "photo-1584622781564-1d987f7333c1",
    ],
}


def unsplash(photo_id, width=1200):
    return (
        f"https://images.unsplash.com/{photo_id}"
        f"?auto=format&fit=crop&w={width}&q=80"
    )


class Command(BaseCommand):
    help = "Seed sample Kenyan rental listings, tenants and reviews"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete previously seeded sample data first",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            Property.objects.filter(is_sample=True).delete()
            Review.objects.filter(
                property__is_sample=True
            ).delete()
            User.objects.filter(
                username__in=(
                    "sunrise_homes",
                    "parkway_properties",
                    "demo_tenant_1",
                    "demo_tenant_2",
                    "demo_tenant_3",
                )
            ).delete()
            self.stdout.write("Cleared previous sample data.")

        landlords = {}
        for username, business in (
            ("sunrise_homes", "Sunrise Homes Ltd"),
            ("parkway_properties", "Parkway Properties"),
        ):
            landlords[username], _ = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.com",
                    "role": User.Role.LANDLORD,
                    "business_name": business,
                    "phone": "+254 700 000 000",
                },
            )

        tenants = {}
        for i in range(1, 4):
            tenants[f"demo_tenant_{i}"], _ = User.objects.get_or_create(
                username=f"demo_tenant_{i}",
                defaults={
                    "email": f"tenant{i}@example.com",
                    "role": User.Role.TENANT,
                    "first_name": f"Demo",
                    "last_name": f"Tenant {i}",
                },
            )

        listings = [
            {
                "owner": "sunrise_homes",
                "title": "Sunny 2-Bedroom Apartment in Roysambu",
                "description": (
                    "Bright two-bedroom apartment on Roysambu Road. Gated "
                    "compound, backup generator, reliable borehole water, "
                    "and 24-hour security. Minutes to the tarmac and matatu "
                    "stage."
                ),
                "property_type": "apartment",
                "county": "Nairobi",
                "town": "Nairobi",
                "estate": "Roysambu",
                "address": "Roysambu Road, Roysambu",
                "rent": 18500,
                "bedrooms": 2,
                "bathrooms": 1.0,
                "latitude": -1.2186,
                "longitude": 36.8911,
                "amenities": ["Security", "Generator", "Water", "Parking"],
                "featured": True,
                "images": [
                    ("photo-1545324418-cc1a3fa10c00", "Apartment block exterior"),
                    ("photo-1560185007-cde436f6a4d0", "Master bedroom"),
                    ("photo-1484154218962-a197022b5858", "Kitchen"),
                    ("photo-1584622650111-993a426fbf0a", "Bathroom"),
                ],
            },
            {
                "owner": "sunrise_homes",
                "title": "Modern Bedsitter in Roysambu",
                "description": (
                    "Compact bedsitter with en-suite bathroom, wardrobes and "
                    "kitchenette. Water is available daily and the compound "
                    "has a night guard. Ideal for students and solo renters."
                ),
                "property_type": "bedsitter",
                "county": "Nairobi",
                "town": "Nairobi",
                "estate": "Roysambu",
                "address": "Off Roysambu Road",
                "rent": 8500,
                "bedrooms": 0,
                "bathrooms": 1.0,
                "latitude": -1.2214,
                "longitude": 36.8956,
                "amenities": ["Water", "Security"],
                "featured": False,
                "images": [
                    ("photo-1560185127-6ed189bf02f4", "Bedsitter interior"),
                    ("photo-1620626011761-996317b8d101", "En-suite bathroom"),
                ],
            },
            {
                "owner": "parkway_properties",
                "title": "Elegant 1-Bedroom in Kilimani",
                "description": (
                    "One-bedroom apartment in the heart of Kilimani with a "
                    "balcony, modern kitchen and lift access. Walking distance "
                    "to malls, restaurants and the Yaya Centre."
                ),
                "property_type": "apartment",
                "county": "Nairobi",
                "town": "Nairobi",
                "estate": "Kilimani",
                "address": "Yaya Centre area, Kilimani",
                "rent": 32000,
                "bedrooms": 1,
                "bathrooms": 1.0,
                "latitude": -1.3034,
                "longitude": 36.7773,
                "amenities": ["WiFi", "Generator", "Parking", "Balcony"],
                "featured": True,
                "images": [
                    ("photo-1502672260266-1c1ef2d93688", "Apartment living area"),
                    ("photo-1595526114035-0d45ed16cfbf", "Bedroom"),
                    ("photo-1556912173-3bb406ef7e77", "Modern kitchen"),
                ],
            },
            {
                "owner": "parkway_properties",
                "title": "Family Maisonette in Lavington",
                "description": (
                    "Three-bedroom maisonette with a garden, servants' "
                    "quarter and covered parking. Quiet, leafy Lavington "
                    "with easy access to Lavington Mall and the Gitanga "
                    "Road circuit."
                ),
                "property_type": "maisonette",
                "county": "Nairobi",
                "town": "Nairobi",
                "estate": "Lavington",
                "address": "Off Gitanga Road, Lavington",
                "rent": 65000,
                "bedrooms": 3,
                "bathrooms": 2.0,
                "latitude": -1.2936,
                "longitude": 36.7619,
                "amenities": ["Security", "Parking", "Generator", "Water"],
                "featured": True,
                "images": [
                    ("photo-1568605114967-8130f3a36994", "Maisonette exterior"),
                    ("photo-1522708323590-d24dbb6b0267", "Living room"),
                    ("photo-1560185007-cde436f6a4d0", "Bedroom"),
                    ("photo-1584622650111-993a426fbf0a", "Bathroom"),
                ],
            },
            {
                "owner": "sunrise_homes",
                "title": "2-Bedroom Flat in Westlands",
                "description": (
                    "Spacious two-bedroom flat in Westlands with a lounge, "
                    "dining area and fitted wardrobes. Close to Westgate "
                    "and Sarit Avenue malls."
                ),
                "property_type": "apartment",
                "county": "Nairobi",
                "town": "Nairobi",
                "estate": "Westlands",
                "address": "Sarit Avenue, Westlands",
                "rent": 42000,
                "bedrooms": 2,
                "bathrooms": 2.0,
                "latitude": -1.2624,
                "longitude": 36.8067,
                "amenities": ["WiFi", "Generator", "Security", "Parking"],
                "featured": False,
                "images": [
                    ("photo-1600607687939-ce8a6c25118c", "Open-plan lounge"),
                    ("photo-1616594039964-ae9021a400a0", "Bedroom"),
                    ("photo-1571175443880-49e1d25b2bc5", "Kitchen"),
                ],
            },
            {
                "owner": "parkway_properties",
                "title": "Cozy Studio in Eastleigh",
                "description": (
                    "Affordable studio apartment in Eastleigh with a "
                    "kitchenette and en-suite bathroom. Great for single "
                    "renters working in the city."
                ),
                "property_type": "studio",
                "county": "Nairobi",
                "town": "Nairobi",
                "estate": "Eastleigh",
                "address": "First Avenue, Eastleigh",
                "rent": 12000,
                "bedrooms": 0,
                "bathrooms": 1.0,
                "latitude": -1.2733,
                "longitude": 36.8514,
                "amenities": ["Water", "WiFi"],
                "featured": False,
                "images": [
                    ("photo-1554995207-c18c203602cb", "Studio interior"),
                    ("photo-1600210492486-724fe5c67fb0", "Studio corner"),
                ],
            },
            {
                "owner": "sunrise_homes",
                "title": "Standalone House in South B",
                "description": (
                    "Two-bedroom standalone house with a small yard in "
                    "South B. Gated estate with a watchman, street lighting "
                    "and reliable Nairobi Water supply."
                ),
                "property_type": "house",
                "county": "Nairobi",
                "town": "Nairobi",
                "estate": "South B",
                "address": "South B Estate",
                "rent": 25000,
                "bedrooms": 2,
                "bathrooms": 1.0,
                "latitude": -1.3142,
                "longitude": 36.8423,
                "amenities": ["Security", "Parking", "Water"],
                "featured": False,
                "images": [
                    ("photo-1570129477492-45c003edd2be", "House exterior"),
                    ("photo-1493809842364-78817add7ffb", "Living room"),
                    ("photo-1556912167-f556f1f39fdf", "Kitchen"),
                ],
            },
            {
                "owner": "parkway_properties",
                "title": "Duplex Apartment in Ruaka, Kiambu",
                "description": (
                    "Two-bedroom duplex in Ruaka with a balcony overlooking "
                    "the compound. Gated community with a generator and "
                    "borehole water. Quick drive to Two Rivers Mall."
                ),
                "property_type": "duplex",
                "county": "Kiambu",
                "town": "Ruaka",
                "estate": "Ruaka",
                "address": "Ruaka, Kiambu County",
                "rent": 28000,
                "bedrooms": 2,
                "bathrooms": 2.0,
                "latitude": -1.2334,
                "longitude": 36.7369,
                "amenities": ["Security", "Generator", "Water", "Parking"],
                "featured": True,
                "images": [
                    ("photo-1600585154340-be6161a56a0c", "Duplex exterior"),
                    ("photo-1600566753086-00f18fb6b3ea", "Upper lounge"),
                    ("photo-1595526051245-4506e0005bd0", "Bedroom"),
                ],
            },
            {
                "owner": "sunrise_homes",
                "title": "Affordable Bedsitter in Ruiru",
                "description": (
                    "Budget bedsitter in Ruiru with shared bathrooms and a "
                    "communal kitchen. Suitable for students near the Ruiru "
                    "campus area."
                ),
                "property_type": "bedsitter",
                "county": "Kiambu",
                "town": "Ruiru",
                "estate": "Ruiru",
                "address": "Ruiru Town",
                "rent": 4500,
                "bedrooms": 0,
                "bathrooms": 0.5,
                "latitude": -1.1684,
                "longitude": 36.9657,
                "amenities": ["Water"],
                "featured": False,
                "images": [
                    ("photo-1616594039964-ae9021a400a0", "Bedsitter room"),
                ],
            },
            {
                "owner": "parkway_properties",
                "title": "Beachfront 2-Bedroom in Nyali, Mombasa",
                "description": (
                    "Two-bedroom apartment in Nyali with ocean views, a "
                    "swimming pool and 24-hour security. Walking distance "
                    "to Nyali Beach and the Mombasa Mall."
                ),
                "property_type": "apartment",
                "county": "Mombasa",
                "town": "Mombasa",
                "estate": "Nyali",
                "address": "Nyali Beach Road",
                "rent": 45000,
                "bedrooms": 2,
                "bathrooms": 2.0,
                "latitude": -4.0042,
                "longitude": 39.7169,
                "amenities": ["WiFi", "Security", "Parking", "Pool"],
                "featured": True,
                "images": [
                    ("photo-1512917774080-9991f1c4c750", "Residence exterior"),
                    ("photo-1586023492125-27b2c045efd7", "Living room"),
                    ("photo-1565182999561-18d7dc61c393", "Bedroom"),
                    ("photo-1552321554-5fefe8c9ef14", "Bathroom"),
                ],
            },
            {
                "owner": "sunrise_homes",
                "title": "3-Bedroom House in Nakuru",
                "description": (
                    "Spacious three-bedroom bungalow in Nakuru with a "
                    "large compound, mature trees and a garage. Close to "
                    "Nakuru Town and Lake Nakuru National Park."
                ),
                "property_type": "bungalow",
                "county": "Nakuru",
                "town": "Nakuru",
                "estate": "Nakuru",
                "address": "Nakuru Town",
                "rent": 30000,
                "bedrooms": 3,
                "bathrooms": 2.0,
                "latitude": -0.2819,
                "longitude": 36.0635,
                "amenities": ["Parking", "Water", "Security"],
                "featured": False,
                "images": [
                    ("photo-1480074568708-e7b720bb3f09", "Bungalow exterior"),
                    ("photo-1554995207-c18c203602cb", "Living room"),
                    ("photo-1484154218962-a197022b5858", "Kitchen"),
                ],
            },
            {
                "owner": "parkway_properties",
                "title": "Townhouse in Thika",
                "description": (
                    "Two-bedroom townhouse in Thika with a small garden, "
                    "modern kitchen and secure parking. Near Thika Road "
                    "Mall and schools."
                ),
                "property_type": "townhouse",
                "county": "Kiambu",
                "town": "Thika",
                "estate": "Thika",
                "address": "Thika Town",
                "rent": 15000,
                "bedrooms": 2,
                "bathrooms": 1.0,
                "latitude": -1.0333,
                "longitude": 37.0833,
                "amenities": ["Parking", "Water", "Security"],
                "featured": False,
                "images": [
                    ("photo-1580587771525-78b9dba3b914", "Townhouse exterior"),
                    ("photo-1616486338812-3dadae4b4ace", "Lounge"),
                ],
            },
            {
                "owner": "sunrise_homes",
                "title": "Budget Room in Kahawa Sukari",
                "description": (
                    "Single room with a shared bathroom in Kahawa Sukari "
                    "along Thika Road. Quiet neighbourhood, water on tap "
                    "and a watchman at the gate."
                ),
                "property_type": "bedsitter",
                "county": "Nairobi",
                "town": "Nairobi",
                "estate": "Kahawa",
                "address": "Kahawa Sukari",
                "rent": 5500,
                "bedrooms": 0,
                "bathrooms": 0.5,
                "latitude": -1.1586,
                "longitude": 36.9297,
                "amenities": ["Water", "Security"],
                "featured": False,
                "images": [
                    ("photo-1617806118233-18e1de247200", "Room interior"),
                ],
            },
            {
                "owner": "parkway_properties",
                "title": "Condo in Hurlingham",
                "description": (
                    "Two-bedroom condominium in Hurlingham with a gym, "
                    "pool and concierge. Secure underground parking and "
                    "backup power."
                ),
                "property_type": "condo",
                "county": "Nairobi",
                "town": "Nairobi",
                "estate": "Hurlingham",
                "address": "Hurlingham, off Ngong Road",
                "rent": 55000,
                "bedrooms": 2,
                "bathrooms": 2.0,
                "latitude": -1.3197,
                "longitude": 36.7931,
                "amenities": ["WiFi", "Security", "Parking", "Pool", "Generator"],
                "featured": False,
                "images": [
                    ("photo-1600573472592-401b489a3cdc", "Condo exterior"),
                    ("photo-1600607687920-4e2a09cf159d", "Condo interior"),
                    ("photo-1616594039964-ae9021a400a0", "Bedroom"),
                ],
            },
        ]

        review_samples = [
            # (property_index, tenant_index, overall, condition, location,
            #  water, security, value, landlord, comment, recommends,
            #  verified, response_message_or_None)
            (
                0, 0, 4, 4, 5, 3, 4, 4, 5,
                "Nice apartment, very secure compound. Water is borehole "
                "and runs most of the day but pressure drops in the "
                "evening. Matatu stage is two minutes away.",
                True, True,
                "Thank you for the honest review. We are installing a "
                "booster pump to improve evening water pressure.",
            ),
            (
                0, 1, 5, 5, 4, 4, 5, 4, 5,
                "Great value for Roysambu. Generator kicks in within "
                "seconds during outages and the night guards are thorough.",
                True, True, None,
            ),
            (
                1, 2, 3, 3, 4, 2, 4, 4, 4,
                "The bedsitter itself is fine but water is unreliable on "
                "Sundays. Security is good and the landlord responds "
                "quickly to repair requests.",
                True, True,
                "We have drilled a deeper borehole and Sunday supply has "
                "improved since this review.",
            ),
            (
                2, 0, 5, 5, 5, 4, 5, 3, 5,
                "Perfect location in Kilimani — everything is walkable. "
                "Apartment is spotless and the lift works. Slightly "
                "steep rent but worth it.",
                True, True, None,
            ),
            (
                3, 1, 4, 4, 5, 4, 5, 4, 4,
                "Lovely maisonette, garden is well kept. The servants' "
                "quarter is a bonus. Parking fills up quickly on "
                "weekends though.",
                True, True, None,
            ),
            (
                4, 2, 4, 4, 4, 4, 4, 4, 4,
                "Spacious flat, good natural light. Generator covers "
                "the common areas but not each unit. Management is "
                "responsive.",
                True, False, None,
            ),
            (
                7, 0, 4, 4, 4, 4, 5, 4, 5,
                "Ruaka is growing fast and the duplex is modern. "
                "Borehole water is reliable. Two Rivers Mall is five "
                "minutes by car.",
                True, True, None,
            ),
            (
                9, 1, 5, 5, 5, 4, 5, 4, 5,
                "Ocean views are stunning and the pool is well "
                "maintained. Nyali is calm and safe. Slightly pricey "
                "but you get what you pay for.",
                True, True, None,
            ),
            (
                6, 2, 3, 3, 3, 3, 4, 4, 3,
                "House is decent for the price. Street lighting could "
                "be better at night and the yard needs some fencing "
                "work.",
                True, False, None,
            ),
            (
                10, 0, 4, 4, 4, 4, 4, 5, 4,
                "Big compound and quiet neighbourhood. Water is from "
                "Nakuru municipality and is fairly reliable. Good "
                "value for a three-bedroom.",
                True, True, None,
            ),
        ]

        created_properties = []
        for data in listings:
            landlord = landlords[data["owner"]]
            property_obj, _ = Property.objects.get_or_create(
                owner=landlord,
                title=data["title"],
                defaults={
                    "description": data["description"],
                    "property_type": data["property_type"],
                    "county": data["county"],
                    "town": data["town"],
                    "estate": data["estate"],
                    "address": data["address"],
                    "rent": data["rent"],
                    "bedrooms": data["bedrooms"],
                    "bathrooms": data["bathrooms"],
                    "amenities": data["amenities"],
                    "is_featured": data["featured"],
                    "is_sample": True,
                    "available": True,
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                },
            )
            # Backfill coordinates for properties seeded by an
            # earlier version of the command.
            if (
                data.get("latitude") is not None
                and (property_obj.latitude is None
                     or property_obj.longitude is None)
            ):
                property_obj.latitude = data["latitude"]
                property_obj.longitude = data["longitude"]
                property_obj.save(update_fields=["latitude", "longitude"])

            # Sample listings use externally hosted photos so the
            # demo works without uploading binary files locally.
            for order, (photo_id, alt) in enumerate(data["images"], start=1):
                PropertyImage.objects.get_or_create(
                    property=property_obj,
                    order=order,
                    defaults={
                        "remote_url": unsplash(photo_id, 1200),
                        "alt_text": alt,
                    },
                )
            created_properties.append(property_obj)

        self.stdout.write(
            f"Seeded {len(created_properties)} sample properties."
        )

        for (
            prop_idx, tenant_idx, overall, condition, location, water,
            security, value, landlord, comment, recommends, verified,
            response_message,
        ) in review_samples:
            property_obj = created_properties[prop_idx]
            tenant = tenants[f"demo_tenant_{tenant_idx + 1}"]
            review, _ = Review.objects.get_or_create(
                property=property_obj,
                tenant=tenant,
                defaults={
                    "overall": overall,
                    "condition": condition,
                    "location": location,
                    "water": water,
                    "security": security,
                    "value_for_money": value,
                    "landlord_rating": landlord,
                    "comment": comment,
                    "recommends": recommends,
                    "is_verified": verified,
                },
            )
            if response_message:
                LandlordResponse.objects.get_or_create(
                    review=review,
                    defaults={
                        "landlord": property_obj.owner,
                        "message": response_message,
                    },
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done — seeded {len(created_properties)} properties and "
                f"{len(review_samples)} sample reviews."
            )
        )
