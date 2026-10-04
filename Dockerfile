FROM node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY --from=frontend /app/backend/app/static/frontend ./backend/app/static/frontend
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini

# Migrate, create the demo user when configured, then serve.
CMD ["sh", "-c", "python -m alembic upgrade head && python -m backend.app.seed_demo && exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
