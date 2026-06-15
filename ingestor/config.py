"""Configuración del ingestor: lee variables de entorno en cada llamada."""

import os

_DSN_BD_DEFAULT = "postgresql://ingestor:ingestor@localhost:5435/ingestor"
_API_BASE_DEFAULT = "https://rickandmortyapi.com/api"


def dsn_bd() -> str:
    """Devuelve el DSN de la base de datos desde la variable de entorno DSN_BD."""
    return os.environ.get("DSN_BD", _DSN_BD_DEFAULT)


def api_base() -> str:
    """Devuelve la URL base de la API desde la variable de entorno API_BASE."""
    return os.environ.get("API_BASE", _API_BASE_DEFAULT)
