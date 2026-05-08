from fastapi import APIRouter, HTTPException, Query

from app.bot.dependencies import session_scope
from app.models.enums import IntegrationType
from app.services.integrations import IntegrationService
from app.services.oauth_state import oauth_state_store
from app.services.poe_oauth import PoeOAuthConfigError, PoeOAuthService
from app.services.users import UserService

router = APIRouter(prefix="/oauth/poe", tags=["poe-oauth"])


@router.get("/start")
async def start_poe_oauth(
    telegram_id: int = Query(..., description="Telegram user id"),
    scopes: str | None = Query(default=None, description="Space-separated OAuth scopes"),
) -> dict[str, str]:
    service = PoeOAuthService()
    try:
        auth_request = service.build_authorization_request(scopes=scopes)
    except PoeOAuthConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    oauth_state_store.create(
        state=auth_request.state,
        code_verifier=auth_request.verifier,
        scopes=auth_request.scopes,
        telegram_id=telegram_id,
    )
    return {"authorization_url": auth_request.url, "state": auth_request.state}


@router.get("/callback")
async def poe_oauth_callback(code: str, state: str) -> dict[str, str]:
    state_item = oauth_state_store.pop(state)
    if state_item is None:
        raise HTTPException(status_code=400, detail="OAuth state is missing or expired.")

    service = PoeOAuthService()
    try:
        token = await service.exchange_authorization_code(
            code=code,
            code_verifier=state_item.code_verifier,
            scopes=state_item.scopes,
        )
    except PoeOAuthConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {exc}") from exc

    async with session_scope() as session:
        user = await UserService(session).get_or_create(
            telegram_id=state_item.telegram_id,
            username=None,
        )
        await IntegrationService(session).upsert_oauth_tokens(
            user=user,
            integration_type=IntegrationType.poe_oauth,
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            scopes=token.scope,
            external_account_id=token.sub,
            external_account_name=token.username,
            expires_in=token.expires_in,
        )

    return {
        "status": "connected",
        "account_name": token.username or "",
        "scopes": token.scope or "",
    }
