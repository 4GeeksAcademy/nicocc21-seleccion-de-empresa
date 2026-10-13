# services/Dockerfile — Imagen para el backend Brasaland (FastAPI + WSGI legacy)
FROM python:3.12-slim

# Evitar .pyc y buffers
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Dependencias del sistema (psycopg2 necesita gcc/libpq)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar e instalar dependencias Python
COPY services/brasaland_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la API
COPY services/brasaland_api/ ./services/brasaland_api/
COPY services/__init__.py ./services/__init__.py
COPY packages/ ./packages/

# Script de arranque
COPY services/start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 8000 8001

CMD ["/start.sh"]