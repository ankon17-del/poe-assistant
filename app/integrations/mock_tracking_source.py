from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlparse

from app.integrations.tracking_source import SaleEventDTO, TrackingRequest, TrackingSource


class MockTrackingSource(TrackingSource):
    source_name = "mock"

    async def poll_sales(self, request: TrackingRequest) -> list[SaleEventDTO]:
        if not request.trade_url or not request.trade_url.startswith("mock://"):
            return []

        parsed = urlparse(request.trade_url)
        query = parse_qs(parsed.query)
        external_id = parsed.netloc or parsed.path.strip("/") or "mock-sale"
        item_name = query.get("item", [request.item_name or "Mock Item"])[0]
        price_text = query.get("price", ["1 div"])[0]
        price_amount, price_currency = self._parse_price_text(price_text)

        return [
            SaleEventDTO(
                external_id=external_id,
                item_name=item_name,
                price_text=price_text,
                price_amount=price_amount,
                price_currency=price_currency,
                league_name=request.league_name,
                sold_at=None,
                source=self.source_name,
                raw_payload={
                    "external_id": external_id,
                    "item_name": item_name,
                    "price_text": price_text,
                    "source": self.source_name,
                },
                game=request.game,
            )
        ]

    @staticmethod
    def _parse_price_text(price_text: str) -> tuple[Decimal | None, str | None]:
        parts = price_text.split(maxsplit=1)
        if not parts:
            return None, None

        try:
            amount = Decimal(parts[0].replace(",", "."))
        except InvalidOperation:
            amount = None

        currency = parts[1] if len(parts) > 1 else None
        return amount, currency
