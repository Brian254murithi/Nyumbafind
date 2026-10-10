from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Platform user with a server-enforced role.

    Roles:
      - tenant:  can search, book viewings (future), and review properties.
      - landlord: can create and manage their own property listings.
      - admin:   staff-level moderation (also requires is_staff for admin site).

    The role is never accepted from client input beyond the two values a
    normal registration may request (tenant/landlord). Admins are created
    through the Django admin or ``createsuperuser`` only.
    """

    class Role(models.TextChoices):
        TENANT = "tenant", "Tenant"
        LANDLORD = "landlord", "Landlord"
        ADMIN = "admin", "Admin"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.TENANT)
    phone = models.CharField(max_length=20, blank=True)
    business_name = models.CharField(
        max_length=120, blank=True, help_text="Landlord or agency name"
    )
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    # Landlords explicitly authorize NyumbaFind to collect rent
    # payments on their behalf (M-Pesa only).
    accepts_payments = models.BooleanField(
        default=False,
        help_text="Landlord authorizes NyumbaFind to collect rent payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def is_landlord(self):
        return (
            self.role in (self.Role.LANDLORD, self.Role.ADMIN)
            or self.is_superuser
        )

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_staff
