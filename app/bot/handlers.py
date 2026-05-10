from __future__ import annotations

from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.bot.dependencies import session_scope
from app.bot.keyboards import (
    add_entry_keyboard,
    duplicate_resolution_keyboard,
    game_keyboard,
    league_keyboard,
    search_results_keyboard,
    templates_keyboard,
    threshold_currency_keyboard,
    tracking_actions_keyboard,
)
from app.models.league import League
from app.services.economy import EconomyService
from app.services.item_catalog import ItemCatalogService
from app.services.leagues import LeagueService
from app.services.stats import StatsService
from app.services.templates import TemplateService
from app.services.tracking import TrackingService
from app.services.users import UserService

router = Router()


class AddTrackingStates(StatesGroup):
    choosing_mode = State()
    choosing_game = State()
    choosing_league = State()
    entering_search = State()
    choosing_currency = State()
    entering_trade_url = State()
    entering_trade_name = State()
    entering_threshold = State()
    resolving_duplicate = State()


async def ensure_user(session, telegram_id: int, username: str | None):
    return await UserService(session).get_or_create(telegram_id=telegram_id, username=username)


def format_decimal(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def build_tracking_lines(item) -> list[str]:
    league_name = item.league.name if item.league else "Без лиги"
    game_label = "POE 2" if item.league and item.league.realm == "poe2" else "POE 1"
    lines = [f"#{item.id} - {item.item_name}", f"Игра: {game_label}", f"Лига: {league_name}"]
    if item.target_price is not None:
        lines.append(f"Порог: {format_decimal(Decimal(item.target_price))} {item.target_currency}")
    if item.trade_url:
        lines.append("Источник: trade URL")
    return lines


def build_tracking_list_text(items: list) -> str:
    lines = [f"Активный трекинг: {len(items)}"]
    for item in items:
        lines.append("\n".join(build_tracking_lines(item)))
    return "\n\n".join(lines)


def build_economy_text(summaries: list) -> str:
    lines = ["Экономика:"]
    for summary in summaries:
        game_label = "POE 2" if summary.game == "poe2" else "POE 1"
        lines.append("")
        lines.append(f"{game_label} / {summary.league_name}")

        snapshot = summary.exchange_snapshot
        if snapshot:
            rates = snapshot.rates
            lines.append(f"Источник: {snapshot.source}")
            if "div" in rates:
                lines.append(f"1 div ~= {format_decimal(rates['div'])} chaos")
            if "ex" in rates:
                lines.append(f"1 ex ~= {format_decimal(rates['ex'])} chaos")
            if "div" in rates and "ex" in rates and rates["ex"] != 0:
                lines.append(f"1 div ~= {format_decimal(rates['div'] / rates['ex'])} ex")
        else:
            lines.append("Курсы сейчас недоступны.")

        if summary.active_watchers:
            lines.append(f"Активные currency alerts: {len(summary.active_watchers)}")
            for watcher in summary.active_watchers[:5]:
                lines.append(
                    f"- #{watcher.tracked_item_id} {watcher.item_name} >= "
                    f"{format_decimal(watcher.target_price)} {watcher.target_currency}"
                )
            if len(summary.active_watchers) > 5:
                lines.append(f"- ... еще {len(summary.active_watchers) - 5}")
        else:
            lines.append("Активных currency alerts пока нет.")

    lines.append("")
    lines.append("Подсказка: currency alert срабатывает, когда рыночная цена достигает или превышает твой порог.")
    return "\n".join(lines)


def infer_trade_context(trade_url: str) -> tuple[str | None, str | None]:
    parsed = urlparse(trade_url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) >= 4 and segments[0] == "trade" and segments[1] == "search":
        return "poe1", segments[2]
    if len(segments) >= 5 and segments[0] == "trade2" and segments[1] == "search":
        realm = segments[2]
        league_name = segments[3]
        return ("poe2" if realm == "poe2" else realm, league_name)
    return None, None


def normalize_threshold_currency(raw_value: str) -> str:
    mapping = {
        "ex": "ex",
        "exa": "ex",
        "exalted": "ex",
        "chaos": "chaos",
        "c": "chaos",
        "div": "div",
        "divine": "div",
    }
    normalized = raw_value.strip().lower()
    if normalized not in mapping:
        raise InvalidOperation
    return mapping[normalized]


def parse_threshold_input(raw_value: str) -> tuple[Decimal, str]:
    normalized = raw_value.strip().lower().replace(",", ".")
    parts = normalized.split()
    if not parts:
        raise InvalidOperation

    amount = Decimal(parts[0])
    currency = "ex" if len(parts) == 1 else normalize_threshold_currency(parts[1])
    return amount, currency


async def delete_if_possible(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass


async def show_wizard_message(
    *,
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup=None,
) -> None:
    data = await state.get_data()
    wizard_message_id = data.get("wizard_message_id")
    if wizard_message_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=wizard_message_id,
                text=text,
                reply_markup=reply_markup,
            )
            return
        except Exception:
            pass

    sent = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
    await state.update_data(wizard_message_id=sent.message_id, wizard_chat_id=chat_id)


async def finish_wizard(
    *,
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup=None,
) -> None:
    await show_wizard_message(state=state, bot=bot, chat_id=chat_id, text=text, reply_markup=reply_markup)
    await state.clear()


async def begin_add_wizard(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddTrackingStates.choosing_mode)
    await show_wizard_message(
        state=state,
        bot=message.bot,
        chat_id=message.chat.id,
        text=(
            "Добавим новый трекинг.\n\n"
            "Сначала выбери, что именно хочешь отслеживать."
        ),
        reply_markup=add_entry_keyboard(),
    )


async def render_duplicate_resolution(
    *,
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    items: list,
) -> None:
    lines = [
        "Я нашел похожие watcher'ы для этого предмета.",
        "Можно обновить один из них или создать новый отдельно.",
        "",
    ]
    for item in items:
        threshold = (
            f"{format_decimal(Decimal(item.target_price))} {item.target_currency}"
            if item.target_price is not None
            else "без порога"
        )
        lines.append(f"#{item.id} - {item.item_name} ({threshold})")

    await show_wizard_message(
        state=state,
        bot=bot,
        chat_id=chat_id,
        text="\n".join(lines),
        reply_markup=duplicate_resolution_keyboard(items),
    )


async def finalize_tracking_creation(
    *,
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    user_telegram_id: int,
    username: str | None,
    create_new: bool,
    existing_item_id: int | None = None,
) -> None:
    data = await state.get_data()
    async with session_scope() as session:
        user = await ensure_user(session, user_telegram_id, username)
        result = await TrackingService(session).add_item(
            user=user,
            item_name=data["item_name"],
            item_type=data.get("item_type", "item"),
            trade_url=data.get("trade_url"),
            target_price=Decimal(data["target_price"]) if data.get("target_price") is not None else None,
            target_currency=data.get("target_currency", "ex"),
            league_name=data.get("league_name"),
            game=data.get("game"),
            existing_item_id=existing_item_id,
            create_new=create_new,
        )

    item = result.item
    action_text = "Обновил" if result.action == "updated" else "Добавил"
    response_lines = [f"{action_text} трекинг #{item.id}: {item.item_name}"]
    if item.target_price is not None:
        response_lines.append(f"Порог: {format_decimal(Decimal(item.target_price))} {item.target_currency}")
    if item.trade_url:
        response_lines.append("Источник: trade URL")

    await finish_wizard(
        state=state,
        bot=bot,
        chat_id=chat_id,
        text="\n".join(response_lines),
        reply_markup=tracking_actions_keyboard([item]),
    )


@router.message(Command("start"))
async def start(message: Message) -> None:
    async with session_scope() as session:
        await ensure_user(session, message.from_user.id, message.from_user.username)

    await message.answer(
        "Привет! Я POE / POE2 ассистент для трекинга торговли, статистики и шаблонов.\n\n"
        "Быстрый старт:\n"
        "/add\n"
        "/list\n"
        "/templates\n\n"
        "Через /add можно выбрать игру, лигу, предмет и порог без ручного ввода длинной команды."
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "Команды:\n"
        "/add - открыть мастер добавления трекинга\n"
        "/add <название>\n"
        "/add <название> | <цена> [ex|chaos|div]\n"
        "/add <trade_url>\n"
        "/remove <id> - отключить трекинг\n"
        "/list - список активного трекинга\n"
        "/stats - статистика продаж\n"
        "/templates - готовые наборы\n"
        "/settings - текущие настройки MVP"
    )


@router.message(Command("add"))
async def add_tracking(message: Message, state: FSMContext) -> None:
    raw_text = message.text or ""
    payload = raw_text.removeprefix("/add").strip()
    if not payload:
        await begin_add_wizard(message, state)
        return

    trade_url = payload if payload.startswith("http") else None
    item_name = "Trade URL" if trade_url else payload
    target_price: Decimal | None = None
    target_currency = "ex"

    if trade_url:
        game, league_name = infer_trade_context(trade_url)
        await state.clear()
        await state.update_data(
            item_type="item",
            trade_url=trade_url,
            target_price=None,
            target_currency="ex",
            game=game,
            league_name=league_name,
        )
        await state.set_state(AddTrackingStates.entering_trade_name)
        await show_wizard_message(
            state=state,
            bot=message.bot,
            chat_id=message.chat.id,
            text=(
                "Ссылка получена.\n\n"
                "Теперь пришли короткое название трекера (например: Mageblood, TS Bow, Mirror Ring)."
            ),
        )
        return

    if "|" in payload and not trade_url:
        name_part, price_part = [part.strip() for part in payload.split("|", 1)]
        item_name = name_part
        try:
            target_price, target_currency = parse_threshold_input(price_part)
        except InvalidOperation:
            await message.answer(
                "Не понял порог цены. Пример:\n"
                "/add Divine Orb | 1\n"
                "/add Divine Orb | 150 chaos\n"
                "/add Divine Orb | 0.5 div"
            )
            return
    elif not trade_url:
        await message.answer(
            "Для команды в одну строку нужен порог цены.\n\n"
            "Примеры:\n"
            "/add Divine Orb | 1\n"
            "/add Divine Orb | 150 chaos\n"
            "/add Divine Orb | 0.5 div\n\n"
            "Либо используй просто /add — там мастер с выбором и поиском."
        )
        return

    async with session_scope() as session:
        user = await ensure_user(session, message.from_user.id, message.from_user.username)
        result = await TrackingService(session).add_item(
            user=user,
            item_name=item_name,
            trade_url=trade_url,
            target_price=target_price,
            target_currency=target_currency,
        )

    response_lines = [f"{'Обновил' if result.action == 'updated' else 'Добавил'} трекинг #{result.item.id}: {result.item.item_name}"]
    if target_price is not None:
        response_lines.append(f"Порог: {format_decimal(target_price)} {target_currency}")
    if trade_url:
        response_lines.append("Источник: trade URL")
    await message.answer("\n".join(response_lines), reply_markup=tracking_actions_keyboard([result.item]))


@router.callback_query(F.data == "add:mode:item")
async def add_mode_item(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddTrackingStates.choosing_game)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text="Выбери игру, для которой будем создавать watcher.",
        reply_markup=game_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "add:mode:trade_url")
