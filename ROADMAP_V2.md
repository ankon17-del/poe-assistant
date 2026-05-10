# POE / POE2 Telegram Assistant - Roadmap V2

This roadmap reflects the actual state of the repository and Railway deployment on 2026-05-10.

## Current State

The project already has a solid MVP foundation:

- FastAPI service is present and deployed separately from the bot and worker.
- Telegram bot is running with `aiogram 3`.
- Railway is split into `poe-assistant`, `poe-assistant-bot`, and `poe-assistant-worker`.
- PostgreSQL migrations are working.
- Redis is available in infrastructure.
- League-first data model is in place, including POE1 / POE2 realm separation.
- Template packs are seeded and can generate user tracking entries.
- Currency price alerts are working for supported currency items.
- `/economy` gives a lightweight league-aware currency snapshot and shows active currency alerts.
- OAuth groundwork for Path of Exile account/service scopes is implemented.

The product is not yet in a "daily useful" state for general trade tracking, because normal item watchers still do not have a real production-grade trade polling source.

## Done

### Foundation

- Project structure split into `api`, `bot`, `services`, `integrations`, `workers`, `models`, `db`.
- Config, logging, async SQLAlchemy session management, Alembic migrations.
- Healthcheck endpoints for Railway service modes.

### Database

- `users`
- `leagues`
- `tracked_items`
- `notifications`
- `sales_stats`
- `integrations`
- `template_groups`
- `template_items`
- `user_templates`
- `sale_events`

Additional completed model upgrades:

- league `realm` support for POE1 / POE2
- tracking threshold currency support (`ex`, `chaos`, `div`)

### Telegram MVP

- `/start`
- `/help`
- `/add`
- `/remove`
- `/list`
- `/stats`
- `/economy`
- `/templates`
- `/settings`

### UX already improved

- Interactive `/add` wizard
- Game selection: POE1 / POE2
- League selection
- Search-based item selection
- Threshold currency selection
- Duplicate resolution: update existing or create new
- Inline list removal flow
- URL-based add flow now asks for tracker name and threshold

### Worker / Notifications

- Background worker service exists and runs separately
- Telegram notifier service exists
- Price alert pipeline exists for currency watchers
- Notification persistence exists
- Sale event deduplication exists

### Integrations already present

- Official PoE API client
- League sync script
- OAuth token flow
- Currency market source for POE economy data
- Mock tracking source for pipeline testing

## Partially Done

### Trade Tracking

Implemented:

- tracked item persistence
- worker polling loop
- normalized tracking request layer
- source registry abstraction

Missing:

- real production source for standard item trade polling
- reliable parsing of trade URL market state
- true item sale / item price notifications

### Economy System

Implemented:

- currency price fetching
- multi-unit alert thresholds
- POE2 fallback source

Missing:

- item market trends
- economy dashboard
- price spike / crash analytics

### OAuth / Account Integration

Implemented:

- callback flow
- token storage
- service token request flow

Missing:

- user-facing Telegram flow for account linking
- actual use of account scopes in product features

## Not Done Yet

- Real trade URL watcher for ordinary items
- Sale notifications for real PoE trade sales
- Stash analysis
- Build assistant
- AI recommendations
- FunPay feature set
- Community template sharing/import/export
- Telegram Mini App
- Production job queue layer (`Celery` / `RQ`)
- Docker / docker-compose production workflow
- Automated tests beyond skeleton structure

## Actual Priority Order

### Phase A - Finish real item tracking

This is the highest-value missing block.

Tasks:

- implement a real tracking source for item trade URLs
- support polling by saved trade URL
- extract meaningful market signals from search results
- trigger Telegram alerts for item threshold conditions
- verify deduplication and repeat notification behavior

### Phase B - Stabilize worker behavior

Tasks:

- improve worker logging
- add better failure visibility
- verify Railway worker deployment behavior
- make alert behavior deterministic and debuggable

### Phase C - Make tracking genuinely useful

Tasks:

- improve tracker naming and state clarity
- refine search quality in `/add`
- expose watcher type clearly: currency vs item vs trade URL
- improve notification text quality

### Phase D - Expand economy features

Tasks:

- broader currency coverage
- item trend support where feasible
- basic opportunity alerts

### Phase E - Activate account-based features

Tasks:

- user account linking flow
- start using approved OAuth scopes
- prepare stash/account-based services without bloating MVP

## MVP Definition Now

The project should be considered a true MVP only when all of the following are stable:

- users can add watchers without confusing flows
- currency alerts work reliably
- ordinary trade URL item watchers also work reliably
- worker runs unattended on Railway
- stats remain correct and deduplicated
- templates accelerate setup without breaking independent tracking

## What We Should Not Build Before That

- Telegram Mini App
- advanced AI assistant features
- stash valuation system
- FunPay business logic
- public/community template marketplace
- desktop / overlay tools

## Immediate Practical Next Step

Because Railway is currently blocked by `403 Forbidden` on the website trade flow, the practical next step is:

- strengthen the currency / economy MVP,
- improve worker stability and observability,
- keep the item watcher isolated until it can run from a more suitable environment.

The real trade URL item watcher remains an important gap, but it should not block the rest of the product now.
