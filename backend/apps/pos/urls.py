from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("stores", views.StoreViewSet, basename="pos-store")
router.register("tills", views.TillViewSet, basename="pos-till")
router.register("shifts", views.POSShiftViewSet, basename="pos-shift")
router.register("sales", views.POSSaleViewSet, basename="pos-sale")
router.register("returns", views.POSReturnViewSet, basename="pos-return")

urlpatterns = [
    path("", include(router.urls)),
]
