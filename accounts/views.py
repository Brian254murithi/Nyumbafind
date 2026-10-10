from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .serializers import LoginSerializer, RegisterSerializer, TokenResponseSerializer, UserSerializer

User = get_user_model()


def _token_payload(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"token": token.key, "user": UserSerializer(user).data}


class RegisterView(APIView):
    """POST /api/auth/register/ — create a tenant or landlord account."""

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        return Response(_token_payload(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """POST /api/auth/login/ — authenticate and receive a token."""

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.validated_data["user"]
        return Response(_token_payload(user), status=status.HTTP_200_OK)


class LogoutView(APIView):
    """POST /api/auth/logout/ — invalidate the caller's token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.auth.delete() if request.auth else Token.objects.filter(user=request.user).delete()
        return Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)


class MeView(APIView):
    """GET /api/auth/me/ — current authenticated user.

    PATCH /api/auth/me/ — update own settings.
    Only ``accepts_payments`` may be changed this way
    (a landlord authorizing NyumbaFind to collect rent
    payments on their behalf).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"user": UserSerializer(request.user).data}, status=status.HTTP_200_OK)

    def patch(self, request):
        accepts = request.data.get("accepts_payments")
        if accepts is None:
            return Response(
                {"errors": {"accepts_payments": "This field is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(accepts, bool):
            return Response(
                {"errors": {"accepts_payments": "Must be true or false."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if request.user.role not in (User.Role.LANDLORD, User.Role.ADMIN):
            return Response(
                {"errors": {"accepts_payments": "Only landlords can authorize rent collection."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        request.user.accepts_payments = accepts
        request.user.save(update_fields=["accepts_payments"])
        return Response(
            {"user": UserSerializer(request.user).data},
            status=status.HTTP_200_OK,
        )
