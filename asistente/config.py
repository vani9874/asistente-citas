"""Configuración: modelos y límites. Se puede cambiar con variables de entorno."""
import os

from dotenv import load_dotenv
from google.genai import types

load_dotenv()

# Modelo del bot (rápido y barato) y modelo del juez de evaluaciones.
# Ver .env.example para la lista de modelos sugeridos y sus precios.
MODELO_BOT = os.getenv("MODELO_BOT", "gemini-3.1-flash-lite")
MODELO_JUEZ = os.getenv("MODELO_JUEZ", "gemini-3.5-flash-lite")

MAX_TOKENS = 1024
MAX_VUELTAS_HERRAMIENTAS = 6  # tope de llamadas a herramientas por mensaje


# Reintentos automáticos ante límites de uso (429) o fallas temporales del servicio.
REINTENTOS = types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=3, initial_delay=2.0))


def hay_api_key() -> bool:
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))


def config_pensamiento(modelo: str) -> types.ThinkingConfig | None:
    """El "pensamiento" de Gemini se cobra como tokens de salida: lo bajamos al mínimo.

    - Gemini 2.5 Flash / Flash-Lite: se puede apagar (budget 0).
    - Gemini 3.x: no se apaga, pero se puede pedir nivel "low".
    - Gemini 2.5 Pro: no permite apagarlo; se deja por defecto.
    """
    if modelo.startswith("gemini-3.5-flash-lite"):
        return types.ThinkingConfig(thinking_budget=0)
    if modelo.startswith("gemini-3"):
        return types.ThinkingConfig(thinking_level="low")
    return None
