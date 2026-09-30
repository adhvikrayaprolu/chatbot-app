FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home appuser
COPY app.py gpt_handler.py storage.py ./
COPY templates/ templates/
COPY static/ static/
RUN mkdir instance && chown -R appuser:appuser /app
USER appuser
EXPOSE 5000
HEALTHCHECK --interval=10s --timeout=8s --start-period=10s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=6).close()"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "30", "app:create_app()"]
