"""Servicio de sincronización: orquesta cliente HTTP y repositorio."""

from __future__ import annotations

import psycopg

from ingestor import config, repositorio
from ingestor.cliente import ClienteRickAndMorty
from ingestor.modelos import Personaje, ResumenSync

_TAMANO_LOTE = 100
_PERSONAJES_POR_PAGINA = 20


def sincronizar(
    dsn: str,
    base_url: str | None = None,
    incremental: bool = False,
) -> ResumenSync:
    """Sincroniza personajes desde la API de Rick and Morty hacia PostgreSQL.

    Si incremental=True y ya hay datos en la BD, calcula la página inicial
    a partir del id máximo para evitar reprocesar datos ya existentes.
    """
    with psycopg.connect(dsn) as conexion:
        repositorio.asegurar_esquema(conexion)

        # Determinar desde qué página empezar
        if incremental:
            id_maximo = repositorio.max_id(conexion)
            if id_maximo is not None:
                pagina_inicial = (id_maximo // _PERSONAJES_POR_PAGINA) + 1
                modo = "incremental"
            else:
                pagina_inicial = 1
                modo = "completo"
        else:
            pagina_inicial = 1
            modo = "completo"

        paginas_leidas = 0
        registros_upsert = 0
        lote: list[Personaje] = []

        url_base = base_url or config.api_base()

        with ClienteRickAndMorty(base_url=url_base) as cliente:
            personaje_anterior_pagina = None

            for personaje in cliente.obtener_personajes(pagina_inicial=pagina_inicial):
                # Contar páginas detectando cambio de página (cada 20 personajes)
                pagina_actual = ((personaje.id - 1) // _PERSONAJES_POR_PAGINA) + 1
                if personaje_anterior_pagina != pagina_actual:
                    paginas_leidas += 1
                    personaje_anterior_pagina = pagina_actual

                lote.append(personaje)

                if len(lote) >= _TAMANO_LOTE:
                    registros_upsert += repositorio.upsert_personajes(conexion, lote)
                    lote = []

            # Vaciar el lote restante
            if lote:
                registros_upsert += repositorio.upsert_personajes(conexion, lote)

        total = repositorio.contar(conexion)

    return ResumenSync(
        modo=modo,
        paginas_leidas=paginas_leidas,
        registros_upsert=registros_upsert,
        total_en_bd=total,
    )
