from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("accounts", views.AccountViewSet, basename="account")
router.register("journal-entries", views.JournalEntryViewSet, basename="journal-entry")

urlpatterns = [
    path("auth/csrf/", views.csrf_view, name="csrf"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("reports/trial-balance/", views.TrialBalanceView.as_view(), name="trial-balance"),
    path("", include(router.urls)),
]
