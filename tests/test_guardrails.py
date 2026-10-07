from asistente.guardrails import verificar_respuesta

OK = [{"nombre": "agendar_cita", "argumentos": {}, "resultado": {"ok": True}}]
ERROR = [{"nombre": "agendar_cita", "argumentos": {}, "resultado": {"error": "x"}}]


def test_detecta_cita_inventada_sin_llamada():
    assert verificar_respuesta("¡Listo! Tu cita quedó agendada para mañana.", [])


def test_detecta_cita_inventada_con_herramienta_fallida():
    assert verificar_respuesta("Tu cita quedó agendada.", ERROR)


def test_acepta_cita_respaldada_por_herramienta():
    assert verificar_respuesta("Tu cita quedó agendada.", OK) == []


def test_detecta_cancelacion_inventada():
    assert verificar_respuesta("Tu cita fue cancelada.", OK)  # agendar_cita no respalda cancelar


def test_texto_normal_no_dispara():
    assert verificar_respuesta("Tenemos horarios a las 09:00 y 10:00.", []) == []
