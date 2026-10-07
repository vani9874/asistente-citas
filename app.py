"""Interfaz Shiny para Python del asistente de citas de la Clínica Sol (demo)."""
import asyncio

from shiny import App, reactive, render, ui
from shinychat import Chat, chat_ui

from asistente import config
from asistente.agent import Asistente, mensaje_de_error

SALUDO = """### 👋 Hola, soy el asistente de la Clínica Sol

Puedo ayudarte a ver especialidades, buscar horarios y agendar o cancelar citas.
Elige una opción o escríbeme directamente:

- <span class='suggestion submit' title='🩺 Especialidades'>¿Qué especialidades tienen?</span>
- <span class='suggestion submit' title='👶 Pediatría'>Quiero una cita con pediatría</span>
- <span class='suggestion' title='❌ Cancelar'>Necesito cancelar mi cita C001</span>
"""

ESTILOS = """
.panel-titulo { font-size: .8rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: .04em; color: var(--bs-secondary-color); margin: 1rem 0 .4rem; }
.resumen { display: grid; grid-template-columns: repeat(3, 1fr); gap: .5rem; }
.resumen .dato { background: var(--bs-tertiary-bg); border-radius: .6rem; padding: .5rem; text-align: center; }
.resumen .num { font-size: 1.3rem; font-weight: 700; line-height: 1.1; }
.resumen .etq { font-size: .7rem; color: var(--bs-secondary-color); }
.tarjeta-cita { border: 1px solid var(--bs-border-color); border-radius: .6rem;
  padding: .5rem .65rem; margin-bottom: .45rem; font-size: .82rem; }
.tarjeta-cita.cancelada { opacity: .6; }
.tarjeta-cita .cabecera { display: flex; justify-content: space-between; align-items: center; gap: .5rem; }
.lista-simple { list-style: none; padding: 0; margin: 0; font-size: .8rem; }
.lista-simple li { padding: .3rem 0; border-bottom: 1px dashed var(--bs-border-color); }
.lista-simple li:last-child { border-bottom: 0; }
.lista-simple code { font-size: .78rem; }
.vacio { font-size: .8rem; color: var(--bs-secondary-color); font-style: italic; }
.chip-modelo { font-size: .72rem; }
"""

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.div(
            ui.span("Panel de la clínica", class_="fw-semibold"),
            ui.span(config.MODELO_BOT, class_="badge text-bg-light border chip-modelo"),
            class_="d-flex justify-content-between align-items-center",
        ),
        ui.p("Datos de prueba. Aquí ves lo que el asistente hace por detrás.", class_="text-muted small mb-0"),
        ui.output_ui("aviso_api_key"),
        ui.output_ui("panel_resumen"),
        ui.div("📅 Citas", class_="panel-titulo"),
        ui.output_ui("panel_citas"),
        ui.div("🔧 Herramientas usadas", class_="panel-titulo"),
        ui.output_ui("panel_herramientas"),
        ui.div("🙋 Derivaciones a una persona", class_="panel-titulo"),
        ui.output_ui("panel_derivaciones"),
        ui.input_action_button(
            "reiniciar", "↺ Reiniciar conversación", class_="btn-outline-secondary btn-sm w-100 mt-3"
        ),
        width=340,
        open="desktop",
    ),
    chat_ui(
        "chat",
        greeting=SALUDO,
        placeholder="Escribe tu mensaje… (Enter para enviar)",
        height="100%",
        show_thinking_after_s=0.3,
    ),
    ui.tags.style(ESTILOS),
    title=ui.div(
        ui.span("🏥 Asistente de citas · Clínica Sol"),
        ui.input_dark_mode(id="modo_oscuro"),
        class_="d-flex justify-content-between align-items-center w-100 gap-2",
    ),
    window_title="Asistente de citas · Clínica Sol",
    fillable=True,
)


def _fue_exitosa(llamada: dict) -> bool:
    return "error" not in llamada["resultado"]


