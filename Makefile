# StreamStudio — developer entry points. Run on the Mac Studio.
PY := server/.venv/bin/python

.PHONY: setup dev api worker web build test lint

setup:            ## install everything (python venv + node modules)
	cd server && uv venv -p 3.12 .venv && uv pip install -e . --group dev
	cd web && npm install

dev:              ## api + worker + vite dev server with hot reload
	@trap 'kill 0' EXIT; \
	$(MAKE) -s api & $(MAKE) -s worker & cd web && npm run dev

api:              ## FastAPI on :8787 (localhost + tailnet)
	$(PY) -m streamstudio.api.main

worker:           ## job worker
	$(PY) -m streamstudio.worker.main

web:              ## vite dev server only
	cd web && npm run dev

build:            ## production web build (served by the api at /)
	cd web && npm run build

test:             ## all tests
	cd server && .venv/bin/python -m pytest
	cd web && npx vitest run

lint:
	cd server && .venv/bin/ruff check src tests
	cd web && npx tsc -b
