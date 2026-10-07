# Asistente de citas · Shiny para Python + Gemini

Chatbot en español que agenda y cancela citas de la **Clínica Sol**, una clínica
**de demostración** (datos de prueba, sin datos reales). La interfaz de chat
está hecha con [Shiny para Python](https://shiny.posit.co/py/) y el bot usa la
API de Gemini (SDK `google-genai`) con *tool calling*: el modelo no inventa
horarios, los consulta y modifica a través de herramientas que validan todo.

## Índice

- [Qué incluye](#qué-incluye)
- [Requisitos](#requisitos)
- [Instalación y uso](#instalación-y-uso)
- [Configuración](#configuración)
- [Cómo funciona](#cómo-funciona)
- [Datos de prueba](#datos-de-prueba)
- [Tests](#tests)
- [Evaluación con juez LLM](#evaluación-con-juez-llm)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Problemas comunes](#problemas-comunes)
- [Limitaciones conocidas](#limitaciones-conocidas)
- [Ideas para mejorar](#ideas-para-mejorar)

## Qué incluye

- **Interfaz**: chat con sugerencias en tarjetas, modo oscuro y un panel lateral
  que muestra lo que el bot hace por detrás: un resumen (citas confirmadas,
  canceladas y derivaciones), las citas en tarjetas, las herramientas que usó y
  las derivaciones a una persona. Avisa si falta la API key y traduce los
  errores de la API (límite de uso, clave inválida, modelo inexistente) a
  mensajes claros.
- **Tool calling**: `listar_especialidades`, `buscar_horarios`, `agendar_cita`,
  `cancelar_cita` y `derivar_a_humano` ([asistente/tools.py](asistente/tools.py)).
- **Guardrails** ([asistente/guardrails.py](asistente/guardrails.py)):
  - Las herramientas validan todo: no se puede agendar un horario inventado u
    ocupado, ni sin nombre completo y teléfono válidos.
  - Si el modelo dice que una cita "quedó agendada/cancelada" sin una llamada
    exitosa a la herramienta, la respuesta se bloquea, se reintenta una vez y,
    si persiste, se responde con un mensaje seguro y se deriva a una persona.
- **Evaluación** ([evals/](evals/)): 10 casos (urgencias, inyección de prompt,
  datos faltantes, especialidad inexistente…) con chequeos deterministas y un
  **juez LLM** que puntúa de 1 a 5.
- **Tests** ([tests/](tests/)): 25 tests que corren sin API key, con un cliente
  de Gemini simulado.

## Requisitos

- **Python 3.11 o superior**.
- **[uv](https://docs.astral.sh/uv/)** para instalar dependencias y correr la app.
- **[just](https://github.com/casey/just)** *(opcional)*: atajos para las tareas
  comunes. Sin `just` puedes usar directamente los comandos `uv run …`.
- Una **clave de Gemini**, gratis en
  [aistudio.google.com/apikey](https://aistudio.google.com/apikey). Solo hace
  falta para chatear y para la evaluación; los tests no la necesitan.

Instalar `uv` y `just`:

```bash
# Windows (PowerShell)
winget install --id=astral-sh.uv -e
winget install --id=Casey.Just -e

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
brew install just            # o el gestor de paquetes de tu sistema
```

## Instalación y uso

```bash
git clone https://github.com/vani9874/asistente-citas.git
cd asistente-citas
uv sync                      # crea .venv e instala las dependencias (incluye pytest)
```

Crea el archivo `.env` a partir del ejemplo y pon tu clave en `GEMINI_API_KEY`:

```bash
cp .env.example .env         # Windows (PowerShell): Copy-Item .env.example .env
```

Luego:

| Tarea | Con `just` | Sin `just` |
|---|---|---|
| Levantar la app en <http://localhost:8000> | `just app` | `uv run shiny run app.py --reload` |
| Tests unitarios (sin API key) | `just test` | `uv run pytest -q` |
| Evaluación con juez LLM (consume tokens) | `just eval` | `uv run python -m evals.run_eval` |

### Ejemplo de conversación

> **Paciente:** Quiero una cita con pediatría
> **Asistente:** *(llama a `buscar_horarios`)* Tengo estos horarios con el Dr. Mamani: …
> **Paciente:** El primero. Soy Ana Pérez, mi teléfono es 70012345
> **Asistente:** *(llama a `agendar_cita`)* Listo, tu cita **C001** quedó agendada para …

La cita aparece al instante en el panel lateral, junto con las herramientas
usadas. Luego puedes probar `Cancela mi cita C001`, pedir una especialidad que
no existe o describir una urgencia para ver cómo responde.

## Configuración

Todo se configura en `.env` (ver [.env.example](.env.example)):

| Variable | Por defecto | Para qué sirve |
|---|---|---|
| `GEMINI_API_KEY` | — | Clave de Gemini (también se acepta `GOOGLE_API_KEY`). |
| `MODELO_BOT` | `gemini-3.1-flash-lite` | Modelo del chatbot. Se usa en cada mensaje, así que conviene el más barato. |
| `MODELO_JUEZ` | `gemini-3.5-flash-lite` | Modelo del juez; solo se usa en `just eval`. |

En [asistente/config.py](asistente/config.py) hay además límites fijos: máximo
1024 tokens de salida, máximo 6 vueltas de herramientas por mensaje y 3
reintentos automáticos ante errores 429 o fallas temporales del servicio.

### Modelos y costo

En `.env.example` hay una tabla con los modelos sugeridos y sus precios. Todos
tienen plan gratuito, que alcanza para probar la app (con límites por minuto y
por día). Los modelos 2.5 ya no están disponibles para cuentas nuevas (dan error
404); usa los de la familia 3.x.

El "pensamiento" de Gemini se cobra como tokens de salida, por eso la app lo
baja al mínimo: nivel `low` en los modelos 3.x y apagado en `gemini-3.5-flash-lite`.

## Cómo funciona

```
Paciente ──► app.py (Shiny) ──► Asistente.responder()
                                    │
                                    ▼
                    ┌──── Gemini (con prompt de sistema + herramientas)
                    │          │
                    │          ├─ pide una herramienta ──► Agenda.ejecutar() valida y responde
                    │          │                            (se repite hasta 6 vueltas)
                    │          └─ responde con texto
                    │                   │
                    │                   ▼
                    │          guardrails.verificar_respuesta()
                    │            ├─ OK ──────────────────► se muestra al paciente
                    └── reintento con aviso del sistema ◄─ problema (1 vez)
                                    └─ falla otra vez ──► mensaje seguro + derivar_a_humano
```

1. **Prompt de sistema** ([asistente/prompts.py](asistente/prompts.py)): define
   el tono y las reglas (no inventar datos, pedir nombre y teléfono, no dar
   consejos médicos, derivar urgencias).
2. **Bucle de herramientas** ([asistente/agent.py](asistente/agent.py)): las
   funciones las ejecuta el código, no el SDK (`automatic_function_calling`
   desactivado), para poder validarlas y registrarlas en el panel.
3. **Agenda** ([asistente/tools.py](asistente/tools.py)): cada sesión de chat
   tiene su propia agenda en memoria; las herramientas devuelven `{"ok": True, …}`
   o `{"error": "…"}` y el modelo debe actuar según eso.
4. **Guardrail de salida**: revisa con expresiones regulares si la respuesta
   afirma algo que ninguna herramienta confirmó.

## Datos de prueba

| Especialidad | Doctor/a |
|---|---|
| Medicina general | Dra. Rojas |
| Pediatría | Dr. Mamani |
| Dermatología | Dra. Quispe |
| Odontología | Dr. Salazar |

- Horarios: 09:00, 10:00, 11:00, 15:00 y 16:00, de lunes a viernes, durante los
  próximos 7 días.
- Las citas reciben ids correlativos: `C001`, `C002`, …
- Para agendar se exige nombre y apellido, y un teléfono de al menos 7 dígitos.

## Tests

```bash
just test
```

Los 25 tests usan un cliente de Gemini simulado ([tests/conftest.py](tests/conftest.py)),
así que no necesitan API key ni consumen tokens. Cubren:

- [test_tools.py](tests/test_tools.py): validaciones de la agenda (horarios
  inexistentes u ocupados, nombre y teléfono inválidos, cancelaciones).
- [test_guardrails.py](tests/test_guardrails.py): detección de afirmaciones no verificadas.
- [test_agente.py](tests/test_agente.py): el bucle de herramientas, el reintento
  del guardrail, que el historial quede limpio y que la app abra sin API key.
- [test_evals.py](tests/test_evals.py): los chequeos deterministas y la lectura
  del veredicto del juez.

## Evaluación con juez LLM

```bash
just eval
```

Corre cada caso de [evals/casos.py](evals/casos.py) como una conversación real
con Gemini y lo evalúa de dos formas:

1. **Chequeos deterministas**: qué herramientas debía usar (`debe_llamar`) y
   cuáles no (`no_debe_llamar`). Por ejemplo, ante una urgencia debe llamar a
   `derivar_a_humano` y nunca a `agendar_cita`.
2. **Juez LLM**: otro modelo (`MODELO_JUEZ`) lee la conversación y puntúa de 1 a
   5 si la última respuesta cumple el `criterio` del caso.

Un caso **pasa** si no tiene fallas deterministas y el juez le da 4 o más. El
resultado se imprime en consola y se guarda en `evals/resultados.md`. El
comando termina con código 1 si algún caso falla, así que sirve también en CI.

Casos incluidos: `especialidades`, `buscar_horarios`, `agendar_completo`,
`faltan_datos`, `especialidad_inexistente`, `urgencia`, `consejo_medico`,
`cancelar_inexistente`, `paciente_molesto` e `inyeccion_de_prompt`.

Para agregar uno, añade un diccionario a `CASOS` con `id`, `mensajes`,
`criterio` y, si aplica, `debe_llamar` / `no_debe_llamar`.

## Estructura del proyecto

```
app.py                  # interfaz Shiny: chat + panel lateral
asistente/
  agent.py              # bucle de tool calling con Gemini y manejo de errores
  tools.py              # agenda en memoria y definición de herramientas
  guardrails.py         # verificación de la respuesta antes de mostrarla
  prompts.py            # prompt de sistema
  config.py             # modelos, límites y reintentos
evals/
  casos.py              # casos de evaluación
  run_eval.py           # corre los casos y genera evals/resultados.md
tests/                  # pytest (sin API key)
.env.example            # plantilla de configuración con tabla de modelos
justfile                # atajos: app, test, eval
```

## Problemas comunes

| Mensaje o síntoma | Causa y solución |
|---|---|
| "Falta la clave de Gemini" | No existe `.env` o `GEMINI_API_KEY` está vacía. Créalo y reinicia la app. |
| "La clave `GEMINI_API_KEY` no es válida" | Revisa que la copiaste completa, sin espacios ni comillas. |
| "El modelo … no existe" (404) | El modelo no está disponible para tu cuenta (p. ej. los 2.5). Cambia `MODELO_BOT` a `gemini-3.1-flash-lite`. |
| "Se alcanzó el límite de uso" (429) | Cuota gratuita por minuto o por día agotada. Espera un momento; la app ya reintenta 3 veces. |
| `uv` o `just` no se reconoce | No están instalados o falta reiniciar la terminal. Ver [Requisitos](#requisitos). |
| Las citas desaparecieron | La agenda vive en memoria: se pierde al recargar la página o reiniciar la app. |

## Limitaciones conocidas

- La agenda vive en memoria: se reinicia al reiniciar la app y no se comparte
  entre sesiones.
- Las respuestas no se muestran en streaming (se envían completas).
- El guardrail detecta afirmaciones de cita agendada/cancelada con expresiones
  regulares; es una primera línea de defensa, no una garantía total.
- La evaluación con juez LLM tiene variabilidad; conviene correrla varias veces.

## Ideas para mejorar

- Guardar la agenda en una base de datos (por ejemplo SQLite).
- Mostrar las respuestas en streaming.
- Correr `just test` automáticamente en GitHub Actions.
- Ampliar los casos de evaluación (reprogramar citas, varias citas por paciente).
