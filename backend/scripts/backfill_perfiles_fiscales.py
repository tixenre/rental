"""Backfill de `cliente_perfiles_fiscales` desde el perfil default de `clientes` (one-off, #1240).

Con la migración a perfiles fiscales múltiples, un cliente con historial (CUIT
ya guardado en `clientes.cuit` antes de esta iniciativa) no tiene ninguna fila
en la tabla nueva — el selector del portal le aparecería vacío pese a tener un
perfil de siempre.

Este script copia TAL CUAL (sin re-verificar contra ARCA) el perfil default de
cada cliente con `cuit` no-nulo a una fila `es_default=TRUE` en
`cliente_perfiles_fiscales`. NO reabre el problema del fallback manual sin
verificar: el backstop de `emitir_factura`/`previsualizar_factura` (regla
"facturación siempre usa el dato de AFIP verificado") ya impide que un dato
viejo sin confirmar llegue a una factura real — este backfill es solo para que
la UX del selector no arranque en blanco para cuentas con historial.

Idempotente: salta clientes que ya tienen alguna fila en `cliente_perfiles_
fiscales` (respeta `uq_cliente_perfiles_fiscales_cuit`/`_default`). Best-effort
por cliente: si uno falla, loguea y sigue.

Uso:
  cd backend && source .venv/bin/activate && python scripts/backfill_perfiles_fiscales.py --dry-run
  # Contra prod (DATABASE_URL apuntando a prod):
  cd backend && source .venv/bin/activate && \\
    DATABASE_URL='postgres://...' python scripts/backfill_perfiles_fiscales.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db  # noqa: E402


def backfill(dry_run: bool = False) -> dict:
    conn = get_db()
    stats = {"candidatos": 0, "creados": 0, "errores": 0}
    try:
        rows = conn.execute(
            """
            SELECT c.id, c.cuit, c.perfil_impuestos, c.razon_social,
                   c.domicilio_fiscal, c.email_facturacion
            FROM clientes c
            WHERE c.cuit IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM cliente_perfiles_fiscales p WHERE p.cliente_id = c.id
              )
            """
        ).fetchall()
        stats["candidatos"] = len(rows)
        print(f"Clientes con CUIT sin ningún perfil fiscal: {len(rows)}")

        for r in rows:
            try:
                if dry_run:
                    print(f"  cliente {r['id']}: crearía perfil default con cuit={r['cuit']}")
                    continue
                conn.execute(
                    """INSERT INTO cliente_perfiles_fiscales
                           (cliente_id, cuit, perfil_impuestos, razon_social,
                            domicilio_fiscal, email_facturacion, es_default)
                       VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                       ON CONFLICT (cliente_id, cuit) DO NOTHING""",
                    (
                        r["id"], r["cuit"], r["perfil_impuestos"] or "consumidor_final",
                        r["razon_social"], r["domicilio_fiscal"], r["email_facturacion"],
                    ),
                )
                conn.commit()
                stats["creados"] += 1
                print(f"  cliente {r['id']}: perfil default creado (cuit={r['cuit']})")
            except Exception as e:  # noqa: BLE001
                conn.rollback()
                stats["errores"] += 1
                print(f"  cliente {r['id']}: ERROR {e}")
    finally:
        conn.close()
    return stats


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    print(f"=== Backfill perfiles fiscales {'(DRY RUN)' if dry else '(APLICANDO)'} ===")
    s = backfill(dry_run=dry)
    print(f"=== Resumen: {s} ===")