async def add_mode_trade_url(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(item_type="item", trade_url=None)
    await state.set_state(AddTrackingStates.entering_trade_url)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text="Пришли trade URL отдельным сообщением. Я сохраню его как отдельный watcher.",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("add:game:"))
async def add_choose_game(callback: CallbackQuery, state: FSMContext) -> None:
    game = callback.data.rsplit(":", 1)[1]
    async with session_scope() as session:
        leagues = await LeagueService(session).list_selection_options(game)

    await state.update_data(game=game)
    await state.set_state(AddTrackingStates.choosing_league)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=(
            "Теперь выбери лигу.\n"
            "Актуальные лиги показываю выше стандартных, чтобы свежие варианты было проще выбрать."
        ),
        reply_markup=league_keyboard(leagues),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("add:league:"))
async def add_choose_league(callback: CallbackQuery, state: FSMContext) -> None:
    league_id = int(callback.data.rsplit(":", 1)[1])
    async with session_scope() as session:
        league = await session.get(League, league_id)

    if not league:
        await callback.answer("Не нашел эту лигу", show_alert=True)
        return

    await state.update_data(league_id=league.id, league_name=league.name, game=league.realm)
    await state.set_state(AddTrackingStates.entering_search)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=(
            f"Лига: {league.name}\n\n"
            "Теперь пришли часть названия предмета или валюты. "
            "Я покажу варианты и буду обновлять это сообщение, чтобы не засорять чат."
        ),
    )
    await callback.answer()


