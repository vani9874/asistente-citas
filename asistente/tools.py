"""Herramientas del asistente: una agenda en memoria con datos de PRUEBA.

Cada sesión de chat tiene su propia `Agenda`. Las herramientas validan todo lo
que reciben, de modo que el modelo no puede agendar horarios que no existen.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

# Datos de prueba: especialidad -> doctor
DOCTORES = {
    "medicina general": "Dra. Rojas",
    "pediatría": "Dr. Mamani",
    "dermatología": "Dra. Quispe",
    "odontología": "Dr. Salazar",
}
HORAS = ["09:00", "10:00", "11:00", "15:00", "16:00"]
DIAS_ADELANTE = 7


def _normalizar(texto: str) -> str:
    return texto.strip().lower()


@dataclass
class Agenda:
    hoy: date = field(default_factory=date.today)
    citas: dict[str, dict] = field(default_factory=dict)
    derivaciones: list[str] = field(default_factory=list)
    _contador: int = 0

    # ---- horarios -------------------------------------------------------
    def _todos_los_slots(self) -> list[dict]:
        slots = []
        for i in range(1, DIAS_ADELANTE + 1):
            dia = self.hoy + timedelta(days=i)
            if dia.weekday() >= 5:  # sin sábados ni domingos
                continue
            for especialidad, doctor in DOCTORES.items():
                for hora in HORAS:
                    slots.append(
                        {
                            "slot_id": f"{especialidad[:3]}-{dia.isoformat()}-{hora}",
                            "especialidad": especialidad,
                            "doctor": doctor,
                            "fecha": dia.isoformat(),
                            "hora": hora,
                        }
                    )
        return slots

    def _slot_ocupado(self, slot_id: str) -> bool:
        return any(c["slot_id"] == slot_id and c["estado"] == "confirmada" for c in self.citas.values())

    # ---- herramientas ---------------------------------------------------
    def listar_especialidades(self) -> dict:
        return {"especialidades": [{"nombre": e, "doctor": d} for e, d in DOCTORES.items()]}

    def buscar_horarios(self, especialidad: str, fecha: str | None = None) -> dict:
        esp = _normalizar(especialidad)
        if esp not in DOCTORES:
            return {"error": f"Especialidad no encontrada: {especialidad!r}", "disponibles": list(DOCTORES)}
        slots = [s for s in self._todos_los_slots() if s["especialidad"] == esp and not self._slot_ocupado(s["slot_id"])]
        if fecha:
            slots = [s for s in slots if s["fecha"] == fecha]
        return {"horarios": slots[:8], "total": len(slots)}

    def agendar_cita(self, slot_id: str, nombre_paciente: str, telefono: str) -> dict:
        slot = next((s for s in self._todos_los_slots() if s["slot_id"] == slot_id), None)
        if slot is None:
            return {"error": "Ese horario no existe. Usa un slot_id devuelto por buscar_horarios."}
        if self._slot_ocupado(slot_id):
            return {"error": "Ese horario ya fue ocupado. Busca otro horario."}
        if len(nombre_paciente.strip().split()) < 2:
            return {"error": "Falta el nombre completo del paciente (nombre y apellido)."}
        if len(re.sub(r"\D", "", telefono)) < 7:
            return {"error": "El teléfono no es válido. Pide un número de al menos 7 dígitos."}
        self._contador += 1
        cita_id = f"C{self._contador:03d}"
        self.citas[cita_id] = {
            "cita_id": cita_id,
            "estado": "confirmada",
            "paciente": nombre_paciente.strip(),
            "telefono": telefono.strip(),
            **slot,
        }
        return {"ok": True, "cita": self.citas[cita_id]}

    def cancelar_cita(self, cita_id: str) -> dict:
        cita = self.citas.get(cita_id.strip().upper())
        if cita is None:
            return {"error": f"No existe una cita con id {cita_id!r}."}
        if cita["estado"] == "cancelada":
            return {"error": "Esa cita ya estaba cancelada."}
        cita["estado"] = "cancelada"
        return {"ok": True, "cita": cita}

    def derivar_a_humano(self, motivo: str) -> dict:
        self.derivaciones.append(motivo)
        return {"ok": True, "mensaje": "Se avisó al equipo de la clínica; una persona contactará al paciente."}

    # ---- despacho -------------------------------------------------------
    def ejecutar(self, nombre: str, argumentos: dict) -> dict:
        funcion = getattr(self, nombre, None)
        if nombre not in NOMBRES_HERRAMIENTAS or funcion is None:
            return {"error": f"Herramienta desconocida: {nombre}"}
        try:
            return funcion(**argumentos)
        except TypeError as e:  # argumentos faltantes o sobrantes
            return {"error": f"Argumentos inválidos: {e}"}


def _herramienta(nombre: str, descripcion: str, propiedades: dict, requeridas: list[str]) -> dict:
    return {
        "name": nombre,
        "description": descripcion,
        # JSON Schema estándar; Gemini lo recibe como `parameters_json_schema`.
        "parameters": {"type": "object", "properties": propiedades, "required": requeridas},
    }


HERRAMIENTAS = [
    _herramienta("listar_especialidades", "Lista las especialidades y doctores de la clínica.", {}, []),
    _herramienta(
        "buscar_horarios",
        "Busca horarios libres de una especialidad, opcionalmente en una fecha (AAAA-MM-DD).",
        {"especialidad": {"type": "string"}, "fecha": {"type": "string", "description": "AAAA-MM-DD"}},
        ["especialidad"],
    ),
    _herramienta(
        "agendar_cita",
        "Agenda una cita en un horario libre. Requiere nombre completo y teléfono.",
        {
            "slot_id": {"type": "string", "description": "slot_id devuelto por buscar_horarios"},
            "nombre_paciente": {"type": "string"},
            "telefono": {"type": "string"},
        },
        ["slot_id", "nombre_paciente", "telefono"],
    ),
    _herramienta("cancelar_cita", "Cancela una cita por su id (ej. C001).", {"cita_id": {"type": "string"}}, ["cita_id"]),
    _herramienta(
        "derivar_a_humano",
        "Pasa la conversación a una persona del equipo (urgencias, molestia, pedidos fuera de alcance).",
        {"motivo": {"type": "string"}},
        ["motivo"],
    ),
]
NOMBRES_HERRAMIENTAS = {h["name"] for h in HERRAMIENTAS}
