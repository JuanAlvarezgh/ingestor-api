"""Modelos Pydantic del ingestor de personajes."""

from pydantic import BaseModel


class Personaje(BaseModel):
    """Representa un personaje de Rick and Morty."""

    id: int
    nombre: str
    estado: str
    especie: str
    genero: str
    origen: str
    ubicacion: str


class ResumenSync(BaseModel):
    """Resumen del resultado de una sincronización."""

    modo: str
    paginas_leidas: int
    registros_upsert: int
    total_en_bd: int
