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
        processed_price_watchers = 0
        processed_sale_watchers = 0
        snapshot_misses = 0
        worker_errors = 0

        logger.info("Tracking worker tick started, polling_items=%s", len(tracking_items))

        for tracked_item in tracking_items:
            try:
                request = TrackingService.build_tracking_request(tracked_item)
                if request.target_price is not None:
                    processed_price_watchers += 1
                    logger.info(
                        "Checking price watcher id=%s item=%s game=%s league=%s target=%s %s source=%s",
                        tracked_item.id,
                        request.item_name,
                        request.game,
                        request.league_name,
                        request.target_price,
                        request.target_currency,
                        "trade_url" if request.trade_url else "currency-market",
                    )
                    if request.trade_url:
                        snapshot = await self.poe_trade_client.get_price_snapshot(request)
                    else:
                        snapshot = await self.currency_market_source.get_price(request)
                    if snapshot:
                        result = await price_alert_service.process_snapshot(tracked_item=tracked_item, snapshot=snapshot)
                        if result.triggered:
                            triggered_alerts += 1
                            logger.info(
                                "Price alert triggered id=%s item=%s current=%s %s target=%s %s source=%s",
                                tracked_item.id,
                                request.item_name,
                                result.current_value,
                                result.target_currency,
                                result.target_price,
                                result.target_currency,
                                result.source,
                            )
                        else:
                            logger.info(
                                "Price watcher not triggered id=%s item=%s reason=%s current=%s target=%s currency=%s source=%s",
                                tracked_item.id,
                                request.item_name,
                                result.reason,
                                result.current_value,
                                result.target_price,
                                result.target_currency,
                                result.source,
                            )
                    else:
                        snapshot_misses += 1
                        logger.warning(
                            "No price snapshot for watcher id=%s item=%s game=%s league=%s",
                            tracked_item.id,
                            request.item_name,
                            request.game,
                            request.league_name,
                        )
                    continue

                processed_sale_watchers += 1
                logger.info(
                    "Checking sale watcher id=%s item=%s game=%s league=%s source=%s",
                    tracked_item.id,
                    request.item_name,
                    request.game,
                    request.league_name,
                    "trade_url" if request.trade_url else "registry",
                )
                source = self.source_registry.resolve(request)
                sales = await source.poll_sales(request)
                logger.info(
                    "Sale watcher polled id=%s item=%s candidates=%s source=%s",
                    tracked_item.id,
                    request.item_name,
                    len(sales),
                    source.source_name,
                )
                for sale in sales:
                    result = await sales_service.process_sale_event(tracked_item=tracked_item, sale=sale)
                    if result.created:
                        created_sales += 1
            except Exception:
                worker_errors += 1
                logger.exception("Tracking worker failed for tracked_item_id=%s", tracked_item.id)

        logger.info(
            "Tracking worker tick finished, created_sales=%s triggered_alerts=%s processed_price_watchers=%s processed_sale_watchers=%s snapshot_misses=%s worker_errors=%s",
            created_sales,
            triggered_alerts,
            processed_price_watchers,
            processed_sale_watchers,
            snapshot_misses,
            worker_errors,
        )
