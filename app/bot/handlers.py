from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.dependencies import session_scope
from app.bot.keyboards import templates_keyboard
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


@router.message(Command("start"))
async def start(message: Message) -> None:
    async with session_scope() as session:
        await ensure_user(session, message.from_user.id, message.from_user.username)

    await message.answer(
        "Привет! Я POE / POE2 ассистент для трекинга торговли, статистики и шаблонов.\n\n"
        "Начни с `/add Divine Orb`, `/list` или открой `/templates`."
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
            "Напиши предмет или trade URL после команды.\n"
            "Примеры:\n"
            "`/add Divine Orb`\n"
            "`/add Divine Orb | 1`\n"
            "`/add https://...`",
            parse_mode="Markdown",
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
            await message.answer("Порог цены должен быть числом. Пример: `/add Divine Orb | 1`", parse_mode="Markdown")
            return

    async with session_scope() as session:
        user = await ensure_user(session, message.from_user.id, message.from_user.username)
        tracked_item = await TrackingService(session).add_item(
            user=user,
            item_name=item_name,
            trade_url=trade_url,
            target_price=target_price,
        )

    response = f"Добавил трекинг `#{tracked_item.id}`: **{tracked_item.item_name}**"
    if target_price is not None:
        response += f"\nПорог цены: {format_decimal(target_price)}"
    if trade_url:
        response += "\nИсточник: trade URL"
    await message.answer(response, parse_mode="Markdown")


@router.message(Command("remove"))
async def remove_tracking(message: Message) -> None:
    payload = (message.text or "").removeprefix("/remove").strip()
    if not payload.isdigit():
        await message.answer("Укажи id трекинга. Пример: `/remove 12`", parse_mode="Markdown")
        return

    async with session_scope() as session:
        user = await ensure_user(session, message.from_user.id, message.from_user.username)
        removed = await TrackingService(session).remove_item(user=user, tracked_item_id=int(payload))

    await message.answer("Трекинг отключен." if removed else "Не нашел такой активный трекинг.")


@router.message(Command("list"))
async def list_tracking(message: Message) -> None:
    async with session_scope() as session:
        user = await ensure_user(session, message.from_user.id, message.from_user.username)
        items = await TrackingService(session).list_items(user)

    if not items:
        await message.answer("Активного трекинга пока нет. Добавь предмет через `/add`.", parse_mode="Markdown")
        return

    lines = ["Активный трекинг:"]
    for item in items:
        league_name = item.league.name if item.league else "Без лиги"
        details = [f"`#{item.id}` - **{item.item_name}**", f"лига: {league_name}"]
        if item.target_price is not None:
            details.append(f"порог: {format_decimal(Decimal(item.target_price))}")
        if item.trade_url:
            details.append("источник: trade URL")
        lines.append("\n".join(details))

    await message.answer("\n\n".join(lines), parse_mode="Markdown")


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

    await message.answer("Доступные шаблоны:", reply_markup=templates_keyboard(template_groups))


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
        f"Шаблон **{result.template_name}** подключен.\n"
        f"Новых или реактивированных трекингов: {result.created_count}.",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(Command("settings"))
async def settings(message: Message) -> None:
    await message.answer("Настройки MVP: лига сейчас берется из `DEFAULT_LEAGUE_NAME`.", parse_mode="Markdown")
