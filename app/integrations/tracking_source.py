from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.models.tracked_item import TrackedItem


@dataclass(frozen=True)
class SaleEventDTO:
    external_id: str
    item_name: str
    price_text: str
    price_amount: Decimal | None
    price_currency: str | None
    league_name: str | None
    sold_at: datetime | None
    source: str
    raw_payload: dict[str, Any] = field(default_factory=dict)
    game: str | None = None


@dataclass(frozen=True)
class TrackingRequest:
    tracked_item_id: int
    item_name: str
    item_type: str
    trade_url: str | None
    target_price: Decimal | None
    league_name: str | None
    game: str | None


class TrackingSource(ABC):
    source_name: str = "unknown"

    @abstractmethod
    async def poll_sales(self, request: TrackingRequest) -> list[SaleEventDTO]:
        raise NotImplementedError


class NullTrackingSource(TrackingSource):
    source_name = "null"

    async def poll_sales(self, request: TrackingRequest) -> list[SaleEventDTO]:
        return []
