"""Pruebas del cliente HTTP de Rick and Morty."""

import httpx
import pytest
import respx

from ingestor.cliente import ClienteRickAndMorty, ErrorAPI

# ------------------------------------------------------------------
# Datos de ayuda
# ------------------------------------------------------------------

_BASE = "https://rickandmortyapi.com/api"


def _personaje_api(id_: int, nombre: str = "Personaje") -> dict:
    """Devuelve un personaje con la estructura mínima que devuelve la API."""
    return {
        "id": id_,
        "name": nombre,
        "status": "Alive",
        "species": "Human",
        "gender": "Male",
        "origin": {"name": "Earth"},
        "location": {"name": "Earth"},
    }


def _respuesta_pagina(
    resultados: list[dict],
    pagina_siguiente: str | None = None,
    total_paginas: int = 1,
) -> dict:
    """Construye una respuesta de página de la API."""
    return {
        "info": {
            "count": len(resultados),
            "pages": total_paginas,
            "next": pagina_siguiente,
            "prev": None,
        },
        "results": resultados,
    }


# ------------------------------------------------------------------
# Test 1: paginación y mapeo correcto
# ------------------------------------------------------------------

@respx.mock
def test_paginacion_y_mapeo():
    """Verifica que obtener_personajes itera 2 páginas y mapea los campos correctamente."""
    url_pagina_2 = f"{_BASE}/character?page=2"

    pagina_1 = _respuesta_pagina(
        resultados=[_personaje_api(1, "Rick"), _personaje_api(2, "Morty")],
        pagina_siguiente=url_pagina_2,
        total_paginas=2,
    )
    pagina_2 = _respuesta_pagina(
        resultados=[_personaje_api(3, "Beth"), _personaje_api(4, "Summer")],
        pagina_siguiente=None,
        total_paginas=2,
    )

    # La primera petición lleva params page=1; respx la intercepta sin importar los params
    # usando un patrón de URL que incluye el query string
    respx.get(f"{_BASE}/character", params={"page": "1"}).mock(
        return_value=httpx.Response(200, json=pagina_1)
    )
    respx.get(url_pagina_2).mock(
        return_value=httpx.Response(200, json=pagina_2)
    )

    cliente_http = httpx.Client()
    cliente = ClienteRickAndMorty(
        base_url=_BASE,
        cliente_http=cliente_http,
    )

    personajes = list(cliente.obtener_personajes(pagina_inicial=1))

    assert len(personajes) == 4
    assert personajes[0].nombre == "Rick"
    assert personajes[0].id == 1
    assert personajes[1].nombre == "Morty"
    assert personajes[2].nombre == "Beth"
    assert personajes[3].nombre == "Summer"

    # Verificar mapeo de campos
    rick = personajes[0]
    assert rick.estado == "Alive"
    assert rick.especie == "Human"
    assert rick.genero == "Male"
    assert rick.origen == "Earth"
    assert rick.ubicacion == "Earth"


# ------------------------------------------------------------------
# Test 2: reintento ante HTTP 429
# ------------------------------------------------------------------

@respx.mock
def test_reintento_ante_429():
    """Verifica que el cliente reintenta cuando recibe un 429."""
    dormidas: list[float] = []

    def dormir_falso(segundos: float) -> None:
        dormidas.append(segundos)

    pagina_ok = _respuesta_pagina(
        resultados=[_personaje_api(1, "Rick")],
        pagina_siguiente=None,
    )

    ruta = respx.get(f"{_BASE}/character", params={"page": "1"}).mock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(200, json=pagina_ok),
        ]
    )

    cliente_http = httpx.Client()
    cliente = ClienteRickAndMorty(
        base_url=_BASE,
        cliente_http=cliente_http,
        retardo_base=0.1,
        dormir=dormir_falso,
    )

    personajes = list(cliente.obtener_personajes(pagina_inicial=1))

    assert len(personajes) == 1
    assert personajes[0].nombre == "Rick"
    assert ruta.call_count == 2  # Un intento fallido + uno exitoso
    assert len(dormidas) == 1    # Durmió una vez entre reintentos


# ------------------------------------------------------------------
# Test 3: error al agotar reintentos con múltiples 503
# ------------------------------------------------------------------

@respx.mock
def test_error_al_agotar_reintentos():
    """Verifica que ErrorAPI se lanza cuando se agotan todos los reintentos."""
    dormidas: list[float] = []

    def dormir_falso(segundos: float) -> None:
        dormidas.append(segundos)

    respx.get(f"{_BASE}/character", params={"page": "1"}).mock(
        return_value=httpx.Response(503)
    )

    cliente_http = httpx.Client()
    cliente = ClienteRickAndMorty(
        base_url=_BASE,
        cliente_http=cliente_http,
        max_reintentos=3,
        retardo_base=0.1,
        dormir=dormir_falso,
    )

    with pytest.raises(ErrorAPI, match="reintentos"):
        list(cliente.obtener_personajes(pagina_inicial=1))

    assert len(dormidas) == 3  # Durmió en cada uno de los 3 reintentos
