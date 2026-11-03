# Архітектура та рішення

## 1. Чому Freqtrade, а не власний рушій

Стратегії — TA на свічках + ML на spot Binance/Bybit. Freqtrade закриває весь цикл
(`download-data`, `backtesting`, `hyperopt`, dry-run, live, FreqUI, Telegram, Docker) і
перевірений на довгих аптаймах. NautilusTrader сильніший у мікроструктурі, але для свічкового
споту це передчасне ускладнення. Execution-шар ізольований, тож замінити його пізніше можна
без переписування research-коду.

## 2. Три шари і один контракт

```
data  →  research  →  execution
```

Контракт між research і execution — це функція `add_signals(df) -> df` у
`src/mycryptotrader/signals/`. Вона:

- не робить I/O, не ходить у мережу, не знає про біржу;
- працює на pandas DataFrame (саме це Freqtrade передає стратегії);
- використовується і бектестером, і Freqtrade-обгорткою.

polars/DuckDB — тільки для масових операцій із даними, не для самих фічей. Це прибирає
train/serve skew: та сама функція, ті самі числа.

## 3. Дані

- Parquet, Hive-партиції `exchange=/symbol=/timeframe=/year=/month=`, UTC epoch ms.
- DuckDB читає store напряму (`make data-sql`), без окремого сервера БД.
- `validate_ohlcv` перевіряє діри, дублі, null, некоректні OHLC. Бектест на битих даних
  блокується.
- Ідемпотентний upsert: повторне завантаження не створює дублів.

## 4. Бектестер

Навмисно маленький:

- long-only spot, одна позиція, повний капітал;
- сигнал на закритті бару `t`, вхід/вихід по **open** бару `t+1`;
- комісія з обох боків;
- примусове закриття відкритої позиції на останньому close;
- метрики: total return, CAGR, Sharpe, Sortino, max drawdown, Calmar, win rate, profit factor,
  exposure, buy & hold.

Для реалістичної симуляції ордерів використовується Freqtrade. Цей бектестер — для швидкої
перевірки гіпотез і тестів на lookahead.

## 5. Захист від lookahead

Окремий тест: рахуємо фічі/сигнали на повному датасеті й на обрізаному. Значення на спільному
префіксі мусять збігатися. Той самий принцип для бектестера: equity на префіксі не змінюється
від майбутніх барів.

## 6. ML (наступний етап)

- спочатку стабільний TA-бейзлайн;
- далі **meta-labeling**: TA дає напрямок, модель — ймовірність успіху й розмір;
- walk-forward з purge/embargo (`research/splits.py`);
- scaling/відбір фічей тільки на train;
- оцінка після комісій, з поправкою на множинне тестування.

## 7. Деплой

- Docker Compose, офіційний образ Freqtrade (pinned via `FREQTRADE_IMAGE`).
- Код монтується в контейнер (`PYTHONPATH`), тому зміна стратегії не потребує rebuild.
- API/FreqUI — тільки на `127.0.0.1`, назовні не світити.
- chrony/UTC, ufw, fail2ban, бекапи SQLite, зовнішній heartbeat.
- dry-run і live — окремі сервіси/БД; одночасно не запускати.

## 8. Що далі

1. ML meta-labeling + збереження артефактів моделі.
2. Feature store-версіонування (DVC або manifest із хешами).
3. Prometheus/Grafana + алерти.
4. Портфельний розподіл капіталу між парами.
5. За потреби — NautilusTrader для futures/HFT.
