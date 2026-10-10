from django.db.models import Avg, Count, Q
from rest_framework import generics, status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotFound,
    ParseError,
    PermissionDenied,
    ValidationError,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from properties.geo import (
    bounding_box,
    county_centroid,
    haversine_km,
    parse_bound,
    parse_latitude,
    parse_longitude,
    parse_radius,
)
from properties.models import Property, PropertyImage
from properties.permissions import IsLandlordOrAdmin, IsOwnerOrAdmin
from properties.serializers import (
    PropertyCreateUpdateSerializer,
    PropertyDetailSerializer,
    PropertyImageSerializer,
    PropertyImageUploadSerializer,
    PropertyListSerializer,
)


ALLOWED_ORDERINGS = {
    "newest": "-created_at",
    "oldest": "created_at",
    "price_asc": "rent",
    "price_desc": "-rent",
    "rating": "rating",
    "bedrooms": "-bedrooms",
    "rent_asc": "rent",
    "rent_desc": "-rent",
}


def sort_property_list(items, sort):
    """Python-side ordering for radius searches (which return lists)."""
    reverse = True
    if sort == "newest":
        key = "created_at"
    elif sort == "oldest":
        key = "created_at"
        reverse = False
    elif sort in ("price_asc", "rent_asc"):
        key = "rent"
        reverse = False
    elif sort in ("price_desc", "rent_desc"):
        key = "rent"
    elif sort == "bedrooms":
        key = "bedrooms"
    elif sort == "rating":
        def rating_key(p):
            score = getattr(p, "rating", None)
            count = getattr(p, "review_count", 0) or 0
            return (float(score) if score is not None else 0.0, count)
        items.sort(key=rating_key, reverse=True)
        return items
    else:
        key = "created_at"

    items.sort(
        key=lambda p: getattr(p, key, None) or 0,
        reverse=reverse,
    )
    return items



class PropertyPaginationMixin:
    def paginate(self, queryset, request, view=None):
        page = super().paginate(queryset, request, view)
        if page is not None:
            return self.get_paginated_response(
                self.serializer_class(
                    page, many=True, context={"request": request}
                ).data
            )
        return None


class PropertyListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/properties/ — list & filter properties
    POST /api/properties/ — create a property (landlords only)

    Query parameters:
      county, town, estate (case-insensitive contains)
      property_type, min_rent, max_rent, bedrooms, available
      q (search across title/description/location), featured, sort
      latitude, longitude, radius (km) — distance search
      min_lat, max_lat, min_lng, max_lng — bounding-box search
      has_coords — only properties with coordinates
    """

    queryset = Property.objects.select_related("owner").prefetch_related("images")
    serializer_class = PropertyListSerializer

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PropertyCreateUpdateSerializer
        return PropertyListSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsLandlordOrAdmin()]
        return [AllowAny()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        if params.get("county"):
            qs = qs.filter(county__iexact=params["county"])
        if params.get("town"):
            qs = qs.filter(town__icontains=params["town"])
        if params.get("estate"):
            qs = qs.filter(estate__icontains=params["estate"])
        if params.get("property_type"):
            qs = qs.filter(property_type__iexact=params["property_type"])
        if params.get("min_rent"):
            try:
                qs = qs.filter(rent__gte=int(params["min_rent"]))
            except (TypeError, ValueError):
                raise ValidationError({"min_rent": "Must be a whole number."})
        if params.get("max_rent"):
            try:
                qs = qs.filter(rent__lte=int(params["max_rent"]))
            except (TypeError, ValueError):
                raise ValidationError({"max_rent": "Must be a whole number."})
        if params.get("bedrooms") not in (None, ""):
            try:
                qs = qs.filter(bedrooms=int(params["bedrooms"]))
            except (TypeError, ValueError):
                raise ValidationError({"bedrooms": "Must be a whole number."})
        if params.get("available") in ("true", "1", "yes"):
            qs = qs.filter(available=True)
        if params.get("featured") in ("true", "1", "yes"):
            qs = qs.filter(is_featured=True)
        if params.get("q"):
            query = params["q"]
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(estate__icontains=query)
                | Q(town__icontains=query)
                | Q(county__icontains=query)
                | Q(address__icontains=query)
            )

        # --- Geographic filters (map search) -------------------
        # All browser-supplied coordinates are validated server-side.
        geo_search = None  # (lat, lng, radius_km)
        if params.get("has_coords") in ("true", "1", "yes"):
            qs = qs.exclude(
                latitude__isnull=True
            ).exclude(longitude__isnull=True)

        geo_lat_raw = params.get("latitude")
        geo_lng_raw = params.get("longitude")
        if geo_lat_raw is not None or geo_lng_raw is not None:
            if geo_lat_raw in (None, "") or geo_lng_raw in (None, ""):
                raise ValidationError({
                    "latitude": "Provide both latitude and longitude."
                })
            geo_lat = parse_latitude(geo_lat_raw)
            geo_lng = parse_longitude(geo_lng_raw)
            radius_km = parse_radius(params.get("radius"))
            # Bounding-box pre-filter in SQL, then a precise
            # haversine refinement in Python below.
            min_lat, max_lat, min_lng, max_lng = bounding_box(
                geo_lat, geo_lng, radius_km
            )
            qs = qs.filter(
                latitude__gte=min_lat,
                latitude__lte=max_lat,
                longitude__gte=min_lng,
                longitude__lte=max_lng,
            )
            geo_search = (geo_lat, geo_lng, radius_km)

        # Bounding-box search for "search this area" on the map.
        bounds = {}
        for label, low, high in (
            ("min_lat", -90.0, 90.0),
            ("max_lat", -90.0, 90.0),
            ("min_lng", -180.0, 180.0),
            ("max_lng", -180.0, 180.0),
        ):
            value = parse_bound(params.get(label), label, low, high)
            if value is not None:
                bounds[label] = value
        if bounds:
            for required in ("min_lat", "max_lat", "min_lng", "max_lng"):
                if required not in bounds:
                    raise ValidationError({
                        required: "Bounding-box search needs all four "
                                  "of min_lat, max_lat, min_lng, max_lng."
                    })
            if bounds["min_lat"] >= bounds["max_lat"]:
                raise ValidationError(
                    {"max_lat": "max_lat must be greater than min_lat."}
                )
            if bounds["min_lng"] >= bounds["max_lng"]:
                raise ValidationError(
                    {"max_lng": "max_lng must be greater than min_lng."}
                )
            qs = qs.filter(
                latitude__gte=bounds["min_lat"],
                latitude__lte=bounds["max_lat"],
                longitude__gte=bounds["min_lng"],
                longitude__lte=bounds["max_lng"],
            )

        sort = params.get("sort", "newest")
        if sort == "rating":
            qs = (
                qs.annotate(
                    rating=Avg("reviews__overall", filter=Q(reviews__status="approved"))
                )
                .annotate(review_count=Count("reviews", filter=Q(reviews__status="approved")))
                .order_by("-rating", "-review_count", "-created_at")
            )
        elif sort in ALLOWED_ORDERINGS:
            qs = qs.order_by(ALLOWED_ORDERINGS[sort])

        qs = qs.distinct()

        # Precise radius refinement (haversine) — returns a
        # sorted list; DRF paginates lists the same way.
        if geo_search:
            lat, lng, radius_km = geo_search
            items = [
                p for p in qs
                if p.latitude is not None
                and p.longitude is not None
                and haversine_km(lat, lng, float(p.latitude), float(p.longitude))
                <= radius_km
            ]
            return sort_property_list(items, sort)

        return qs

    def perform_create(self, serializer):
        if not self.request.user.is_landlord:
            raise PermissionDenied("Only landlords can create property listings.")
        serializer.save(owner=self.request.user)
        # Attach any additional photographs submitted alongside the listing.
        extra_images = self.request.FILES.getlist("images")
        for index, uploaded in enumerate(extra_images):
            PropertyImage.objects.create(
                property=serializer.instance,
                image=uploaded,
                alt_text=self.request.data.get("image_alt_text", ""),
                order=index + 1,
            )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        detail = PropertyDetailSerializer(
            serializer.instance, context={"request": request}
        ).data
        return Response(detail, status=status.HTTP_201_CREATED, headers=headers)


class PropertyDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET      /api/properties/<id>/ — public property details
    PUT/PATCH/DELETE /api/properties/<id>/ — owner or admin only
    """

    queryset = Property.objects.select_related("owner").prefetch_related("images")
    serializer_class = PropertyDetailSerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [AllowAny()]
        return [IsAuthenticated(), IsLandlordOrAdmin(), IsOwnerOrAdmin()]

    def get_serializer_class(self):
        return PropertyDetailSerializer

    def perform_update(self, serializer):
        # Ownership is enforced by IsOwnerOrAdmin at object level.
        serializer.save()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = PropertyCreateUpdateSerializer(
            instance, data=request.data, partial=partial, context={"request": request}
        )
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        self.perform_update(serializer)
        return Response(
            PropertyDetailSerializer(instance, context={"request": request}).data
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({"message": "Property deleted."}, status=status.HTTP_204_NO_CONTENT)


class PropertyImagesView(APIView):
    """POST /api/properties/<id>/images/ — upload extra photos (owner/admin only)."""

    permission_classes = [IsAuthenticated, IsLandlordOrAdmin]

    def post(self, request, pk):
        try:
            property_obj = Property.objects.get(pk=pk)
        except Property.DoesNotExist:
            raise NotFound("Property not found.")

        if not (request.user.is_admin_role or property_obj.owner_id == request.user.id):
            raise PermissionDenied("You can only add photos to your own properties.")

        uploaded = request.FILES.getlist("images")
        if not uploaded:
            raise ValidationError({"images": "Select at least one image."})
        if len(uploaded) + property_obj.images.count() > 12:
            raise ValidationError({"images": "A listing may have at most 12 images."})

        created = []
        for index, image_file in enumerate(uploaded):
            image_serializer = PropertyImageUploadSerializer(
                data={"image": image_file, "alt_text": request.data.get("alt_text", "")},
            )
            if not image_serializer.is_valid():
                raise ValidationError({"images": image_serializer.errors})
            created.append(
                PropertyImage.objects.create(
                    property=property_obj,
                    image=image_file,
                    alt_text=request.data.get("alt_text", ""),
                    order=property_obj.images.count() + index + 1,
                )
            )

        return Response(
            PropertyImageSerializer(created, many=True, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class LocationSearchView(APIView):
    """
    GET /api/locations/search/ — real locations from the database.

    Autocomplete source for the map search bar. Matches
    counties, towns and estates that actually have listings,
    with a representative coordinate (the centroid of the
    matching properties) so the map can fly there.

    ?q=roysambu  — autocomplete query (min 2 characters)
    ?all=1       — every county with listings + centroid
    """

    permission_classes = [AllowAny]

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        list_all = request.query_params.get("all") in ("true", "1", "yes")

        if not list_all and len(q) < 2:
            return Response({"results": []})

        results = []
        seen = set()

        def add_entry(kind, name, county, town, count):
            key = (kind, (name or "").lower())
            if key in seen or not name:
                return
            seen.add(key)
            # Representative coordinate: centroid of the
            # matching properties, else the known county
            # centroid (map centring only — never property data).
            centroid = self._group_centroid(kind, name, county, town)
            results.append({
                "type": kind,
                "name": name,
                "county": county,
                "town": town or "",
                "count": count,
                "latitude": centroid[0] if centroid else None,
                "longitude": centroid[1] if centroid else None,
            })

        # Counties
        county_qs = Property.objects.values("county").annotate(
            count=Count("id")
        ).order_by("-count")
        if list_all:
            county_rows = county_qs[:50]
        else:
            county_rows = county_qs.filter(county__icontains=q)[:8]
        for row in county_rows:
            add_entry("county", row["county"], row["county"], None, row["count"])

        # Towns
        town_qs = (
            Property.objects.exclude(town="")
            .values("town", "county")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        town_rows = (
            town_qs[:10] if list_all else town_qs.filter(town__icontains=q)[:8]
        )
        for row in town_rows:
            add_entry("town", row["town"], row["county"], row["town"], row["count"])

        # Estates
        estate_qs = (
            Property.objects.exclude(estate="")
            .values("estate", "county", "town")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        estate_rows = (
            estate_qs[:10] if list_all else estate_qs.filter(estate__icontains=q)[:8]
        )
        for row in estate_rows:
            add_entry(
                "estate", row["estate"], row["county"], row["town"], row["count"]
            )

        return Response({"results": results})

    @staticmethod
    def _group_centroid(kind, name, county, town):
        from django.db.models import Avg as _Avg

        qs = Property.objects.exclude(latitude__isnull=True).exclude(
            longitude__isnull=True
        )
        if kind == "county":
            qs = qs.filter(county__iexact=name)
        elif kind == "town":
            qs = qs.filter(town__iexact=name, county__iexact=county)
        else:
            qs = qs.filter(estate__iexact=name, county__iexact=county)
        agg = qs.aggregate(lat=_Avg("latitude"), lng=_Avg("longitude"))
        if agg["lat"] is not None and agg["lng"] is not None:
            return (float(agg["lat"]), float(agg["lng"]))
        return county_centroid(county)
