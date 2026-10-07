"""Bucle de tool calling con la API de Gemini (SDK google-genai)."""
from __future__ import annotations

from dataclasses import dataclass, field

from google import genai
from google.genai import errors, types

from . import config
from .guardrails import MENSAJE_SEGURO, verificar_respuesta
from .prompts import SISTEMA
from .tools import HERRAMIENTAS, Agenda

_TOOLS = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=h["name"], description=h["description"], parameters_json_schema=h["parameters"])
    for h in HERRAMIENTAS
])]


@dataclass
class Resultado:
    texto: str
    llamadas: list[dict] = field(default_factory=list)  # [{nombre, argumentos, resultado}]
    problemas_guardrail: list[str] = field(default_factory=list)


def _texto_usuario(texto: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=texto)])


def _texto_de(contenido: types.Content | None) -> str:
    # Solo partes de texto visibles (sin "pensamientos" ni llamadas a funciones).
    partes = (contenido.parts if contenido else None) or []
    return "".join(p.text for p in partes if p.text and not p.thought).strip()


def mensaje_de_error(e: Exception) -> str:
    """Traduce errores comunes de la API a un mensaje entendible para la interfaz."""
    if isinstance(e, ValueError) and not config.hay_api_key():
        return "Falta la clave de Gemini. Agrega `GEMINI_API_KEY` en el archivo `.env` y reinicia la app."
    if isinstance(e, errors.APIError):
        if e.code == 429:
            return "Se alcanzó el límite de uso de Gemini (cuota gratuita o por minuto). Espera un momento e intenta de nuevo."
        if e.code in (400, 401, 403) and "key" in str(e).lower():
            return "La clave `GEMINI_API_KEY` no es válida. Revísala en el archivo `.env`."
        if e.code == 404:
            return (f"El modelo `{config.MODELO_BOT}` no existe o no está disponible para tu cuenta "
                    "(los modelos 2.5 ya no se ofrecen a cuentas nuevas). Cambia `MODELO_BOT` en `.env`, "
                    "por ejemplo a `gemini-3.1-flash-lite`.")
        if e.code >= 500:
            return "El servicio de Gemini no está disponible en este momento. Intenta de nuevo en unos segundos."
    return f"No pude responder en este momento (`{type(e).__name__}`). Intenta de nuevo."


class Asistente:
    def __init__(self, agenda: Agenda | None = None, cliente: genai.Client | None = None):
        self.agenda = agenda or Agenda()
        self._cliente = cliente
        self.historial: list[types.Content] = []

    @property
    def cliente(self) -> genai.Client:
        # Se crea al primer uso: así la app abre aunque falte la API key.
        if self._cliente is None:
            self._cliente = genai.Client(http_options=config.REINTENTOS)  # lee GEMINI_API_KEY
        return self._cliente

    def _llamar_modelo(self, mensajes: list[types.Content]) -> types.GenerateContentResponse:
        return self.cliente.models.generate_content(
            model=config.MODELO_BOT,
            contents=mensajes,
            config=types.GenerateContentConfig(
                system_instruction=SISTEMA,
                tools=_TOOLS,
                max_output_tokens=config.MAX_TOKENS,
                thinking_config=config.config_pensamiento(config.MODELO_BOT),
                # Las funciones las ejecutamos nosotros (con validación), no el SDK.
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )

    def _turno(self, mensajes: list[types.Content]) -> tuple[str, list[dict]]:
        """Corre el modelo hasta que deje de pedir herramientas."""
        llamadas: list[dict] = []
        for _ in range(config.MAX_VUELTAS_HERRAMIENTAS):
            resp = self._llamar_modelo(mensajes)
            contenido = resp.candidates[0].content if resp.candidates else None
            if contenido is not None:
                # Se guarda completo: Gemini 3 exige devolver sus "thought signatures".
                mensajes.append(contenido)
            pedidas = [p.function_call for p in (contenido.parts if contenido else None) or [] if p.function_call]
            if not pedidas:
                return _texto_de(contenido), llamadas
            respuestas = []
            for fc in pedidas:
                argumentos = dict(fc.args or {})
                salida = self.agenda.ejecutar(fc.name, argumentos)
                llamadas.append({"nombre": fc.name, "argumentos": argumentos, "resultado": salida})
                respuestas.append(types.Part(function_response=types.FunctionResponse(
                    id=fc.id, name=fc.name, response=salida)))
            mensajes.append(types.Content(role="user", parts=respuestas))
        return MENSAJE_SEGURO, llamadas  # demasiadas vueltas: mejor escalar

    def responder(self, mensaje_usuario: str) -> Resultado:
        mensajes = self.historial + [_texto_usuario(mensaje_usuario)]
        texto, llamadas = self._turno(mensajes)

        problemas = verificar_respuesta(texto, llamadas)
        if problemas:  # un reintento con aviso; si falla otra vez, mensaje seguro
            mensajes.append(_texto_usuario("AVISO DEL SISTEMA: " + " ".join(problemas)
                                           + " Corrige tu respuesta usando las herramientas."))
            texto2, llamadas2 = self._turno(mensajes)
            llamadas += llamadas2
            if verificar_respuesta(texto2, llamadas):
                texto = MENSAJE_SEGURO
                self.agenda.derivar_a_humano("Guardrail: respuesta no verificable")
            else:
                texto = texto2

        if not texto:  # p. ej. respuesta bloqueada por filtros de seguridad
            texto = "Disculpa, no entendí bien. ¿Puedes contarme de otra forma qué necesitas?"

        # guardamos el historial solo con texto limpio (sin avisos internos)
        self.historial += [
            _texto_usuario(mensaje_usuario),
            types.Content(role="model", parts=[types.Part(text=texto)]),
        ]
        return Resultado(texto=texto, llamadas=llamadas, problemas_guardrail=problemas)
