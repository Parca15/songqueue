# SongQueue - Makefile

.PHONY: help install dev test migrate seed up down logs fmt

help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Instala dependencias
	pip install -r requirements.txt

dev: ## Levanta el servidor en modo desarrollo
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test: ## Ejecuta tests
	pytest -v

migrate: ## Ejecuta migraciones
	alembic upgrade head

seed: ## Puebla datos de prueba
	python seed_data.py

up: ## Levanta todo con Docker Compose
	docker-compose up -d

down: ## Detiene Docker Compose
	docker-compose down

logs: ## Muestra logs de la app
	docker-compose logs -f app

fmt: ## Formatea código
	black src/ tests/
	isort src/ tests/
