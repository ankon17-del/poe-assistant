# POE / POE2 Telegram Assistant - Roadmap V2

## Update 2026-06-13

Текущий главный вектор проекта смещён из режима "готовим OAuth/stash foundation" в режим
"строим полезный personal stash assistant на официальных account scopes".

### Актуальный приоритет по фазам

- Phase 1: готово
- Phase 2: частично готово, currency-case живой, item trade polling всё ещё ограничен внешним 403
- Phase 3: сильно готово
- Phase 4: хорошо для POE2, частично для POE1
- Phase 5: сильный foundation уже собран
- Phase 6: активная рабочая фаза прямо сейчас
- Phase 7: отложена
- Phase 8-10: вторичный приоритет, пока не добьём полезность stash/account слоя

### Phase 6 - текущий milestone

1. official OAuth уже работает
2. account linking уже работает
3. live PoE1 stash-read уже работает
4. теперь цель — превратить `/stash` в полезный экран:
   - liquid tabs
   - dense tabs
   - dump candidates
   - what to check first
   - дальше hidden liquidity и sell-first hints

### Ближайший маршрут

1. Дожать stash assistant v1 до реально полезного summary
2. Добавить вторую волну stash-insights по ликвидности и приоритету продажи
3. После этого переходить к account-aware recommendations и расширению экономического слоя

Актуализировано по фактическому состоянию репозитория и Railway-деплоя на `2026-05-12`.

## 1. Где мы сейчас

Проект уже не на стадии "скелета". У нас есть живой Telegram-бот, отдельный API, отдельный worker, рабочий economy-контур для POE2, развитый template-flow, build assistant и начатая Phase 6 для stash-analysis.

При этом важно честно разделять:

- что уже реально полезно пользователю каждый день;
- что собрано как foundation и готово к наращиванию;
- что упирается во внешние ограничения (`GGG OAuth`, `PoE trade 403`, отсутствие stash-scopes).

Сейчас проект лучше всего описывается так:

- **Foundation собран хорошо**
- **MVP уже живой для currency / economy / templates / builds**
- **item trade tracking и real stash-analysis ещё не доведены до production-ready**

---

## 2. Статус по фазам

### Phase 1 - Project Foundation
**Статус: практически завершена**

Сделано:

- разделение на `api / bot / services / integrations / workers / models / db`
- `FastAPI` сервис
- `aiogram 3` бот
- конфиг через `.env`
- логирование
- async SQLAlchemy + Alembic
- healthchecks для Railway
- split-деплой:
  - `poe-assistant`
  - `poe-assistant-bot`
  - `poe-assistant-worker`
- `Postgres` и `Redis` подключены

Остаточный хвост:

- полноценный production docker-compose / container workflow
- отдельная очередь уровня `Celery/RQ` пока не внедрена

Итог:

- **Phase 1 можно считать закрытой для текущего продукта**

---

### Phase 2 - Trade Tracking System
**Статус: частично завершена**

Сделано:

- `tracked_items`
- worker polling loop
- source registry
- currency watcher pipeline
- inline-управление watcher'ами
- `/add`, `/list`, `/alerts`, `/stats`
- переактивация сработавших alerts
- массовые действия по alerts
- worker observability стала лучше

Работает хорошо:

- currency alerts
- worker cycle
- dedupe / paused / reactivate flow

Не закрыто:

- real item trade URL watcher в production
- ordinary item market polling
- real sale notifications по настоящим trade-sales

Ключевой блокер:

- `pathofexile.com` режет Railway worker по `403 Forbidden` на website trade flow

Итог:

- **Phase 2 закрыта для currency-кейса**
- **Phase 2 не закрыта для обычных item watchers**

---

### Phase 3 - Template System
**Статус: хорошо продвинута, почти готова для MVP**

Сделано:

- `template_groups`
- `template_items`
- seed-логика
- realm-aware шаблоны
- выбор игры перед шаблонами
- фильтрация шаблонов по игре
- preview перед активацией
- выбор лиги перед применением
- отчёт:
  - что создано
  - что реактивировано / обновлено
- отдельные POE1/POE2 template packs
- target currency внутри template items

Итог:

- **Phase 3 можно считать достаточно зрелой для MVP**

Что можно докрутить потом:

- community templates
- import / export
- template versioning UX

---

### Phase 4 - Economy System
**Статус: живая и полезная, но не полностью закрыта**

Сделано:

- `/economy`
- POE2 currency snapshots
- overview summary
- top watched currencies
- nearest alerts
- paused alerts visibility
- market movement summary
- market pulse
- actionable hints
- связка `/economy <-> /alerts <-> /stats`

Работает хорошо:

- POE2 economy loop
- currency market awareness
- operational обзор по watcher'ам

Частично работает:

- POE1 league awareness и fallback-логика есть
- `Mirage` поддержан как лига
- но POE1 external rate sources по-прежнему нестабильны / пусты в текущем окружении

