from django.core.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import AuditLogEntry

from . import chat
from .models import PendingApproval
from .serializers import ChatRequestSerializer, ChatResponseSerializer, PendingApprovalSerializer


class ChatView(APIView):
    """
    REQ-CORE-AI-001/002/003/004/006/007/008/009. The single entry point for
    the AI side-panel (frontend/src/ai-panel/). Authenticates as the
    requesting user's own session -- there is no elevated AI service
    account, so every tool call this view triggers (read or write) is
    scoped to exactly what `request.tenant` permits, same as any other
    endpoint (technical.md §8.5). Write actions never execute from here --
    see chat.answer()'s docstring and PendingApprovalViewSet.approve.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        req = ChatRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)

        tenant = getattr(request, "tenant", None)
        active_packages = tenant.active_packages if tenant else []

        result = chat.answer(
            user=request.user,
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
                {
                    "reply": result["reply"],
                    "citations": result["citations"],
                    "configured": result["configured"],
                    "pending_action": result["pending_action"],
                }
            ).data,
            status=status.HTTP_200_OK,
        )


class PendingApprovalViewSet(viewsets.ReadOnlyModelViewSet):
    """
    REQ-CORE-AI-007/010: list/approve/reject the write actions the AI has
    proposed. Read-only ModelViewSet (list/retrieve) plus the two explicit
    state-transition actions -- there's no generic update/delete on a
    PendingApproval, only the two sanctioned transitions out of `pending`,
    same "narrow API surface, wide state machine" shape as
    JournalEntryViewSet.post_entry / SendableDocumentMixin elsewhere.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PendingApprovalSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status"]

    def get_queryset(self):
        # Every authenticated user on the tenant can see and act on any
        # pending approval, not just the one who triggered it -- a
        # colleague should be able to review/approve what a teammate's AI
        # conversation proposed. Field/row-level restriction beyond "same
        # tenant" is the same known gap flagged elsewhere in this codebase
        # (e.g. EmployeeViewSet's docstring), not unique to this endpoint.
        return PendingApproval.objects.select_related("requested_by", "resolved_by").all()

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        approval = self.get_object()
        tenant = getattr(request, "tenant", None)
        active_packages = tenant.active_packages if tenant else []
        try:
            approval.approve(request.user, active_packages)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(approval).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        approval = self.get_object()
        try:
            approval.reject(request.user)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(approval).data)
