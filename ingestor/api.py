"""API FastAPI del microservicio de ingestión de personajes."""

from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, Query

from ingestor import config, repositorio, servicio
from ingestor.modelos import Personaje, ResumenSync

app = FastAPI(
    title="Ingestor API",
    description="Microservicio de ingestión de la API de Rick and Morty hacia PostgreSQL",
    version="0.1.0",
)


# ------------------------------------------------------------------
# Dependencia de conexión a la base de datos
# ------------------------------------------------------------------

def obtener_conexion() -> Generator[psycopg.Connection, None, None]:
    """Abre una conexión psycopg por request y la cierra al terminar."""
    with psycopg.connect(config.dsn_bd()) as conexion:
        yield conexion


ConexionDep = Annotated[psycopg.Connection, Depends(obtener_conexion)]


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@app.get("/salud", tags=["sistema"])
def salud() -> dict:
    """Verifica que el servicio está en línea."""
    return {"estado": "ok"}


@app.post("/sincronizar", response_model=ResumenSync, tags=["ingestión"])
def sincronizar(incremental: bool = False) -> ResumenSync:
    """Ejecuta una sincronización completa o incremental desde la API de Rick and Morty."""
    return servicio.sincronizar(config.dsn_bd(), incremental=incremental)


@app.get("/estado", tags=["monitoreo"])
def estado(conexion: ConexionDep) -> dict:
    """Devuelve estadísticas básicas de los datos en la base de datos."""
    return {
        "total_en_bd": repositorio.contar(conexion),
        "max_id": repositorio.max_id(conexion),
    }


@app.get("/personajes", response_model=list[Personaje], tags=["datos"])
def personajes(
    conexion: ConexionDep,
    especie: str | None = Query(default=None, description="Filtrar por especie"),
    estado: str | None = Query(default=None, description="Filtrar por estado"),
    limite: int = Query(default=50, ge=1, le=200, description="Máximo de resultados"),
    offset: int = Query(default=0, ge=0, description="Desplazamiento para paginación"),
) -> list[Personaje]:
    """Lista personajes con filtros opcionales por especie y estado."""
    return repositorio.listar(
        conexion,
        especie=especie,
        estado=estado,
        limite=limite,
        offset=offset,
    )
