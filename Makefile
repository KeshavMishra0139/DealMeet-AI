.PHONY: dev demo setup test shots e2e reset

# Start API (:8000) and web (:5173). Installs dependencies on first run.
dev:
	node scripts/dev.mjs

# Build the web app and serve everything from one port (:8000), no hot reload.
demo:
	node scripts/dev.mjs --single-port

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

# Click through the key journeys in a real browser (needs `make dev` running).
e2e:
	npm install --no-audit --no-fund --silent
	node qa/flows.mjs

# Reset the in-memory demo data while the app is running.
reset:
	curl -s -X POST -H "X-Requested-With: make" http://localhost:8000/api/demo/reset
