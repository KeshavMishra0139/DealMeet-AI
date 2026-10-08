.PHONY: dev setup test shots demo reset

# Start API (:8000) and web (:5173). Installs dependencies on first run.
dev:
	node scripts/dev.mjs

# Install dependencies only.
setup:
	node scripts/dev.mjs --setup-only

# Engines, copy rules (no guarantees), no-scraping check, type check.
test:
	node scripts/test.mjs

# Screenshot every screen at 390 px and 1440 px (needs `make dev` running).
shots:
	npm install --no-audit --no-fund --silent
	node qa/screenshots.mjs

# Reset the in-memory demo data while the app is running.
reset:
	curl -s -X POST http://localhost:8000/api/demo/reset
