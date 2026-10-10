"""AI assistant API endpoint."""

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from ai import nlp
from ai.providers import apply_filters, get_provider, serialize_property


class ChatView(APIView):
    """
    POST /api/ai/chat/

    Body: {"message": "..."}

    The backend extracts intent and filters, queries the real property
    database, and passes only public listing data to the configured AI
    provider. Private tenant/landlord data is never exposed, and the
    assistant can never bypass Django permissions.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"

    def post(self, request):
        message = (request.data.get("message") or "").strip()

        if not message:
            return Response(
                {"errors": {"message": "Please enter a message."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(message) > settings.AI_MAX_MESSAGE_LENGTH:
            return Response(
                {
                    "errors": {
                        "message": f"Message is too long (max {settings.AI_MAX_MESSAGE_LENGTH} characters)."
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        intent = nlp.determine_intent(message)
        filters = nlp.build_filters(message)
        properties = apply_filters(filters)[:8]

        provider = get_provider()
        reply = provider.generate_reply(message, filters, properties, intent)

        return Response(
            {
                "reply": reply,
                "intent": intent,
                "provider": provider.name,
                "filters_applied": {
                    k: v for k, v in filters.items() if v not in (None, [], "")
                },
                "properties": [serialize_property(p) for p in properties],
            },
            status=status.HTTP_200_OK,
        )
