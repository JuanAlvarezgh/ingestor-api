"""Cliente HTTP para la API pública de Rick and Morty con reintentos y paginación."""

import time
from collections.abc import Iterator
from typing import Any

import httpx

from ingestor import config
from ingestor.modelos import Personaje

# Códigos de estado HTTP que ameritan reintento
_ESTADOS_REINTENTO = {429, 500, 502, 503, 504}


class ErrorAPI(RuntimeError):
    """Error al comunicarse con la API de Rick and Morty."""


class ClienteRickAndMorty:
    """Cliente que pagina la API de Rick and Morty y retorna Personaje mapeados."""

    def __init__(
        self,
        base_url: str | None = None,
        cliente_http: httpx.Client | None = None,
        max_reintentos: int = 4,
        retardo_base: float = 0.5,
        dormir: Any = time.sleep,
    ) -> None:
        self._base_url = base_url or config.api_base()
        self._cliente_http = cliente_http or httpx.Client(timeout=30.0)
        self._max_reintentos = max_reintentos
        self._retardo_base = retardo_base
        self._dormir = dormir

    # ------------------------------------------------------------------
    # Métodos internos
    # ------------------------------------------------------------------

    def _obtener(self, url: str, params: dict | None = None) -> dict:
        """GET con reintentos exponenciales ante fallos transitorios.

        Lanza ErrorAPI si se agotan los reintentos o el status no es 200.
        """
        ultimo_error: Exception | None = None

        for intento in range(self._max_reintentos):
            try:
                respuesta = self._cliente_http.get(url, params=params)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                ultimo_error = exc
                retardo = self._retardo_base * (2**intento)
                self._dormir(retardo)
                continue

            if respuesta.status_code == 200:
                return respuesta.json()

            if respuesta.status_code in _ESTADOS_REINTENTO:
                ultimo_error = ErrorAPI(
                    f"Estado HTTP {respuesta.status_code} en {url!r}"
                )
                retardo = self._retardo_base * (2**intento)
                self._dormir(retardo)
                continue

            raise ErrorAPI(
                f"Estado HTTP inesperado {respuesta.status_code} en {url!r}"
            )

        raise ErrorAPI(
            f"Se agotaron {self._max_reintentos} reintentos para {url!r}"
        ) from ultimo_error

    @staticmethod
    def _mapear_personaje(datos: dict) -> Personaje:
        """Convierte un diccionario de la API a un objeto Personaje."""
        return Personaje(
            id=datos["id"],
            nombre=datos["name"],
            estado=datos["status"],
            especie=datos["species"],
            genero=datos["gender"],
            origen=datos.get("origin", {}).get("name", ""),
            ubicacion=datos.get("location", {}).get("name", ""),
        )

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def obtener_personajes(self, pagina_inicial: int = 1) -> Iterator[Personaje]:
        """Itera sobre todas las páginas de personajes desde pagina_inicial.

        Sigue el campo info.next para avanzar de página.
        """
        url_actual: str | None = f"{self._base_url}/character"
        params: dict | None = {"page": pagina_inicial}

        while url_actual is not None:
            datos = self._obtener(url_actual, params=params)
            params = None  # Solo se usa en la primera petición

            for item in datos.get("results", []):
                yield self._mapear_personaje(item)

            url_actual = datos.get("info", {}).get("next")

    def cerrar(self) -> None:
        """Cierra el cliente HTTP subyacente."""
        self._cliente_http.close()

    def __enter__(self) -> "ClienteRickAndMorty":
        return self

    def __exit__(self, *args: Any) -> None:
        self.cerrar()
