# StreamStudio — developer entry points. Run on the Mac Studio.
PY := server/.venv/bin/python

.PHONY: setup setup-media dev api worker web build test lint mac-app

setup:            ## install everything (python venv with the episode extra + Playwright Chromium + node modules)
	cd server && uv sync -p 3.12 --extra episode
	server/.venv/bin/playwright install chromium
	cd web && npm install

setup-media:      ## also the offline media tools (cut-out, dissolve, opener): large download
	cd server && uv sync -p 3.12 --extra media

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
	cd web && npx tsc -b && npx oxlint

mac-app:          ## install StreamStudio.app into ~/Applications (macOS)
	mkdir -p ~/Applications && rm -rf ~/Applications/StreamStudio.app && cp -R mac/StreamStudio.app ~/Applications/ && chmod +x ~/Applications/StreamStudio.app/Contents/MacOS/StreamStudio
