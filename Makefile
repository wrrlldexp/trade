.PHONY: help init up down restart logs ps build rebuild migrate makemigration superadmin test lint format clean

help:
	@echo "MoneyBot v2 — доступные команды:"
	@echo ""
	@echo "  make init           — первичная настройка (.env, ключи)"
	@echo "  make up             — запустить все сервисы"
	@echo "  make down           — остановить все сервисы"
	@echo "  make restart        — перезапустить"
	@echo "  make logs           — смотреть логи всех сервисов"
	@echo "  make logs-backend   — логи только backend"
	@echo "  make logs-worker    — логи только worker"
	@echo "  make ps             — статус сервисов"
	@echo "  make build          — собрать образы"
	@echo "  make rebuild        — пересобрать образы с нуля"
	@echo ""
	@echo "  make migrate        — применить миграции БД"
	@echo "  make makemigration m=\"описание\" — создать новую миграцию"
	@echo "  make superadmin     — создать первого суперадмина"
	@echo ""
	@echo "  make test           — запустить тесты"
	@echo "  make lint           — проверить код линтерами"
	@echo "  make format         — отформатировать код"
	@echo ""
	@echo "  make clean          — удалить контейнеры и volume (ОСТОРОЖНО)"

init:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✓ Создан .env из .env.example"; \
		echo ""; \
		echo "Теперь сгенерируй секреты и впиши их в .env:"; \
		echo ""; \
		echo "  JWT_SECRET:"; \
		openssl rand -hex 32; \
		echo ""; \
		echo "  ENCRYPTION_KEY:"; \
		python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "  (установи python cryptography: pip install cryptography)"; \
	else \
		echo ".env уже существует"; \
	fi

up:
	docker compose up -d
	@echo ""
	@echo "✓ Сервисы запущены."
	@echo "  Backend:  http://localhost:$${BACKEND_PORT:-8000}/docs"
	@echo "  Frontend: http://localhost:$${FRONTEND_PORT:-5173}"

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-worker:
	docker compose logs -f worker

ps:
	docker compose ps

build:
	docker compose build

rebuild:
	docker compose build --no-cache

migrate:
	docker compose exec backend alembic upgrade head

makemigration:
	docker compose exec backend alembic revision --autogenerate -m "$(m)"

superadmin:
	docker compose exec backend python -m cli.create_superadmin

test:
	docker compose exec backend pytest -v

lint:
	docker compose exec backend ruff check app worker cli tests
	docker compose exec backend mypy app worker cli

format:
	docker compose exec backend ruff format app worker cli tests
	docker compose exec backend ruff check --fix app worker cli tests

clean:
	docker compose down -v
	@echo "✓ Контейнеры и volume удалены"
