"""Términos y Condiciones del checkout: aceptación versionada.

La versión actual se controla con `TYC_VERSION_ACTUAL` — sube junto al texto de
los T&C cuando cambia. Cada versión nueva requiere una nueva aceptación.
El texto visible de los T&C es responsabilidad del front (que lo renderiza según la
versión vigente); el backend solo sabe si el cliente ya aceptó esa versión.
"""

TYC_VERSION_ACTUAL = "v1"


def ya_acepto(conn, cliente_id: int, version: str = TYC_VERSION_ACTUAL) -> bool:
    """True si el cliente aceptó esta versión de los T&C."""
    row = conn.execute(
        "SELECT 1 FROM aceptaciones_tyc WHERE cliente_id = %s AND version = %s",
        (cliente_id, version),
    ).fetchone()
    return row is not None


def registrar_aceptacion(conn, cliente_id: int, version: str = TYC_VERSION_ACTUAL) -> None:
    """Registra la aceptación del cliente (idempotente: ON CONFLICT DO NOTHING)."""
    conn.execute(
        """INSERT INTO aceptaciones_tyc (cliente_id, version)
           VALUES (%s, %s)
           ON CONFLICT (cliente_id, version) DO NOTHING""",
        (cliente_id, version),
    )
