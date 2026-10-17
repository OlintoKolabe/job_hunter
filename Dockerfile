FROM node:22-alpine AS frontend
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY index.html vite.config.js ./
COPY src ./src
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m playwright install --with-deps chromium
COPY app.py collectors.py catalog_engine.py source_extensions.py catalog_bootstrap.py scrapling_fallback.py catalog_seed.json test_phase3.py ./
RUN python -m compileall -q app.py collectors.py catalog_engine.py source_extensions.py catalog_bootstrap.py scrapling_fallback.py test_phase3.py && python -m unittest -q test_phase3
COPY --from=frontend /app/dist ./dist
EXPOSE 10000
CMD ["sh","-c","uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
