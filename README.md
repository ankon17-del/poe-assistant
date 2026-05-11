# POE / POE2 Telegram Assistant

Scalable MVP foundation for a Telegram assistant focused on Path of Exile and Path of Exile 2 trade tracking, sale notifications, basic stats, and reusable tracking templates.

Current implementation status and next priorities are tracked in [ROADMAP_V2.md](/D:/!Work/CodexGames/POE AI/ROADMAP_V2.md).

## MVP Scope

- Telegram bot with `/start`, `/help`, `/add`, `/remove`, `/list`, `/alerts`, `/account`, `/builds`, `/stats`, `/economy`, `/templates`, `/settings`.
- League-first SQLAlchemy models.
- Template packs generate independent tracking configs.
- Integration and worker placeholders are isolated from bot handlers.
- FastAPI health endpoint for deployment checks.

## Setup

1. Create `.env` from `.env.example`.
2. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

3. Apply migrations:

```bash
alembic upgrade head
```

For a quick local MVP fallback without Alembic:

```bash
python -m scripts.create_tables
```

4. Seed starter templates:

```bash
python -m scripts.seed_templates
```

5. Sync leagues from the official PoE API:

```bash
python -m scripts.sync_leagues
```

6. Run the bot:

```bash
python launcher.py
```

7. Run the tracking worker:

```bash
python -m scripts.run_tracking_worker
```

8. Run the API:

```bash
uvicorn app.api.main:app --reload
```

## Railway Service Modes

`railway.json` supports three runtime modes through the `SERVICE_MODE` environment variable:

- unset or `web` -> run FastAPI via `uvicorn`
- `bot` -> run the Telegram polling bot
- `worker` -> run the background tracking worker

Both the bot and worker expose `/health` on `PORT` so Railway healthchecks can succeed without a public HTTP app.

## Railway API Deploy

This repo includes a minimal `railway.json` deployment config for the FastAPI service.

Recommended production split:

- `poeassistant.ru` -> Tilda
- `api.poeassistant.ru` -> Railway FastAPI service
- `poe-assistant-bot` -> Railway service with `SERVICE_MODE=bot`
- `poe-assistant-worker` -> Railway service with `SERVICE_MODE=worker`

Suggested first deploy flow:

1. Create a Railway project.
2. Deploy this repo as a web service.
3. Set required environment variables in Railway.
4. Generate a temporary Railway domain and verify `GET /health`.
5. Add `api.poeassistant.ru` as a custom domain in Railway.
6. Add the DNS records Railway gives you at your DNS provider.
7. Set `POE_OAUTH_REDIRECT_URI=https://api.poeassistant.ru/oauth/poe/callback`.

## Local worker check

You can create a mock tracked item and test the full worker flow with a synthetic trade URL such as:

```text
mock://sale-001?item=Mageblood&price=112 div
```

The worker will treat it as one sale event, notify once, and then ignore repeats with the same external id because of deduplication.

## Official API Notes

- `app/integrations/poe_api.py` uses the documented PoE API at `https://api.pathofexile.com`.
- League sync already uses the official `GET /league` resource.
- `scripts/sync_leagues.py` will first try to request a `client_credentials` service token when OAuth client credentials are configured.
- `mock://` is now implemented as a dedicated `TrackingSource` and feeds the same normalized event pipeline as future real adapters.
- Configure a real `POE_API_USER_AGENT` in `.env` before calling the official API outside local tests.

## Tracking Source Layer

- `app/integrations/tracking_source.py` defines the normalized `SaleEventDTO` and `TrackingSource` contract.
- `app/integrations/source_registry.py` resolves which adapter should handle each tracked item.
- `app/integrations/mock_tracking_source.py` is the first concrete source and exists to keep the pipeline testable.
- `app/workers/tracking_worker.py` now depends on the registry and normalized events instead of a concrete trade client.

## OAuth Flow

For service scopes such as `service:leagues`, configure:

```text
POE_OAUTH_CLIENT_ID=...
POE_OAUTH_CLIENT_SECRET=...
POE_OAUTH_REDIRECT_URI=https://your-domain.example/oauth/poe/callback
```

Then you can request a service token directly:

```bash
python -m scripts.request_service_token
```

For account scopes, the API exposes a minimal connect/callback flow:

- `GET /oauth/poe/connect?telegram_id=<id>&scopes=account:profile`
- `GET /oauth/poe/callback?code=...&state=...`

The callback stores tokens in `integrations` under `integration_type=poe_oauth`.
The bot-side user flow is available through `/account` and mirrored in `/settings`.

## Architecture Rules

- Telegram handlers only coordinate user input and call services.
- Business logic lives in `app/services`.
- External systems live in `app/integrations`.
- Background polling belongs in `app/workers`.
- Economy and trade data must remain league-aware.
