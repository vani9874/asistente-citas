from datetime import date

import pytest

from asistente.tools import Agenda


@pytest.fixture
def agenda():
    return Agenda(hoy=date(2026, 10, 5))  # lunes


def primer_slot(agenda, esp="medicina general"):
    return agenda.buscar_horarios(esp)["horarios"][0]["slot_id"]


def test_especialidad_inexistente_devuelve_error(agenda):
    r = agenda.buscar_horarios("astrología")
    assert "error" in r and "medicina general" in r["disponibles"]


def test_no_hay_horarios_en_fin_de_semana(agenda):
    r = agenda.buscar_horarios("pediatría", fecha="2026-10-10")  # sábado
    assert r["total"] == 0


def test_agendar_ok_y_slot_queda_ocupado(agenda):
    slot = primer_slot(agenda)
    r = agenda.agendar_cita(slot, "Ana Pérez", "70012345")
    assert r["ok"] and r["cita"]["cita_id"] == "C001"
    assert slot not in [s["slot_id"] for s in agenda.buscar_horarios("medicina general")["horarios"]]
    assert "error" in agenda.agendar_cita(slot, "Luis Gómez", "70012345")  # ya ocupado


def test_no_se_puede_agendar_slot_inventado(agenda):
    r = agenda.agendar_cita("med-2030-01-01-09:00", "Ana Pérez", "70012345")
    assert "error" in r and not agenda.citas


@pytest.mark.parametrize("nombre,tel", [("Ana", "70012345"), ("Ana Pérez", "123")])
def test_datos_del_paciente_invalidos(agenda, nombre, tel):
    assert "error" in agenda.agendar_cita(primer_slot(agenda), nombre, tel)


def test_cancelar_libera_el_horario(agenda):
    slot = primer_slot(agenda)
    cita = agenda.agendar_cita(slot, "Ana Pérez", "70012345")["cita"]["cita_id"]
    assert agenda.cancelar_cita(cita)["ok"]
    assert slot in [s["slot_id"] for s in agenda.buscar_horarios("medicina general")["horarios"]]
    assert "error" in agenda.cancelar_cita(cita)  # ya cancelada


def test_ejecutar_herramienta_desconocida_o_argumentos_malos(agenda):
    assert "error" in agenda.ejecutar("borrar_todo", {})
    assert "error" in agenda.ejecutar("buscar_horarios", {"foo": 1})
