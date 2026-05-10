from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.league import League


class LeagueService:
    DEFAULT_LEAGUES: dict[str, list[str]] = {
        "poe1": ["Mirage", "Standard", "Hardcore"],
        "poe2": ["POE2 Standard"],
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, name: str, realm: str = "poe2") -> League:
        league = await self.session.scalar(select(League).where(League.name == name, League.realm == realm))
        if league:
            return league

        league = League(name=name, realm=realm)
        self.session.add(league)
        await self.session.flush()
        return league

    async def upsert(self, name: str, realm: str, is_active: bool) -> League:
        league = await self.session.scalar(select(League).where(League.name == name, League.realm == realm))
        if league:
            league.is_active = is_active
            return league

        league = League(name=name, realm=realm, is_active=is_active)
        self.session.add(league)
        await self.session.flush()
        return league

    async def list_active(self, realm: str) -> list[League]:
        await self.ensure_defaults(realm)
        result = await self.session.scalars(
            select(League)
            .where(League.realm == realm, League.is_active.is_(True))
            .order_by(League.name.asc())
        )
        return list(result)

    async def ensure_defaults(self, realm: str) -> None:
        for league_name in self.DEFAULT_LEAGUES.get(realm, []):
            await self.get_or_create(league_name, realm=realm)

    async def list_selection_options(self, realm: str) -> list[League]:
        leagues = await self.list_active(realm)
        if not leagues:
            return []

        def sort_key(league: League) -> tuple[int, str]:
            lower = league.name.lower()
            is_standardish = any(token in lower for token in ("standard", "hardcore", "ssf", "solo self-found"))
            return (1 if is_standardish else 0, league.name)

        return sorted(leagues, key=sort_key)
