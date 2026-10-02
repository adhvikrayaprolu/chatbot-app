FROM rust:1.99-slim AS retrieval
WORKDIR /build
COPY retrieval/ .
RUN cargo build --locked --release
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home appuser
COPY --from=retrieval /build/target/release/document-retrieval /usr/local/bin/document-retrieval
ENV RETRIEVAL_BIN=/usr/local/bin/document-retrieval
COPY app.py gpt_handler.py storage.py knowledge.py strategies.py observability.py ./
COPY templates/ templates/
COPY static/ static/
COPY fixtures/ fixtures/
RUN mkdir instance && chown -R appuser:appuser /app
USER appuser
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "600", "app:create_app()"]
