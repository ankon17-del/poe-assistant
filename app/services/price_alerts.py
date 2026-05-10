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
    reason: str | None = None
    current_value: Decimal | None = None
    target_price: Decimal | None = None
    target_currency: str | None = None
    source: str | None = None


class PriceAlertService:
    def __init__(self, session: AsyncSession, notifier: TelegramNotifier | None = None):
        self.session = session
        self.notifier = notifier

    async def process_snapshot(self, tracked_item: TrackedItem, snapshot: PriceSnapshotDTO) -> PriceAlertResult:
        if tracked_item.target_price is None:
            return PriceAlertResult(triggered=False, reason="missing-target")

        target_price = Decimal(tracked_item.target_price)
        target_currency = (tracked_item.target_currency or snapshot.unit).lower()
        current_value = snapshot.quote_values.get(target_currency)
        if current_value is None and target_currency == snapshot.unit:
            current_value = Decimal(snapshot.market_value)
        if current_value is None:
            return PriceAlertResult(
                triggered=False,
                reason="missing-current-value",
                target_price=target_price,
                target_currency=target_currency,
                source=snapshot.source,
            )
        if current_value < target_price:
            return PriceAlertResult(
                triggered=False,
                reason="below-threshold",
                current_value=current_value,
                target_price=target_price,
                target_currency=target_currency,
                source=snapshot.source,
            )

        game_label = "POE 2" if tracked_item.league and tracked_item.league.realm == "poe2" else "POE 1"

        message = "\n".join(
            [
                "Price alert triggered!",
                f"Трекер: #{tracked_item.id} {snapshot.item_name}",
                f"Игра: {game_label}",
                f"Лига: {snapshot.league_name or 'unknown league'}",
                f"Текущая цена: {self._format_decimal(current_value)} {target_currency}",
                f"Твой порог: {self._format_decimal(target_price)} {target_currency}",
                f"Источник: {snapshot.source}",
                "Статус: алерт сработал, трекер поставлен на паузу.",
            ]
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
        return PriceAlertResult(
            triggered=True,
            message=message,
            reason="triggered",
            current_value=current_value,
            target_price=target_price,
            target_currency=target_currency,
            source=snapshot.source,
        )

    @staticmethod
    def _format_decimal(value: Decimal) -> str:
        normalized = value.normalize()
        return format(normalized, "f").rstrip("0").rstrip(".") or "0"
