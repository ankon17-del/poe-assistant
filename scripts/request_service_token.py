import asyncio

from app.services.poe_oauth import PoeOAuthConfigError, PoeOAuthService


async def main() -> None:
    try:
        token = await PoeOAuthService().request_service_token()
        print(token.access_token)
    except PoeOAuthConfigError as exc:
        print(str(exc))


if __name__ == "__main__":
    asyncio.run(main())
