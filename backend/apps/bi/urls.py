from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("reports", views.SavedReportViewSet, basename="bi-report")
router.register("dashboards", views.DashboardViewSet, basename="bi-dashboard")

urlpatterns = [
    path("series/", views.AvailableSeriesView.as_view(), name="bi-available-series"),
    path("series/run/", views.RunSeriesView.as_view(), name="bi-run-series"),
    path("", include(router.urls)),
]
