import asyncio
from decimal import Decimal

from app.services.poe_account import StashItemSummary, StashSnapshot, StashTabOverview
from app.services.stash import StashService


class _FakePrice:
    def __init__(self, chaos: str, source: str = "test-source"):
        self.market_value = Decimal(chaos)
        self.quote_values = {"chaos": Decimal(chaos)}
        self.source = source


class _FakeCurrencySource:
    def __init__(self, mapping: dict[str, str]):
        self.mapping = mapping

    async def get_price(self, request):
        chaos = self.mapping.get(request.item_name)
        if chaos is None:
            return None
        return _FakePrice(chaos)


def _tab(name: str, tab_type: str, summaries: tuple[StashItemSummary, ...]) -> StashTabOverview:
    return StashTabOverview(
        id=name,
        name=name,
        type=tab_type,
        item_count=sum(item.entry_count for item in summaries),
        is_folder=False,
        is_special=True,
        priority_score=0,
        priority_reason=None,
        preview_items=(),
        item_summaries=summaries,
    )


def test_build_priced_candidates_uses_currency_source_for_liquid_tabs() -> None:
    service = StashService(None)  # type: ignore[arg-type]
    service.currency_market_source = _FakeCurrencySource(
        {
            "Chaos Orb": "1",
            "Divine Orb": "180",
            "Exalted Orb": "10",
        }
    )

    snapshot = StashSnapshot(
        league_name="Mirage",
        total_tabs=2,
        folder_tabs=0,
        special_tabs=2,
        empty_tabs=0,
        total_items=3,
        sample_tabs=("Currency", "Fragments"),
        liquid_tabs=(),
        dense_tabs=(),
        dump_tabs=(),
        tabs=(
            _tab(
                "Currency",
                "CurrencyStash",
                (
                    StashItemSummary(name="Divine Orb", quantity=2, entry_count=1),
                    StashItemSummary(name="Chaos Orb", quantity=40, entry_count=1),
                ),
            ),
            _tab(
                "Fragments",
                "FragmentStash",
                (
                    StashItemSummary(name="Exalted Orb", quantity=3, entry_count=1),
                ),
            ),
        ),
    )

    candidates, source, estimate = asyncio.run(service._build_priced_candidates(snapshot))

    assert source == "test-source"
    assert estimate == 430.0
    assert candidates[0].item_name == "Divine Orb"
    assert candidates[0].total_price_chaos == 360.0
    assert candidates[1].item_name == "Chaos Orb"
    assert candidates[1].total_price_chaos == 40.0
    assert candidates[2].item_name == "Exalted Orb"
    assert candidates[2].total_price_chaos == 30.0
