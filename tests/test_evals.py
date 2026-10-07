import pytest

from evals.casos import CASOS
from evals.run_eval import chequeos_deterministas, parsear_veredicto


def llamada(nombre):
    return {"nombre": nombre, "argumentos": {}, "resultado": {"ok": True}}


def test_los_casos_estan_bien_formados():
    ids = [c["id"] for c in CASOS]
    assert len(ids) == len(set(ids))
    assert all(c["mensajes"] and c["criterio"] for c in CASOS)


def test_chequeos_detectan_herramienta_faltante_y_prohibida():
    caso = {"debe_llamar": ["buscar_horarios"], "no_debe_llamar": ["agendar_cita"]}
    assert chequeos_deterministas(caso, [llamada("buscar_horarios")]) == []
    assert len(chequeos_deterministas(caso, [llamada("agendar_cita")])) == 2


def test_parsear_veredicto_tolera_texto_extra():
    v = parsear_veredicto('Claro: {"puntaje": 4, "razon": "bien"} fin')
    assert v == {"puntaje": 4, "razon": "bien"}


@pytest.mark.parametrize("texto", ["sin json", '{"puntaje": 9, "razon": "x"}', '{"razon": "x"}'])
def test_parsear_veredicto_rechaza_respuestas_invalidas(texto):
    with pytest.raises((ValueError, KeyError)):
        parsear_veredicto(texto)
