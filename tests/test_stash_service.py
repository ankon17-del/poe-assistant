import asyncio
from decimal import Decimal

from app.integrations.stash_market_source import MarketPriceEntry
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

    async def get_exchange_rates(self, league_name: str, game: str | None):
        return {
            "chaos": Decimal("1"),
            "ex": Decimal("10"),
            "div": Decimal("180"),
        }


class _FakeStashMarketSource:
    def __init__(self, mapping: dict[str, dict[str, str]]):
        self.mapping = mapping

    async def get_price_index(self, *, league_name: str, stash_type: str):
        entries = self.mapping.get(stash_type)
        if not entries:
            return None
        return (
            {
                name: MarketPriceEntry(name=name, chaos_value=Decimal(chaos), source="stash-market")
                for name, chaos in entries.items()
            },
            "stash-market",
        )


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
    service.currency_market_source = _FakeCurrencySource({})
    service.stash_market_source = _FakeStashMarketSource(
        {
            "CurrencyStash": {
                "Chaos Orb": "1",
                "Divine Orb": "180",
            },
            "FragmentStash": {
                "Exalted Orb": "10",
            },
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

    candidates, category_totals, tab_totals, source, estimate = asyncio.run(service._build_priced_candidates(snapshot))

    assert source == "stash-market"
    assert estimate == 430.0
    assert [(row.category_key, row.total_price_chaos) for row in category_totals] == [
        ("currency", 400.0),
        ("fragments", 30.0),
    ]
    assert [(row.tab_name, row.total_price_chaos) for row in tab_totals] == [
        ("Currency", 400.0),
        ("Fragments", 30.0),
    ]
    assert candidates[0].item_name == "Divine Orb"
    assert candidates[0].category_key == "currency"
    assert candidates[0].tab_type == "CurrencyStash"
    assert candidates[0].total_price_chaos == 360.0
    assert candidates[1].item_name == "Chaos Orb"
    assert candidates[1].total_price_chaos == 40.0
    assert candidates[2].item_name == "Exalted Orb"
    assert candidates[2].total_price_chaos == 30.0


def test_build_priced_candidates_supports_essences_and_div_cards() -> None:
    service = StashService(None)  # type: ignore[arg-type]
    service.currency_market_source = _FakeCurrencySource({})
    service.stash_market_source = _FakeStashMarketSource(
        {
            "EssenceStash": {
                "Screaming Essence of Hatred": "4",
            },
            "DivinationCardStash": {
                "A Fate Worse Than Death": "22",
            },
        }
    )

    snapshot = StashSnapshot(
        league_name="Mirage",
        total_tabs=2,
        folder_tabs=0,
        special_tabs=2,
        empty_tabs=0,
        total_items=2,
        sample_tabs=("Essences", "Div Cards"),
        liquid_tabs=(),
        dense_tabs=(),
        dump_tabs=(),
        tabs=(
            _tab(
                "Essences",
                "EssenceStash",
                (
                    StashItemSummary(name="Screaming Essence of Hatred", quantity=6, entry_count=1),
                ),
            ),
            _tab(
                "Div Cards",
                "DivinationCardStash",
                (
                    StashItemSummary(name="A Fate Worse Than Death", quantity=4, entry_count=1),
                ),
            ),
        ),
    )

    candidates, category_totals, tab_totals, source, estimate = asyncio.run(service._build_priced_candidates(snapshot))

    assert source == "stash-market"
    assert estimate == 112.0
    assert [(row.category_key, row.total_price_chaos) for row in category_totals] == [
        ("div_cards", 88.0),
        ("essences", 24.0),
    ]
    assert [(row.tab_name, row.total_price_chaos) for row in tab_totals] == [
        ("Div Cards", 88.0),
        ("Essences", 24.0),
    ]
    assert candidates[0].category_key == "div_cards"
    assert candidates[0].tab_type == "DivinationCardStash"
    assert [candidate.item_name for candidate in candidates] == [
        "A Fate Worse Than Death",
        "Screaming Essence of Hatred",
    ]
