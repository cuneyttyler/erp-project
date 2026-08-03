"""
Marketplace adapter interface (REQ-ECOM-001, technical.md §9's
"integrations/... e-commerce marketplace clients" pattern) -- the same
"country/vendor-agnostic internal interface, pluggable implementation" shape
as compliance/turkey's `engine.py` (technical.md §7.1:
`file(filing_type, payload) -> FilingResult`). `services.py` never talks to
a marketplace's HTTP API directly, only through this interface -- adding
Trendyol or Hepsiburada later is a new adapter class registered in
`ADAPTERS`, not a rewrite of the sync logic.

`ShopifyAdapter` is implemented against Shopify's public, versioned Admin
REST API docs -- it has NOT been exercised against a real (sandbox or
production) Shopify store; no developer credentials are available in this
environment (docs/notes.md). Treat it as a real implementation awaiting
first live verification, not a stub -- the request/response shapes match
Shopify's documented API exactly.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

import requests


@dataclass
class ExternalOrderLine:
    sku: str
    quantity: Decimal
    unit_price: Decimal


@dataclass
class ExternalOrder:
    external_order_id: str
    customer_email: str
    customer_name: str
    lines: list[ExternalOrderLine]
    raw_payload: dict = field(default_factory=dict)


class MarketplaceAdapter:
    """One subclass per platform. `account` is the `MarketplaceAccount` row
    carrying this tenant's shop identifier/credentials."""

    def __init__(self, account):
        self.account = account

    def fetch_new_orders(self, since: datetime) -> list[ExternalOrder]:
        raise NotImplementedError

    def push_stock_level(self, listing, quantity: Decimal) -> None:
        raise NotImplementedError


class ShopifyAdapter(MarketplaceAdapter):
    """Shopify Admin REST API (https://shopify.dev/docs/api/admin-rest)."""

    API_VERSION = "2024-01"
    TIMEOUT_SECONDS = 30

    def _base_url(self) -> str:
        return f"https://{self.account.shop_domain}/admin/api/{self.API_VERSION}"

    def _headers(self) -> dict:
        return {"X-Shopify-Access-Token": self.account.api_secret, "Content-Type": "application/json"}

    def fetch_new_orders(self, since: datetime) -> list[ExternalOrder]:
        params = {"status": "any", "created_at_min": since.isoformat()}
        response = requests.get(
            f"{self._base_url()}/orders.json", headers=self._headers(), params=params, timeout=self.TIMEOUT_SECONDS
        )
        response.raise_for_status()
        return [self._parse_order(raw) for raw in response.json().get("orders", [])]

    def _parse_order(self, raw: dict[str, Any]) -> ExternalOrder:
        customer = raw.get("customer") or {}
        lines = [
            ExternalOrderLine(
                sku=line_item["sku"], quantity=Decimal(str(line_item["quantity"])), unit_price=Decimal(str(line_item["price"]))
            )
            for line_item in raw.get("line_items", [])
            if line_item.get("sku")
        ]
        return ExternalOrder(
            external_order_id=str(raw["id"]),
            customer_email=raw.get("email") or customer.get("email") or "",
            customer_name=f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
            lines=lines,
            raw_payload=raw,
        )

    def push_stock_level(self, listing, quantity: Decimal) -> None:
        payload = {
            "location_id": listing.external_location_id,
            "inventory_item_id": listing.external_variant_id,
            "available": int(quantity),
        }
        response = requests.post(
            f"{self._base_url()}/inventory_levels/set.json",
            headers=self._headers(),
            json=payload,
            timeout=self.TIMEOUT_SECONDS,
        )
        response.raise_for_status()


ADAPTERS: dict[str, type[MarketplaceAdapter]] = {"shopify": ShopifyAdapter}


def get_adapter(account) -> MarketplaceAdapter:
    adapter_cls = ADAPTERS.get(account.platform)
    if adapter_cls is None:
        raise ValueError(f"No adapter registered for platform '{account.platform}'.")
    return adapter_cls(account)
