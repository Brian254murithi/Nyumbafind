from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework import serializers
from rest_framework.authtoken.models import Token

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Public representation of a user (never includes password)."""

    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "name",
            "role",
            "phone",
            "business_name",
            "avatar",
            "email_verified",
            "phone_verified",
            "accepts_payments",
            "date_joined",
        ]
        read_only_fields = fields

    def get_name(self, obj):
        return obj.get_full_name() or obj.username


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    role = serializers.ChoiceField(
        choices=[User.Role.TENANT, User.Role.LANDLORD],
        default=User.Role.TENANT,
        help_text="Only tenant or landlord roles may be requested. Admins are created by administrators.",
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "role",
            "phone",
            "business_name",
        ]
        extra_kwargs = {
            "email": {"required": True},
            "first_name": {"required": False},
            "last_name": {"required": False},
        }

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return value

    def create(self, validated_data):
        role = validated_data.pop("role", User.Role.TENANT)
        # Server-side role enforcement: registration can never grant admin.
        if role not in (User.Role.TENANT, User.Role.LANDLORD):
            role = User.Role.TENANT
        try:
            user = User.objects.create_user(
                username=validated_data["username"],
                email=validated_data["email"],
                password=validated_data["password"],
                first_name=validated_data.get("first_name", ""),
                last_name=validated_data.get("last_name", ""),
                phone=validated_data.get("phone", ""),
                business_name=validated_data.get("business_name", ""),
                role=role,
            )
        except IntegrityError:
            raise serializers.ValidationError(
                {"username": "This username is already taken."}
            )
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(help_text="Username or email address")
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        from django.contrib.auth import authenticate

        identifier = attrs.get("username", "").strip()
        password = attrs.get("password", "")

        # Allow login with either username or email.
        user = None
        if "@" in identifier:
            try:
                user = User.objects.get(email__iexact=identifier)
            except User.DoesNotExist:
                user = None
            if user is not None:
                user = (
                    authenticate(username=user.username, password=password) or None
                )
        else:
            user = authenticate(username=identifier, password=password)

        if user is None:
            raise serializers.ValidationError("Invalid username/email or password.")

        attrs["user"] = user
        return attrs


class TokenResponseSerializer(serializers.Serializer):
    token = serializers.CharField()
    user = UserSerializer()

    def to_representation(self, instance):
        user, token = instance
        return {
            "token": token.key,
            "user": UserSerializer(user, context=self.context).data,
        }


def get_or_create_token(user):
    token, _ = Token.objects.get_or_create(user=user)
    return token
