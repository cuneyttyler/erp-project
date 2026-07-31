from rest_framework.permissions import BasePermission


class HasActivePackage(BasePermission):
    """
    Gates an API view behind the requesting tenant having purchased a given
    package (product.md §6.2, technical.md §4) -- "a tenant without a package
    should never even run that package's code." django-tenants' middleware
    resolves the current tenant onto `request.tenant` for every request; this
    reads that tenant's `active_packages` (technical.md §5 `Tenant` entity)
    rather than trusting anything client-supplied.

    Usage: `permission_classes = [IsAuthenticated, HasActivePackage("purchasing")]`
    """

    def __init__(self, package: str):
        self.package = package

    def __call__(self):
        # DRF instantiates permission_classes entries with no args; this
        # lets `HasActivePackage("purchasing")` be used directly in the list
        # (returning itself) instead of requiring a factory-function wrapper.
        return self

    def has_permission(self, request, view):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return False
        return self.package in (tenant.active_packages or [])

    def message_for(self, package):
        return f"Your subscription does not include the '{package}' package."
