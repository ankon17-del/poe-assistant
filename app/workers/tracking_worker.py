import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.source_registry import TrackingSourceRegistry
from app.services.sales import SalesService
from app.services.telegram_notifier import TelegramNotifier
from app.services.tracking import TrackingService

logger = logging.getLogger(__name__)


class TrackingWorker:
    def __init__(
        self,
        session: AsyncSession,
        source_registry: TrackingSourceRegistry,
        notifier: TelegramNotifier | None = None,
    ):
        self.session = session
        self.source_registry = source_registry
        self.notifier = notifier

    async def run_once(self) -> None:
        tracking_items = await TrackingService(self.session).list_items_for_polling()
        sales_service = SalesService(self.session, notifier=self.notifier)
        created_sales = 0

        for tracked_item in tracking_items:
            request = TrackingService.build_tracking_request(tracked_item)
            source = self.source_registry.resolve(request)
            sales = await source.poll_sales(request)
            for sale in sales:
                result = await sales_service.process_sale_event(tracked_item=tracked_item, sale=sale)
                if result.created:
                    created_sales += 1

        logger.info("Tracking worker tick finished, created_sales=%s", created_sales)
