run:
	python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

worker:
	python -m app.workers.worker

migrate:
	python -m alembic upgrade head

test:
	pytest -q

lint:
	ruff check .
	ruff format --check .
	mypy app