@router.message(AddTrackingStates.entering_search)
async def add_search_query(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    if not query:
        return

    async with session_scope() as session:
        results = await ItemCatalogService(session).search(query=query)

    await state.update_data(search_query=query, search_results=results)
    await state.set_state(AddTrackingStates.entering_search)
    await delete_if_possible(message)
    await show_wizard_message(
        state=state,
        bot=message.bot,
        chat_id=message.chat.id,
        text=f"Нашел варианты для: {query}\nВыбери готовый вариант или используй свой текст как есть.",
        reply_markup=search_results_keyboard(results, query),
    )


@router.callback_query(F.data.startswith("add:item:"))
async def add_choose_item(callback: CallbackQuery, state: FSMContext) -> None:
    token = callback.data.rsplit(":", 1)[1]
    data = await state.get_data()
    if token == "exact":
        item_name = data.get("search_query", "")
    else:
        results = data.get("search_results", [])
        index = int(token)
        if index >= len(results):
            await callback.answer("Этот вариант уже устарел, попробуй поиск еще раз", show_alert=True)
            return
        item_name = results[index]

    await state.update_data(item_name=item_name, item_type="item", trade_url=None)
    await state.set_state(AddTrackingStates.choosing_currency)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=(
            f"Предмет: {item_name}\n\n"
            "В какой валюте будем задавать порог?"
        ),
        reply_markup=threshold_currency_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("add:currency:"))
