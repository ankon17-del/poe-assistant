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


def test_build_character_summaries_prefers_highest_level_characters() -> None:
    characters = [
        {"name": "MapperJoe", "league": "Mirage", "level": 92, "class": "Deadeye"},
        {"name": "BosserAmy", "league": "Mirage", "level": 97, "class": "Pathfinder"},
        {"name": "CrafterTom", "league": "Standard", "level": 88, "class": "Occultist"},
        {"name": "Lowbie", "league": "Mirage", "level": 14, "class": "Ranger"},
    ]

    summaries = PoeAccountApiService._build_character_summaries(characters)

    assert [character.name for character in summaries] == ["BosserAmy", "MapperJoe", "CrafterTom"]
    assert summaries[0].league == "Mirage"
    assert summaries[0].level == 97
    assert summaries[0].class_name == "Pathfinder"


def test_build_account_summary_notes_for_hybrid_account() -> None:
    snapshot = AccountSnapshot(
        account_name="Xa1ha#6754",
        profile_name="Xa1ha#6754",
        poe1_leagues=("Mirage", "Standard"),
        poe1_primary_league="Mirage",
        poe1_character_count=3,
        poe2_character_count=6,
        poe1_characters=(),
        poe2_characters=(),
        poe1_stash_note=None,
    )

    notes = build_account_summary_notes(snapshot, "ru")

    assert len(notes) == 3
    assert "Mirage" in notes[0]
    assert "POE2" in notes[1]
    assert "POE1, и в POE2" in notes[2]


def test_build_account_text_includes_account_aware_summary() -> None:
    poe1_roster = PoeAccountApiService._build_character_summaries(
        [
            {"name": "BosserAmy", "league": "Mirage", "level": 97, "class": "Pathfinder"},
            {"name": "MapperJoe", "league": "Mirage", "level": 92, "class": "Deadeye"},
        ]
    )
    poe2_roster = PoeAccountApiService._build_character_summaries(
        [
            {"name": "RunesMage", "league": "Aldur Runes", "level": 88, "class": "Sorceress"},
        ]
    )

    snapshot = AccountSnapshot(
        account_name="Xa1ha#6754",
        profile_name="Xa1ha#6754",
        poe1_leagues=("Mirage", "Standard"),
        poe1_primary_league="Mirage",
        poe1_character_count=5,
        poe2_character_count=2,
        poe1_characters=poe1_roster,
        poe2_characters=poe2_roster,
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
    assert "Кого бот видит в POE1" in text
    assert "BosserAmy lvl 97 Pathfinder [Mirage]" in text
    assert "RunesMage lvl 88 Sorceress [Aldur Runes]" in text
