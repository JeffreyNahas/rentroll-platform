.PHONY: help up down reset migrate load discover eval test lint
DIR ?= data/raw

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

load:      ## parse and load all excel files
	python -m ingest load --dir $(DIR)

eval:      ## run the golden question set
	python -m evals.run

test:
	pytest -q

lint:
	ruff check . && ruff format --check .