"""
Perfiles fiscales personales + productoras vinculadas a un cliente — solo
lectura (#1240). La escritura (alta de perfil vía AFIP, alta/edición de
productora) sigue en `services/facturacion/padron.py` (verificación AFIP,
dominio de facturación) y `routes/productoras.py` (admin, membership) — este
módulo NO la duplica, solo consulta.

Fuente única de ambas queries — antes `routes/clientes.py` (admin) y
`routes/cliente_portal/cuenta.py` (portal) tenían cada uno su propio SELECT,
con columnas ligeramente distintas (el admin no traía `email_facturacion` ni
el `domicilio_fiscal` de la productora). Acá siempre se trae el superset —
un consumidor que no necesita un campo simplemente no lo muestra.
"""
from database import row_to_dict


def perfiles_fiscales(conn, cliente_id: int) -> list[dict]:
    rows = conn.execute(
        """SELECT id, cuit, perfil_impuestos, razon_social, domicilio_fiscal,
                  email_facturacion, etiqueta, es_default
           FROM cliente_perfiles_fiscales
           WHERE cliente_id = %s
           ORDER BY es_default DESC, created_at ASC""",
        (cliente_id,),
    ).fetchall()
    return [row_to_dict(r) for r in rows]


def productoras_vinculadas(conn, cliente_id: int, solo_facturables: bool = False) -> list[dict]:
    """`solo_facturables=True` excluye productoras BORRADOR (sin CUIT — #1251
    Fase 3): no se pueden facturar, así que no tienen que aparecer como opción
    en el selector "Facturar a nombre de" del checkout. La ficha admin (que no
    pasa este flag) sigue viendo todas, borrador incluido."""
    filtro_cuit = "AND p.cuit IS NOT NULL" if solo_facturables else ""
    rows = conn.execute(
        f"""SELECT p.id, p.cuit, p.perfil_impuestos, p.razon_social, p.domicilio_fiscal, p.nombre
           FROM productoras p
           JOIN productora_miembros pm ON pm.productora_id = p.id
           WHERE pm.cliente_id = %s {filtro_cuit}
           ORDER BY p.razon_social NULLS LAST, p.id""",
        (cliente_id,),
    ).fetchall()
    return [row_to_dict(r) for r in rows]


def resumen_fiscal(conn, cliente_id: int) -> dict:
    """Combina ambas listas — lo que usa la ficha admin en un solo endpoint."""
    return {
        "perfiles": perfiles_fiscales(conn, cliente_id),
        "productoras": productoras_vinculadas(conn, cliente_id),
    }
