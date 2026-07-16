COMPOSE = docker compose --env-file .env.example -f docker-compose.yml -f docker-compose.development.yml

.PHONY: dev down logs test lint typecheck contracts

dev:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

test:
	uv run pytest -m "not integration" && pnpm test

lint:
	uv run ruff check apps && pnpm lint

typecheck:
	uv run mypy apps/api apps/worker && pnpm typecheck

contracts:
	pnpm contracts:generate
