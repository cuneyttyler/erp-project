from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("employees", views.EmployeeViewSet, basename="employee")
router.register("leave-requests", views.LeaveRequestViewSet, basename="leave-request")
router.register("payroll-runs", views.PayrollRunViewSet, basename="payroll-run")

urlpatterns = [
    path("", include(router.urls)),
]
