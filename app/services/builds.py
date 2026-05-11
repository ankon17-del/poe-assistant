from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BuildRecommendation:
    title: str
    game: str
    archetype: str
    class_name: str
    budget_tier: str
    playstyles: tuple[str, ...]
    core_skill: str
    strengths: tuple[str, ...]
    cautions: tuple[str, ...]
    gear_focus: tuple[str, ...]
    summary: str


class BuildService:
    _catalog: tuple[BuildRecommendation, ...] = (
        BuildRecommendation(
            title="Lightning Arrow Deadeye",
            game="poe1",
            archetype="mapper",
            class_name="Ranger / Deadeye",
            budget_tier="mid",
            playstyles=("speed", "allround"),
            core_skill="Lightning Arrow",
            strengths=("очень быстрый маппинг", "комфортный старт фарма", "приятный clear"),
            cautions=("хуже чувствует себя в жёстком босcинге", "любит хороший лук"),
            gear_focus=("лук с высоким ele DPS", "крит и projectile scaling", "evasion + suppression"),
            summary="Классический быстрый маппер для POE1, если хочется фармить карты и валюту в темпе.",
        ),
        BuildRecommendation(
            title="Hexblast Mines Trickster",
            game="poe1",
            archetype="allround",
            class_name="Shadow / Trickster",
            budget_tier="mid",
            playstyles=("boss", "allround"),
            core_skill="Hexblast Mines",
            strengths=("сильный урон по боссам", "хороший scaling в мидгейме", "универсальный"),
            cautions=("нужно привыкнуть к mine-геймплею", "не самый ленивый clear"),
            gear_focus=("gem levels", "crit multi", "mine throwing speed"),
            summary="Хороший универсальный выбор, если нужен баланс между фармом и убийством боссов.",
        ),
        BuildRecommendation(
            title="Righteous Fire Chieftain",
            game="poe1",
            archetype="tank",
            class_name="Marauder / Chieftain",
            budget_tier="starter",
            playstyles=("safe", "allround"),
            core_skill="Righteous Fire",
            strengths=("очень комфортный геймплей", "живучесть", "спокойный маппинг"),
            cautions=("урон на босcах растёт не сразу", "любят regen и max res"),
            gear_focus=("life regen", "fire res / max res", "burning damage"),
            summary="Надёжный старт, если хочется играть спокойно, толстым персонажем и без суеты.",
        ),
        BuildRecommendation(
            title="Spark Stormweaver",
            game="poe2",
            archetype="allround",
            class_name="Sorceress / Stormweaver",
            budget_tier="starter",
            playstyles=("allround", "speed"),
            core_skill="Spark",
            strengths=("лёгкий вход", "хороший clear", "приятный scaling в early economy"),
            cautions=("нужны нормальные каст-статы", "позиционка важна на боссах"),
            gear_focus=("cast speed", "lightning damage", "mana sustain"),
            summary="Очень крепкий POE2-старт, если нужен универсальный caster для раннего фарма.",
        ),
        BuildRecommendation(
            title="Ice Strike Monk",
            game="poe2",
            archetype="mapper",
            class_name="Monk",
            budget_tier="mid",
            playstyles=("speed", "allround"),
            core_skill="Ice Strike",
            strengths=("высокий темп", "приятный melee clear", "хороший feel на картах"),
            cautions=("более требователен к оружию", "ошибки позиционки наказывают"),
            gear_focus=("weapon DPS", "attack speed", "cold scaling"),
            summary="Если хочется динамичного POE2-мели билда для темпового фарма и маппинга.",
        ),
        BuildRecommendation(
            title="Minion Infernalist",
            game="poe2",
            archetype="safe",
            class_name="Witch / Infernalist",
            budget_tier="starter",
            playstyles=("safe", "allround"),
            core_skill="Minions",
            strengths=("спокойный стиль игры", "меньше требований к механике", "хороший старт"),
            cautions=("темп ниже, чем у топ-clear билдов", "нужен контроль summon setup"),
            gear_focus=("minion levels", "spirit / mana economy", "defensive layers"),
            summary="Хороший выбор, если хочется безопасного старта и меньше давления по механике.",
        ),
        BuildRecommendation(
            title="Gas Arrow Huntress",
            game="poe2",
            archetype="boss",
            class_name="Huntress",
            budget_tier="mid",
            playstyles=("boss", "allround"),
            core_skill="Gas Arrow",
            strengths=("сильный single target", "хороший scaling", "гибкость под контент"),
            cautions=("нужен аккуратный setup", "не самый тупо-прямой геймплей"),
            gear_focus=("bow DPS", "chaos / poison style scaling", "attack uptime"),
            summary="Подходит, если хочется уже не только фармить, но и уверенно давить более жирные цели.",
        ),
        BuildRecommendation(
            title="Titan Slam Warrior",
            game="poe2",
            archetype="tank",
            class_name="Warrior / Titan",
            budget_tier="mid",
            playstyles=("safe", "boss"),
            core_skill="Slam skills",
            strengths=("живучесть", "мощные удары по жирным целям", "понятный progression path"),
            cautions=("темп ниже, чем у быстрых билдов", "хочет нормальное оружие"),
            gear_focus=("weapon physical DPS", "armour", "stun / heavy hit scaling"),
            summary="Крепкий путь, если нужен плотный персонаж для более спокойного, но уверенного прогресса.",
        ),
    )

    def recommend(
        self,
        *,
        game: str,
        budget_tier: str,
        playstyle: str,
        limit: int = 3,
    ) -> list[BuildRecommendation]:
        scored: list[tuple[int, BuildRecommendation]] = []
        for build in self._catalog:
            if build.game != game:
                continue

            score = 0
            if build.budget_tier == budget_tier:
                score += 3
            elif budget_tier == "starter" and build.budget_tier == "mid":
                score += 1
            elif budget_tier == "high" and build.budget_tier == "mid":
                score += 2

            if playstyle in build.playstyles:
                score += 4
            elif playstyle == "allround":
                score += 1

            if build.archetype == playstyle:
                score += 2

            scored.append((score, build))

        scored.sort(key=lambda item: (item[0], item[1].budget_tier == budget_tier), reverse=True)
        return [build for _, build in scored[:limit]]

    @staticmethod
    def game_label(game: str) -> str:
        return "POE 2" if game == "poe2" else "POE 1"

    @staticmethod
    def budget_label(budget_tier: str) -> str:
        return {
            "starter": "стартовый",
            "mid": "средний",
            "high": "высокий",
        }.get(budget_tier, budget_tier)

    @staticmethod
    def playstyle_label(playstyle: str) -> str:
        return {
            "speed": "быстрый фарм",
            "safe": "спокойный / живучий",
            "boss": "босcинг",
            "allround": "универсальный",
        }.get(playstyle, playstyle)
