from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Account, Bill, Invoice, JournalEntry, Party, Payment
from .serializers import (
    AccountSerializer,
    AgingRowSerializer,
    BillSerializer,
    InvoiceSerializer,
    JournalEntrySerializer,
    LoginSerializer,
    PartySerializer,
    PaymentSerializer,
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


class PartyViewSet(viewsets.ModelViewSet):
    """Unified Customer/Vendor record (REQ-CORE-AR-*/AP-*)."""

    queryset = Party.objects.all()
    serializer_class = PartySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["party_type", "is_active"]


class SendableDocumentMixin:
    """
    Shared `send_document` action for Invoice/Bill viewsets -- moves a draft
    to `sent` via FinancialDocument.mark_sent() (models.py), the one
    sanctioned transition out of draft, mirroring JournalEntryViewSet's
    post_entry action for the same "draft is freely editable, anything past
    it isn't" shape.
    """

    @action(detail=True, methods=["post"])
    def send_document(self, request, pk=None):
        obj = self.get_object()
        try:
            obj.mark_sent()
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(obj).data)


class InvoiceViewSet(SendableDocumentMixin, viewsets.ModelViewSet):
    """Customer invoices (REQ-CORE-AR-001/002)."""

    queryset = Invoice.objects.select_related("party").prefetch_related("lines", "payments").all()
    serializer_class = InvoiceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "party"]


class BillViewSet(SendableDocumentMixin, viewsets.ModelViewSet):
    """Vendor bills (REQ-CORE-AP-001/002)."""

    queryset = Bill.objects.select_related("party").prefetch_related("lines", "payments").all()
    serializer_class = BillSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "party"]


class PaymentViewSet(viewsets.ModelViewSet):
    """
    Payments against an Invoice or Bill (REQ-CORE-AR-002/REQ-CORE-AP-002).
    Creating one triggers Payment.save() -> target.recompute_status(), so the
    parent document's status/balance is always current immediately after.
    """

    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["invoice", "bill"]


def _build_aging_rows(queryset):
    """
    Shared bucketing logic for AR/AP aging (REQ-CORE-AR-003/REQ-CORE-AP-002).
    Iterates in Python over a prefetched queryset rather than annotating
    Sum() over `lines` and `payments` in one query -- see FinancialDocument's
    docstring (models.py) for why that join would silently double-count.
    """
    today = timezone.localdate()
    rows = []
    for doc in queryset:
        balance = doc.balance_due
        if balance <= 0:
            continue
        days_overdue = (today - doc.due_date).days
        if days_overdue <= 0:
            bucket = "current"
        elif days_overdue <= 30:
            bucket = "1-30"
        elif days_overdue <= 60:
            bucket = "31-60"
        elif days_overdue <= 90:
            bucket = "61-90"
        else:
            bucket = "90+"
        rows.append(
            {
                "document_id": doc.id,
                "party_name": doc.party.name,
                "due_date": doc.due_date,
                "balance_due": balance,
                "days_overdue": max(days_overdue, 0),
                "bucket": bucket,
            }
        )
    return rows


class ARAgingView(APIView):
    """REQ-CORE-AR-003: AR aging report, bucketed by days overdue."""

    def get(self, request):
        queryset = Invoice.objects.filter(
            status__in=[Invoice.SENT, Invoice.PARTIALLY_PAID]
        ).select_related("party").prefetch_related("lines", "payments")
        return Response(AgingRowSerializer(_build_aging_rows(queryset), many=True).data)


class APAgingView(APIView):
    """REQ-CORE-AP-002: AP aging report, bucketed by days overdue."""

    def get(self, request):
        queryset = Bill.objects.filter(
            status__in=[Bill.SENT, Bill.PARTIALLY_PAID]
        ).select_related("party").prefetch_related("lines", "payments")
        return Response(AgingRowSerializer(_build_aging_rows(queryset), many=True).data)
