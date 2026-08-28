# Etapa 1: Build
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Etapa 2: Runtime
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ffmpeg para el re-mux de streams de YouTube (fallback HTML5)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copiar dependencias instaladas
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copiar codigo fuente
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY seed_data.py .
COPY entrypoint.sh .

# Hacer ejecutable el script
RUN chmod +x entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
