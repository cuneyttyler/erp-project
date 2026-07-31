from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("boms", views.BOMViewSet, basename="bom")
router.register("work-orders", views.WorkOrderViewSet, basename="work-order")

urlpatterns = [
    path("", include(router.urls)),
]
