from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.dependencies import session_scope
from app.bot.keyboards import templates_keyboard, tracking_actions_keyboard
from app.services.stats import StatsService
from app.services.templates import TemplateService
from app.services.tracking import TrackingService
from app.services.users import UserService

router = Router()


async def ensure_user(session, telegram_id: int, username: str | None):
    return await UserService(session).get_or_create(telegram_id=telegram_id, username=username)


def format_decimal(value: Decimal) -> str:
    normalized = value.normalize() if value == value.to_integral() else value.normalize()
    return format(normalized, "f").rstrip("0").rstrip(".") or "0"


def build_tracking_lines(item) -> list[str]:
    league_name = item.league.name if item.league else "Без лиги"
    lines = [f"#{item.id} - {item.item_name}", f"Лига: {league_name}"]
    if item.target_price is not None:
        lines.append(f"Порог: {format_decimal(Decimal(item.target_price))}")
    if item.trade_url:
        lines.append("Источник: trade URL")
    return lines


@router.message(Command("start"))
async def start(message: Message) -> None:
    async with session_scope() as session:
        await ensure_user(session, message.from_user.id, message.from_user.username)

    await message.answer(
        "Привет! Я POE / POE2 ассистент для трекинга торговли, статистики и шаблонов.\n\n"
        "Быстрый старт:\n"
        "/add Divine Orb\n"
        "/list\n"
        "/templates\n\n"
        "Если захочешь посмотреть все команды, набери /help."
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "Команды:\n"
        "/add <название> - добавить предмет в трекинг\n"
        "/add <название> | <цена> - добавить предмет с порогом цены\n"
        "/add <trade_url> - добавить trade URL в трекинг\n"
        "/remove <id> - отключить трекинг\n"
        "/list - список активного трекинга\n"
        "/stats - статистика продаж\n"
        "/templates - готовые наборы\n"
        "/settings - текущие настройки MVP"
    )


@router.message(Command("add"))
async def add_tracking(message: Message) -> None:
    raw_text = message.text or ""
    payload = raw_text.removeprefix("/add").strip()
    if not payload:
        await message.answer(
            "Напиши предмет или trade URL после команды.\n\n"
            "Примеры:\n"
            "/add Divine Orb\n"
            "/add Divine Orb | 1\n"
            "/add https://..."
        )
        return

    trade_url = payload if payload.startswith("http") else None
    item_name = "Trade URL" if trade_url else payload
    target_price: Decimal | None = None

    if "|" in payload and not trade_url:
        name_part, price_part = [part.strip() for part in payload.split("|", 1)]
        item_name = name_part
        try:
            target_price = Decimal(price_part)
        except InvalidOperation:
            await message.answer("Порог цены должен быть числом. Пример: /add Divine Orb | 1")
            return

    async with session_scope() as session:
        user = await ensure_user(session, message.from_user.id, message.from_user.username)
        tracked_item = await TrackingService(session).add_item(
            user=user,
            item_name=item_name,
            trade_url=trade_url,
            target_price=target_price,
        )

    response_lines = [f"Добавил трекинг #{tracked_item.id}: {tracked_item.item_name}"]
    if target_price is not None:
        response_lines.append(f"Порог: {format_decimal(target_price)}")
    if trade_url:
        response_lines.append("Источник: trade URL")
    await message.answer("\n".join(response_lines), reply_markup=tracking_actions_keyboard([tracked_item]))


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


@router.callback_query(F.data.startswith("tracking:remove:"))
async def remove_tracking_callback(callback: CallbackQuery) -> None:
    tracked_item_id = int(callback.data.rsplit(":", 1)[1])

    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        removed = await TrackingService(session).remove_item(user=user, tracked_item_id=tracked_item_id)

    if removed:
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

    await message.answer("\n\n".join(lines), reply_markup=tracking_actions_keyboard(items))


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
    await message.answer("Настройки MVP: лига сейчас берется из DEFAULT_LEAGUE_NAME.")
