.PHONY: help up down reset migrate load discover parse api web eval test lint
DIR ?= data/raw
PORT ?= 8000
WEB_PORT ?= 3000

help:
	@grep -E '^[a-z-]+:.*##' Makefile | sed 's/:.*##/\t/'

up:        ## start postgres and adminer
	docker compose up -d
	@until docker compose exec -T db pg_isready -U postgres -d rentroll >/dev/null 2>&1; \
	  do sleep 1; done
	@echo "db ready on :5432  |  adminer on :8080"

down:      ## stop containers
	docker compose down

reset:     ## wipe the database and rebuild an empty schema
	docker compose down -v
	$(MAKE) up
	$(MAKE) migrate

migrate:   ## apply pending migrations
	python -m ingest.migrate

discover:  ## profile the source files (no db)
	python scripts/discover.py

parse:     ## run both parsers across all 50 files and reconcile (no db)
	python scripts/batch_parse.py

api:       ## run the fastapi dev server (PORT=8000 by default)
	uvicorn api.app:app --reload --port $(PORT)

web:       ## run the old next 14 dashboard in web/ (WEB_PORT=3000)
	cd web && npm run dev -- --port $(WEB_PORT)

dashboard: ## run the next 16 dashboard in dashboard-app/ (WEB_PORT=3000)
	cd dashboard-app && npx next dev --port $(WEB_PORT)

load:      ## parse and load all excel files (idempotent by file hash)
	python -m ingest --dir $(DIR)

eval:      ## run the golden question set
	python -m evals.run

test:
	pytest -q

lint:
	ruff check . && ruff format --check .