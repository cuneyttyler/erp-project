from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import AuditLogEntry

from . import chat
from .serializers import ChatRequestSerializer, ChatResponseSerializer


class ChatView(APIView):
    """
    REQ-CORE-AI-001/002/003/004/006/008/009. The single entry point for the
    AI side-panel (frontend/src/ai-panel/). Authenticates as the requesting
    user's own session -- there is no elevated AI service account, so every
    tool call this view triggers is scoped to exactly what `request.tenant`
    permits, same as any other endpoint (technical.md §8.5).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        req = ChatRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)

        tenant = getattr(request, "tenant", None)
        active_packages = tenant.active_packages if tenant else []

        result = chat.answer(
            active_packages=active_packages,
            locale=req.validated_data.get("locale", "en"),
            history=req.validated_data.get("history", []),
            message=req.validated_data["message"],
        )

        # Append-only audit trail (REQ-CORE-AI-008, technical.md §8.6) --
        # AuditLogEntry is the same table human-initiated actions log to
        # (models.py's docstring on AuditLogEntry), actor prefixed "ai:" per
        # REQ-CORE-AUDIT-003 so AI-originated rows are distinguishable from
        # user-originated ones without a separate table.
        AuditLogEntry.objects.create(
            actor=f"ai:{request.user.id}",
            action="ai_chat",
            target_type="conversation",
            target_id=str(request.user.id),
            before={"message": req.validated_data["message"]},
            after={"reply": result["reply"], "tool_calls": result["tool_calls"], "configured": result["configured"]},
        )

        return Response(
            ChatResponseSerializer(
                {"reply": result["reply"], "citations": result["citations"], "configured": result["configured"]}
            ).data,
            status=status.HTTP_200_OK,
        )
