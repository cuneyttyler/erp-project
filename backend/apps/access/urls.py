from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("permissions", views.PermissionViewSet, basename="access-permission")
router.register("roles", views.RoleViewSet, basename="access-role")
router.register("users", views.UserViewSet, basename="access-user")
router.register("audit-log", views.AuditLogViewSet, basename="audit-log")

urlpatterns = [
    path("actions/", views.ActionCatalogView.as_view(), name="access-actions"),
    path("", include(router.urls)),
]
