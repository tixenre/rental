"""Extracción de los datos de RENAPER del objeto `decision` de Didit (API v3).

En la API v3 los datos del documento NO viven en un `kyc.document` singular
(shape viejo), sino en arrays **plurales** dentro de `decision`:

    decision = {
      "id_verifications": [
        { "status": "Approved", "document_number": "...", "personal_number": "...",
          "first_name": "...", "last_name": "...", "full_name": "...",
          "date_of_birth": "...", "formatted_address": "...", ... }
      ],
      "face_matches": [...], "liveness_checks": [...], ...
    }

El mismo `decision` llega de dos fuentes equivalentes (mismo schema):
  - embebido en el webhook (`payload["decision"]`), o
  - vía `GET /v3/session/{id}/decision/` (fuente canónica, `client.retrieve_decision`).

Este módulo es **puro** (sin DB ni red) para poder testearlo de punta a punta.

Ley 25.326: devuelve solo texto plano (nombre, DNI, CUIL, fecha, domicilio). No
hay imagen ni biométrico — esas URLs del documento NO se extraen ni se persisten.

Refs: https://docs.didit.me/sessions-api/retrieve-session
"""

from dataclasses import dataclass


@dataclass
class DatosRenaper:
    """Datos del documento confirmados por RENAPER. Todos opcionales: una
    verificación puede venir incompleta y no queremos pisar lo ya guardado."""

    dni: str | None = None
    cuil: str | None = None
    nombre: str | None = None
    apellido: str | None = None
    nombre_completo: str | None = None
    fecha_nacimiento: str | None = None
    direccion: str | None = None

    @property
    def tiene_datos(self) -> bool:
        """True si se extrajo al menos el DNI — la señal de que la decisión
        traía datos del documento (y no un webhook 'liviano' sin payload)."""
        return bool(self.dni)


def _limpiar(valor) -> str | None:
    """Normaliza un campo a texto plano o None (vacío/espacios → None)."""
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _elegir_verificacion(verifs: list) -> dict | None:
    """Elige la entrada de `id_verifications` con datos de documento, prefiriendo
    las Approved. Defensivo ante entradas malformadas (no-dict, sin número)."""
    candidato = None
    for v in verifs:
        if not isinstance(v, dict) or not _limpiar(v.get("document_number")):
            continue
        if (v.get("status") or "").strip().lower() == "approved":
            return v  # la mejor: aprobada y con número de documento
        candidato = candidato or v
    return candidato


def extraer_datos_renaper(decision: dict | None) -> DatosRenaper:
    """Extrae los datos del documento del objeto `decision` (API v3).

    Mapa de campos (Argentina / RENAPER vía Didit):
      - dni            ← document_number   (número de DNI)
      - cuil           ← personal_number   (CUIL; fallbacks tax_id/cuil)
      - nombre         ← first_name
      - apellido       ← last_name
      - nombre_completo← full_name         (nombre legal autoritativo, p/ contratos)
      - fecha_nacimiento ← date_of_birth
      - direccion      ← formatted_address (fallback address)

    Tolerante a payloads incompletos o con shape inesperado: devuelve un
    DatosRenaper vacío en vez de romper (el webhook siempre responde 200).
    """
    if not isinstance(decision, dict):
        return DatosRenaper()
    verifs = decision.get("id_verifications")
    if not isinstance(verifs, list):
        return DatosRenaper()

    v = _elegir_verificacion(verifs)
    if v is None:
        return DatosRenaper()

    return DatosRenaper(
        dni=_limpiar(v.get("document_number")),
        cuil=_limpiar(v.get("personal_number") or v.get("tax_id") or v.get("cuil")),
        nombre=_limpiar(v.get("first_name")),
        apellido=_limpiar(v.get("last_name")),
        nombre_completo=_limpiar(v.get("full_name")),
        fecha_nacimiento=_limpiar(v.get("date_of_birth")),
        direccion=_limpiar(v.get("formatted_address") or v.get("address")),
    )
