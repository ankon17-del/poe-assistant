import logging

from app.integrations.currency_market_source import CurrencyMarketSource
from app.integrations.poe_trade import PoeTradeClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.source_registry import TrackingSourceRegistry
from app.services.price_alerts import PriceAlertService
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
        self.currency_market_source = CurrencyMarketSource()
        self.poe_trade_client = PoeTradeClient()

    async def run_once(self) -> None:
        tracking_items = await TrackingService(self.session).list_items_for_polling()
        sales_service = SalesService(self.session, notifier=self.notifier)
        price_alert_service = PriceAlertService(self.session, notifier=self.notifier)
        created_sales = 0
        triggered_alerts = 0

        for tracked_item in tracking_items:
            try:
                request = TrackingService.build_tracking_request(tracked_item)
                if request.target_price is not None:
                    if request.trade_url:
                        snapshot = await self.poe_trade_client.get_price_snapshot(request)
                    else:
                        snapshot = await self.currency_market_source.get_price(request)
                    if snapshot:
                        result = await price_alert_service.process_snapshot(tracked_item=tracked_item, snapshot=snapshot)
                        if result.triggered:
                            triggered_alerts += 1
                    continue

                source = self.source_registry.resolve(request)
                sales = await source.poll_sales(request)
                for sale in sales:
                    result = await sales_service.process_sale_event(tracked_item=tracked_item, sale=sale)
                    if result.created:
                        created_sales += 1
            except Exception:
                logger.exception("Tracking worker failed for tracked_item_id=%s", tracked_item.id)

        logger.info(
            "Tracking worker tick finished, created_sales=%s triggered_alerts=%s",
            created_sales,
            triggered_alerts,
        )
