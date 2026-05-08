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
            leagues = await LeagueSyncService(
                session,
                PoeApiClient(access_token=access_token or None),
            ).sync_active_leagues(realm="poe2")
            await session.commit()
            print(f"synced {len(leagues)} leagues")
    except PoeApiAuthError as exc:
        print(str(exc))


if __name__ == "__main__":
    asyncio.run(main())
