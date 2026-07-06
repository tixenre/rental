"""
Nombre/dirección a MOSTRAR de un cliente — RENAPER si está verificado, si no
el dato base. Delega en `identity/` (fuente única de la regla "preferí
RENAPER"); esto solo arma el fallback al nombre base cuando no hay RENAPER.

Fuente única — antes se recomputaba en 4 lugares: `routes/clientes.py` (admin,
`f"{nombre} {apellido}"` crudo, no None-safe), `routes/cliente_portal/cuenta.py`
(portal, misma expresión), `routes/cliente_portal/documentos.py` (contrato/
factura, misma expresión) y `services/pedidos_enriquecimiento.py`
(`nombre_validado(c) or nombre_completo_cliente(...)`, que además importaba el
helper de un ROUTE). `nombre_completo_cliente` (movido acá desde
`routes/clientes.py`) es la versión None-safe — la fuente única ahora también
corrige el caso `nombre`/`apellido` ambos `None` (cuenta liviana sin datos)
que el `f"..."` crudo mostraba como `"None None"`.
"""
from identity import nombre_validado, direccion_validada


def nombre_completo_cliente(nombre, apellido) -> str:
    """Compone el nombre visible de un cliente: **"Nombre Apellido"** (nombre
    primero). Decisión del dueño 2026-06-06: el nombre se muestra siempre con
    el nombre primero. Si falta el apellido, devuelve solo el nombre."""
    n = (nombre or "").strip()
    a = (apellido or "").strip()
    return f"{n} {a}".strip() if a else n


def nombre_legal(c: dict) -> str:
    return nombre_validado(c) or nombre_completo_cliente(c.get("nombre"), c.get("apellido"))


def direccion_legal(c: dict) -> str | None:
    return direccion_validada(c) or c.get("direccion")
