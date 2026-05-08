from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.league import League


class LeagueService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, name: str) -> League:
        league = await self.session.scalar(select(League).where(League.name == name))
        if league:
            return league

        league = League(name=name)
        self.session.add(league)
        await self.session.flush()
        return league

    async def upsert(self, name: str, is_active: bool) -> League:
        league = await self.session.scalar(select(League).where(League.name == name))
        if league:
            league.is_active = is_active
            return league

        league = League(name=name, is_active=is_active)
        self.session.add(league)
        await self.session.flush()
        return league
