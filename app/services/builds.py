from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus


def _search_url(query: str) -> str:
    return f"https://duckduckgo.com/?q={quote_plus(query)}"


@dataclass(frozen=True)
class BuildRecommendation:
    title: str
    game: str
    archetype: str
    goals: tuple[str, ...]
    class_name: str
    budget_tier: str
    playstyles: tuple[str, ...]
    core_skill: str
    budget_estimate: str
    strengths: tuple[str, ...]
    cautions: tuple[str, ...]
    gear_focus: tuple[str, ...]
    buy_priority: tuple[str, ...]
    stat_targets: tuple[str, ...]
    tree_focus: tuple[str, ...]
    atlas_focus: tuple[str, ...]
    farm_mechanics: tuple[str, ...]
    pantheon_or_defense_notes: tuple[str, ...]
    endgame_slot_checklist: tuple[str, ...]
    endgame_goals: tuple[str, ...]
    endgame_milestones: tuple[str, ...]
    chase_upgrades: tuple[str, ...]
    first_upgrades: tuple[str, ...]
    comfort_upgrades: tuple[str, ...]
    damage_upgrades: tuple[str, ...]
    defense_fixes: tuple[str, ...]
    alternative_hint: str
    summary: str
    market_targets: tuple[str, ...] = ()
    gear_sheet: tuple[str, ...] = ()
    gear_progression: tuple[str, ...] = ()
    avoid_warnings: tuple[str, ...] = ()
    planner_url: str | None = None
    guide_url: str | None = None
    tree_url: str | None = None
    atlas_url: str | None = None
    source_note: str | None = None


