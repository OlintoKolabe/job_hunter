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
COPY first_seen.py public_remote_feeds.py app.py collectors.py catalog_engine.py source_extensions.py catalog_bootstrap.py scrapling_fallback.py search_filters.py jd_signals.py block4_score.py jd_enrichment.py jd_retrieval.py ai_interpreter.py score_repository.py resume_engine.py resume_hybrid.py catalog_seed.json test_phase3.py ./
COPY scripts/check_scope.py ./scripts/check_scope.py
COPY tests/test_publication_period.py tests/test_br_source_expansion.py tests/test_quickin_public_api.py tests/test_first_seen.py tests/test_public_remote_feeds.py tests/test_block4_1.py tests/test_resume_engine.py tests/test_resume_hybrid.py tests/test_terminal_history_exclusion.py tests/test_disposition_buttons.py tests/test_source_identity.py tests/test_source_coverage.py tests/test_jd_role_recall.py tests/test_out_of_filter_decisions.py tests/test_search_500_regression.py ./tests/
RUN python -m compileall -q first_seen.py public_remote_feeds.py app.py collectors.py catalog_engine.py source_extensions.py catalog_bootstrap.py scrapling_fallback.py search_filters.py jd_signals.py block4_score.py jd_enrichment.py test_phase3.py && python -m unittest discover -s tests -p test_publication_period.py -q && python -m unittest discover -s tests -p test_br_source_expansion.py -q && python -m unittest discover -s tests -p test_quickin_public_api.py -q && python -m unittest discover -s tests -p test_first_seen.py -q && python -m unittest discover -s tests -p test_public_remote_feeds.py -q && python -m unittest -q test_phase3 && python -m unittest discover -s tests -p test_terminal_history_exclusion.py -q && python -m unittest discover -s tests -p test_disposition_buttons.py -q && python -m unittest discover -s tests -p test_source_identity.py -q && python -m unittest discover -s tests -p test_source_coverage.py -q && python -m unittest discover -s tests -p test_jd_role_recall.py -q && python -m unittest discover -s tests -p test_out_of_filter_decisions.py -q && python -m unittest discover -s tests -p test_search_500_regression.py -q && python -m unittest discover -s tests -p test_block4_1.py -q && python -m unittest discover -s tests -p test_resume_engine.py -q && python -m unittest discover -s tests -p test_resume_hybrid.py -q
COPY --from=frontend /app/dist ./dist
EXPOSE 10000
CMD ["sh","-c","uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
