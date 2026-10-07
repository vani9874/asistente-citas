"""Prueba del bucle de tool calling con un cliente simulado (sin API key)."""
from datetime import date

from google.genai import types

from asistente.agent import Asistente
from asistente.guardrails import MENSAJE_SEGURO
from asistente.tools import Agenda


def _respuesta(*partes):
    contenido = types.Content(role="model", parts=list(partes))
    return types.GenerateContentResponse(candidates=[types.Candidate(content=contenido)])


def texto(t):
    return _respuesta(types.Part(text=t))


def herramienta(nombre, **args):
    return _respuesta(types.Part(function_call=types.FunctionCall(id="t1", name=nombre, args=args)))


class ClienteFalso:
    """Devuelve respuestas guionadas, una por llamada (imita client.models.generate_content)."""

    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.models = self
        self.pedidos = []

    def generate_content(self, **kwargs):
        self.pedidos.append(kwargs)
        return self.respuestas.pop(0)


def test_flujo_con_herramienta():
    agenda = Agenda(hoy=date(2026, 10, 5))
    bot = Asistente(agenda, ClienteFalso([herramienta("buscar_horarios", especialidad="pediatría"),
                                          texto("Hay horarios a las 09:00.")]))
    r = bot.responder("¿Hay pediatra?")
    assert [c["nombre"] for c in r.llamadas] == ["buscar_horarios"]
    assert r.texto == "Hay horarios a las 09:00."


def test_guardrail_bloquea_cita_inventada_y_deriva():
    agenda = Agenda(hoy=date(2026, 10, 5))
    bot = Asistente(agenda, ClienteFalso([texto("¡Tu cita quedó agendada!"), texto("Sí, quedó agendada.")]))
    r = bot.responder("Quiero una cita")
    assert r.texto == MENSAJE_SEGURO
    assert r.problemas_guardrail and agenda.derivaciones


def test_guardrail_permite_correccion_en_el_reintento():
    agenda = Agenda(hoy=date(2026, 10, 5))
    bot = Asistente(agenda, ClienteFalso([texto("Tu cita quedó agendada."),
                                          texto("Perdón, aún no agendo nada. ¿Me das tu nombre completo?")]))
    r = bot.responder("Quiero una cita")
    assert "nombre completo" in r.texto and not agenda.derivaciones


def test_devuelve_resultado_de_herramienta_al_modelo():
    cliente = ClienteFalso([herramienta("listar_especialidades"), texto("Tenemos 4 especialidades.")])
    bot = Asistente(Agenda(hoy=date(2026, 10, 5)), cliente)
    bot.responder("¿Qué especialidades hay?")
    ultimo = cliente.pedidos[-1]["contents"][-2]  # [-1] es la respuesta final
    fr = ultimo.parts[0].function_response
    assert fr.name == "listar_especialidades" and fr.id == "t1" and "especialidades" in fr.response


def test_ignora_pensamientos_y_guarda_historial_limpio():
    cliente = ClienteFalso([_respuesta(types.Part(text="razonando...", thought=True), types.Part(text="¡Hola!"))])
    bot = Asistente(Agenda(hoy=date(2026, 10, 5)), cliente)
    assert bot.responder("hola").texto == "¡Hola!"
    assert [c.role for c in bot.historial] == ["user", "model"]


def test_app_abre_sin_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    Asistente()  # el cliente se crea recién al primer mensaje
