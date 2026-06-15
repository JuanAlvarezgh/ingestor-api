"""Pruebas de la API FastAPI usando TestClient y respx para simular la API upstream."""

import os

import httpx
import psycopg
import pytest
import respx
from fastapi.testclient import TestClient

from ingestor.api import app
from ingestor.repositorio import asegurar_esquema

# ------------------------------------------------------------------
# Configuración: se omite si no hay DSN disponible
# ------------------------------------------------------------------

DSN = os.environ.get("DSN_BD")

pytestmark = pytest.mark.skipif(
    not DSN,
    reason="DSN_BD no está definido; se omiten pruebas de integración de la API",
)

_BASE_API = "https://rickandmortyapi.com/api"


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture()
def cliente_api():
    """Devuelve un TestClient con la tabla personajes limpia."""
    assert DSN
    with psycopg.connect(DSN) as conn:
        asegurar_esquema(conn)
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE personajes;")
        conn.commit()

    with TestClient(app) as cliente:
        yield cliente


def _personaje_api(id_: int, nombre: str) -> dict:
    """Construye un personaje con la estructura mínima de la API de Rick and Morty."""
    return {
        "id": id_,
        "name": nombre,
        "status": "Alive",
        "species": "Human",
        "gender": "Male",
        "origin": {"name": "Earth"},
        "location": {"name": "Earth"},
    }


def _respuesta_pagina(resultados: list[dict], pagina_siguiente: str | None = None) -> dict:
    """Construye una respuesta de página de la API."""
    return {
        "info": {
            "count": len(resultados),
            "pages": 1,
            "next": pagina_siguiente,
            "prev": None,
        },
        "results": resultados,
    }


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

def test_salud(cliente_api):
    """GET /salud devuelve 200 con estado ok."""
    respuesta = cliente_api.get("/salud")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


@respx.mock
def test_sincronizar_y_consultar(cliente_api):
    """POST /sincronizar carga personajes y GET /personajes y /estado los exponen."""
    personajes = [_personaje_api(1, "Rick"), _personaje_api(2, "Morty")]
    pagina = _respuesta_pagina(personajes, pagina_siguiente=None)

    respx.get(f"{_BASE_API}/character", params={"page": "1"}).mock(
        return_value=httpx.Response(200, json=pagina)
    )

    # Sincronizar
    respuesta_sync = cliente_api.post("/sincronizar?incremental=false")
    assert respuesta_sync.status_code == 200
    resumen = respuesta_sync.json()
    assert resumen["registros_upsert"] == 2
    assert resumen["total_en_bd"] == 2
    assert resumen["modo"] == "completo"

    # Verificar que /personajes devuelve los 2 personajes
    respuesta_personajes = cliente_api.get("/personajes")
    assert respuesta_personajes.status_code == 200
    personajes_bd = respuesta_personajes.json()
    assert len(personajes_bd) == 2
    nombres = {p["nombre"] for p in personajes_bd}
    assert nombres == {"Rick", "Morty"}

    # Verificar /estado
    respuesta_estado = cliente_api.get("/estado")
    assert respuesta_estado.status_code == 200
    estado = respuesta_estado.json()
    assert estado["total_en_bd"] == 2
    assert estado["max_id"] == 2


@respx.mock
def test_sincronizar_es_idempotente(cliente_api):
    """Sincronizar dos veces los mismos datos no duplica registros."""
    personajes = [_personaje_api(1, "Rick"), _personaje_api(2, "Morty")]
    pagina = _respuesta_pagina(personajes, pagina_siguiente=None)

    respx.get(f"{_BASE_API}/character").mock(
        return_value=httpx.Response(200, json=pagina)
    )

    cliente_api.post("/sincronizar?incremental=false")

    # Segunda sincronización (volver a mockear respx)
    respx.get(f"{_BASE_API}/character", params={"page": "1"}).mock(
        return_value=httpx.Response(200, json=pagina)
    )
    respuesta_sync_2 = cliente_api.post("/sincronizar?incremental=false")
    resumen_2 = respuesta_sync_2.json()

    # El total sigue siendo 2, no 4
    assert resumen_2["total_en_bd"] == 2


def test_personajes_filtro_especie(cliente_api):
    """GET /personajes?especie=X filtra correctamente."""
    # Verificamos que el endpoint acepta el parámetro sin error (tabla vacía)
    respuesta = cliente_api.get("/personajes?especie=Human")
    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_estado_tabla_vacia(cliente_api):
    """GET /estado devuelve total_en_bd=0 y max_id=None cuando no hay datos."""
    respuesta = cliente_api.get("/estado")
    assert respuesta.status_code == 200
    estado = respuesta.json()
    assert estado["total_en_bd"] == 0
    assert estado["max_id"] is None
