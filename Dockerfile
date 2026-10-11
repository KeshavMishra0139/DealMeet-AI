# JodiDar AI as one container: the API serves the built web app on $PORT.
# Build:  docker build -t jodidar-ai .
# Run:    docker run -p 8000:8000 jodidar-ai   ->  http://localhost:8000

# 1) Build the web app (Vite). The copy-rules check reads shared/.
FROM node:22-slim AS web
WORKDIR /app
COPY shared ./shared
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci --no-audit --no-fund
COPY frontend ./frontend
# Optional Google sign-in: Vite bakes VITE_* values in at build time.
ARG VITE_FIREBASE_API_KEY=""
ARG VITE_FIREBASE_AUTH_DOMAIN=""
ARG VITE_FIREBASE_PROJECT_ID=""
ARG VITE_FIREBASE_APP_ID=""
RUN cd frontend && npm run build

# 2) The API, with the built app next to it.
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # This image runs the shared demo: seeded personas and demo sign-in (DEMO_MODE=1),
    # put back to its seeded state every 30 minutes (skipped while someone is
    # mid-walkthrough). Set DEMO_MODE=0 on the host for real accounts only.
    DEMO_MODE=1 \
    DEMO_RESET_MINUTES=30
WORKDIR /app
COPY backend/requirements.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/app ./backend/app
COPY shared ./shared
COPY --from=web /app/frontend/dist ./frontend/dist
WORKDIR /app/backend
EXPOSE 8000
# One worker and one instance: the demo data lives in this process's memory.
CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
