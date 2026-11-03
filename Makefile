SHELL := /bin/bash
.DEFAULT_GOAL := help

# Pick up STRATEGY/TIMEFRAME/exchange overrides from .env when present.
-include .env

EXCHANGE ?= binance
SYMBOL ?= BTC/USDT
TIMEFRAME ?= 1h
STRATEGY ?= TaBaseline
export STRATEGY
TIMERANGE ?= 20240101-20240630
SINCE ?= 2023-01-01
UNTIL ?= 2024-01-01
FEE ?= 0.001
DATA_DIR ?= data
RUN_DIR ?= research/runs
FREQTRADE_DRYRUN_PORT ?= 18080
FREQTRADE_LIVE_PORT ?= 18081
export FREQTRADE_DRYRUN_PORT
export FREQTRADE_LIVE_PORT
DOMAIN ?=
EMAIL ?=
NGINX_PORT ?= $(FREQTRADE_DRYRUN_PORT)
FREQTRADE_CONFIG ?= /freqtrade/config/config.dryrun.json
COMPOSE ?= docker compose
FREQTRADE_RUN := $(COMPOSE) run --rm --no-deps trading
STRATEGY_PATH := /opt/mycryptotrader/src/mycryptotrader/strategies

.PHONY: help install lock fmt format-check lint typecheck test test-cov ci \
	data-demo data-download data-validate data-list data-sql backtest \
	download backtest-ft dryrun up live stop restart ps logs shell \
	build deploy clean clean-runs nginx nginx-tls nginx-remove

help: ## Показати цю довідку
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage: make <target>\n\n"} /^[a-zA-Z0-9_-]+:.*##/ {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

install: ## Локальне оточення (uv sync)
	uv sync

lock: ## Оновити uv.lock
	uv lock

fmt: ## Форматування + автовиправлення
	uv run ruff format .
	uv run ruff check --fix .

format-check: ## Перевірка форматування (без змін)
	uv run ruff format --check .

lint: ## Перевірка стилю
	uv run ruff check .

typecheck: ## Перевірка типів
	uv run mypy src

test: ## Юніт-тести
	uv run pytest

test-cov: ## Тести з покриттям
	uv run pytest --cov=mycryptotrader --cov-report=term-missing

ci: lint format-check typecheck test ## Те саме, що в CI

data-demo: ## Синтетичні свічки (офлайн)
	uv run mycryptotrader --data-dir $(DATA_DIR) data demo --exchange $(EXCHANGE) --symbol "$(SYMBOL)" --timeframe $(TIMEFRAME) --days 365

data-download: ## Історія через ccxt
	uv run mycryptotrader --data-dir $(DATA_DIR) data download --exchange $(EXCHANGE) --symbol "$(SYMBOL)" --timeframe $(TIMEFRAME) --since $(SINCE) --until $(UNTIL)

data-validate: ## Перевірка дір/дублів у даних
	uv run mycryptotrader --data-dir $(DATA_DIR) data validate --exchange $(EXCHANGE) --symbol "$(SYMBOL)" --timeframe $(TIMEFRAME)

data-list: ## Список датасетів
	uv run mycryptotrader --data-dir $(DATA_DIR) data list

data-sql: ## SQL через DuckDB: make data-sql SQL="select ..."
	uv run mycryptotrader --data-dir $(DATA_DIR) data sql "$(SQL)"

backtest: ## Research-бектест + артефакти
	uv run mycryptotrader --data-dir $(DATA_DIR) backtest --strategy $(STRATEGY) --exchange $(EXCHANGE) --symbol "$(SYMBOL)" --timeframe $(TIMEFRAME) --fee $(FEE) --out $(RUN_DIR)/$(STRATEGY)-$(shell date -u +%Y%m%dT%H%M%SZ)

download: ## Freqtrade: завантажити свічки для бектесту
	$(FREQTRADE_RUN) download-data --config $(FREQTRADE_CONFIG) --timeframes $(TIMEFRAME) --timerange $(TIMERANGE)

backtest-ft: ## Freqtrade-бектест у Docker
	$(FREQTRADE_RUN) backtesting --config $(FREQTRADE_CONFIG) --strategy $(STRATEGY) --strategy-path $(STRATEGY_PATH) --timerange $(TIMERANGE) --enable-protections

dryrun: ## Підняти dry-run бота
	$(COMPOSE) up -d trading
	@echo "Dry-run started. Logs: make logs | UI: http://127.0.0.1:$(FREQTRADE_DRYRUN_PORT)"

up: dryrun ## Аліас для dryrun

live: ## LIVE-торгівля (питає підтвердження)
	@test -f config/freqtrade/config.private.json || (echo "Missing config/freqtrade/config.private.json"; echo "Copy config.private.example.json, fill it and run: chmod 600 config/freqtrade/config.private.json"; exit 1)
	@read -r -p "Start LIVE trading with real funds? [y/N] " ans; [ "$$ans" = "y" ] || (echo "aborted"; exit 1)
	$(COMPOSE) --profile live up -d trading-live

stop: ## Зупинити всі контейнери
	$(COMPOSE) --profile live down

restart: ## Перезапустити dry-run
	$(COMPOSE) restart trading

ps: ## Статус контейнерів
	$(COMPOSE) --profile live ps

logs: ## Логи dry-run бота
	$(COMPOSE) logs -f --tail=200 trading

shell: ## Shell у контейнері
	$(COMPOSE) run --rm --no-deps --entrypoint bash trading

build: ## Оновити образ Freqtrade
	$(COMPOSE) pull

deploy: ## Сервер: git pull + рестарт
	git pull --ff-only
	$(COMPOSE) pull
	$(COMPOSE) up -d --remove-orphans trading

nginx: ## Nginx reverse proxy: make nginx DOMAIN=freq.example.com
	@test -n "$(DOMAIN)" || (echo "Usage: make nginx DOMAIN=freq.example.com [NGINX_PORT=18080]"; exit 1)
	@sudo sh ops/nginx/install.sh "$(DOMAIN)" "$(NGINX_PORT)"

nginx-tls: ## TLS via Let's Encrypt: make nginx-tls DOMAIN=freq.example.com EMAIL=you@example.com
	@test -n "$(DOMAIN)" || (echo "Usage: make nginx-tls DOMAIN=freq.example.com EMAIL=you@example.com"; exit 1)
	@test -n "$(EMAIL)" || (echo "EMAIL is required"; exit 1)
	@case "$(DOMAIN)" in *.local|*.internal|*.lan|*.home.arpa) \
		echo "ERROR: Let's Encrypt cannot issue certificates for $(DOMAIN)."; \
		echo "Use a public domain, or a self-signed/mkcert certificate for local access."; \
		exit 1;; \
	esac
	sudo apt-get update
	sudo apt-get install -y certbot python3-certbot-nginx
	sudo certbot --nginx -d "$(DOMAIN)" --non-interactive --agree-tos -m "$(EMAIL)" --redirect

nginx-remove: ## Видалити nginx-сайт: make nginx-remove DOMAIN=freq.example.com
	@test -n "$(DOMAIN)" || (echo "Usage: make nginx-remove DOMAIN=freq.example.com"; exit 1)
	sudo sh ops/nginx/remove.sh "$(DOMAIN)"

clean: ## Прибрати кеші
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage

clean-runs: ## Прибрати артефакти research
	rm -rf $(RUN_DIR)
