"""Pruebas de integración del repositorio contra PostgreSQL real."""

import os

import psycopg
import pytest

from ingestor.modelos import Personaje
from ingestor.repositorio import (
    asegurar_esquema,
    contar,
    listar,
    max_id,
    upsert_personajes,
)

# ------------------------------------------------------------------
# Configuración de la suite: se omite si no hay DSN disponible
# ------------------------------------------------------------------

DSN = os.environ.get("DSN_BD")

pytestmark = pytest.mark.skipif(
    not DSN,
    reason="DSN_BD no está definido; se omiten pruebas de integración",
)


@pytest.fixture()
def conexion():
    """Abre una conexión a la BD y limpia la tabla al inicio y al final del test."""
    assert DSN  # Ya garantizado por skipif, pero satisface a mypy
    with psycopg.connect(DSN) as conn:
        asegurar_esquema(conn)
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE personajes;")
        conn.commit()
        yield conn


# ------------------------------------------------------------------
# Personajes de prueba
# ------------------------------------------------------------------

def _crear_personaje(id_: int, especie: str = "Human", estado: str = "Alive") -> Personaje:
    return Personaje(
        id=id_,
        nombre=f"Personaje {id_}",
        estado=estado,
        especie=especie,
        genero="Male",
        origen="Earth",
        ubicacion="Earth",
    )


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

def test_asegurar_esquema_crea_tabla(conexion):
    """Verifica que la tabla personajes existe tras asegurar_esquema."""
    # Si llegamos aquí sin error, la tabla existe
    with conexion.cursor() as cur:
        cur.execute(
            "SELECT to_regclass('public.personajes');"
        )
        resultado = cur.fetchone()
    assert resultado[0] == "personajes"


def test_upsert_idempotente(conexion):
    """Verifica que hacer upsert dos veces de los mismos datos no duplica registros."""
    personajes = [_crear_personaje(1), _crear_personaje(2)]

    procesados_1 = upsert_personajes(conexion, personajes)
    procesados_2 = upsert_personajes(conexion, personajes)

    assert procesados_1 == 2
    assert procesados_2 == 2
    assert contar(conexion) == 2  # Sin duplicados


def test_upsert_actualiza_campo(conexion):
    """Verifica que un upsert posterior actualiza los campos del personaje."""
    personaje_original = _crear_personaje(10, estado="Alive")
    upsert_personajes(conexion, [personaje_original])

    personaje_actualizado = Personaje(
        id=10,
        nombre="Personaje 10",
        estado="Dead",
        especie="Human",
        genero="Male",
        origen="Earth",
        ubicacion="Earth",
    )
    upsert_personajes(conexion, [personaje_actualizado])

    resultado = listar(conexion, limite=1)
    assert resultado[0].estado == "Dead"


def test_listar_con_filtro_por_especie(conexion):
    """Verifica el filtro por especie en listar."""
    personajes = [
        _crear_personaje(1, especie="Human"),
        _crear_personaje(2, especie="Alien"),
        _crear_personaje(3, especie="Human"),
    ]
    upsert_personajes(conexion, personajes)

    humanos = listar(conexion, especie="Human")
    assert len(humanos) == 2
    assert all(p.especie == "Human" for p in humanos)


def test_listar_con_filtro_por_estado(conexion):
    """Verifica el filtro por estado en listar."""
    personajes = [
        _crear_personaje(1, estado="Alive"),
        _crear_personaje(2, estado="Dead"),
        _crear_personaje(3, estado="Alive"),
    ]
    upsert_personajes(conexion, personajes)

    vivos = listar(conexion, estado="Alive")
    assert len(vivos) == 2
    assert all(p.estado == "Alive" for p in vivos)


def test_max_id(conexion):
    """Verifica que max_id devuelve el id más alto insertado."""
    personajes = [_crear_personaje(5), _crear_personaje(12), _crear_personaje(3)]
    upsert_personajes(conexion, personajes)

    assert max_id(conexion) == 12


def test_max_id_tabla_vacia(conexion):
    """Verifica que max_id devuelve None cuando la tabla está vacía."""
    assert max_id(conexion) is None


def test_contar(conexion):
    """Verifica el conteo de registros."""
    assert contar(conexion) == 0
    upsert_personajes(conexion, [_crear_personaje(1), _crear_personaje(2)])
    assert contar(conexion) == 2
