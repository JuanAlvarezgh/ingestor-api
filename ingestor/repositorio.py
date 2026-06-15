"""Funciones de acceso a la base de datos PostgreSQL para personajes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ingestor.modelos import Personaje

if TYPE_CHECKING:
    import psycopg

_SQL_CREAR_TABLA = """
CREATE TABLE IF NOT EXISTS personajes (
    id            INT PRIMARY KEY,
    nombre        TEXT NOT NULL,
    estado        TEXT NOT NULL,
    especie       TEXT NOT NULL,
    genero        TEXT NOT NULL,
    origen        TEXT NOT NULL,
    ubicacion     TEXT NOT NULL,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

_SQL_UPSERT = """
INSERT INTO personajes (id, nombre, estado, especie, genero, origen, ubicacion, actualizado_en)
VALUES (%s, %s, %s, %s, %s, %s, %s, now())
ON CONFLICT (id) DO UPDATE SET
    nombre        = EXCLUDED.nombre,
    estado        = EXCLUDED.estado,
    especie       = EXCLUDED.especie,
    genero        = EXCLUDED.genero,
    origen        = EXCLUDED.origen,
    ubicacion     = EXCLUDED.ubicacion,
    actualizado_en = now();
"""


def asegurar_esquema(conexion: "psycopg.Connection") -> None:
    """Crea la tabla personajes si no existe."""
    with conexion.cursor() as cur:
        cur.execute(_SQL_CREAR_TABLA)
    conexion.commit()


def upsert_personajes(
    conexion: "psycopg.Connection",
    personajes: list[Personaje],
) -> int:
    """Inserta o actualiza una lista de personajes de forma idempotente.

    Devuelve la cantidad de registros procesados.
    """
    if not personajes:
        return 0

    filas = [
        (p.id, p.nombre, p.estado, p.especie, p.genero, p.origen, p.ubicacion)
        for p in personajes
    ]

    with conexion.cursor() as cur:
        cur.executemany(_SQL_UPSERT, filas)
    conexion.commit()

    return len(filas)


def contar(conexion: "psycopg.Connection") -> int:
    """Devuelve la cantidad total de personajes en la base de datos."""
    with conexion.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM personajes;")
        fila = cur.fetchone()
    return fila[0] if fila else 0


def max_id(conexion: "psycopg.Connection") -> int | None:
    """Devuelve el id máximo de personajes en la base de datos, o None si está vacía."""
    with conexion.cursor() as cur:
        cur.execute("SELECT MAX(id) FROM personajes;")
        fila = cur.fetchone()
    return fila[0] if fila else None


def listar(
    conexion: "psycopg.Connection",
    especie: str | None = None,
    estado: str | None = None,
    limite: int = 50,
    offset: int = 0,
) -> list[Personaje]:
    """Lista personajes con filtros opcionales por especie y estado.

    Ordena por id, aplica limite y offset.
    """
    condiciones: list[str] = []
    valores: list[str | int] = []

    if especie is not None:
        condiciones.append("especie = %s")
        valores.append(especie)

    if estado is not None:
        condiciones.append("estado = %s")
        valores.append(estado)

    clausula_where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

    sql = f"""
        SELECT id, nombre, estado, especie, genero, origen, ubicacion
        FROM personajes
        {clausula_where}
        ORDER BY id
        LIMIT %s OFFSET %s;
    """
    valores.extend([limite, offset])

    with conexion.cursor() as cur:
        cur.execute(sql, valores)
        filas = cur.fetchall()

    return [
        Personaje(
            id=fila[0],
            nombre=fila[1],
            estado=fila[2],
            especie=fila[3],
            genero=fila[4],
            origen=fila[5],
            ubicacion=fila[6],
        )
        for fila in filas
    ]
