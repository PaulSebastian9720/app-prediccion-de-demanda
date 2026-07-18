.PHONY: install dev lint format test test-unit test-integration migrate migrate-new \
	seed seed-catalog create-admin db-up docker-build docker-up docker-down docker-logs locust clean

install:
	uv sync

dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

lint:
	uv run ruff check src tests scripts
	uv run mypy src

format:
	uv run ruff check --fix src tests scripts
	uv run ruff format src tests scripts

test:
	uv run pytest

test-unit:
	uv run pytest tests/unit -v

test-integration:
	uv run pytest tests/integration -v

migrate:
	uv run alembic upgrade head

migrate-new:
	uv run alembic revision --autogenerate -m "$(name)"

seed:
	uv run python scripts/seed_sales_history.py

seed-catalog:
	uv run python scripts/seed_products_and_stock.py

create-admin:
	uv run python scripts/create_admin.py

db-up:
	docker compose -f ../docker/compose.yml up -d

docker-build:
	docker compose build

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f backend

locust:
	uv run locust -f tests/load/locustfile.py --headless \
		-u 20 -r 5 --run-time 60s \
		--host http://localhost:8000

clean:
	find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
