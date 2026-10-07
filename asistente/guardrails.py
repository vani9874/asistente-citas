"""Guardrails: revisan la respuesta del modelo antes de mostrarla al paciente."""
from __future__ import annotations

import re

MENSAJE_SEGURO = (
    "Disculpa, no pude confirmar esa operación. Para evitar errores, "
    "te paso con una persona del equipo que te ayudará."
)

_DICE_AGENDADA = re.compile(r"\b(agendad[ao]|reservad[ao]|qued[oó] agendada|cita confirmada)\b", re.I)
_DICE_CANCELADA = re.compile(r"\b(cancelad[ao]|qued[oó] cancelada)\b", re.I)


def _exito(llamadas: list[dict], herramienta: str) -> bool:
    return any(c["nombre"] == herramienta and c["resultado"].get("ok") for c in llamadas)


def verificar_respuesta(texto: str, llamadas: list[dict]) -> list[str]:
    """Devuelve la lista de problemas encontrados (vacía = respuesta aceptable).

    Regla principal: no se puede afirmar que una cita fue agendada o cancelada
    si la herramienta correspondiente no devolvió ok en este turno.
    """
    problemas = []
    if _DICE_AGENDADA.search(texto) and not _exito(llamadas, "agendar_cita"):
        problemas.append("Afirma que la cita fue agendada sin una llamada exitosa a agendar_cita.")
    if _DICE_CANCELADA.search(texto) and not _exito(llamadas, "cancelar_cita"):
        problemas.append("Afirma que la cita fue cancelada sin una llamada exitosa a cancelar_cita.")
    return problemas
