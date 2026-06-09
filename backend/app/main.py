"""API de Backend — reto-devops.

Un servicio FastAPI mínimo y con pocas dependencias al que el frontend (Nginx)
redirige sus llamadas `/api/*`. Se mantiene intencionalmente pequeño para que la
imagen del contenedor sea liviana y la superficie de ataque mínima.
"""
import os
import socket

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Los metadatos de build se inyectan al construir la imagen vía variables de entorno,
# para que cada imagen inmutable pueda reportar exactamente qué commit la produjo.
APP_VERSION = os.getenv("APP_VERSION", "dev")
GIT_SHA = os.getenv("GIT_SHA", "unknown")

app = FastAPI(
    title="reto-devops Backend API",
    version=APP_VERSION,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    """Objetivo de las probes de liveness/readiness. Barato y sin efectos secundarios."""
    return {"status": "ok"}


@app.get("/api/info")
def info() -> dict:
    """Devuelve metadatos de build + runtime para que la UI pueda demostrar qué imagen corre."""
    return {
        "service": "backend",
        "version": APP_VERSION,
        "git_sha": GIT_SHA,
        "hostname": socket.gethostname(),
    }


@app.get("/api/message")
def message() -> dict:
    """El único endpoint de negocio que renderiza el frontend."""
    return {
        "message": "Hola desde la API del backend de reto-devops 👋... Probando cambio",
        "version": APP_VERSION,
        "git_sha": GIT_SHA,
    }
