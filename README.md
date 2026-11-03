# myCryptoTrader

Research + execution stack for crypto strategies on **Binance / Bybit spot**.

Один репозиторій, три шари:

```
data  ──▶  research  ──▶  execution
```

- **data** — завантаження, валідація і зберігання OHLCV у Parquet (DuckDB зверху).
- **research** — спільні фічі, сигнали, walk-forward спліти, маленький чесний бектестер.
- **execution** — Freqtrade (dry-run → live) у Docker, з тим самим кодом сигналів.

Головний принцип: **логіка сигналів існує в одному місці**. І бектест, і Freqtrade викликають
`mycryptotrader.signals.ta_baseline.add_signals`. Ніякого дублювання в ноутбуках.

---

## Швидкий старт

Потрібні: Python 3.11+, [uv](https://docs.astral.sh/uv/), GNU Make (Linux/macOS/WSL).

```bash
uv sync                 # створити .venv і встановити залежності
make data-demo          # згенерувати синтетичні свічки (без мережі)
make test               # юніт-тести
make backtest           # бектест + артефакти в research/runs/
make ci                 # lint + typecheck + tests
```

На Windows без WSL/Make використовуй напряму:

```powershell
uv run mycryptotrader data demo --days 365
uv run mycryptotrader backtest
```

## Основні make-команди

| Команда | Що робить |
|---|---|
| `make install` | `uv sync` — локальне оточення |
| `make fmt` / `make lint` | ruff format + autofix / перевірка |
| `make format-check` | перевірка форматування без змін |
| `make typecheck` | mypy по `src/` |
| `make test` / `make test-cov` | тести / тести з покриттям |
| `make ci` | lint + typecheck + tests (те саме, що в CI) |
| `make data-demo` | синтетичні дані для офлайн-перевірки |
| `make data-download SINCE=2023-01-01 UNTIL=2024-01-01` | історія через ccxt |
| `make data-validate` | перевірка дір/дублів у даних |
| `make data-list` | список збережених датасетів |
| `make data-sql SQL="select ..."` | SQL через DuckDB |
| `make backtest` | локальний research-бектест |
| `make download` | Freqtrade: свічки для свого бектесту |
| `make backtest-ft` | Freqtrade-бектест у Docker |
| `make dryrun` / `make up` | підняти dry-run бота |
| `make live` | LIVE-торгівля (з підтвердженням) |
| `make logs` | логи бота |
| `make stop` | зупинити все |
| `make deploy` | на сервері: `git pull` + restart |
| `make nginx DOMAIN=...` | nginx reverse proxy для FreqUI |
| `make nginx-tls DOMAIN=... EMAIL=...` | HTTPS-сертифікат Let's Encrypt |

Приклади з іншими параметрами:

```bash
make data-download SYMBOL=ETH/USDT TIMEFRAME=15m SINCE=2024-01-01 UNTIL=2024-06-01
make backtest SYMBOL=ETH/USDT TIMEFRAME=15m STRATEGY=TaBaseline
make backtest-ft TIMERANGE=20240101-20240630
```

## Дані

```
data/raw/exchange=binance/symbol=BTC_USDT/timeframe=1h/year=2024/month=01/part.parquet
```

- таймстемпи — UTC epoch **milliseconds** (int64), без двозначності;
- запис ідемпотентний: повторне завантаження оновлює існуючі свічки;
- `data/` у `.gitignore`; у git живе тільки код і конфіги.

Для великої історії швидше брати офіційні дампи (наприклад `data.binance.vision`) і
завантажувати їх через `write_ohlcv`, ніж тягнути все через ccxt.

## Стратегії

| Назва | Логіка | Чистий код | Freqtrade-обгортка |
|---|---|---|---|
| `TaBaseline` | EMA 20/50 cross + RSI-фільтр | `signals/ta_baseline.py` | `strategies/ta_baseline.py` |
| `RsiReversion` | RSI виходить з oversold + фільтр EMA200 | `signals/rsi_reversion.py` | `strategies/rsi_reversion.py` |

Обидві стратегії зареєстровані в `signals/registry.py`. Вибір — через `STRATEGY`:

```bash
make backtest    STRATEGY=RsiReversion
make backtest-ft STRATEGY=RsiReversion
make dryrun      STRATEGY=RsiReversion
```

Або задай `STRATEGY=RsiReversion` у `.env` — тоді контейнер підхопить його автоматично.

Щоб додати нову стратегію: чиста функція `add_signals(df) -> df` у `signals/`, обгортка
`IStrategy` у `strategies/`, один рядок у `registry.py`, тести на бінарність і causality.

Покроковий серверний сценарій — у [docs/server-runbook.md](docs/server-runbook.md).

## Freqtrade

Конфіги лежать у `config/freqtrade/`:

- `config.dryrun.json` — безпечний режим без ключів;
- `config.live.json` — реальні гроші, базовий конфіг без секретів;
- `config.private.json` — ключі та паролі (git-ignored, створюється локально).

Стратегії — у `src/mycryptotrader/strategies/` і монтуються в контейнер, тому
контейнер не треба перебудовувати після зміни стратегії.

```bash
cp .env.example .env      # STRATEGY/TIMEFRAME; секретів тут немає
make download             # свічки для Freqtrade-бектесту
make backtest-ft          # бектест
make dryrun               # dry-run + FreqUI на 127.0.0.1:18080
make logs
```

## Деплой на Ubuntu-сервер

```bash
# на сервері, один раз
sudo apt update && sudo apt install -y docker.io docker-compose-plugin make git chrony
sudo timedatectl set-timezone UTC
curl -LsSf https://astral.sh/uv/install.sh | sh

git clone <repo> myCryptoTrader && cd myCryptoTrader
cp .env.example .env

# лише для live:
cp config/freqtrade/config.private.example.json config/freqtrade/config.private.json
chmod 600 config/freqtrade/config.private.json
# заповни ключі (trade-only, без withdraw, IP-whitelist)

make download             # історія для бектесту
make backtest-ft          # перевірка стратегії
make dryrun               # 2–4 тижні dry-run
make logs
```

Перед live:

1. окремі API-ключі для testnet/live, тільки `trade`, без `withdraw`;
2. IP-whitelist на біржі;
3. `make dryrun` пропрацював щонайменше 2–4 тижні без збоїв;
4. є зовнішній heartbeat (healthchecks.io) і Telegram-алерти;
5. бекап `user_data/*.sqlite` і конфігів.

`make live` запускає окремий контейнер на порту `127.0.0.1:18081`. **Не запускай dry-run і live
одночасно** — це різні БД, але плутанина в стані неминуча.

## FreqUI через nginx + домен

Спочатку DNS: A-запис `freq.example.com` → IP сервера, і відкритий порт 80.

```bash
# HTTP reverse proxy (+ опційний basic auth)
make nginx DOMAIN=freq.example.com AUTH_USER=roma AUTH_PASSWORD='strong-password'

# HTTPS через Let's Encrypt
make nginx-tls DOMAIN=freq.example.com EMAIL=you@example.com
```

`make nginx`:

- пише `/etc/nginx/sites-available/mycryptotrader-<domain>.conf`;
- робить symlink у `sites-enabled`;
- перевіряє `nginx -t`, робить reload, а при помилці відкочує зміни.

`AUTH_USER`/`AUTH_PASSWORD` додають HTTP Basic Auth — рекомендовано, якщо UI дивиться в
інтернет. Пароль краще не світити в історії shell:

```bash
read -rs NGINX_AUTH_PASSWORD
export NGINX_AUTH_PASSWORD
make nginx DOMAIN=freq.example.com AUTH_USER=roma
```

Для live-UI: `make nginx DOMAIN=freq.example.com NGINX_PORT=18081`.
Видалити сайт: `make nginx-remove DOMAIN=freq.example.com`.

Перед публічним доступом зміни пароль FreqUI: стандартний `dry-run-only-password`
не призначений для інтернету. Для live використовуй пароль з `config.private.json`.

## Правила безпеки

- Ключі — тільки в `config/freqtrade/config.private.json` (chmod 600), ніколи в git.
- Ніяких ключів із правом виведення коштів на сервері.
- Live — тільки після dry-run і тільки малим капіталом.
- Бектест без комісій і slippage — не результат.
- `data/`, `research/runs/`, `user_data/data/` не комітяться.

## Структура

```
src/mycryptotrader/
├─ data/        # store, ccxt downloader, validation, DuckDB
├─ features/    # індикатори + єдиний feature pipeline
├─ signals/     # стратегії як чисті функції
├─ research/    # спліти, метрики, бектестер
├─ strategies/  # обгортки Freqtrade (IStrategy)
├─ config.py
└─ cli.py
tests/          # unit + інтеграційні (включно з тестами на lookahead)
config/freqtrade/
docker-compose.yml
docs/architecture.md
```

Детальніше про рішення — у [docs/architecture.md](docs/architecture.md).
