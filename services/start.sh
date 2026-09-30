#!/bin/sh
# start.sh — Lanza el servidor WSGI (incidencias) y el FastAPI (uvicorn)
# en segundo plano dentro del mismo contenedor.
# Atrapa SIGTERM para apagado graceful de ambos procesos.

set -e

echo "=== Iniciando servidor WSGI (incidencias) en puerto 8000 ==="
python3 /app/services/brasaland_api/app.py &
PID_WSGI=$!

echo "=== Iniciando FastAPI (uvicorn) en puerto 8001 ==="
cd /app
python3 -m uvicorn services.brasaland_api.main:app \
    --host 0.0.0.0 \
    --port 8001 \
    --reload &
PID_UVICORN=$!

# Trap SIGTERM/SIGINT: apagar ambos procesos ordenadamente
trap 'echo "Apagando servicios..."; kill $PID_WSGI $PID_UVICORN 2>/dev/null; wait $PID_WSGI $PID_UVICORN 2>/dev/null; exit 0' INT TERM

# Esperar a que cualquier proceso hijo termine
wait