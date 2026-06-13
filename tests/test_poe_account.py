from app.bot.handlers import build_account_summary_notes, build_account_text
from app.services.poe_account import AccountSnapshot, PoeAccountApiService


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


def test_build_account_summary_notes_for_hybrid_account() -> None:
    snapshot = AccountSnapshot(
        account_name="Xa1ha#6754",
        profile_name="Xa1ha#6754",
        poe1_leagues=("Mirage", "Standard"),
        poe1_primary_league="Mirage",
        poe1_character_count=3,
        poe2_character_count=6,
        poe1_stash_note=None,
    )

    notes = build_account_summary_notes(snapshot, "ru")

    assert len(notes) == 3
    assert "Mirage" in notes[0]
    assert "POE2" in notes[1]
    assert "POE1, и в POE2" in notes[2]


def test_build_account_text_includes_account_aware_summary() -> None:
    snapshot = AccountSnapshot(
        account_name="Xa1ha#6754",
        profile_name="Xa1ha#6754",
        poe1_leagues=("Mirage", "Standard"),
        poe1_primary_league="Mirage",
        poe1_character_count=5,
        poe2_character_count=2,
        poe1_stash_note="Сейчас этот stash-view работает по PoE1 account stashes.",
    )

    text = build_account_text(
        integration=None,
        oauth_config_error=None,
        locale="ru",
        snapshot=snapshot,
        live_error=None,
    )

    assert "Короткий account-aware вывод:" in text
    assert "Mirage" in text
    assert "POE1-слой" in text
