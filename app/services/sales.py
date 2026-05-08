import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.tracking_source import SaleEventDTO
from app.models.enums import NotificationType
from app.models.sale_event import SaleEvent
from app.models.tracked_item import TrackedItem
from app.services.notifications import NotificationService
from app.services.stats import StatsService
from app.services.telegram_notifier import TelegramNotifier


@dataclass(frozen=True)
class SaleProcessResult:
    created: bool
    sale_event: SaleEvent | None = None


class SalesService:
    def __init__(self, session: AsyncSession, notifier: TelegramNotifier | None = None):
        self.session = session
        self.notifier = notifier

    async def process_sale_event(self, tracked_item: TrackedItem, sale: SaleEventDTO) -> SaleProcessResult:
        existing = await self.session.scalar(
            select(SaleEvent).where(
                SaleEvent.tracked_item_id == tracked_item.id,
                SaleEvent.external_id == sale.external_id,
            )
        )
        if existing:
            return SaleProcessResult(created=False, sale_event=existing)

        sale_event = SaleEvent(
            tracked_item_id=tracked_item.id,
            user_id=tracked_item.user_id,
            league_id=tracked_item.league_id,
            external_id=sale.external_id,
            item_name=sale.item_name,
            price_text=sale.price_text,
            price_amount=sale.price_amount,
            price_currency=sale.price_currency,
            raw_payload=json.dumps(sale.raw_payload, ensure_ascii=True),
            sold_at=sale.sold_at or datetime.now(UTC),
        )
        self.session.add(sale_event)
        await self.session.flush()

        stats_service = StatsService(self.session)
        await stats_service.register_sale(
            user=tracked_item.user,
            league_id=tracked_item.league_id,
            amount=sale.price_amount,
        )

        message = f"Sale detected: {sale.item_name} sold for {sale.price_text}"
        await NotificationService(self.session).record(
            user=tracked_item.user,
            notification_type=NotificationType.sale,
            message=message,
        )

        if tracked_item.notify_enabled and self.notifier:
            await self.notifier.send_sale_notification(
                telegram_id=tracked_item.user.telegram_id,
                message=f"{sale.item_name} sold for {sale.price_text}",
            )

        return SaleProcessResult(created=True, sale_event=sale_event)
