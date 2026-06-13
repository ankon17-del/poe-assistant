import asyncio
from decimal import Decimal

from app.bot.handlers import build_stash_action_text, build_stash_text
from app.integrations.stash_market_source import MarketPriceEntry
from app.services.poe_account import AccountSnapshot, CharacterSummary, StashItemSummary, StashSnapshot, StashTabOverview
from app.services.stash import (
    PricedStashCandidate,
    StashCapabilityStatus,
    StashCategoryTotal,
    StashPanelSummary,
    StashService,
    StashTabTotal,
)


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


def test_build_stash_action_text_for_liquid_uses_live_candidates() -> None:
    summary = StashPanelSummary(
        account_connected=True,
        account_name="Xa1ha#6754",
        account_snapshot=None,
        oauth_available=True,
        oauth_blocker=None,
        approved_scopes=("account:stashes",),
        stash_scopes_ready=True,
        live_snapshot=StashSnapshot(
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
            tabs=(),
        ),
        live_error=None,
        priced_candidates=(
            PricedStashCandidate(
                tab_name="Currency",
                tab_type="CurrencyStash",
                category_key="currency",
                item_name="Divine Orb",
                quantity=3,
                unit_price_chaos=587.2,
                total_price_chaos=1762.0,
            ),
        ),
        category_totals=(StashCategoryTotal(category_key="currency", total_price_chaos=3551.0),),
        tab_totals=(StashTabTotal(tab_name="Currency", tab_type="CurrencyStash", total_price_chaos=3551.0),),
        valuation_source="poe.ninja",
        estimated_liquid_chaos=11875.0,
        statuses=(StashCapabilityStatus(title="ok", status="ok", detail="ok"),),
        next_steps=("next",),
    )

    text = build_stash_action_text(summary, "liquid", "ru")

    assert "Видимая ликвидность сейчас" in text
    assert "Divine Orb x3 [Currency]" in text
    assert "Источник оценки: poe.ninja" in text
    assert "live-слой" in text


def test_build_stash_action_text_for_triage_uses_live_tabs() -> None:
    live_snapshot = StashSnapshot(
        league_name="Mirage",
        total_tabs=3,
        folder_tabs=0,
        special_tabs=2,
        empty_tabs=0,
        total_items=180,
        sample_tabs=("Currency", "Fragments", "Dump"),
        liquid_tabs=(
            _tab(
                "Currency",
                "CurrencyStash",
                (StashItemSummary(name="Divine Orb", quantity=3, entry_count=1),),
            ),
        ),
        dense_tabs=(
            _tab(
                "Dump",
                "NormalStash",
                (StashItemSummary(name="Random Rare", quantity=80, entry_count=80),),
            ),
        ),
        dump_tabs=(
            _tab(
                "Dump",
                "NormalStash",
                (StashItemSummary(name="Random Rare", quantity=80, entry_count=80),),
            ),
        ),
        tabs=(
            _tab("Currency", "CurrencyStash", (StashItemSummary(name="Divine Orb", quantity=3, entry_count=1),)),
            _tab("Fragments", "FragmentStash", (StashItemSummary(name="Horned Scarab of Nemeses", quantity=20, entry_count=1),)),
            _tab("Dump", "NormalStash", (StashItemSummary(name="Random Rare", quantity=80, entry_count=80),)),
        ),
    )
    summary = StashPanelSummary(
        account_connected=True,
        account_name="Xa1ha#6754",
        account_snapshot=None,
        oauth_available=True,
        oauth_blocker=None,
        approved_scopes=("account:stashes",),
        stash_scopes_ready=True,
        live_snapshot=live_snapshot,
        live_error=None,
        priced_candidates=(),
        category_totals=(),
        tab_totals=(StashTabTotal(tab_name="Fragments", tab_type="FragmentStash", total_price_chaos=6540.0),),
        valuation_source="poe.ninja",
        estimated_liquid_chaos=6540.0,
        statuses=(StashCapabilityStatus(title="ok", status="ok", detail="ok"),),
        next_steps=("next",),
    )

    text = build_stash_action_text(summary, "triage", "ru")

    assert "Что делать прямо сейчас:" in text
    assert "Топ вкладки по value:" in text
    assert "Где вероятен разбор:" in text
    assert "Fragments (fragments)" in text or "Fragments (fragment" in text


def test_build_stash_text_includes_account_aware_context() -> None:
    summary = StashPanelSummary(
        account_connected=True,
        account_name="Xa1ha#6754",
        account_snapshot=AccountSnapshot(
            account_name="Xa1ha#6754",
            profile_name="Xa1ha#6754",
            poe1_leagues=("Mirage", "Standard"),
            poe1_primary_league="Mirage",
            poe1_character_count=3,
            poe2_character_count=6,
            poe1_characters=(
                CharacterSummary(name="BosserAmy", league="Mirage", level=97, class_name="Pathfinder"),
            ),
            poe2_characters=(
                CharacterSummary(name="RunesMage", league="Aldur Runes", level=88, class_name="Sorceress"),
            ),
            poe1_stash_note=None,
        ),
        oauth_available=True,
        oauth_blocker=None,
        approved_scopes=("account:stashes",),
        stash_scopes_ready=True,
        live_snapshot=StashSnapshot(
            league_name="Mirage",
            total_tabs=1,
            folder_tabs=0,
            special_tabs=1,
            empty_tabs=0,
            total_items=10,
            sample_tabs=("Currency",),
            liquid_tabs=(),
            dense_tabs=(),
            dump_tabs=(),
            tabs=(),
        ),
        live_error=None,
        priced_candidates=(),
        category_totals=(),
        tab_totals=(),
        valuation_source=None,
        estimated_liquid_chaos=None,
        statuses=(StashCapabilityStatus(title="ok", status="ok", detail="ok"),),
        next_steps=("next",),
    )

    text = build_stash_text(summary, "ru")

    assert "Account-aware контекст:" in text
    assert "POE1-фокус: Mirage (BosserAmy lvl 97 Pathfinder)" in text
    assert "POE2-фокус: Aldur Runes (RunesMage lvl 88 Sorceress)" in text
    assert "Текущий stash-scan совпадает с основной PoE1-лигой аккаунта: Mirage." in text