async def add_choose_threshold_currency(callback: CallbackQuery, state: FSMContext) -> None:
    target_currency = callback.data.rsplit(":", 1)[1]
    await state.update_data(target_currency=target_currency)
    await state.set_state(AddTrackingStates.entering_threshold)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=(
            f"Ок, порог будем хранить в {target_currency}.\n\n"
            "Теперь пришли только число. Например: 1, 150 или 0.5"
        ),
    )
    await callback.answer()


@router.message(AddTrackingStates.entering_threshold)
async def add_enter_threshold(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    try:
        amount = Decimal(value.replace(",", "."))
    except InvalidOperation:
        await message.answer("Не получилось разобрать число. Пример: 1, 150 или 0.5")
        return

    await delete_if_possible(message)
    await state.update_data(target_price=str(amount))
    data = await state.get_data()

    league_id = data.get("league_id")
    if not league_id:
        await finalize_tracking_creation(
            state=state,
            bot=message.bot,
            chat_id=message.chat.id,
            user_telegram_id=message.from_user.id,
            username=message.from_user.username,
            create_new=False,
        )
        return

    async with session_scope() as session:
        user = await ensure_user(session, message.from_user.id, message.from_user.username)
        similar_items = await TrackingService(session).find_similar_items(
            user=user,
            league_id=league_id,
            item_name=data["item_name"],
            trade_url=data.get("trade_url"),
        )

    if similar_items:
        await state.set_state(AddTrackingStates.resolving_duplicate)
        await render_duplicate_resolution(
            state=state,
            bot=message.bot,
            chat_id=message.chat.id,
            items=similar_items,
        )
        return

    await finalize_tracking_creation(
        state=state,
        bot=message.bot,
        chat_id=message.chat.id,
        user_telegram_id=message.from_user.id,
        username=message.from_user.username,
        create_new=False,
    )


@router.message(AddTrackingStates.entering_trade_url)
async def add_enter_trade_url(message: Message, state: FSMContext) -> None:
    trade_url = (message.text or "").strip()
    if not trade_url.startswith("http"):
        await message.answer("Жду полноценный URL, который начинается с http или https.")
        return

    await delete_if_possible(message)
    game, league_name = infer_trade_context(trade_url)
    await state.update_data(
        trade_url=trade_url,
        item_type="item",
        target_price=None,
        target_currency="ex",
        game=game,
        league_name=league_name,
    )
    await state.set_state(AddTrackingStates.entering_trade_name)
    await show_wizard_message(
        state=state,
        bot=message.bot,
        chat_id=message.chat.id,
        text=(
            "Ссылка принята.\n\n"
            "Теперь пришли название трекера (например: Mageblood)."
        ),
    )


@router.message(AddTrackingStates.entering_trade_name)
async def add_enter_trade_name(message: Message, state: FSMContext) -> None:
    item_name = (message.text or "").strip()
    if not item_name:
        await message.answer("Нужен текст названия. Например: Mageblood")
        return

    await delete_if_possible(message)
    await state.update_data(item_name=item_name, item_type="item")
    await state.set_state(AddTrackingStates.choosing_currency)
    await show_wizard_message(
        state=state,
        bot=message.bot,
        chat_id=message.chat.id,
        text=(
            f"Название: {item_name}\n\n"
            "В какой валюте задаем порог уведомления?"
        ),
        reply_markup=threshold_currency_keyboard(),
    )


@router.callback_query(F.data.startswith("add:resolve:update:"))
async def add_resolve_update(callback: CallbackQuery, state: FSMContext) -> None:
    tracked_item_id = int(callback.data.rsplit(":", 1)[1])
    await finalize_tracking_creation(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        user_telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        create_new=False,
        existing_item_id=tracked_item_id,
    )
    await callback.answer("Watcher обновлен")


@router.callback_query(F.data == "add:resolve:create")
async def add_resolve_create(callback: CallbackQuery, state: FSMContext) -> None:
    await finalize_tracking_creation(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        user_telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        create_new=True,
    )
    await callback.answer("Создал отдельный watcher")


@router.callback_query(F.data == "add:cancel")
async def add_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await finish_wizard(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text="Ок, отменил создание трекинга.",
    )
    await callback.answer("Отменено")


@router.callback_query(F.data == "add:back:game")
async def add_back_to_game(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddTrackingStates.choosing_game)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text="Выбери игру, для которой будем создавать watcher.",
        reply_markup=game_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "add:back:league")
