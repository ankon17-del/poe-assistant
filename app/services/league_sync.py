from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.poe_api import PoeApiClient
from app.models.league import League
from app.services.leagues import LeagueService


class LeagueSyncService:
    def __init__(self, session: AsyncSession, client: PoeApiClient):
        self.session = session
        self.client = client

    async def sync_active_leagues(self, realm: str = "poe2", limit: int = 50) -> list[League]:
        leagues_payload = await self.client.list_leagues(realm=realm, limit=limit)
        league_service = LeagueService(self.session)
        synced: list[League] = []

        for league_data in leagues_payload:
            league = await league_service.upsert(
                name=league_data["name"],
                realm=realm,
                is_active=not bool(league_data.get("endAt")),
            )
            synced.append(league)

        return synced
