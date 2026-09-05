# RazorRecover development commands
#
# Requires: Python 3.10+, Node.js 18+, Docker/Redis for the full stack.

.PHONY: install test run celery frontend-install frontend-typecheck frontend-build frontend-dev

install: ## Install backend dependencies (Python)
	pip install -r requirements.txt
	pip install -e .

test: ## Run the backend test suite (unit + integration; skips unavailable services)
	pytest

run: ## Start the API server on http://localhost:8000
	uvicorn razor_recover.main:app --app-dir src --reload --port 8000

celery: ## Start the async recovery Celery worker (note: --pool=solo is for Windows)
	celery -A razor_recover.tasks.celery_app:celery_app worker --pool=solo --loglevel=info

frontend-install: ## Install frontend dependencies (npm)
	cd frontend && npm install

frontend-typecheck: ## Typecheck the frontend
	cd frontend && npm run typecheck

frontend-build: ## Production-build the frontend
	cd frontend && npm run build

frontend-dev: ## Start the frontend dev server on http://localhost:5173
	cd frontend && npm run dev
