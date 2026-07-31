from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("leads", views.LeadViewSet, basename="lead")
router.register("sales-orders", views.SalesOrderViewSet, basename="sales-order")

urlpatterns = [
    path("", include(router.urls)),
]
