"""Tests for the accounts authentication API."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

User = get_user_model()


class RegisterViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("accounts:register")
        self.valid = {
            "username": "wanjiku",
            "email": "wanjiku@example.com",
            "password": "strongpass123",
            "first_name": "Wanjiku",
            "last_name": "Mwangi",
            "role": "tenant",
        }

    def test_register_creates_tenant_and_token(self):
        response = self.client.post(self.url, self.valid, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="wanjiku")
        self.assertEqual(user.role, User.Role.TENANT)
        self.assertIn("token", response.data)
        Token.objects.get(user=user)

    def test_register_defaults_to_tenant(self):
        data = dict(self.valid)
        data.pop("role")
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.get(username="wanjiku").role, User.Role.TENANT)

    def test_register_never_grants_admin(self):
        data = dict(self.valid)
        data["role"] = "admin"
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_rejects_duplicate_email(self):
        self.client.post(self.url, self.valid, format="json")
        data = dict(self.valid)
        data["username"] = "someoneelse"
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data["errors"])

    def test_register_rejects_duplicate_username(self):
        self.client.post(self.url, self.valid, format="json")
        data = dict(self.valid)
        data["email"] = "other@example.com"
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_rejects_weak_password(self):
        data = dict(self.valid)
        data["password"] = "123"
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_landlord_can_register(self):
        data = dict(self.valid)
        data["role"] = "landlord"
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.get(username="wanjiku").role, User.Role.LANDLORD)


class LoginViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("accounts:login")
        self.user = User.objects.create_user(
            username="kamau",
            email="kamau@example.com",
            password="strongpass123",
        )

    def test_login_with_username(self):
        response = self.client.post(
            self.url,
            {"username": "kamau", "password": "strongpass123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)

    def test_login_with_email(self):
        response = self.client.post(
            self.url,
            {"username": "kamau@example.com", "password": "strongpass123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_rejects_wrong_password(self):
        response = self.client.post(
            self.url,
            {"username": "kamau", "password": "wrong"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_rejects_unknown_user(self):
        response = self.client.post(
            self.url,
            {"username": "ghost", "password": "strongpass123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AuthFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="aki", email="aki@example.com", password="strongpass123"
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)

    def test_me_returns_current_user(self):
        response = self.client.get(reverse("accounts:me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["username"], "aki")

    def test_me_requires_authentication(self):
        self.client.credentials()
        response = self.client.get(reverse("accounts:me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_invalidates_token(self):
        response = self.client.post(reverse("accounts:logout"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Token.objects.filter(key=self.token.key).exists())


class MePatchTests(TestCase):
    """PATCH /api/auth/me/ — landlord rent-collection authorization."""

    def setUp(self):
        self.client = APIClient()
        self.landlord = User.objects.create_user(
            username="mp_landlord",
            email="mp_landlord@example.com",
            password="strongpass123",
            role=User.Role.LANDLORD,
        )
        self.tenant = User.objects.create_user(
            username="mp_tenant",
            email="mp_tenant@example.com",
            password="strongpass123",
        )
        self.landlord_token = Token.objects.create(user=self.landlord)
        self.tenant_token = Token.objects.create(user=self.tenant)
        self.url = reverse("accounts:me")

    def test_landlord_can_authorize_payments(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.landlord_token.key
        )
        response = self.client.patch(
            self.url, {"accepts_payments": True}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["user"]["accepts_payments"])
        self.landlord.refresh_from_db()
        self.assertTrue(self.landlord.accepts_payments)

    def test_landlord_can_revoke_authorization(self):
        self.landlord.accepts_payments = True
        self.landlord.save()
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.landlord_token.key
        )
        response = self.client.patch(
            self.url, {"accepts_payments": False}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.landlord.refresh_from_db()
        self.assertFalse(self.landlord.accepts_payments)

    def test_tenant_cannot_authorize_payments(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.tenant_token.key
        )
        response = self.client.patch(
            self.url, {"accepts_payments": True}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_requires_authentication(self):
        response = self.client.patch(
            self.url, {"accepts_payments": True}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_rejects_invalid_payload(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.landlord_token.key
        )
        for bad in ({}, {"accepts_payments": "yes"}, {"accepts_payments": 1}):
            response = self.client.patch(self.url, bad, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_serializer_exposes_accepts_payments(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.landlord_token.key
        )
        response = self.client.get(self.url)
        self.assertIn("accepts_payments", response.data["user"])