Итог:

- **Phase 4 закрыта для POE2 MVP-контура**
- **Phase 4 частично закрыта для POE1**

---

### Phase 5 - Build Assistant
**Статус: уверенно начата и уже полезна**

Сделано:

- `/builds`
- flow:
  - игра
  - цель
  - бюджет
  - стиль
  - список билдов
  - detail-card
- verdict summary
- alternatives
- upgrade guidance
- endgame focus
- slot checklist
- gear sheet
- progression stages
- trade targets
- content warnings
- внешние кнопки:
  - `Planner`
  - `Guide`
  - `Tree`
  - `Atlas`
- browse-flow с `Назад`
- source-backed flagship builds
- остальные билды тоже приведены к рабочему уровню с external entry points и внутренними блоками

Что уже даёт ценность:

- не просто "текст о билде"
- а старт build research прямо из Telegram
- с market-facing подсказками и внешними visual refs

Что ещё не закрыто:

- gem setup / links
- более точные curated sources для всех билдов, а не только части
- реально visual-native build surfaces внутри продукта (пока это внешние planner / guide / atlas links)

Итог:

- **Phase 5 собрана как сильный foundation**
- **Phase 5 достаточно зрелая, чтобы двигаться дальше**

---

### Phase 6 - Stash Analysis
**Статус: начата**

Сделано:

- `/stash`
- stash readiness panel
- статус:
  - аккаунта
  - OAuth/scopes
  - готовности к live stash read
- ручные stash playbooks:
  - быстрый stash triage
  - что продавать быстрее всего
  - как проверять unique tabs
  - как смотреть currency / fragments

Что это значит:

- реального stash-scan ещё нет
- но UX, framing и ручная практическая польза уже появились

Что нужно, чтобы Phase 6 стала "настоящей":

- рабочий PoE account OAuth с нужными scopes
- доступ к stash/account data
- реальные сервисы чтения вкладок
- автоматические insights вместо только manual playbooks

Итог:

- **Phase 6 начата, но пока это foundation + manual layer**

---

### Phase 7 - FunPay Integration
**Статус: не начата**

---

### Phase 8 - Advanced Template System
**Статус: не начата**

---

### Phase 9 - Telegram Mini App
**Статус: не начата**

---

## 3. Что готово полностью или почти полностью

Можно считать собранными или почти собранными:

- **Phase 1**
- **Phase 3**
- **POE2-часть Phase 4**

Можно считать рабочими, но не завершёнными:

- **Phase 2**
- **Phase 5**
- **Phase 6**

Пока не начаты:

- **Phase 7**
- **Phase 8**
- **Phase 9**

---

## 4. Главные незакрытые блоки проекта

Это самые важные реальные gaps сейчас:

1. **Real item tracking**
   - ordinary item watchers
   - production-grade trade URL polling

2. **POE1 data quality**
   - currency/economy sources по-прежнему нестабильны

3. **OAuth / account scopes**
   - код готов
   - но нет подтверждённых client credentials и stash-scopes от GGG

4. **Real stash analysis**
   - пока только foundation и manual playbooks

5. **Phase 7+**
   - FunPay
   - advanced templates
   - mini app

---

## 5. Текущий рабочий план

Сейчас оптимальный порядок такой:

### Текущий активный этап
**Продолжать Phase 6**

Ближайший правильный шаг:

1. усилить manual stash-audit flow
2. сделать более структурированные stash сценарии:
   - currency tab audit
   - unique tab audit
   - dump tab audit
   - liquidation checklist
3. подготовить внутреннюю форму данных под future auto-analysis

### После этого
**Подойти к Phase 7**

Но только если:

- Phase 6 manual layer уже ощущается полезной и оформленной
- и мы не хотим ждать GGG, чтобы двигать продукт дальше

---

## 6. Что нас сейчас блокирует извне

### GGG OAuth

Не получены:

- `POE_OAUTH_CLIENT_ID`
- `POE_OAUTH_CLIENT_SECRET`
- stash-related scopes

Это блокирует:

- real account linking usage
- live stash read
- account-based analytics

### PoE website trade flow

Railway worker получает:

- `403 Forbidden`

Это блокирует:

- production item trade URL polling

---

## 7. Что не надо сейчас распылять

Пока не стоит уходить глубоко в:

- Telegram Mini App
- public/community template marketplace
- FunPay heavy logic
- desktop / overlay tools
- сложный AI без входных данных

---

## 8. Краткий вывод

Если совсем коротко:

- **Foundation — крепкий**
- **Currency/economy/templates/builds — уже живые**
- **Stash-analysis — начат правильно**
- **Главные реальные блокеры — GGG OAuth и item trade polling**

Прямо сейчас проект лучше всего двигать так:

1. **добить полезный manual слой Phase 6**
2. **потом решить: идём в Phase 7 или возвращаемся к техническим долгам**
3. **когда GGG откроют доступ — резко усиливаем account/stash сторону**
