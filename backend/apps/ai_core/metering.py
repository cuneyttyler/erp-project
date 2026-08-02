"""
REQ-CORE-AI-011 / technical.md §8.8: the usage ledger underlying "AI Action
credits" billing. One call, one row -- see AIUsageRecord's docstring for
what's real here (the ledger) versus what isn't yet (billing/credit-balance
reconciliation on top of it).
"""

from .llm_gateway import LLMResponse
from .models import AIUsageRecord


def record_usage(user, model: str, response: LLMResponse) -> None:
    AIUsageRecord.objects.create(
        user=user,
        model=model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )
