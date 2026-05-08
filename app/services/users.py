from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return await self.session.scalar(select(User).where(User.telegram_id == telegram_id))

    async def get_or_create(self, telegram_id: int, username: str | None) -> User:
        user = await self.session.scalar(select(User).where(User.telegram_id == telegram_id))
        if user:
            if user.username != username:
                user.username = username
            return user

        user = User(telegram_id=telegram_id, username=username)
        self.session.add(user)
        await self.session.flush()
        return user
