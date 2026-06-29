"""identity/ — motor único de identidad ("quién sos").

Frontera (MEMORIA): `auth/` = ¿podés entrar? · `identity/` = ¿quién sos? + ¿en qué
estado está la cuenta? Se tocan solo en `clientes.id` — `auth/` nunca ve un CUIL,
`identity/` nunca ve una cookie. El proveedor KYC vive aislado en `services/didit/`
(el payload crudo muere ahí); `identity/` recibe datos normalizados.

**API única de salida:** `get_validated_identity(cliente_id)` — el ÚNICO lector de la
identidad validada + estado. Contrato / factura / remito consultan ESTO; nadie copia
ni tipea estos campos en otra tabla (cero drift). Si la cuenta NO está verificada, los
campos de identidad legal son None (no se inventa con el nombre base/Google).
"""
from dataclasses import dataclass

from database import get_db, row_to_dict, to_iso

from identity.contacts import email_comunicacion, telefono_contacto


@dataclass
class ValidatedIdentity:
    """Foto única de la identidad + estado de una cuenta."""

    cliente_id: int
    estado: str  # "no_verificado" | "verificado" | "conflicto"
    verificado: bool
    # Identidad legal (RENAPER) — None si no está verificado.
    nombre_legal: str | None = None  # nombre_completo_renaper (autoritativo p/ contrato)
    nombre: str | None = None  # nombre_renaper
    apellido: str | None = None  # apellido_renaper
    dni: str | None = None
    cuil: str | None = None
    fecha_nacimiento: str | None = None
    direccion: str | None = None  # direccion_renaper (p/ contrato)
    # Contacto de comunicación — disponible aún sin verificar (Google desde el alta).
    email: str | None = None
    telefono: str | None = None
    # Detalle de verificación (para mostrarle al cliente).
    didit_status: str | None = None
    verificado_at: str | None = None


def _estado(c: dict) -> str:
    """Estado simple derivado (la verdad vive en dni_validado_at + identidad_conflicto,
    no en una columna de estado que pudiera desincronizarse)."""
    if c.get("identidad_conflicto"):
        return "conflicto"
    if c.get("dni_validado_at"):
        return "verificado"
    return "no_verificado"


def get_validated_identity(cliente_id: int, conn=None) -> "ValidatedIdentity | None":
    """Lector ÚNICO de la identidad validada + estado. None si el cliente no existe.

    Acepta un `conn` para correr dentro de la transacción del request (o abre el suyo).
    Sin verificar → los campos de identidad legal quedan None (honesto sobre el estado;
    el contrato/factura exigen `verificado`, el gate de pedidos ya bloquea pedir sin verificar).
    """
    own = conn is None
    conn = conn or get_db()
    try:
        row = conn.execute(
            """SELECT id, dni_validado_at, identidad_conflicto, dni_verificacion_estado,
                      nombre_renaper, apellido_renaper, nombre_completo_renaper,
                      dni, cuil, fecha_nacimiento_renaper, direccion_renaper
               FROM clientes WHERE id=%s""",
            (cliente_id,),
        ).fetchone()
        if row is None:
            return None
        c = row_to_dict(row)
        estado = _estado(c)
        verificado = estado == "verificado"
        vi = ValidatedIdentity(
            cliente_id=cliente_id,
            estado=estado,
            verificado=verificado,
            didit_status=c.get("dni_verificacion_estado"),
            verificado_at=to_iso(c.get("dni_validado_at")),
            email=email_comunicacion(conn, cliente_id),
            telefono=telefono_contacto(conn, cliente_id),
        )
        if verificado:
            vi.nombre_legal = c.get("nombre_completo_renaper")
            vi.nombre = c.get("nombre_renaper")
            vi.apellido = c.get("apellido_renaper")
            vi.dni = c.get("dni")
            vi.cuil = c.get("cuil")
            vi.fecha_nacimiento = c.get("fecha_nacimiento_renaper")
            vi.direccion = c.get("direccion_renaper")
        return vi
    finally:
        if own:
            conn.close()


# ── Helpers de display sobre una fila ya leída (sin N+1 en listados) ──────────
# Fuente ÚNICA de la regla "preferí RENAPER si está verificado". Los lectores que ya
# tienen la fila del cliente (contrato/remito, enriquecido de pedidos en vivo) la usan
# en vez de duplicar el `if nombre_renaper …` — el supervisor marca esa duplicación.


def nombre_validado(c: dict) -> str | None:
    """Nombre legal de RENAPER si la identidad fue verificada; None si no (para que el
    lector caiga a su propio fallback al nombre base). Puro, sobre una fila de clientes."""
    if c.get("nombre_renaper"):
        return f"{c['nombre_renaper']} {c.get('apellido_renaper') or ''}".strip()
    return None


def direccion_validada(c: dict) -> str | None:
    """Dirección oficial de RENAPER si está; None si no (el lector usa la base)."""
    return c.get("direccion_renaper") or None


__all__ = [
    "ValidatedIdentity",
    "get_validated_identity",
    "nombre_validado",
    "direccion_validada",
]
