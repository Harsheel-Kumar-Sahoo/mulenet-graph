# SYNTHETIC-DATA DEMO image. Stage 1 builds the React dashboard if present (Phase 5); stage 2 runs the API.
FROM node:20-alpine AS ui
WORKDIR /ui
COPY frontend/ ./
RUN if [ -f package.json ]; then npm install --no-audit --no-fund && npm run build; else mkdir -p dist; fi

FROM python:3.11-slim
WORKDIR /app
COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt
COPY mulenet ./mulenet
COPY config.yaml .
COPY checkpoints ./checkpoints
COPY --from=ui /ui/dist ./frontend/dist
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn mulenet.api.app:app --host 0.0.0.0 --port ${PORT}"]
