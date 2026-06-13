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
