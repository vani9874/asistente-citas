# Asistente de citas · Shiny para Python + Gemini

Chatbot en español que agenda y cancela citas de una clínica **de demostración**
(datos de prueba, sin datos reales). Interfaz de chat con Shiny para Python y
la API de Gemini (SDK `google-genai`) con *tool calling*.

## Qué incluye

- **Interfaz**: chat con sugerencias en tarjetas, modo oscuro y un panel lateral
  con un resumen (citas confirmadas/canceladas/derivaciones), las citas en
  tarjetas, las herramientas que usó el bot y las derivaciones a una persona.
  Avisa si falta la API key y traduce los errores de la API (límite de uso,
  clave inválida, modelo inexistente) a mensajes claros.
- **Tool calling**: `listar_especialidades`, `buscar_horarios`, `agendar_cita`,
  `cancelar_cita`, `derivar_a_humano` (`asistente/tools.py`).
- **Guardrails** (`asistente/guardrails.py`):
  - Las herramientas validan todo: no se puede agendar un horario inventado,
    ocupado, ni sin nombre completo y teléfono válidos.
  - Si el modelo dice que una cita "quedó agendada/cancelada" sin una llamada
    exitosa a la herramienta, se bloquea, se reintenta una vez y, si persiste,
    se responde con un mensaje seguro y se deriva a una persona.
- **Evaluación** (`evals/`): 10 casos (urgencias, inyección de prompt, datos
  faltantes, especialidad inexistente…) con dos tipos de chequeo:
  deterministas (qué herramientas se llamaron) y **LLM-as-judge** (puntaje 1–5).
- **Tests** (`tests/`): 25 tests que corren sin API key, con un cliente simulado.

## Cómo correrlo

```bash
cp .env.example .env        # y pon tu GEMINI_API_KEY (gratis en aistudio.google.com/apikey)
just app                    # o: uv run shiny run app.py --reload
just test                   # tests unitarios
just eval                   # evaluación con juez LLM (consume tokens)
```

## Modelos y costo

Por defecto el bot usa `gemini-3.1-flash-lite` (el más barato disponible) y
el juez `gemini-3.5-flash-lite`. Se cambian con `MODELO_BOT` y `MODELO_JUEZ`
en `.env`; ahí mismo hay una tabla con los modelos sugeridos y sus precios.
Los modelos 2.5 ya no están disponibles para cuentas nuevas (error 404).
Para ahorrar, la app deja el "pensamiento" del modelo en nivel `low`.

## Estructura

```
app.py                 # interfaz Shiny
asistente/             # agent.py (bucle de tools), tools.py, guardrails.py, prompts.py
evals/                 # casos.py, run_eval.py → genera evals/resultados.md
tests/                 # pytest
```

## Limitaciones conocidas

- La agenda vive en memoria: se reinicia al reiniciar la app.
- Las respuestas no se muestran en streaming (se envían completas).
- El guardrail detecta afirmaciones de cita agendada/cancelada con expresiones
  regulares; es una primera línea de defensa, no una garantía total.
- La evaluación con juez LLM tiene variabilidad; conviene correrla varias veces.
