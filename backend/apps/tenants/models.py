from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Client(TenantMixin):
    """
    The tenant registry entity — technical.md §5 `Tenant`. Lives in the shared
    public schema; every other app's tables live inside this tenant's own
    Postgres schema (technical.md §3 schema-per-tenant decision).
    """

    STARTER = "starter"
    GROWTH = "growth"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    SUBSCRIPTION_TIER_CHOICES = [
        (STARTER, "Starter"),
        (GROWTH, "Growth"),
        (PROFESSIONAL, "Professional"),
        (ENTERPRISE, "Enterprise"),
    ]

    name = models.CharField(max_length=255)
    subscription_tier = models.CharField(
        max_length=20, choices=SUBSCRIPTION_TIER_CHOICES, default=STARTER
    )
    locale = models.CharField(max_length=10, default="tr")
    # Which packages this tenant has purchased (product.md §6.2 / requirements.md §5).
    # The frontend uses this list to decide which package modules to lazy-load
    # (technical.md §10.1) and the backend uses it to gate package API access.
    active_packages = models.JSONField(default=list, blank=True)
    created_on = models.DateField(auto_now_add=True)

    auto_create_schema = True

    def __str__(self) -> str:
        return self.name


class Domain(DomainMixin):
    """Maps a hostname to a Client — required by django-tenants."""
