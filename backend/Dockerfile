###############################################################################
# Backend (FastAPI) — build multi-stage
#   Etapa 1 "builder": instala las dependencias de Python en un virtualenv aislado.
#   Etapa 2 "runtime": copia solo el venv + el código de la app sobre una base
#                      liviana y corre como usuario no-root.
# Esto mantiene la imagen final pequeña y libre de compiladores/headers (menor
# superficie de ataque).
###############################################################################

# ---- Etapa 1: builder -------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Construye el venv en una capa que solo cambia cuando cambian los requirements.
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---- Etapa 2: runtime -------------------------------------------------------
FROM python:3.12-slim AS runtime

# Build args convertidos en metadatos de runtime (ver main.py).
ARG APP_VERSION=dev
ARG GIT_SHA=unknown

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_VERSION=${APP_VERSION} \
    GIT_SHA=${GIT_SHA}

# Usuario dedicado sin privilegios (uid 10001) — nunca correr como root.
RUN groupadd --system --gid 10001 appuser \
    && useradd --system --uid 10001 --gid appuser --no-create-home appuser

WORKDIR /app

# Solo el venv y el código fuente de la aplicación llegan a la imagen final.
COPY --from=builder /opt/venv /opt/venv
COPY app/ ./app/

EXPOSE 8000
USER 10001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
