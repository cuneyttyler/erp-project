from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("warehouses", views.WarehouseViewSet, basename="warehouse")
router.register("stock-moves", views.StockMoveViewSet, basename="stock-move")

urlpatterns = [
    path("reports/stock-levels/", views.StockLevelView.as_view(), name="stock-levels"),
    path("", include(router.urls)),
]
