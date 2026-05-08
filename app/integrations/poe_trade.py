from app.integrations.mock_tracking_source import MockTrackingSource
from app.integrations.tracking_source import SaleEventDTO, TrackingRequest


class PoeTradeClient:
    # Compatibility wrapper while the worker migrates to source registry based polling.
    async def poll_sales(self, trade_url: str, item_name: str | None = None) -> list[SaleEventDTO]:
        request = TrackingRequest(
            tracked_item_id=0,
            item_name=item_name or "Unknown Item",
            trade_url=trade_url,
            league_name=None,
            game=None,
        )
        return await MockTrackingSource().poll_sales(request)
