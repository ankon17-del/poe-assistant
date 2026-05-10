from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.currency_market_source import PriceSnapshotDTO
from app.models.enums import NotificationType
from app.models.tracked_item import TrackedItem
from app.services.notifications import NotificationService
from app.services.telegram_notifier import TelegramNotifier


@dataclass(frozen=True)
class PriceAlertResult:
    triggered: bool
    message: str | None = None


class PriceAlertService:
    def __init__(self, session: AsyncSession, notifier: TelegramNotifier | None = None):
        self.session = session
        self.notifier = notifier

    async def process_snapshot(self, tracked_item: TrackedItem, snapshot: PriceSnapshotDTO) -> PriceAlertResult:
        if tracked_item.target_price is None:
            return PriceAlertResult(triggered=False)

        target_price = Decimal(tracked_item.target_price)
        current_value = Decimal(snapshot.market_value)
        if current_value < target_price:
            return PriceAlertResult(triggered=False)

        message = (
            f"Price alert: {snapshot.item_name} reached {self._format_decimal(current_value)} {snapshot.unit} "
            f"in {snapshot.league_name or 'unknown league'} "
            f"(target {self._format_decimal(target_price)} {snapshot.unit})."
        )

        await NotificationService(self.session).record(
            user=tracked_item.user,
            notification_type=NotificationType.price_alert,
            message=message,
        )

        if tracked_item.notify_enabled and self.notifier:
            await self.notifier.send_price_alert(
                telegram_id=tracked_item.user.telegram_id,
                message=message,
            )

        tracked_item.notify_enabled = False
        return PriceAlertResult(triggered=True, message=message)

    @staticmethod
    def _format_decimal(value: Decimal) -> str:
        normalized = value.normalize()
        return format(normalized, "f").rstrip("0").rstrip(".") or "0"
