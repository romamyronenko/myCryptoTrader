# Серверний runbook

Покроковий сценарій: від чистого Ubuntu до dry-run бота і першого live-запуску.

## 0. Де лежить код стратегії

```
src/mycryptotrader/signals/ta_baseline.py     ← логіка EMA-cross (чиста функція)
src/mycryptotrader/strategies/ta_baseline.py  ← обгортка Freqtrade

src/mycryptotrader/signals/rsi_reversion.py     ← логіка RSI mean-reversion
src/mycryptotrader/strategies/rsi_reversion.py  ← обгортка Freqtrade

src/mycryptotrader/signals/registry.py        ← список стратегій для CLI
```

Правило: логіку змінюй **тільки** у `signals/`, обгортка майже завжди залишається тонкою.
Тести на causality/lookahead автоматично перевірять, що ти не підглядаєш у майбутнє.

## 1. Підготовка сервера (один раз)

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin make git chrony
sudo systemctl enable --now docker
sudo timedatectl set-timezone UTC
sudo systemctl enable --now chrony

# uv (менеджер Python-оточення)
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"   # або перезайди в shell

git clone <repo-url> myCryptoTrader
cd myCryptoTrader
```

Перевір, що все на місці:

```bash
docker --version
docker compose version
uv --version
make --version
```

## 2. Конфігурація

```bash
cp .env.example .env
nano .env     # STRATEGY, TIMEFRAME, EXCHANGE — секретів тут немає
```

Для **dry-run** більше нічого не потрібно: `config/freqtrade/config.dryrun.json` уже містить
безпечні локальні значення, а API-ключі не використовуються.

Для **live** створи окремий приватний конфіг (git-ignored, мержиться поверх базового):

```bash
cp config/freqtrade/config.private.example.json config/freqtrade/config.private.json
chmod 600 config/freqtrade/config.private.json
nano config/freqtrade/config.private.json
```

Заповни `exchange.key/secret` (право **тільки `trade`**, без `withdraw`, IP-whitelist) і
`api_server`:

```bash
openssl rand -hex 32   # у jwt_secret_key
```

Freqtrade не підставляє `${VAR}` з `.env`, тому секрети живуть саме в `config.private.json`,
а не в змінних оточення.

## 3. Перевірка коду перед запуском

```bash
make ci
```

Має бути: ruff OK, mypy OK, 47 тестів passed.

## 4. Дані

Є два сховища, вони не перетинаються:

| Сховище | Для чого | Команда |
|---|---|---|
| `data/` (Parquet + DuckDB) | research-бектест, аналіз | `make data-download`, `make data-demo` |
| `user_data/data/` (Freqtrade) | Freqtrade backtest/hyperopt | `make download` |

**Freqtrade dry-run/live не потребує завантажених свічок** — він тягне їх з біржі сам.
`make download` потрібен лише для `make backtest-ft`.

```bash
# історія для Freqtrade-бектесту (пари беруться з pair_whitelist у конфізі)
make download TIMEFRAME=1h TIMERANGE=20230101-20240630

