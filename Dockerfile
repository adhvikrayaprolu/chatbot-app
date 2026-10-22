FROM rust:1.99-slim AS retrieval
WORKDIR /build
COPY retrieval/ .
RUN cargo build --locked --release
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ .
RUN npm run build
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home appuser
COPY --from=retrieval /build/target/release/document-retrieval /usr/local/bin/document-retrieval
# Revision-pinned tokenizer so evidence budgets match native runs.
RUN python -c "import urllib.request; urllib.request.urlretrieve('https://huggingface.co/Qwen/Qwen3-4B/resolve/1cfa9a7208912126459214e8b04321603b3df60c/tokenizer.json', '/usr/local/share/tokenizer.json')"
ENV RETRIEVAL_BIN=/usr/local/bin/document-retrieval LOCAL_TOKENIZER=/usr/local/share/tokenizer.json
COPY app.py providers.py storage.py knowledge.py strategies.py observability.py ./
COPY --from=web /web/dist web/dist/
COPY fixtures/ fixtures/
RUN mkdir instance && chown -R appuser:appuser /app
USER appuser
EXPOSE 5000
HEALTHCHECK --interval=10s --timeout=8s --start-period=10s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=6).close()"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "600", "app:create_app()"]
