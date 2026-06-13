# POE Assistant Roadmap V2

## Актуально на 2026-06-13

Это уже не просто бот с парой команд. Текущий вектор проекта:

- единый Telegram-хаб для игрока POE 1 / POE 2
- официальный OAuth уже работает
- аккаунт и stash уже читаются с официального API
- теперь главный вопрос не "как подключить", а "как превратить это в реально полезного ассистента"

Ниже честная карта: что уже готово, что сломано, что частично, и куда идем дальше.

---

## 1. Быстрый аудит

### Уже живое и полезное

- OAuth-привязка PoE-аккаунта
- account panel внутри Telegram
- currency/economy контур
- price alerts
- template flows
- build assistant
- мультиязычное меню и навигация
- live read личного stash для PoE 1 через `account:stashes`

### Уже есть как foundation, но пользы пока мало

- stash panel
- stash tab summary
- character/account context
- language settings
- groundwork для wealth / valuation / account-aware advice

### Что сейчас реально ломает пользу

1. `/stash` иногда показывает пустые вкладки или ноль предметов из-за rate limit `429` от официального PoE API.
2. Stash valuation слой пока ненадежен: текущий источник для tab-level pricing бьется в `404`, поэтому блок "что продать" неустойчив.
3. Обычный item trade tracking по shared trade URLs все еще страдает от внешних ограничений `403` со стороны trade сайта.
4. Продвинутый account intelligence еще не построен:
   - wealth tracker
   - dead currency detector
   - character analytics
   - atlas/build advisor

---

## 2. Стадии продукта

### Stage 1. Core Assistant
Статус: в основном готово

- OAuth
- trade / currency tracking foundation
- price alerts
- economy snapshots
- Telegram-native menu / flows

Что еще добить:

- item watchers вне currency-case
- более надежный sale / market event слой

### Stage 2. Stash Analytics
Статус: активная рабочая фаза

Цель этой стадии:

- показать не просто содержимое тайника
- а ответить на вопросы:
  - где лежат деньги
  - что продавать первым
  - какая валюта залежалась
  - какие вкладки самые плотные
  - где мусор, а где ликвидность

Подстадии:

1. Trustworthy stash snapshot
2. Sell-first candidates
3. Wealth summary by category
4. Dead currency detector
5. History / wealth tracker

### Stage 3. Character Intelligence
Статус: еще не начато по-настоящему

- character dashboard
- build health checks
- gear gap hints
- atlas-aware recommendations

### Stage 4. Full AI POE Assistant
Статус: дальняя, но уже логичная цель

Идеальный сценарий:

Пользователь пишет в Telegram:

> Что мне сейчас выгоднее фармить?

А бот отвечает, опираясь на:

- текущую лигу
- его stash
- его валюту
- его персонажей
- его билд
- его atlas / прогресс
- текущую экономику

---

## 3. Честный статус по направлениям

### Trade Tracking
Статус: частично готово

Готово:

- currency watchers
- thresholds
- alerts lifecycle
- worker loop

Проблемы:

- item trade URL polling нестабилен из-за внешних `403`

### Economy
Статус: рабочее

Готово:

- `/economy`
- currency alerts summary
- активные / paused alerts
- POE2 economy layer

Проблемы:

- часть POE1 источников все еще нестабильна

### Templates
Статус: рабочее

Готово:

- game-aware templates
- goal-based template selection
- activation flow

### Builds
Статус: рабочее, но еще не финальный уровень

Готово:

- build browse flow
- detailed cards
- planner / guide / tree / atlas links

Еще нужно:

- глубже связать билды с аккаунтом, stash и market reality

### Account
Статус: готово как foundation

Готово:

- OAuth
- scopes
- account panel
- league / character context

### Stash
Статус: не хватает product value

Готово:

- live stash read
- tab grouping
- dense / liquid / dump heuristics

Не хватает:

- trustworthy anti-rate-limit fetching
- market valuation
- wealth summary
- concrete sell recommendations

---

## 4. Новый приоритет

### Главная задача прямо сейчас

Сделать `Stage 2 / Stash Analytics v1` реально полезным.

Это значит:

1. перестать показывать пустой или ложный stash snapshot
2. честно обрабатывать rate limits
3. показывать пользователю, где лежит ликвидность
4. дать хотя бы первый usable слой wealth / sell-first insights

### Почему именно это

Потому что OAuth и `account:stashes` уже открыли нам дверь в самый сильный дифференциатор продукта.

Если stash раздел останется просто "списком вкладок", мы теряем самую ценную часть ассистента.

---

## 5. Конкретный маршрут

### Milestone A. Stash trust layer
Цель: stash не должен врать

Сделать:

- ограничение параллелизма запросов в PoE API
- retry / backoff на `429`
- короткий кэш снапшота
- явная пометка partial/cached snapshot в UI

### Milestone B. Stash valuation v1
Цель: показать реальные кандидаты на продажу

Сделать:

- стабилизировать market source для stash categories
- начать с валюты / fragments / essences / div cards / maps
- вывести top sell candidates
- вывести top valuable tabs

### Milestone C. Wealth screen
Цель: пользователь видит общую картину капитала

Сделать:

- команда `/wealth` или раздел внутри `/stash`
- total estimated value
- value by category
- liquid vs slow assets

### Milestone D. Dead Currency Detector
Цель: показать залежавшуюся валюту и предложить конверсию

Сделать:

- identify bulky low-priority currency
- пересчет в chaos/div
- shortlist "можно слить без боли"

### Milestone E. Character-aware assistant
Цель: связать stash с персонажами

Сделать:

- active character context
- build gaps
- stash-to-build suggestions

---

## 6. Что откладываем

Пока не лезем глубоко в:

- FunPay / монетизацию
- mini app
- тяжелый AI advisor без нормального stash/account intelligence

Сначала добиваем ядро пользы.

---

## 7. Что делаем в текущем цикле

Текущий выбранный рабочий фокус:

### `Stash Analytics v1: trust first`

Внутри него:

1. исправить ложные пустые snapshots
2. стабилизировать чтение stash
3. только потом наращивать wealth / sell-first аналитику

Это и есть правильный следующий шаг после получения официальных OAuth scopes.
