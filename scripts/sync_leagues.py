import asyncio

from app.core.logging import setup_logging
from app.db.session import async_session_factory
from app.integrations.poe_api import PoeApiAuthError, PoeApiClient
from app.services.league_sync import LeagueSyncService
from app.services.poe_oauth import PoeOAuthConfigError, PoeOAuthService


async def main() -> None:
    setup_logging()
    try:
        access_token = ""
        try:
            service_token = await PoeOAuthService().request_service_token(scopes="service:leagues")
            access_token = service_token.access_token
        except PoeOAuthConfigError:
            access_token = ""

        async with async_session_factory() as session:
            client = PoeApiClient(access_token=access_token or None)
            poe2_leagues = await LeagueSyncService(session, client).sync_active_leagues(realm="poe2")
            poe1_leagues = await LeagueSyncService(session, client).sync_active_leagues(realm="poe1")
            await session.commit()
            print(f"synced {len(poe2_leagues)} poe2 leagues and {len(poe1_leagues)} poe1 leagues")
    except PoeApiAuthError as exc:
        print(str(exc))


if __name__ == "__main__":
    asyncio.run(main())
