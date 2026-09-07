# SongQueue - Makefile

.PHONY: help install dev test lint fmt migrate seed up down logs

help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Instala dependencias
	pip install -r requirements.txt

dev: ## Levanta el servidor en modo desarrollo
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test: ## Ejecuta tests con cobertura mínima
	pytest -q --cov=src --cov-fail-under=50

lint: ## Revisa formato y lint (igual que CI)
	black --check src/ tests/
	isort --check-only src/ tests/
	flake8 src/ tests/ --max-line-length=120 --extend-ignore=E203,W503

fmt: ## Formatea código
	black src/ tests/
	isort src/ tests/

migrate: ## Ejecuta migraciones
	alembic upgrade head

seed: ## Puebla datos de ejemplo (manual/dev)
	python seed_data.py

up: ## Levanta todo con Docker Compose
	docker compose up -d --build

down: ## Detiene Docker Compose
	docker compose down

tunnel: ## Levanta todo + túnel Cloudflare (requiere CLOUDFLARE_TUNNEL_TOKEN y SERVER_BASE_URL)
	docker compose --profile tunnel up -d --build

logs: ## Muestra logs de la app
	docker compose logs -f app