# історія для research-бектесту
make data-download SYMBOL=BTC/USDT TIMEFRAME=1h SINCE=2023-01-01 UNTIL=2024-06-30
make data-validate SYMBOL=BTC/USDT TIMEFRAME=1h
make data-list
```

`TIMERANGE` у `make download` і `make backtest-ft` має збігатися, інакше Freqtrade
поскаржиться на брак даних.

## 5. Бектест

### Research-бектест (швидкий, наш рушій)

```bash
make backtest STRATEGY=TaBaseline
make backtest STRATEGY=RsiReversion
```

Результат друкується в консоль і пише артефакти в `research/runs/<Strategy>-<timestamp>/`:

- `metrics.json` — метрики;
- `equity.parquet` — крива капіталу;
- `trades.parquet` — усі угоди;
- `run.json` — git SHA, хеш даних, конфіг.

На що дивитись у першу чергу:

1. `total return` **проти** `buy & hold` — стратегія має додавати цінність, а не просто ловити ринок;
2. `max drawdown` — чи переживеш ти таку просадку психологічно;
3. `trades` — менше ~20 угод = статистично нічого;
4. `fees paid` — на 1h з 0.1% комісія з'їдає більшість дрібних переваг.

### Freqtrade-бектест (реалістичніший)

```bash
make backtest-ft STRATEGY=TaBaseline TIMERANGE=20230101-20240630
make backtest-ft STRATEGY=RsiReversion TIMERANGE=20230101-20240630
```

Результати — у `user_data/backtest_results/`, звіт також друкується в консоль.

## 6. Dry-run (тестовий запуск без грошей)

```bash
make dryrun STRATEGY=TaBaseline
make logs
```

Перевірка стану:

```bash
make ps
docker compose logs --tail=100 trading
```

FreqUI не світимо в інтернет. Дивись через SSH-тунель зі своєї машини:

```bash
ssh -L 18080:127.0.0.1:18080 user@server
# потім відкрий http://127.0.0.1:18080
# dry-run: freqtrader / dry-run-only-password (config.dryrun.json)
# live: логін/пароль з config/freqtrade/config.private.json
```

Що перевіряти щодня:

- бот живій (`make ps`), healthcheck не в `unhealthy`;
- у логах немає помилок ордерів;
- сигнали з'являються, угоди відкриваються/закриваються;
- фактичні ціни входу близькі до очікуваних.

### Змінити стратегію

```bash
make stop
make dryrun STRATEGY=RsiReversion
```

### Скинути стан dry-run

Історія dry-run лежить у `user_data/tradesv3.dryrun.sqlite`. Якщо хочеш почати з чистого
аркуша (наприклад, після зміни стратегії):

```bash
make stop
mv user_data/tradesv3.dryrun.sqlite user_data/tradesv3.dryrun.sqlite.bak
make dryrun STRATEGY=RsiReversion
```

## 7. Live (тільки після 2–4 тижнів dry-run)

Чекліст:

- [ ] dry-run пропрацював 2–4 тижні без технічних збоїв;
- [ ] бектест і dry-run дають схожу картину;
- [ ] API-ключ створений з правом `trade`, **без** `withdraw`;
- [ ] IP-whitelist на біржі налаштований;
- [ ] `config/freqtrade/config.private.json` заповнений, `chmod 600`;
- [ ] є Telegram-алерти або зовнішній heartbeat;
- [ ] є бекап `user_data/tradesv3.sqlite` і конфігів;
- [ ] сума, яку не страшно втратити.

```bash
make live STRATEGY=TaBaseline
make logs
```

Перші 24 години — стежити вручну. Зупинка:

```bash
make stop
```

## 8. Оновлення після `git push`

```bash
make deploy
```

Це робить `git pull --ff-only`, `docker compose pull`, перезапуск dry-run сервісу.

## 9. Типові проблеми

| Симптом | Причина / рішення |
|---|---|
| `permission denied` на `user_data` | `sudo chown -R 1000:1000 user_data` |
| `port is already allocated` | інший сервіс на цьому порту; зміни `FREQTRADE_DRYRUN_PORT`/`FREQTRADE_LIVE_PORT` у `.env` |
| `No data found` у Freqtrade-бектесті | `make download` з тим самим `TIMERANGE`/`TIMEFRAME` |
| `pair not found` | перевір `pair_whitelist` у `config/freqtrade/config.dryrun.json` |
| контейнер постійно рестартиться | `make logs`; найчастіше — незаповнений `config.private.json` або поганий конфіг |
| `Invalid API key` при live | ключ без прав `trade`, невірний IP-whitelist, не той акаунт |
| бектест раптом «ідеально» прибутковий | перевір діри в даних (`make data-validate`) і що комісія не 0 |
| час на сервері плаває | `timedatectl`, `chronyc tracking` |

## 10. Куди дивитись далі

- `docs/architecture.md` — чому саме така архітектура;
- `research/runs/*/metrics.json` — накопичуй результати й порівнюй стратегії;
- після стабільного TA-бейзлайну — ML meta-labeling (`research/splits.py` вже готовий).
