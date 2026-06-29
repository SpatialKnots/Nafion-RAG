up:
	docker compose up --build

migrate:
	python -m alembic upgrade head

test:
	pytest -q

lint:
	ruff check .
	ruff format --check .
	mypy app
