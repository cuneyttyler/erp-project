from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("pending-approvals", views.PendingApprovalViewSet, basename="pending-approval")

urlpatterns = [
    path("chat/", views.ChatView.as_view(), name="ai-chat"),
    path("", include(router.urls)),
]
