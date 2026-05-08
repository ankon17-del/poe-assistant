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


@router.message(Command("start"))
async def start(message: Message) -> None:
    async with session_scope() as session:
        await ensure_user(session, message.from_user.id, message.from_user.username)

    await message.answer(
        "Привет. Я POE/POE2 ассистент для трекинга торговли, статистики и шаблонов.\n\n"
        "Начни с /add Mageblood или открой /templates."
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "Команды:\n"
        "/add <название> - добавить предмет\n"
        "/remove <id> - отключить трекинг\n"
        "/list - список трекинга\n"
        "/stats - статистика продаж\n"
        "/templates - готовые наборы\n"
        "/settings - настройки"
    )


@router.message(Command("add"))
async def add_tracking(message: Message) -> None:
    raw_text = message.text or ""
    payload = raw_text.removeprefix("/add").strip()
    if not payload:
        await message.answer("Напиши предмет или trade URL после команды. Например: /add Divine Orb")
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

    await message.answer(f"Добавил трекинг #{tracked_item.id}: {tracked_item.item_name}")


@router.message(Command("remove"))
async def remove_tracking(message: Message) -> None:
    payload = (message.text or "").removeprefix("/remove").strip()
    if not payload.isdigit():
        await message.answer("Укажи id трекинга. Например: /remove 12")
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
        await message.answer("Активного трекинга пока нет. Добавь предмет через /add.")
        return

    lines = ["Активный трекинг:"]
    lines.extend(f"#{item.id} - {item.item_name}" for item in items)
    await message.answer("\n".join(lines))


@router.message(Command("stats"))
async def stats(message: Message) -> None:
    async with session_scope() as session:
        user = await ensure_user(session, message.from_user.id, message.from_user.username)
        summary = await StatsService(session).get_summary(user)

    await message.answer(
        "Статистика:\n"
        f"Продаж всего: {summary.total_sales}\n"
        f"Валюты всего: {summary.total_currency}\n"
        f"Продаж сегодня: {summary.daily_sales}\n"
        f"Валюты сегодня: {summary.daily_currency}"
    )


@router.message(Command("templates"))
async def templates(message: Message) -> None:
    async with session_scope() as session:
        await ensure_user(session, message.from_user.id, message.from_user.username)
        template_groups = await TemplateService(session).list_public()

    if not template_groups:
        await message.answer("Шаблонов пока нет. Запусти seed-скрипт: python -m scripts.seed_templates")
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
        f"Шаблон '{result.template_name}' подключен. Добавлено трекингов: {result.created_count}."
    )
    await callback.answer()


@router.message(Command("settings"))
async def settings(message: Message) -> None:
    await message.answer("Настройки MVP: лига берется из DEFAULT_LEAGUE_NAME в .env.")
