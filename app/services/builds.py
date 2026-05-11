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
    first_upgrades: tuple[str, ...]
    comfort_upgrades: tuple[str, ...]
    damage_upgrades: tuple[str, ...]
    defense_fixes: tuple[str, ...]
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
            first_upgrades=("нормальный лук", "6-link под основную связку", "точность и crit consistency"),
            comfort_upgrades=("больше attack speed", "quiver с quality-of-life статами", "move speed на ботинках"),
            damage_upgrades=("лучший ele bow", "crit multi", "дополнительные projectile scaling слои"),
            defense_fixes=("spell suppression cap", "evasion", "life на редких слотах"),
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
            first_upgrades=("уровни камней", "нормальный wand / sceptre", "mine throw speed"),
            comfort_upgrades=("faster detonation feel", "mana comfort", "movement quality-of-life"),
            damage_upgrades=("gem levels", "crit multi", "better curse / exposure setup"),
            defense_fixes=("evasion or ES слой", "spell suppression", "хаос-рез, если проседает"),
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
            first_upgrades=("cap резистов", "regen", "+max fire res"),
            comfort_upgrades=("movement speed", "radius / clear comfort", "recovery feel"),
            damage_upgrades=("burning damage", "gem levels", "dot multi where applicable"),
            defense_fixes=("life pool", "armour", "max res и sustain под RF"),
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
            first_upgrades=("cast speed", "mana sustain", "уровни основного камня"),
            comfort_upgrades=("быстрый cast feel", "удобный movement setup", "качество life/mana flask слоя"),
            damage_upgrades=("lightning scaling", "crit / shock value", "лучший weapon/focus"),
            defense_fixes=("energy shield или life слой", "резисты", "позиционная выживаемость"),
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
            first_upgrades=("оружие с нормальным DPS", "attack speed", "связка под clear"),
            comfort_upgrades=("качество мувмента", "ресурс на sustain", "упрощение clear-loop"),
            damage_upgrades=("лучшее оружие", "cold scaling", "crit / penetration где доступно"),
            defense_fixes=("evade / armour слои", "life", "не проседать по резистам"),
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
            first_upgrades=("уровни minion-камней", "spirit economy", "база по защите"),
            comfort_upgrades=("удобный summon loop", "ресурс под поддерживающие кнопки", "плавность clear"),
            damage_upgrades=("minion levels", "миньон-урон", "лучший support setup"),
            defense_fixes=("щит/броня по ситуации", "life or ES", "резисты и recovery"),
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
            first_upgrades=("лук с хорошим base DPS", "attack uptime", "ядро под single target"),
            comfort_upgrades=("speed/feel в ротации", "ресурс на sustain", "чистка packs без просадки"),
            damage_upgrades=("chaos / poison scaling", "лучший bow", "single-target multipliers"),
            defense_fixes=("позиционная защита", "life", "не проседать по элементальным резистам"),
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
            first_upgrades=("оружие", "armour база", "основная slam-связка"),
            comfort_upgrades=("ускорение ротации", "ресурс на sustain", "качество передвижения"),
            damage_upgrades=("weapon DPS", "physical scaling", "heavy hit multipliers"),
            defense_fixes=("armour", "life", "анти-ваншот слои"),
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