class BuildService:
    _catalog: tuple[BuildRecommendation, ...] = (
        BuildRecommendation(
            title="Lightning Arrow Deadeye",
            game="poe1",
            archetype="mapper",
            goals=("league_start", "currency_farm"),
            class_name="Ranger / Deadeye",
            budget_tier="mid",
            playstyles=("speed", "allround"),
            core_skill="Lightning Arrow",
            budget_estimate="комфортный старт 3-8 div, midgame 15-30 div, сильный эндгейм 60+ div",
            strengths=("очень быстрый маппинг", "комфортный старт фарма", "приятный clear"),
            cautions=("хуже чувствует себя в жёстком босcинге", "любит хороший лук"),
            gear_focus=("лук с высоким ele DPS", "крит и projectile scaling", "evasion + suppression"),
            buy_priority=("6-link body", "bow с высоким elemental DPS и crit base", "quiver с crit multi / attack speed / life"),
            stat_targets=("100% spell suppression", "4k+ life до позднего эндгейма", "chance to crit достаточно для уверенного crit swap"),
            tree_focus=("bow/projectile колёса", "crit и mastery под bows", "life + suppression по пути"),
            atlas_focus=("быстрый sustain карт", "сильный pack size", "altars и map duplication"),
            farm_mechanics=("Legion", "Harbinger", "Expedition", "Strongboxes"),
            pantheon_or_defense_notes=("Major: Lunaris для маппинга", "Minor: Garukhan/Shakari по ситуации"),
            endgame_slot_checklist=(
                "Weapon: редкий bow с высоким ele DPS, crit chance и attack speed",
                "Quiver: crit multi, attack speed, life, по возможности additional arrow или strong projectile value",
                "Body: 6-link rare/body base с life и suppress, позже luxury offensive chest",
                "Helm/Boots/Gloves: life, spell suppression, резисты, move speed на ботинках",
                "Rings/Amulet/Belt: elemental damage with attacks, crit, life, атрибуты и закрытие резистов",
                "Flasks/Jewels: diamond + jade/granite по feel, jewels на crit multi / projectile / life",
            ),
            endgame_goals=("быстрый T16 mapping", "фарм altar-циклов", "Legion/Expedition ротации"),
            endgame_milestones=("лук, который уже уверенно чистит T16 без просадки по редким", "cap spell suppression и нормальный life pool", "6-link + quiver, после которых можно жать pack size смелее"),
            chase_upgrades=("топовый crit ele bow", "сильный quiver с crit multi и speed", "дорогие jewel / cluster-слоты под чистый DPS"),
            first_upgrades=("нормальный лук", "6-link под основную связку", "точность и crit consistency"),
            comfort_upgrades=("больше attack speed", "quiver с quality-of-life статами", "move speed на ботинках"),
            damage_upgrades=("лучший ele bow", "crit multi", "дополнительные projectile scaling слои"),
            defense_fixes=("spell suppression cap", "evasion", "life на редких слотах"),
            alternative_hint="Если хочется похожий темп, но больше универсальности, смотри в сторону Hexblast Mines Trickster.",
            summary="Классический быстрый маппер для POE1, если хочется фармить карты и валюту в темпе.",
            market_targets=(
                "Bow: tri-ele или высокий elemental DPS, crit chance, attack speed, по возможности clean suffixes под craft",
                "Quiver: crit multi, attack speed, life, additional arrow или сильный projectile value",
                "Amulet/Rings: elemental damage with attacks, crit multi, life, attributes и закрытие резистов",
                "Boots/Gloves/Helm: suppression, life, move speed, accuracy/attack quality-of-life где доступно",
            ),
            gear_sheet=(
                "Weapon: редкий bow с сильным ele base, crit chance и attack speed — это главный слот для роста feel и clear",
                "Quiver: crit multi, attack speed, life, дополнительный projectile value или arrow, если рынок позволяет",
                "Helmet: suppression, life, резисты; offensive luxury только после стабильной защиты",
                "Body: 6-link first, потом уже luxury chest, если не страдают suppression и life",
                "Gloves/Boots: move speed, life, spell suppression, attack feel и закрытие резистов",
                "Rings/Amulet/Belt: ele damage with attacks, crit multi, life, attributes, res coverage",
                "Jewels/Flasks: crit multi, projectile, life; diamond + jade/granite/quartz под комфорт карт",
            ),
            gear_progression=(
                "Entry: добери 6-link, нормальный bow и cap резистов, не пытайся прыгнуть в luxury DPS раньше времени",
                "Midgame: подними bow, quiver и crit consistency, затем дочисти suppression и life pool под плотные T16",
                "Endgame: дорогой crit ele bow, сильный quiver и jewels/cluster-слоты уже под потолок clear speed и altar-фарм",
            ),
            avoid_warnings=(
                "Map mods: аккуратно с reflect/no-leech-подобными сценариями и любыми модами, которые ломают sustain или feel атаки",
                "Content: не лучший выбор для самого жирного stationary bossing без дорогого лука и нормального single-target слоя",
                "Сырой этап: пока bow и suppression не собраны, не жми слишком злой pack size и не форси жадный altar-цикл",
            ),
            planner_url=_search_url("site:poe-vault.com Lightning Arrow Deadeye passive skill tree gems links"),
            guide_url=_search_url("site:poe-vault.com Lightning Arrow Deadeye build guide"),
            tree_url=_search_url("site:poe-vault.com Lightning Arrow Deadeye passive skill tree gems links"),
            atlas_url="https://www.poe-vault.com/guides/atlas-passive-skill-tree-strategies",
            source_note="Для Lightning Arrow пока даю рабочие внешние entry points: guide и tree через стабильный поиск по PoE Vault, а atlas — через визуальный Atlas guide.",
        ),
        BuildRecommendation(
            title="Hexblast Mines Trickster",
            game="poe1",
            archetype="allround",
            goals=("boss_kill", "comfortable_progress"),
            class_name="Shadow / Trickster",
            budget_tier="mid",
            playstyles=("boss", "allround"),
            core_skill="Hexblast Mines",
            budget_estimate="старт 5-12 div, уверенный мидгейм 20-40 div, сильный боссинг 60+ div",
            strengths=("сильный урон по боссам", "хороший scaling в мидгейме", "универсальный"),
            cautions=("нужно привыкнуть к mine-геймплею", "не самый ленивый clear"),
            gear_focus=("gem levels", "crit multi", "mine throwing speed"),
            buy_priority=("оружие с +levels chaos/spell gems", "щит или off-hand с crit/mana/defense", "amulet под gem levels и crit"),
            stat_targets=("100% spell suppression", "достаточно mine throw speed, чтобы билд не вяз", "хаос-рез хотя бы в ноль, лучше выше"),
            tree_focus=("mine кластеры", "chaos / curse scaling", "defensive ES/evasion путь Trickster"),
            atlas_focus=("одиночные жирные цели", "контент с хорошим reward per encounter", "меньше упора в супер-скорость"),
            farm_mechanics=("Essence", "Expedition", "Harvest", "Maven / boss rushing"),
            pantheon_or_defense_notes=("Major: Solaris для тяжёлых целей", "Minor: Shakari/Abberath по встречному урону"),
            endgame_slot_checklist=(
                "Weapon: wand/sceptre с +chaos gems / +spell gems, crit chance и cast speed",
                "Off-hand: shield или focus с spell damage, crit, mana/res и защитой",
                "Body: 6-link/основной mine setup, life/ES/evasion база без дыр по резистам",
                "Helm/Gloves/Boots: suppression, life или ES, move speed, utility mods",
                "Rings/Amulet/Belt: crit multi, mana sustain, chaos-res, gem levels на амулете как big upgrade",
                "Flasks/Jewels: quartz/diamond/defensive фласки, jewels на crit multi, mine damage, spell damage",
            ),
            endgame_goals=("Maven / guardian / invitation farming", "точечный фарм жирных encounter'ов", "универсальный endgame без упора в zoom"),
            endgame_milestones=("уровни камней и crit уже держат single target на боссах", "mine throw speed не ломает ритм билда", "хаос-рез и suppression не проваливаются на invitation-контенте"),
            chase_upgrades=("топовый wand/sceptre с gem levels", "амулет под дорогой gem-level scaling", "дорогие crit multi jewels и luxury curse setup"),
            first_upgrades=("уровни камней", "нормальный wand / sceptre", "mine throw speed"),
            comfort_upgrades=("faster detonation feel", "mana comfort", "movement quality-of-life"),
            damage_upgrades=("gem levels", "crit multi", "better curse / exposure setup"),
            defense_fixes=("evasion or ES слой", "spell suppression", "хаос-рез, если проседает"),
            alternative_hint="Если хочется спокойнее и толще, но с меньшим микро, посмотри на Righteous Fire Chieftain.",
            summary="Хороший универсальный выбор, если нужен баланс между фармом и убийством боссов.",
            market_targets=(
                "Wand/Sceptre: +1 chaos or spell gems, crit chance for spells, crit multi, cast speed",
                "Shield/Off-hand: spell damage, spell crit, life or ES, suppress or resist suffixes",
                "Amulet: +1 chaos gems or global crit multi, life/ES, attributes if tree is tight",
                "Boots/Gloves/Helm: spell suppression, life or ES, chaos res, move speed on boots",
            ),
            gear_sheet=(
                "Weapon: rare wand/sceptre with +1 chaos or spell gems, spell crit, cast speed, chaos/spell damage",
                "Off-hand: shield or focus with spell crit, life or ES, resist suffixes, suppression if possible",
                "Helmet: life/ES base, suppression, chaos res, open suffixes to finish res caps cleanly",
                "Body: 6-link defensive chest first; avoid greedy pure-DPS swap before your mine feel is stable",
                "Gloves/Boots: suppression, move speed on boots, life/ES, chaos res or attributes",
                "Rings/Amulet/Belt: gem levels or crit multi on amulet, mana comfort where needed, life/ES, capped resistances",
                "Jewels/Flasks: crit multi, spell damage, mine damage, with diamond + quartz/defensive flask setup",
            ),
            gear_progression=(
                "Entry: закрой 6-link, нормальный wand/sceptre и базовую защиту по suppression/life/ES",
                "Midgame: подними gem levels, crit consistency и mine throw speed, затем дочисти chaos res и sustain",
                "Endgame: дорогой wand, сильный амулет под gem levels/crit multi и хорошие jewels под single target ceiling",
            ),
            avoid_warnings=(
                "Map mods: reroll no/low mana sustain, reduced recovery, awkward curse interaction if your setup leans on it",
                "Content: не лучший билд для полностью ленивого zoom-mapping — любит паузы под mine setup",
                "Сырой этап: пока нет нормального throw speed и gem levels, не жми самые жирные invitations",
            ),
            planner_url="https://www.poe-vault.com/guides/hexblast-miner-saboteur-build-guide",
            guide_url="https://www.youtube.com/watch?v=8XHF0seCGZQ",
            tree_url="https://www.poe-vault.com/guides/hexblast-miner-saboteur-passive-skill-tree-gems-links",
            atlas_url="https://www.poe-vault.com/guides/atlas-passive-skill-tree-strategies",
            source_note="PoE1-референс пока community-sourced и может отставать от текущего баланса, но даёт реальную пассивку, гемы и gear-скелет.",
        ),
        BuildRecommendation(
            title="Righteous Fire Chieftain",
            game="poe1",
            archetype="tank",
            goals=("league_start", "comfortable_progress"),
            class_name="Marauder / Chieftain",
            budget_tier="starter",
            playstyles=("safe", "allround"),
            core_skill="Righteous Fire",
            budget_estimate="старт 1-5 div, комфортные карты 10-20 div, хороший эндгейм 40+ div",
            strengths=("очень комфортный геймплей", "живучесть", "спокойный маппинг"),
            cautions=("урон на босcах растёт не сразу", "любят regen и max res"),
            gear_focus=("life regen", "fire res / max res", "burning damage"),
            buy_priority=("щит/оружие с fire dot / +levels где доступно", "ботинки/перчатки с life + res", "источники max fire res и regen"),
            stat_targets=("90% fire res идеал, но сначала max fire res как можно выше", "стабильный life regen под RF", "armour + life без дыр по резистам"),
            tree_focus=("life regen", "burning/fire DOT", "armour/life колёса рядом с Marauder"),
            atlas_focus=("плотный, но спокойный маппинг", "механики без резких one-shot проверок", "контент, где RF просто идёт вперёд"),
            farm_mechanics=("Expedition", "Blight", "Harvest", "Strongboxes"),
            pantheon_or_defense_notes=("Major: Arakaali или Lunaris", "Minor: Abberath для ground degens"),
            endgame_slot_checklist=(
                "Weapon/Shield: fire dot sceptre и shield с max res, life, recover/regen где доступно",
                "Body: плотная armour/life база, желательно с хорошими суффиксами под резисты",
                "Helm: life, nearby fire scaling или utility под RF/Fire Trap версию",
                "Gloves/Boots: regen, life, резисты, move speed и quality-of-life mods",
                "Rings/Amulet/Belt: life regen, max res, fire dot multi, attributes по необходимости",
                "Flasks/Jewels: ruby/armour фласки, jewels на burning/fire dot/life regen",
            ),
            endgame_goals=("спокойный T16 sustain", "Blight/Expedition фарм", "комфортный progression без рваного геймплея"),
            endgame_milestones=("RF sustain больше не проседает на плотных картах", "max fire res и regen уже держат неприятные моды", "броня и life позволяют не ловить случайные ваншоты от карты"),
            chase_upgrades=("дорогой sceptre/shield под fire dot", "максимизация +max fire res", "luxury jewels и слоты на regen/dot multi"),
            first_upgrades=("cap резистов", "regen", "+max fire res"),
            comfort_upgrades=("movement speed", "radius / clear comfort", "recovery feel"),
            damage_upgrades=("burning damage", "gem levels", "dot multi where applicable"),
            defense_fixes=("life pool", "armour", "max res и sustain под RF"),
            alternative_hint="Если хочется быстрее закрывать карты ценой меньшей жирности, можно смотреть Lightning Arrow Deadeye.",
            summary="Надёжный старт, если хочется играть спокойно, толстым персонажем и без суеты.",
            market_targets=(
                "Sceptre: fire dot multi, +fire or spell gems, burning/fire damage, clean suffixes под резисты",
                "Shield: max fire res, life, recovery/regen, armour и удобные defensive suffixes",
                "Amulet/Rings/Belt: regen, max res, fire dot multi, life, attributes и чистое закрытие резистов",
                "Boots/Gloves/Helm: life, armour, regen, move speed, utility под RF/Fire Trap feel",
            ),
            gear_sheet=(
                "Weapon/Shield: sceptre + shield под fire dot, max res, life regen и recovery — сердцевина живучести RF",
                "Helmet: life, armour, nearby fire scaling или utility под RF/Fire Trap версию",
                "Body: armour/life chest с чистыми суффиксами под max fire res и остальную защиту",
                "Gloves/Boots: regen, life, резисты, move speed и любые mods, которые делают RF feel спокойнее",
                "Rings/Amulet/Belt: regen, max res, fire dot multi, life, attributes и удобный sustain",
                "Jewels/Flasks: ruby + armour фласки, jewels на burning damage, life regen и общую стабильность",
            ),
            gear_progression=(
                "Entry: сначала cap резистов, max fire res и sustain под сам RF, потом уже думай про luxury урон",
                "Midgame: подтяни sceptre/shield, regen и body armour, чтобы T16 и неприятные моды не ломали sustain",
                "Endgame: дорогой fire dot weapon, сильный shield, jewels и +max fire res уже под максимально спокойный эндгейм",
            ),
            avoid_warnings=(
                "Map mods: аккуратно с reduced recovery, no-regen-подобными модами и любым сценарием, который ломает sustain",
                "Content: билд не про самый резкий boss burst, так что не жди мгновенного взрыва жирных целей без вложений",
                "Сырой этап: пока max fire res и regen не собраны, не лезь в контент, где тебя долго держат в ground degens",
            ),
            planner_url=_search_url("site:poe-vault.com Righteous Fire Chieftain passive skill tree gems links"),
            guide_url=_search_url("site:poe-vault.com Righteous Fire Chieftain build guide"),
            tree_url=_search_url("site:poe-vault.com Righteous Fire Chieftain passive skill tree gems links"),
            atlas_url="https://www.poe-vault.com/guides/atlas-passive-skill-tree-strategies",
            source_note="Для Righteous Fire пока даю рабочие внешние entry points: guide и tree через стабильный поиск по PoE Vault, плюс визуальный Atlas guide.",
        ),
        BuildRecommendation(
            title="Spark Stormweaver",
            game="poe2",
            archetype="allround",
            goals=("league_start", "currency_farm", "comfortable_progress"),
            class_name="Sorceress / Stormweaver",
            budget_tier="starter",
            playstyles=("allround", "speed"),
            core_skill="Spark",
            budget_estimate="старт 0-3 div, уверенный early-mid 5-15 div, хороший эндгейм 25+ div",
            strengths=("лёгкий вход", "хороший clear", "приятный scaling в early economy"),
            cautions=("нужны нормальные каст-статы", "позиционка важна на боссах"),
            gear_focus=("cast speed", "lightning damage", "mana sustain"),
            buy_priority=("wand/focus с spell/lightning/cast speed", "амулет/кольца на mana sustain", "body/helm под life or ES + res"),
            stat_targets=("достаточно mana sustain для спама Spark", "cast speed без ощущения вязкости", "резисты и базовая выживаемость не в минус"),
            tree_focus=("lightning/cast nodes", "mana efficiency или sustain", "ранние defensive узлы по пути"),
            atlas_focus=("быстрый clear и возврат к следующей пачке", "контент, где ценится coverage", "early economy farming"),
            farm_mechanics=("Breach", "Ritual", "Strongboxes", "Expedition"),
            pantheon_or_defense_notes=("В POE2 вместо пантеона держи фокус на mana sustain", "не жертвуй защитой ради одного только урона"),
            endgame_slot_checklist=(
                "Weapon/Focus: lightning caster base с spell damage, cast speed, +levels или crit/shock scaling",
                "Body: life или ES chest, где не теряется защита ради чистого DPS",
                "Helm/Gloves/Boots: cast comfort, резисты, move speed, defensive suffixes",
                "Rings/Amulet/Belt: mana sustain, cast stats, life/ES, атрибуты и сопротивления",
                "Charm/Jewels: jewels на lightning/cast/shock value, utility charms под sustain и defense",
                "Flasks/Utility: ресурсный и defensive слой, который не ломает темп спама Spark",
            ),
            endgame_goals=("стабильный POE2 mapping", "currency rotations через плотные механики", "универсальный endgame без тяжёлого микроменеджмента"),
            endgame_milestones=("cast speed и sustain уже не тормозят темп карты", "билд без боли держит плотные паки и редких", "weapon/focus достаточно сильные, чтобы не буксовать на tanky encounters"),
            chase_upgrades=("топовый wand/focus под lightning", "дорогие crit/shock value слоты", "luxury jewels и редкие слоты на кастерский ceiling"),
            first_upgrades=("cast speed", "mana sustain", "уровни основного камня"),
            comfort_upgrades=("быстрый cast feel", "удобный movement setup", "качество life/mana flask слоя"),
            damage_upgrades=("lightning scaling", "crit / shock value", "лучший weapon/focus"),
            defense_fixes=("energy shield или life слой", "резисты", "позиционная выживаемость"),
            alternative_hint="Если хочется такой же стартовой надёжности, но спокойнее по механике, рядом стоит Minion Infernalist.",
            summary="Очень крепкий POE2-старт, если нужен универсальный caster для раннего фарма.",
            market_targets=(
                "Wand: spell damage, lightning damage to spells, cast speed, +spell or lightning levels",
                "Focus: cast speed, crit for spells or mana sustain, resist suffixes, defensive base",
                "Rings/Amulet: mana regen, mana on kill or sustain, cast speed, lightning scaling",
                "Body/Helm/Boots: life or ES, resistances, movement speed, free suffixes for fixing stats",
            ),
            gear_sheet=(
                "Weapon: caster wand with spell damage, lightning to spells, cast speed, +spell or lightning levels",
                "Focus: cast speed, spell crit or sustain, life/ES leaning base, resist suffixes to keep gearing flexible",
                "Helmet: life or ES, resistances, optionally offensive suffix if sustain is already solved",
                "Body: defensive ES/life chest first; upgrade to stronger endgame piece after cast feel and mana are clean",
                "Gloves/Boots: move speed, cast feel, resistances, life/ES; do not leave yourself glassy for tiny DPS gains",
                "Rings/Amulet/Belt: mana sustain, cast speed, lightning scaling, attributes and resist coverage",
                "Jewels/Charms: cast speed, lightning damage, crit/shock scaling, and utility that keeps uptime smooth",
            ),
            gear_progression=(
                "Entry: wand/focus с нормальным cast feel, mana sustain и живой defensive body под карты",
                "Midgame: подтяни +levels, cast speed, crit/shock scaling и перестань чинить билд каждым новым кольцом",
                "Endgame: уходи в дорогой planner-state с сильным weapon/focus, плотным ES/life слоем и jewel-слотами под ceiling dps",
            ),
            avoid_warnings=(
                "Map mods: no regen / harsh mana sustain mods и тяжёлые lightning-res stacks ощущаются плохо",
                "Content: если билд ещё сырой, неприятны very tight boss arenas без места для Spark uptime",
                "Сырой этап: не жертвуй защитой ради одного cast speed — без нормального sustain билд быстро становится стеклянным",
            ),
            planner_url="https://maxroll.gg/poe2/planner/xpedn0v4",
            guide_url="https://mobalytics.gg/poe-2/builds/animeprincess-spark-stormweaver",
            tree_url="https://maxroll.gg/poe2/planner/xpedn0v4",
            atlas_url="https://mobalytics.gg/poe-2/builds/animeprincess-spark-stormweaver",
            source_note="Guide теперь ведёт на стабильный endgame-разбор, а tree — прямо в planner с визуальным пассивным деревом и gear layout.",
        ),
        BuildRecommendation(
            title="Ice Strike Monk",
            game="poe2",
            archetype="mapper",
            goals=("currency_farm", "comfortable_progress"),
            class_name="Monk",
            budget_tier="mid",
            playstyles=("speed", "allround"),
            core_skill="Ice Strike",
            budget_estimate="старт 3-8 div, приятный midgame 15-30 div, хороший эндгейм 40+ div",
            strengths=("высокий темп", "приятный melee clear", "хороший feel на картах"),
            cautions=("более требователен к оружию", "ошибки позиционки наказывают"),
            gear_focus=("weapon DPS", "attack speed", "cold scaling"),
            buy_priority=("staff/оружие с сильным base DPS", "attack speed на перчатках/кольцах где доступно", "слоты с evasion/ES и резистами"),
            stat_targets=("оружие не должно отставать по акту", "комфортный attack speed", "достаточно защиты для melee входов"),
            tree_focus=("cold / melee / attack speed", "крит или penetration по версии билда", "defensive узлы по пути к endgame"),
            atlas_focus=("быстрые карты, где можно держать темп", "контент с плотными пачками", "механики, где взрывы clear ощущаются лучше"),
            farm_mechanics=("Breach", "Ritual", "Delirium-подобный плотный контент, если тянет", "Strongboxes"),
            pantheon_or_defense_notes=("В POE2 ключ — не проседать по защите ради оружия", "для melee чувствуется каждая дырка по defense"),
            endgame_slot_checklist=(
                "Weapon: endgame staff/оружие с сильным base DPS, attack speed и cold-friendly scaling",
                "Body: плотная база под melee survive — life/ES/evasion без жадности в урон",
                "Helm/Gloves/Boots: attack speed, move speed, defensive rolls и резисты",
                "Rings/Amulet/Belt: cold/offense stats, sustain, атрибуты, life/defense",
                "Charm/Jewels: jewels на melee/cold/crit, defensive utility charms под close-range игру",
                "Utility: всё, что делает вход в pack безопаснее — sustain, movement, recovery",
            ),
            endgame_goals=("агрессивный endgame mapping", "фарм плотных пачек", "быстрый цикл карт ради валюты"),
            endgame_milestones=("оружие уже не тормозит clear в high-tier картах", "melee survive-слой держит плотные паки", "attack speed и sustain позволяют не рвать ротацию"),
            chase_upgrades=("топовое endgame-оружие", "дорогие offensive аксессуары под cold/crit", "luxury defensive pieces, чтобы билд не был стеклянным"),
            first_upgrades=("оружие с нормальным DPS", "attack speed", "связка под clear"),
            comfort_upgrades=("качество мувмента", "ресурс на sustain", "упрощение clear-loop"),
            damage_upgrades=("лучшее оружие", "cold scaling", "crit / penetration где доступно"),
            defense_fixes=("evade / armour слои", "life", "не проседать по резистам"),
            alternative_hint="Если хочется меньше риска и больше контроля по темпу, смотри Spark Stormweaver или Titan Slam Warrior.",
            summary="Если хочется динамичного POE2-мели билда для темпового фарма и маппинга.",
            market_targets=(
                "Weapon: staff/оружие с высоким DPS, attack speed, cold scaling и clean offensive suffixes",
                "Rings/Amulet: cold damage, crit/penetration по версии, sustain, attributes и life/defense",
                "Body/Helm: defensive bases с life/ES/evasion, не проваливаясь по резистам ради голого урона",
                "Boots/Gloves: move speed, attack speed, defensive rolls, resist coverage и удобный melee feel",
            ),
            gear_sheet=(
                "Weapon: сильный endgame staff/weapon с DPS и attack speed — ключ к тому, чтобы билд не ощущался ватным",
                "Helmet: life/ES/evasion, cold-friendly utility и резисты без жадности в glass-cannon",
                "Body: защитная база под melee survive, а не просто ещё один слот в урон",
                "Gloves/Boots: attack speed, move speed, life/ES, defensive suffixes и резисты",
                "Rings/Amulet/Belt: cold offense, sustain, life/defense, attributes и clean suffix management",
                "Jewels/Charms: melee/cold/crit value плюс defensive utility charms под вход в pack",
            ),
            gear_progression=(
                "Entry: сначала weapon с нормальным DPS, базовая защита и понятная melee-связка без дыр по резистам",
                "Midgame: подними attack speed, cold scaling и defensive слой, чтобы билд не разваливался в плотных картах",
                "Endgame: дорогой staff, offensive jewellery и luxury defensive pieces уже под быстрый high-tier mapping",
            ),
            avoid_warnings=(
                "Map mods: аккуратно с модами, которые убивают sustain, скорость удара или делают melee-вход слишком рискованным",
                "Content: билд любит плотные карты, но до сборки защиты не лучший выбор для слишком злых stationary boss arenas",
                "Сырой этап: пока weapon и defense не дособраны, не форси слишком жадный delirious/плотный pack content",
            ),
            planner_url=_search_url("site:maxroll.gg/poe2 Ice Strike Monk planner"),
            guide_url=_search_url("site:mobalytics.gg/poe-2 Ice Strike Monk build guide"),
            tree_url=_search_url("site:mobalytics.gg/poe-2 Ice Strike Monk passive tree planner"),
            atlas_url=_search_url("site:maxroll.gg/poe2 atlas guide"),
            source_note="Для Ice Strike Monk пока даю рабочие entry points через стабильный поиск по Mobalytics и Maxroll: guide, tree/planner и визуальный atlas reference.",
        ),
        BuildRecommendation(
            title="Minion Infernalist",
            game="poe2",
            archetype="safe",
            goals=("league_start", "comfortable_progress"),
            class_name="Witch / Infernalist",
            budget_tier="starter",
            playstyles=("safe", "allround"),
            core_skill="Minions",
            budget_estimate="старт 0-4 div, комфортный midgame 8-18 div, плотный эндгейм 30+ div",
            strengths=("спокойный стиль игры", "меньше требований к механике", "хороший старт"),
            cautions=("темп ниже, чем у топ-clear билдов", "нужен контроль summon setup"),
            gear_focus=("minion levels", "spirit / mana economy", "defensive layers"),
            buy_priority=("уровни миньон-камней", "spirit economy", "щит/фокус с защитой и utility"),
            stat_targets=("достаточный spirit или ресурс под summon setup", "миньоны не должны отставать по уровням", "твоя база по защите должна быть скучно-стабильной"),
            tree_focus=("minion offense", "spirit / summon utility", "defensive pathing без жадности"),
            atlas_focus=("контент, который не заставляет постоянно спринтовать", "стабильный фарм с безопасным позиционированием", "постепенное раскручивание экономики"),
            farm_mechanics=("Expedition", "Blight", "Ritual", "Harbinger"),
            pantheon_or_defense_notes=("В POE2 здесь выигрывает спокойный темп", "сначала комфорт summon-loop, потом жадность в урон"),
            endgame_slot_checklist=(
                "Weapon/Focus: minion levels, spirit utility, defensive base вместо стеклянного оффенса",
                "Body: life/ES chest, который держит тебя живым, пока миньоны делают работу",
                "Helm/Gloves/Boots: summon utility, резисты, move speed, стабильная защита",
                "Rings/Amulet/Belt: spirit/mana economy, minion offense, life/defense и атрибуты",
                "Charm/Jewels: minion jewels, defensive utility, sustain для длинных боёв",
                "Utility: комфорт summon-loop и recovery важнее, чем жадность в чистый DPS",
            ),
            endgame_goals=("безопасный endgame progression", "спокойный фарм плотного контента", "длинные игровые сессии без утомляющего микроменеджмента"),
            endgame_milestones=("миньоны не разваливаются на плотных encounters", "spirit/setup хватает без постоянной нехватки ресурса", "твоя защита не проседает в high-tier контенте"),
            chase_upgrades=("дорогие уровни minion gems", "luxury spirit / minion jewels", "эндгейм-щит/фокус под потолок урона и защиты"),
            first_upgrades=("уровни minion-камней", "spirit economy", "база по защите"),
            comfort_upgrades=("удобный summon loop", "ресурс под поддерживающие кнопки", "плавность clear"),
            damage_upgrades=("minion levels", "миньон-урон", "лучший support setup"),
            defense_fixes=("щит/броня по ситуации", "life or ES", "резисты и recovery"),
            alternative_hint="Если хочется активнее и быстрее чистить карты, но всё ещё универсально, посмотри Spark Stormweaver.",
            summary="Хороший выбор, если хочется безопасного старта и меньше давления по механике.",
            market_targets=(
                "Wand/Focus: +minion levels, spirit utility, minion damage, defensive suffixes",
                "Helmet: minion or spirit-supporting base, life or ES, resistances, ideally one offensive suffix",
                "Rings/Amulet/Belt: spirit or mana economy, minion stats, life/ES, capped resistances",
                "Boots/Gloves/Body: survivability first — life/ES, resistances, move speed, then minion utility",
            ),
            gear_sheet=(
                "Weapon/Focus: +minion levels, spirit utility, minion damage, but keep enough defensive suffixes to not fall over yourself",
                "Helmet: minion-supporting or spirit-friendly slot with life/ES, resistances, one offensive line if free",
                "Body: defensive chest first; this build wants you alive while minions do the heavy lifting",
                "Gloves/Boots: resistances, move speed, life/ES, then minion utility or convenience mods",
                "Rings/Amulet/Belt: spirit economy, minion stats, life/ES, attributes and clean res coverage",
                "Jewels/Charms: minion offense, spirit comfort, utility that smooths long boss fights and crowded maps",
            ),
            gear_progression=(
                "Entry: реши spirit/setup, базовую защиту и уровни миньонов — без этого билд просто ощущается недособранным",
                "Midgame: подними quality summon-loop, minion offense и сделай свою базу по life/ES скучно-стабильной",
                "Endgame: дорогие +minion levels, сильные jewels и дорогой focus/щит уже под потолок урона и комфорт long fights",
            ),
            avoid_warnings=(
                "Map mods: жёсткие anti-recovery / anti-minion uptime сочетания и хаотичный arena-pressure могут быть неприятны",
                "Content: очень быстрый timed clear билд чувствует хуже, чем стабильные плотные encounter'ы",
                "Сырой этап: пока не закрыт spirit/setup и базовая защита, не лезь в слишком плотный high-tier burst-контент",
            ),
            planner_url="https://maxroll.gg/poe2/planner/fjuim01r",
            guide_url="https://mobalytics.gg/poe-2/builds/life-stacker-infernalist-kripp",
            tree_url="https://maxroll.gg/poe2/planner/fjuim01r",
            atlas_url="https://mobalytics.gg/poe-2/builds/life-stacker-infernalist-kripp",
            source_note="Guide ведёт на стабильный endgame build page, а tree — в planner, где уже можно глазами смотреть дерево и slot layout.",
        ),
        BuildRecommendation(
            title="Gas Arrow Huntress",
            game="poe2",
            archetype="boss",
            goals=("boss_kill", "currency_farm"),
            class_name="Huntress",
            budget_tier="mid",
            playstyles=("boss", "allround"),
            core_skill="Gas Arrow",
            budget_estimate="старт 4-10 div, рабочий midgame 15-35 div, сильный эндгейм 50+ div",
            strengths=("сильный single target", "хороший scaling", "гибкость под контент"),
            cautions=("нужен аккуратный setup", "не самый тупо-прямой геймплей"),
            gear_focus=("bow DPS", "chaos / poison style scaling", "attack uptime"),
            buy_priority=("лук с сильным базовым уроном", "колчан/амулет на chaos/poison scaling или attack quality", "слоты под стабильную защиту и ресурс"),
            stat_targets=("лук нельзя запускать", "attack uptime и feel в ротации", "защита не должна разваливаться, пока ты ставишь урон"),
            tree_focus=("bow + chaos/poison или fire interaction по версии", "single-target scaling", "defensive pathing без жадности"),
            atlas_focus=("контент, где важен single target и reward per encounter", "меньше упора в тупой blitz", "где можно разыграть сильный урон"),
            farm_mechanics=("Boss rushing", "Essence", "Expedition", "Ritual"),
            pantheon_or_defense_notes=("В POE2 следи за тем, чтобы не собрать только урон", "для Huntress позиционка и sustain ощущаются очень сильно"),
            endgame_slot_checklist=(
                "Weapon: сильный bow под chaos/poison или основную endgame-версию билда",
                "Quiver: attack quality, single-target value, chaos/poison synergy где доступно",
                "Body: защита + удобство ротации, а не только голый DPS",
                "Helm/Gloves/Boots: move speed, attack feel, defense и резисты",
                "Rings/Amulet/Belt: offensive scaling, sustain, life/defense и важные атрибуты",
                "Charm/Jewels: jewels под single target / uptime, utility под позиционную игру и выживаемость",
            ),
            endgame_goals=("boss rushing", "фарм жирных точечных encounter'ов", "смешанный currency + boss value контур"),
            endgame_milestones=("лук уже держит single target без долгих простоев", "ротация не разваливается на живых боссах", "защита не падает в ноль, пока билд раскрывает урон"),
            chase_upgrades=("топовый bow под chaos/poison версию", "дорогой quiver/amulet под ceiling single target", "luxury jewels под боссинг и smooth uptime"),
            first_upgrades=("лук с хорошим base DPS", "attack uptime", "ядро под single target"),
            comfort_upgrades=("speed/feel в ротации", "ресурс на sustain", "чистка packs без просадки"),
            damage_upgrades=("chaos / poison scaling", "лучший bow", "single-target multipliers"),
            defense_fixes=("позиционная защита", "life", "не проседать по элементальным резистам"),
            alternative_hint="Если хочется пожирнее и прямолинейнее под жирные цели, рядом Titan Slam Warrior.",
            summary="Подходит, если хочется уже не только фармить, но и уверенно давить более жирные цели.",
            market_targets=(
                "Bow: высокий base DPS, chaos/poison-friendly scaling, attack quality и clean suffix space",
                "Quiver: single-target value, attack speed, chaos/poison synergy и удобный sustain",
                "Amulet/Rings: offensive scaling под ядро билда, life/defense, attributes и резисты",
                "Boots/Gloves/Body: move speed, defensive layer, attack feel и достаточный ресурс под ротацию",
            ),
            gear_sheet=(
                "Weapon: bow, который реально двигает single-target ceiling, а не просто даёт формальный урон на бумаге",
                "Quiver: attack quality, single-target scaling, chaos/poison-friendly affixes и sustain comfort",
                "Helmet/Body: защита и feel ротации, не меняй их на чистый DPS слишком рано",
                "Gloves/Boots: move speed, attack speed/feel, life/defense и чистые резисты",
                "Rings/Amulet/Belt: offensive scaling, sustain, life, attributes и defensive suffixes",
                "Jewels/Charms: single-target jewels и utility charms под позиционную игру и long boss uptime",
            ),
            gear_progression=(
                "Entry: собери bow с нормальным DPS, базовую защиту и attack uptime, чтобы билд не ощущался рваным",
                "Midgame: подними single-target ядро, quiver и sustain, затем доделай defensive слой под живые боссы",
                "Endgame: дорогой bow, сильный quiver/amulet и luxury jewels уже под boss rush и жирный encounter farming",
            ),
            avoid_warnings=(
                "Map mods: будь аккуратен с модами, которые ломают sustain, attack uptime или делают позиционную игру токсичной",
                "Content: без хорошего bow и защиты билд может неприятно ощущаться в самых злых close-pressure encounters",
                "Сырой этап: пока не собран стабильный single-target и defense, не жми слишком агрессивный boss rush в high-tier",
            ),
            planner_url=_search_url("site:maxroll.gg/poe2 Gas Arrow Huntress planner"),
            guide_url=_search_url("site:mobalytics.gg/poe-2 Gas Arrow Huntress build guide"),
            tree_url=_search_url("site:mobalytics.gg/poe-2 Gas Arrow Huntress passive tree planner"),
            atlas_url=_search_url("site:maxroll.gg/poe2 atlas guide"),
            source_note="Для Gas Arrow Huntress пока даю рабочие entry points через стабильный поиск по Mobalytics и Maxroll: guide, tree/planner и визуальный atlas reference.",
        ),
        BuildRecommendation(
            title="Titan Slam Warrior",
            game="poe2",
            archetype="tank",
            goals=("boss_kill", "comfortable_progress"),
            class_name="Warrior / Titan",
            budget_tier="mid",
            playstyles=("safe", "boss"),
            core_skill="Slam skills",
            budget_estimate="старт 3-8 div, midgame 15-30 div, сильный эндгейм 40+ div",
            strengths=("живучесть", "мощные удары по жирным целям", "понятный progression path"),
            cautions=("темп ниже, чем у быстрых билдов", "хочет нормальное оружие"),
            gear_focus=("weapon physical DPS", "armour", "stun / heavy hit scaling"),
            buy_priority=("двурук/оружие с высоким physical DPS", "броня и life на больших слотах", "перчатки/амулет под damage + sustain"),
            stat_targets=("оружие всегда держать свежим", "достаточный armour/life слой", "не проседать по attack feel"),
            tree_focus=("melee physical / slam scaling", "stun / heavy hit synergy", "защитные узлы рядом с Warrior"),
            atlas_focus=("контент, где важна плотность и жирность целей", "спокойный прогресс в картах", "reward per tough encounter"),
            farm_mechanics=("Expedition", "Essence", "Boss farming", "Strongboxes"),
            pantheon_or_defense_notes=("В POE2 здесь сила в том, чтобы не быть стеклянным", "сначала оружие и броня, потом роскошь"),
            endgame_slot_checklist=(
                "Weapon: топовый physical two-hander/weapon base, который реально двигает slam ceiling",
                "Body: armour-heavy chest с life и endgame defensive value",
                "Helm/Gloves/Boots: armour, life, move speed, attack comfort и нужные резисты",
                "Rings/Amulet/Belt: physical offense, sustain, attributes, life и defensive suffixes",
                "Charm/Jewels: heavy-hit / melee jewels, defensive utility под slow melee-endgame",
                "Utility: recovery и anti-one-shot слой обязательны, иначе билд теряет смысл своей жирности",
            ),
            endgame_goals=("жирный endgame progression", "bossing и tough encounters", "спокойный high-tier mapping без стеклянности"),
            endgame_milestones=("оружие и slam-ядро уже уверенно ломают high-tier rares и боссов", "броня/life слой не проседает под реальным endgame уроном", "ротация стала достаточно быстрой, чтобы билд не ощущался вязким"),
            chase_upgrades=("топовое physical weapon", "luxury armour pieces под cap defenses", "дорогие jewels и аксессуары под massive hit ceiling"),
            first_upgrades=("оружие", "armour база", "основная slam-связка"),
            comfort_upgrades=("ускорение ротации", "ресурс на sustain", "качество передвижения"),
            damage_upgrades=("weapon DPS", "physical scaling", "heavy hit multipliers"),
            defense_fixes=("armour", "life", "анти-ваншот слои"),
            alternative_hint="Если хочется больше темпа и меньше тяжёлого melee-feel, попробуй Ice Strike Monk или Gas Arrow Huntress.",
            summary="Крепкий путь, если нужен плотный персонаж для более спокойного, но уверенного прогресса.",
            market_targets=(
                "Weapon: высокий physical DPS, attack feel и clean suffixes под later crafting",
                "Body: armour-heavy defensive chest с life и endgame-стойкостью",
                "Amulet/Rings/Belt: physical offense, sustain, attributes, life и defensive suffixes",
                "Boots/Gloves/Helm: armour, life, move speed, attack comfort и чистые резисты",
            ),
            gear_sheet=(
                "Weapon: physical two-hander/weapon, который действительно поднимает slam ceiling и не делает ротацию вязкой",
                "Helmet: armour, life, резисты и utility под slow melee-endgame, а не стеклянный DPS",
                "Body: большой defensive chest под armour/life, потому что билд выигрывает от возможности стоять в контенте",
                "Gloves/Boots: attack comfort, move speed, life, armour и чистые defensive suffixes",
                "Rings/Amulet/Belt: physical offense, sustain, life, attributes и анти-ваншот utility",
                "Jewels/Charms: heavy-hit / melee value плюс defensive utility под длинные и жирные encounter'ы",
            ),
            gear_progression=(
                "Entry: сначала weapon, armour база и slam-ядро, чтобы билд вообще почувствовался как Titan, а не как slow melee без урона",
                "Midgame: подними weapon DPS, life/armour и ротацию, чтобы high-tier progress не ощущался вязким",
                "Endgame: дорогой physical weapon, luxury armour pieces и дорогие jewels уже под bossing и плотный эндгейм",
            ),
            avoid_warnings=(
                "Map mods: аккуратно с модами, которые режут sustain, скорость ротации или делают тяжелые удары слишком наказуемыми",
                "Content: если weapon слабый, билд начинает проигрывать темпу и feel в контенте, где нужно быстро сносить экраны",
                "Сырой этап: пока нет нормального оружия и defensive слоя, не жми слишком агрессивный high-tier bossing подряд",
            ),
            planner_url=_search_url("site:maxroll.gg/poe2 Titan Slam Warrior planner"),
            guide_url=_search_url("site:mobalytics.gg/poe-2 Titan Slam Warrior build guide"),
            tree_url=_search_url("site:mobalytics.gg/poe-2 Titan Slam Warrior passive tree planner"),
            atlas_url=_search_url("site:maxroll.gg/poe2 atlas guide"),
            source_note="Для Titan Slam Warrior пока даю рабочие entry points через стабильный поиск по Mobalytics и Maxroll: guide, tree/planner и визуальный atlas reference.",
        ),
    )

    def recommend(
        self,
        *,
        game: str,
        goal: str,
        budget_tier: str,
        playstyle: str,
        limit: int = 3,
    ) -> list[BuildRecommendation]:
        scored: list[tuple[int, BuildRecommendation]] = []
        for build in self._catalog:
            if build.game != game:
                continue

            score = 0
            if goal in build.goals:
                score += 5
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

    @staticmethod
    def goal_label(goal: str) -> str:
        return {
            "league_start": "старт лиги",
            "currency_farm": "фарм валюты",
            "comfortable_progress": "комфортный прогресс",
            "boss_kill": "убийство боссов",
        }.get(goal, goal)
