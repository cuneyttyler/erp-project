from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("items", views.ItemViewSet, basename="item")
router.register("accounts", views.AccountViewSet, basename="account")
router.register("journal-entries", views.JournalEntryViewSet, basename="journal-entry")
router.register("parties", views.PartyViewSet, basename="party")
router.register("invoices", views.InvoiceViewSet, basename="invoice")
router.register("bills", views.BillViewSet, basename="bill")
router.register("payments", views.PaymentViewSet, basename="payment")
router.register("saved-views", views.SavedViewViewSet, basename="saved-view")

urlpatterns = [
    path("auth/csrf/", views.csrf_view, name="csrf"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("reports/trial-balance/", views.TrialBalanceView.as_view(), name="trial-balance"),
    path("reports/ar-aging/", views.ARAgingView.as_view(), name="ar-aging"),
    path("reports/ap-aging/", views.APAgingView.as_view(), name="ap-aging"),
    path("", include(router.urls)),
]
