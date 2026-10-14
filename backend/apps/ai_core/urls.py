from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("pending-approvals", views.PendingApprovalViewSet, basename="pending-approval")
router.register("conversations", views.ConversationViewSet, basename="ai-conversation")

urlpatterns = [
    path("chat/", views.ChatView.as_view(), name="ai-chat"),
    path("chat/stream/", views.ChatStreamView.as_view(), name="ai-chat-stream"),
    path("", include(router.urls)),
]
