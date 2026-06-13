from app.services.poe_account import PoeAccountApiService


def test_choose_primary_poe1_league_prefers_configured_default() -> None:
    leagues = ("Mirage", "Standard", "Hardcore")
    selected = PoeAccountApiService.choose_primary_poe1_league(leagues, "Mirage")
    assert selected == "Mirage"


def test_choose_primary_poe1_league_prefers_non_standard_softcore() -> None:
    leagues = ("Hardcore", "SSF Mirage", "Mirage", "Standard")
    selected = PoeAccountApiService.choose_primary_poe1_league(leagues, None)
    assert selected == "Mirage"


def test_choose_primary_poe1_league_falls_back_to_standard() -> None:
    leagues = ("Hardcore", "SSF Standard", "Standard")
    selected = PoeAccountApiService.choose_primary_poe1_league(leagues, None)
    assert selected == "Standard"


def test_choose_primary_poe1_league_does_not_prefer_ruthless_over_standard() -> None:
    leagues = ("Ruthless", "Hardcore", "Standard")
    selected = PoeAccountApiService.choose_primary_poe1_league(leagues, None)
    assert selected == "Standard"


def test_choose_primary_poe1_league_does_not_prefer_ruthless_over_temp_softcore() -> None:
    leagues = ("Ruthless", "Mirage", "Hardcore")
    selected = PoeAccountApiService.choose_primary_poe1_league(leagues, None)
    assert selected == "Mirage"


def test_build_item_summaries_aggregates_stack_sizes() -> None:
    items = [
        {"name": "", "typeLine": "A Fate Worse Than Death", "stackSize": 4},
        {"name": "", "typeLine": "A Fate Worse Than Death", "stackSize": 2},
        {"name": "", "typeLine": "Gemcutter's Promise", "stackSize": 3},
        {"name": "Screaming", "typeLine": "Essence of Hatred"},
    ]

    summaries = PoeAccountApiService._build_item_summaries(items)

    assert summaries[0].name == "A Fate Worse Than Death"
    assert summaries[0].quantity == 6
    assert summaries[0].entry_count == 2
    assert summaries[1].name == "Gemcutter's Promise"
    assert summaries[1].quantity == 3
    assert summaries[2].name == "Screaming Essence of Hatred"
    assert summaries[2].quantity == 1
