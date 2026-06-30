# ruff: noqa
# Fixture smoke para la señal D del harness de evals (ver scripts/evals/README.md).
# Defectos PLANTADOS a propósito: al invocar el skill merged `auditoria-codigo`, cada lente debería
# disparar sobre el suyo. NO es código real — no se importa, no se ejecuta, no se testea.

import sqlite3


# [lente SEGURIDAD] SQL por f-string (inyección). El lente seguridad debe marcarlo.
def buscar_cliente(conn, nombre):
    return conn.execute(f"SELECT * FROM clientes WHERE nombre = '{nombre}'").fetchall()


# [lente PERFORMANCE] N+1: query adentro del loop. El lente performance debe marcarlo.
def total_por_pedido(conn, pedidos):
    out = []
    for p in pedidos:
        row = conn.execute("SELECT SUM(monto) FROM pagos WHERE pedido_id = ?", (p["id"],)).fetchone()
        out.append(row[0])
    return out


# [lente TESTS] assertion vaga: solo chequea 200, no el contenido/efecto. El lente tests debe marcarlo.
def test_endpoint_equipos(client):
    resp = client.get("/admin/equipos")
    assert resp.status_code == 200