async def add_back_to_league(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    game = data.get("game", "poe2")
    async with session_scope() as session:
        leagues = await LeagueService(session).list_selection_options(game)

    await state.set_state(AddTrackingStates.choosing_league)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text="Снова выбери лигу.",
        reply_markup=league_keyboard(leagues),
    )
    await callback.answer()


@router.callback_query(F.data == "add:back:item")
async def add_back_to_item(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    query = data.get("search_query", "")
    results = data.get("search_results", [])
    await state.set_state(AddTrackingStates.entering_search)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=f"Снова выбери вариант для: {query}",
        reply_markup=search_results_keyboard(results, query),
    )
    await callback.answer()


@router.message(Command("remove"))
async def remove_tracking(message: Message) -> None:
    payload = (message.text or "").removeprefix("/remove").strip()
    if not payload.isdigit():
        await message.answer("Укажи id трекинга. Пример: /remove 12")
        return

    async with session_scope() as session:
        user = await ensure_user(session, message.from_user.id, message.from_user.username)
        removed = await TrackingService(session).remove_item(user=user, tracked_item_id=int(payload))

    await message.answer("Трекинг отключен." if removed else "Не нашел такой активный трекинг.")


@router.callback_query(F.data.startswith("list:remove:"))
async def remove_tracking_from_list(callback: CallbackQuery) -> None:
    tracked_item_id = int(callback.data.rsplit(":", 1)[1])

    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        removed = await TrackingService(session).remove_item(user=user, tracked_item_id=tracked_item_id)
        items = await TrackingService(session).list_items(user)

    if removed:
        await callback.answer("Трекинг уже отключен или не найден", show_alert=True)
        return

    await callback.answer("Трекинг отключен")
    if not callback.message:
        return

    if not items:
        await callback.message.edit_text("Активного трекинга пока нет. Добавь предмет через /add.")
        return

    await callback.message.edit_text(
        build_tracking_list_text(items),
        reply_markup=tracking_actions_keyboard(items),
    )


