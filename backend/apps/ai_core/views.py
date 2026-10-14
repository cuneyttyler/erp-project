import json
import logging

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.access import audit, catalog
from apps.access.permissions import granted_actions, is_org_admin

from . import chat, llm_gateway
from .models import Conversation, PendingApproval
from .serializers import (
    ChatRequestSerializer,
    ConversationDetailSerializer,
    ConversationSerializer,
    PendingApprovalSerializer,
    hydrate_blocks,
)

logger = logging.getLogger(__name__)


class ChatView(APIView):
    """
    REQ-CORE-AI-001/002/003/004/006/007/008/009. One turn with the
    assistant. It runs as the requesting user's own session -- there is no
    elevated AI service account, so everything a turn reads or proposes is
    limited to what that user may do (technical.md §8.5). Changes are never
    made from here: the assistant can only propose them (chat.answer's
    docstring), and a person approves each one through
    PendingApprovalViewSet.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        steps, conversation, message = self.start(request)
        while True:
            try:
                next(steps)
            except StopIteration as done:
                return Response(self.finish(request, conversation, message, done.value), status=status.HTTP_200_OK)

    def start(self, request):
        """Validates the request and returns (the turn's step generator,
        the conversation, the message)."""
        req = ChatRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        message = req.validated_data["message"]

        conversation = None
        if llm_gateway.is_configured():
            conversation_id = req.validated_data.get("conversation_id")
            if conversation_id:
                # Scoped to the owner: another user's id is a 404, not a peek.
                conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
            else:
                conversation = Conversation.objects.create(user=request.user, title=" ".join(message.split())[:120])

        steps = chat.answer_steps(
            user=request.user,
            tenant=getattr(request, "tenant", None),
            locale=req.validated_data.get("locale", "en"),
            message=message,
            conversation=conversation,
            entity_id=req.validated_data.get("entity"),
        )
        return steps, conversation, message

    def finish(self, request, conversation, message, result) -> dict:
        """Audits the finished turn and returns the response body."""
        # REQ-CORE-AI-008: what was asked, what was answered and which tools
        # ran. Any change the user later approves is logged separately, as
        # that action, by the resource's own view.
        audit.record(
            user=request.user,
            channel=audit.AI,
            action="ai_chat",
            target_type="conversation",
            target_id=conversation.id if conversation else "",
            # What was asked reads better in the log than the conversation's
            # title, which is the same for every turn in it.
            target_label=" ".join(message.split()),
            before={"message": message},
            after={"reply": result["reply"], "tool_calls": result["tool_calls"], "configured": result["configured"]},
        )

        return {
            "conversation": ConversationSerializer(conversation).data if conversation else None,
            "reply": result["reply"],
            "blocks": hydrate_blocks(result["blocks"], request),
            "citations": result["citations"],
            "configured": result["configured"],
        }


class ChatStreamView(ChatView):
    """The same turn as ChatView, as Server-Sent Events: a `progress` event
    each time the assistant consults the model or a tool ("Looking up
    invoices..."), so a long turn shows what it's doing instead of a bare
    spinner, then one `done` event whose data is exactly ChatView's response
    body. The turn runs in this request's own thread, as the generator is
    read -- same user, same tenant connection, nothing in the background."""

    def post(self, request):
        steps, conversation, message = self.start(request)

        def events():
            # A comment line first, so every proxy on the way starts passing
            # the stream through before the first (slow) model call returns.
            yield ": stream open\n\n"
            try:
                while True:
                    try:
                        progress = next(steps)
                    except StopIteration as done:
                        body = self.finish(request, conversation, message, done.value)
                        yield _sse("done", body)
                        return
                    yield _sse("progress", progress)
            except Exception:
                logger.exception("Assistant turn failed mid-stream")
                yield _sse("error", {"detail": "The assistant couldn't finish this turn."})

        response = StreamingHttpResponse(events(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, cls=DjangoJSONEncoder)}\n\n"


class ConversationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """A user's own conversations with the assistant: list them, reopen one,
    delete one. Never anyone else's -- see Conversation's docstring."""

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        return ConversationDetailSerializer if self.action == "retrieve" else ConversationSerializer


class PendingApprovalViewSet(viewsets.ReadOnlyModelViewSet):
    """
    REQ-CORE-AI-007/010: the changes the assistant has proposed, with the
    two things a person can do to one -- approve it or reject it. There is
    no generic update/delete, only those two transitions out of `pending`.

    A user sees the proposals they asked for and the ones they'd be allowed
    to carry out (so a colleague with the right permission can approve what
    someone else's conversation proposed); an admin sees all of them.
    Approving runs the action as the approver -- PendingApproval.approve.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PendingApprovalSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status"]

    def get_queryset(self):
        user = self.request.user
        proposals = PendingApproval.objects.select_related("requested_by", "resolved_by")
        if is_org_admin(user):
            return proposals
        open_codes = [res.code(op) for res in catalog.grantable_resources() for op in res.open_operations]
        return proposals.filter(Q(requested_by=user) | Q(action_name__in=[*granted_actions(user), *open_codes]))

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        approval = self.get_object()
        try:
            approval.approve(request.user, getattr(request, "tenant", None))
        except ValidationError as exc:
            return Response({"detail": " ".join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(approval).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        approval = self.get_object()
        try:
            approval.reject(request.user)
        except ValidationError as exc:
            return Response({"detail": " ".join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(approval).data)