def _resumen_argumentos(argumentos: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in argumentos.items() if k != "telefono")


def server(input, output, session):
    chat = Chat("chat")
    bot = reactive.Value(Asistente())
    version = reactive.Value(0)  # se incrementa para refrescar el panel lateral
    herramientas = reactive.Value([])

    def refrescar():
        version.set(version() + 1)

    @chat.on_user_submit
    async def _responder(mensaje: str):
        asistente = bot()
        # La llamada a la API es bloqueante: se corre en un hilo para no congelar la app.
        try:
            r = await asyncio.to_thread(asistente.responder, mensaje)
        except Exception as e:  # sin API key, sin red, límite de uso, etc.
            await chat.append_message(f"⚠️ {mensaje_de_error(e)}")
            return
        await chat.append_message(r.texto)
        herramientas.set((herramientas() + r.llamadas)[-8:])
        refrescar()

    @reactive.effect
    @reactive.event(input.reiniciar)
    async def _reiniciar():
        # Un asistente nuevo: historial, agenda y numeración de citas desde cero.
        bot.set(Asistente())
        herramientas.set([])
        await chat.clear_messages()
        refrescar()

    @render.ui
    def aviso_api_key():
        if config.hay_api_key():
            return None
        return ui.div(
            "⚠️ Falta ", ui.tags.code("GEMINI_API_KEY"), " en el archivo ", ui.tags.code(".env"),
            ". Consíguela gratis en ", ui.tags.a("aistudio.google.com", href="https://aistudio.google.com/apikey",
                                                  target="_blank"), ".",
            class_="alert alert-warning small py-2 mt-2 mb-0",
        )

    @render.ui
    def panel_resumen():
        version()
        a = bot().agenda
        confirmadas = sum(c["estado"] == "confirmada" for c in a.citas.values())
        canceladas = len(a.citas) - confirmadas

        def dato(num, etiqueta):
            return ui.div(ui.div(str(num), class_="num"), ui.div(etiqueta, class_="etq"), class_="dato")

        return ui.div(
            dato(confirmadas, "confirmadas"), dato(canceladas, "canceladas"), dato(len(a.derivaciones), "derivaciones"),
            class_="resumen mt-3",
        )

    @render.ui
    def panel_citas():
        version()
        citas = list(bot().agenda.citas.values())
        if not citas:
            return ui.div("Sin citas todavía.", class_="vacio")
        tarjetas = []
        for c in reversed(citas):  # las más recientes primero
            confirmada = c["estado"] == "confirmada"
            tarjetas.append(ui.div(
                ui.div(
                    ui.tags.b(c["cita_id"]),
                    ui.span(c["estado"], class_=f"badge {'text-bg-success' if confirmada else 'text-bg-secondary'}"),
                    class_="cabecera",
                ),
                ui.div(c["paciente"]),
                ui.div(f"{c['especialidad'].capitalize()} · {c['doctor']}", class_="text-muted"),
                ui.div(f"🗓️ {c['fecha']} · 🕘 {c['hora']}"),
                class_=f"tarjeta-cita {'' if confirmada else 'cancelada'}",
            ))
        return ui.div(*tarjetas)

    @render.ui
    def panel_herramientas():
        version()
        items = herramientas()
        if not items:
            return ui.div("Ninguna aún.", class_="vacio")
        return ui.tags.ul(
            *[
                ui.tags.li(
                    "✅ " if _fue_exitosa(c) else "⚠️ ",
                    ui.tags.code(c["nombre"]),
                    ui.div(_resumen_argumentos(c["argumentos"]), class_="text-muted") if c["argumentos"] else None,
                )
                for c in reversed(items)
            ],
            class_="lista-simple",
        )

    @render.ui
    def panel_derivaciones():
        version()
        derivaciones = bot().agenda.derivaciones
        if not derivaciones:
            return ui.div("Ninguna.", class_="vacio")
        return ui.tags.ul(*[ui.tags.li(d) for d in derivaciones], class_="lista-simple")


app = App(app_ui, server)