@router.callback_query(F.data.startswith("list2:remove:"))
async def remove_tracking_from_list_v2(callback: CallbackQuery) -> None:
    tracked_item_id = int(callback.data.rsplit(":", 1)[1])

    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        removed = await TrackingService(session).remove_item(user=user, tracked_item_id=tracked_item_id)
        items = await TrackingService(session).list_items(user)

    if not removed:
        await callback.answer("Трекинг уже отключен или не найден", show_alert=True)
        return

    await callback.answer("Трекинг отключен")
    if not callback.message:
        return

    if not items:
        await callback.message.edit_text("Активного трекинга пока нет. Добавь предмет через /add.")
        return

    await callback.message.edit_text(
        build_tracking_list_text(items),
        reply_markup=tracking_actions_keyboard(items),
    )


@router.callback_query(F.data.startswith("tracking:remove:"))
async def remove_tracking_callback(callback: CallbackQuery) -> None:
    tracked_item_id = int(callback.data.rsplit(":", 1)[1])

    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        removed = await TrackingService(session).remove_item(user=user, tracked_item_id=tracked_item_id)

    if not removed:
        await callback.answer("Трекинг отключен")
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)
    else:
        await callback.answer("Трекинг уже отключен или не найден", show_alert=True)


@router.message(Command("list"))
async def list_tracking(message: Message) -> None:
    async with session_scope() as session:
        user = await ensure_user(session, message.from_user.id, message.from_user.username)
        items = await TrackingService(session).list_items(user)

    if not items:
        await message.answer("Активного трекинга пока нет. Добавь предмет через /add.")
        return

    lines = [f"Активный трекинг: {len(items)}"]
    for item in items:
        lines.append("\n".join(build_tracking_lines(item)))

    await message.answer(build_tracking_list_text(items), reply_markup=tracking_actions_keyboard(items))


@router.message(Command("stats"))
async def stats(message: Message) -> None:
    async with session_scope() as session:
        user = await ensure_user(session, message.from_user.id, message.from_user.username)
        summary = await StatsService(session).get_summary(user)

    await message.answer(
        "Статистика:\n"
        f"Продаж всего: {summary.total_sales}\n"
        f"Валюты всего: {format_decimal(summary.total_currency)}\n"
        f"Продаж сегодня: {summary.daily_sales}\n"
        f"Валюты сегодня: {format_decimal(summary.daily_currency)}"
    )


@router.message(Command("economy"))
async def economy(message: Message) -> None:
    async with session_scope() as session:
        user = await ensure_user(session, message.from_user.id, message.from_user.username)
        summaries = await EconomyService(session).get_user_economy_summary(user)

    await message.answer(build_economy_text(summaries))


@router.message(Command("templates"))
async def templates(message: Message) -> None:
    async with session_scope() as session:
        await ensure_user(session, message.from_user.id, message.from_user.username)
        template_groups = await TemplateService(session).list_public()

    if not template_groups:
        await message.answer("Шаблонов пока нет. Сначала нужно выполнить seed шаблонов.")
        return

    await message.answer(
        "Доступные шаблоны:\nВыбери набор, и я добавлю его в твой трекинг.",
        reply_markup=templates_keyboard(template_groups),
    )


@router.callback_query(F.data.startswith("template:"))
async def activate_template(callback: CallbackQuery) -> None:
    template_id = int(callback.data.split(":", 1)[1])

    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        result = await TemplateService(session).activate(user=user, template_group_id=template_id)

    if not result:
        await callback.answer("Шаблон не найден", show_alert=True)
        return

    await callback.message.answer(
        f"Шаблон {result.template_name} подключен.\n"
        f"Новых или реактивированных трекингов: {result.created_count}."
    )
    await callback.answer("Шаблон подключен")


@router.message(Command("settings"))
async def settings(message: Message) -> None:
    await message.answer("Настройки MVP: лига по умолчанию берется из DEFAULT_LEAGUE_NAME.")
