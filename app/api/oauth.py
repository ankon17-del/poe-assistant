from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.bot.dependencies import session_scope
from app.models.enums import IntegrationType
from app.services.integrations import IntegrationService
from app.services.oauth_state import oauth_state_store
from app.services.poe_oauth import PoeOAuthConfigError, PoeOAuthService
from app.services.users import UserService

router = APIRouter(prefix="/oauth/poe", tags=["poe-oauth"])


def _render_callback_page(
    *,
    title: str,
    message: str,
    success: bool,
    account_name: str = "",
    scopes: str = "",
) -> HTMLResponse:
    accent = "#16a34a" if success else "#dc2626"
    details = ""
    if account_name:
        details += f"<p><strong>Аккаунт:</strong> {account_name}</p>"
    if scopes:
        details += f"<p><strong>Scopes:</strong> {scopes}</p>"

    html = f"""
    <!doctype html>
    <html lang="ru">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>{title}</title>
        <style>
          body {{
            margin: 0;
            font-family: Inter, Arial, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            display: flex;
            min-height: 100vh;
            align-items: center;
            justify-content: center;
            padding: 24px;
          }}
          .card {{
            max-width: 520px;
            width: 100%;
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.35);
          }}
          h1 {{
            margin: 0 0 12px;
            font-size: 24px;
            color: {accent};
          }}
          p {{
            margin: 0 0 12px;
            line-height: 1.5;
          }}
          .muted {{
            color: #94a3b8;
          }}
        </style>
      </head>
      <body>
        <div class="card">
          <h1>{title}</h1>
          <p>{message}</p>
          {details}
          <p class="muted">Теперь можно вернуться в Telegram и открыть /account или /settings.</p>
        </div>
      </body>
    </html>
    """
    return HTMLResponse(content=html)


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


@router.get("/connect")
async def connect_poe_oauth(
    telegram_id: int = Query(..., description="Telegram user id"),
    scopes: str | None = Query(default=None, description="Space-separated OAuth scopes"),
) -> RedirectResponse:
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
    return RedirectResponse(url=auth_request.url, status_code=307)


@router.get("/callback")
async def poe_oauth_callback(code: str, state: str) -> HTMLResponse:
    state_item = oauth_state_store.pop(state)
    if state_item is None:
        return _render_callback_page(
            title="OAuth state истёк",
            message="Состояние авторизации не найдено или уже устарело. Запусти привязку аккаунта ещё раз из Telegram.",
            success=False,
        )

    service = PoeOAuthService()
    try:
        token = await service.exchange_authorization_code(
            code=code,
            code_verifier=state_item.code_verifier,
            scopes=state_item.scopes,
        )
    except PoeOAuthConfigError as exc:
        return _render_callback_page(
            title="OAuth не настроен",
            message=str(exc),
            success=False,
        )
    except Exception as exc:
        return _render_callback_page(
            title="Не удалось завершить привязку",
            message=f"Обмен кода на токен не удался: {exc}",
            success=False,
        )

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

    return _render_callback_page(
        title="PoE аккаунт подключён",
        message="Привязка прошла успешно. Бот теперь может использовать одобренные account scopes.",
        success=True,
        account_name=token.username or "",
        scopes=token.scope or "",
    )
