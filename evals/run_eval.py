"""Evaluación automática del asistente: chequeos deterministas + juez LLM.

Uso:  uv run python -m evals.run_eval          (necesita GEMINI_API_KEY)
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

from google import genai
from google.genai import types

from asistente import config
from asistente.agent import Asistente
from asistente.tools import Agenda
from evals.casos import CASOS

PROMPT_JUEZ = """Eres un evaluador estricto de un chatbot de citas médicas en español.

Conversación (paciente y asistente):
{conversacion}

Herramientas que usó el asistente en el último turno: {herramientas}

Criterio que debe cumplir la ÚLTIMA respuesta del asistente:
{criterio}

Califica de 1 a 5 (5 = cumple perfectamente, 1 = incumple o inventa datos).
Responde SOLO con un JSON: {{"puntaje": <1-5>, "razon": "<una frase>"}}"""


def chequeos_deterministas(caso: dict, llamadas: list[dict]) -> list[str]:
    """Devuelve las fallas (lista vacía = todo bien)."""
    usadas = {c["nombre"] for c in llamadas}
    fallas = [f"Debía llamar a {h}" for h in caso.get("debe_llamar", []) if h not in usadas]
    fallas += [f"No debía llamar a {h}" for h in caso.get("no_debe_llamar", []) if h in usadas]
    return fallas


def parsear_veredicto(texto: str) -> dict:
    """Extrae {"puntaje", "razon"} de la respuesta del juez, tolerando texto extra."""
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        raise ValueError(f"El juez no devolvió JSON: {texto[:80]!r}")
    datos = json.loads(m.group(0))
    puntaje = int(datos["puntaje"])
    if not 1 <= puntaje <= 5:
        raise ValueError(f"Puntaje fuera de rango: {puntaje}")
    return {"puntaje": puntaje, "razon": str(datos.get("razon", ""))}


def juzgar(cliente: genai.Client, caso: dict, conversacion: list[tuple[str, str]], llamadas: list[dict]) -> dict:
    texto_conv = "\n".join(f"{quien}: {txt}" for quien, txt in conversacion)
    herramientas = ", ".join(c["nombre"] for c in llamadas) or "ninguna"
    resp = cliente.models.generate_content(
        model=config.MODELO_JUEZ,
        contents=PROMPT_JUEZ.format(conversacion=texto_conv, herramientas=herramientas, criterio=caso["criterio"]),
        config=types.GenerateContentConfig(
            max_output_tokens=300,
            response_mime_type="application/json",
            thinking_config=config.config_pensamiento(config.MODELO_JUEZ),
        ),
    )
    return parsear_veredicto(resp.text or "")


def correr_caso(cliente: genai.Client, caso: dict) -> dict:
    bot = Asistente(Agenda(hoy=date.today()), cliente)
    conversacion: list[tuple[str, str]] = []
    todas_las_llamadas: list[dict] = []
    for mensaje in caso["mensajes"]:
        r = bot.responder(mensaje)
        conversacion += [("Paciente", mensaje), ("Asistente", r.texto)]
        todas_las_llamadas += r.llamadas  # los chequeos miran todos los turnos
    fallas = chequeos_deterministas(caso, todas_las_llamadas)
    veredicto = juzgar(cliente, caso, conversacion, todas_las_llamadas)
    return {
        "id": caso["id"],
        "fallas": fallas,
        "puntaje": veredicto["puntaje"],
        "razon": veredicto["razon"],
        "respuesta": conversacion[-1][1],
        "pasa": not fallas and veredicto["puntaje"] >= 4,
    }


def escribir_reporte(resultados: list[dict], ruta: Path) -> None:
    lineas = [
        f"# Resultados de evaluación ({date.today().isoformat()})",
        f"Bot: `{config.MODELO_BOT}` · Juez: `{config.MODELO_JUEZ}`",
        "",
        "| Caso | Pasa | Puntaje | Fallas deterministas | Razón del juez |",
        "|---|---|---|---|---|",
    ]
    for r in resultados:
        lineas.append(
            f"| {r['id']} | {'✅' if r['pasa'] else '❌'} | {r['puntaje']}/5 | "
            f"{'; '.join(r['fallas']) or '—'} | {r['razon']} |"
        )
    aprobados = sum(r["pasa"] for r in resultados)
    lineas += ["", f"**{aprobados}/{len(resultados)} casos aprobados.**"]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main() -> int:
    cliente = genai.Client(http_options=config.REINTENTOS)  # lee GEMINI_API_KEY
    resultados = []
    for caso in CASOS:
        try:
            r = correr_caso(cliente, caso)
        except Exception as e:  # un caso roto no debe tumbar toda la evaluación
            r = {"id": caso["id"], "fallas": [f"Error: {type(e).__name__}"], "puntaje": 1, "razon": str(e)[:120],
                 "respuesta": "", "pasa": False}
        resultados.append(r)
        print(f"{'OK ' if r['pasa'] else 'FALLA'} {r['id']:<26} {r['puntaje']}/5  {r['razon']}")
    escribir_reporte(resultados, Path(__file__).parent / "resultados.md")
    aprobados = sum(r["pasa"] for r in resultados)
    print(f"\n{aprobados}/{len(resultados)} casos aprobados → evals/resultados.md")
    return 0 if aprobados == len(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
