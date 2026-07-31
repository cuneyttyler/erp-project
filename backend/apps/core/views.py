from django.contrib.auth import authenticate, login, logout
from django.db.models import Sum
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Account, JournalEntry
from .serializers import (
    AccountSerializer,
    JournalEntrySerializer,
    LoginSerializer,
    TrialBalanceRowSerializer,
    UserSerializer,
)


@require_GET
@ensure_csrf_cookie
def csrf_view(request):
    """
    Sets the csrftoken cookie the SPA needs before it can POST to /login/
    (REST Framework's SessionAuthentication enforces CSRF like plain Django).
    Call this once on app boot, before attempting a login.
    """
    from django.http import JsonResponse

    return JsonResponse({"csrfToken": get_token(request)})


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)
        login(request, user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    # Explicit AllowAny: the global default (IsAuthenticated) would otherwise
    # reject an anonymous request with 403 before this view body ever runs,
    # masking the intended 401 "no session yet" response the frontend's
    # fetchMe() distinguishes from an actual permission error.
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"detail": "Not authenticated."}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(UserSerializer(request.user).data)


class AccountViewSet(viewsets.ModelViewSet):
    """Chart of Accounts (REQ-CORE-GL-001)."""

    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["account_type", "is_active"]


class JournalEntryViewSet(viewsets.ModelViewSet):
    """
    Journal entries (REQ-CORE-GL-002). Entries are created as drafts via the
    standard `create` action; posting is a deliberate separate step
    (`POST /journal-entries/{id}/post_entry/`) so a draft can still be
    corrected freely, while a posted entry never can (JournalEntry.post()).
    """

    queryset = JournalEntry.objects.prefetch_related("lines__account").all()
    serializer_class = JournalEntrySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "date"]

    @action(detail=True, methods=["post"])
    def post_entry(self, request, pk=None):
        entry = self.get_object()
        if entry.status == JournalEntry.POSTED:
            return Response({"detail": "Already posted."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            entry.post()
        except Exception as exc:  # ValidationError -> 400, not 500
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(JournalEntrySerializer(entry).data)


class TrialBalanceView(APIView):
    """
    REQ-CORE-GL-006: trial balance. Deliberately a plain deterministic
    aggregation query, not something the AI layer computes free-form — this
    is exactly the kind of figure that belongs behind the semantic layer
    (technical.md §8.2) once ai_core exists; today it's the one and only
    source of truth this number comes from.
    """

    def get(self, request):
        rows = (
            Account.objects.filter(journal_lines__journal_entry__status=JournalEntry.POSTED)
            .values("code", "name", "account_type")
            .annotate(total_debit=Sum("journal_lines__debit"), total_credit=Sum("journal_lines__credit"))
            .order_by("code")
        )
        return Response(TrialBalanceRowSerializer(rows, many=True).data)
