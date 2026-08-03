from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("accounts", views.MarketplaceAccountViewSet, basename="ecommerce-account")
router.register("listings", views.MarketplaceListingViewSet, basename="ecommerce-listing")
router.register("orders", views.MarketplaceOrderViewSet, basename="ecommerce-order")

urlpatterns = [
    path("", include(router.urls)),
]
