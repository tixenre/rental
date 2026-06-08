"""seeds/demo_data.py — Datos ficticios para auditar / mostrar la app en LOCAL.

NUNCA corre en Railway (prod NI staging): el gate `settings.is_railway` lo
bloquea de entrada. Es para levantar la app en local con catálogo, clientes y
pedidos en varios estados — la base del skill `auditar-flujos` (recorrer los
flujos como agente de navegación) y de las capturas para revisión.

Uso:
    cd backend && . .venv/bin/activate
    export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rambla_rental
    python -m seeds.demo_data            # idempotente (no-op si ya sembrado)
    python -m seeds.demo_data --reset    # borra el contenido demo y resiembra

Idempotente: si ya está sembrado (marcador `app_settings.demo_seeded`) no hace
nada. `--reset` limpia el contenido de catálogo/pedidos de la base LOCAL (deja
intactas las tablas auto-sembradas por init_db: categorías, cuentas, estudio,
y el equipo centinela del estudio).

Los datos son inventados (clientes con email `@demo.local`, CUITs de ejemplo).
"""
import sys
from datetime import datetime, timedelta

from config import settings
from database import get_db, init_db

MARCADOR = "demo_seeded"

MARCAS = ["Sony", "Canon", "Aputure", "Godox", "DJI", "Sennheiser", "Manfrotto", "Nanlite"]

# (nombre, marca, modelo, precio_jornada ARS, categoría hoja existente)
EQUIPOS = [
    ("Sony FX6", "Sony", "ILME-FX6V", 45000, "Video"),
    ("Sony FX3", "Sony", "ILME-FX3", 38000, "Video"),
    ("Sony A7S III", "Sony", "ILCE-7SM3", 30000, "Foto"),
    ("Canon C70", "Canon", "EOS C70", 42000, "Video"),
    ("Canon 24-70 f/2.8", "Canon", "RF 24-70mm", 12000, "Zoom"),
    ("Sony 16-35 GM", "Sony", "FE 16-35mm f/2.8", 13000, "Zoom"),
    ("Sigma 35 f/1.4 Art", "Sony", "35mm Art", 9000, "Fijo"),
    ("Aputure 600D Pro", "Aputure", "LS 600d Pro", 18000, "LED daylight/bicolor"),
    ("Aputure 300X", "Aputure", "LS 300X", 14000, "LED daylight/bicolor"),
    ("Nanlite Forza 500", "Nanlite", "Forza 500", 12000, "LED daylight/bicolor"),
    ("Aputure Nova P300c", "Aputure", "Nova P300c", 16000, "LED RGB"),
    ("Softbox Aputure Light Dome II", "Aputure", "Light Dome II", 6000, "Softbox"),
    ("DJI RS3 Pro", "DJI", "RS 3 Pro", 11000, "Trípodes video"),
    ("Manfrotto 504X", "Manfrotto", "MVH504X", 7000, "Trípodes video"),
    ("Sennheiser MKH 416", "Sennheiser", "MKH 416", 8000, "Video"),
]

# (nombre, apellido, telefono, email, direccion, cuit, perfil, razon_social, descuento)
CLIENTES = [
    ("Santiago", "Pérez", "+54 9 223 555-1010", "santiago@demo.local",
     "Av. Colón 1234, Mar del Plata", "20-30111222-3", "consumidor_final", None, 0),
    ("Lucía", "Gómez", "+54 9 223 555-2020", "lucia@demo.local",
     "San Martín 850, Mar del Plata", "27-28999888-1", "consumidor_final", None, 10),
    ("Productora Faro", "S.R.L.", "+54 9 223 555-3030", "faro@demo.local",
     "Independencia 2200, Mar del Plata", "30-71222333-4", "responsable_inscripto",
     "Faro Contenidos S.R.L.", 5),
    ("Martín", "Díaz", "+54 9 11 4555-4040", "martin@demo.local",
     "Gorriti 4500, CABA", "20-35666777-8", "consumidor_final", None, 0),
]


def _cat_id(conn, nombre):
    row = conn.execute("SELECT id FROM categorias WHERE nombre = ?", (nombre,)).fetchone()
    return row["id"] if row else None


def _reset(conn):
    print("⚠️  --reset: borrando contenido demo de la base LOCAL…")
    conn.execute("DELETE FROM alquiler_pagos")
    conn.execute("DELETE FROM alquiler_items")
    conn.execute("DELETE FROM alquileres")
    conn.execute("DELETE FROM equipo_categorias WHERE equipo_id IN "
                 "(SELECT id FROM equipos WHERE es_recurso_interno = FALSE)")
    conn.execute("DELETE FROM equipos WHERE es_recurso_interno = FALSE")
    conn.execute("DELETE FROM clientes")
    conn.execute("DELETE FROM marcas")
    conn.execute("DELETE FROM app_settings WHERE key = ?", (MARCADOR,))


def seed(reset=False):
    if settings.is_railway:
        print("✗ ABORTADO: este seed NO corre en Railway (prod ni staging). Solo local.")
        sys.exit(1)

    init_db()
    with get_db() as conn:
        if reset:
            _reset(conn)
        already = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (MARCADOR,)
        ).fetchone()
        if already:
            print("• Ya sembrado (app_settings.demo_seeded). No-op. Usá --reset para resembrar.")
            return

        # ── Marcas ──────────────────────────────────────────────────────────
        marca_id = {}
        for nombre in MARCAS:
            row = conn.execute(
                "INSERT INTO marcas (nombre) VALUES (?) "
                "ON CONFLICT (nombre) DO UPDATE SET nombre = EXCLUDED.nombre RETURNING id",
                (nombre,),
            ).fetchone()
            marca_id[nombre] = row["id"]

        # ── Equipos + categorías ────────────────────────────────────────────
        equipo_ids = []
        for nombre, marca, modelo, precio, cat in EQUIPOS:
            row = conn.execute(
                "INSERT INTO equipos (nombre, brand_id, modelo, cantidad, precio_jornada, "
                "precio_jornada_manual, visible_catalogo, estado, ficha_completa) "
                "VALUES (?, ?, ?, ?, ?, TRUE, 1, 'operativo', TRUE) RETURNING id",
                (nombre, marca_id[marca], modelo, 2, precio),
            ).fetchone()
            eid = row["id"]
            equipo_ids.append(eid)
            cid = _cat_id(conn, cat)
            if cid:
                conn.execute(
                    "INSERT INTO equipo_categorias (equipo_id, categoria_id) VALUES (?, ?) "
                    "ON CONFLICT DO NOTHING",
                    (eid, cid),
                )

        # ── Clientes ────────────────────────────────────────────────────────
        cliente_ids = []
        for (nom, ape, tel, email, dir_, cuit, perfil, razon, desc) in CLIENTES:
            row = conn.execute(
                "INSERT INTO clientes (nombre, apellido, telefono, email, direccion, cuit, "
                "perfil_impuestos, razon_social, descuento) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                (nom, ape, tel, email, dir_, cuit, perfil, razon, desc),
            ).fetchone()
            cliente_ids.append(row["id"])

        eq = equipo_ids  # alias
        c_santi, c_lucia, c_faro, c_martin = cliente_ids
        now = datetime.now()
        numero = 1001

        def _crear_pedido(cliente_idx, estado, dias_offset, dur_dias, items, pagado=0,
                          tipo="diaria", descuento=0):
            nonlocal numero
            cid = cliente_ids[cliente_idx]
            cli = CLIENTES[cliente_idx]
            desde = now + timedelta(days=dias_offset)
            hasta = desde + timedelta(days=dur_dias)
            jornadas = max(1, dur_dias)
            total = sum(precio * cant * jornadas for (_, precio, cant) in items)
            total = int(round(total * (1 - descuento / 100)))
            row = conn.execute(
                "INSERT INTO alquileres (cliente_id, cliente_nombre, cliente_email, "
                "cliente_telefono, estado, fecha_desde, fecha_hasta, monto_total, monto_pagado, "
                "descuento_pct, numero_pedido, tipo, fuente) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'catalogo') RETURNING id",
                (cid, f"{cli[0]} {cli[1]}", cli[3], cli[2], estado, desde, hasta,
                 total, pagado, descuento, numero, tipo),
            ).fetchone()
            pid = row["id"]
            numero += 1
            for orden, (eqid, precio, cant) in enumerate(items):
                conn.execute(
                    "INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, precio_jornada, "
                    "subtotal, orden) VALUES (?, ?, ?, ?, ?, ?)",
                    (pid, eqid, cant, precio, precio * cant * jornadas, orden),
                )
            if pagado > 0:
                conn.execute(
                    "INSERT INTO alquiler_pagos (pedido_id, monto, concepto, destinatario, metodo) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (pid, pagado, "Seña" if pagado < total else "Pago total",
                     "Rambla", "transferencia"),
                )
            return pid

        # presupuesto (solicitud nueva, futuro) — Santiago
        _crear_pedido(0, "presupuesto", 7, 2,
                      [(eq[0], 45000, 1), (eq[7], 18000, 2), (eq[4], 12000, 1)])
        # confirmado con seña — Santiago (habilita remito/contrato en el portal)
        _crear_pedido(0, "confirmado", 3, 3,
                      [(eq[3], 42000, 1), (eq[5], 13000, 1)], pagado=50000)
        # retirado (en curso) — Lucía (10% desc)
        _crear_pedido(1, "retirado", -1, 2,
                      [(eq[1], 38000, 1), (eq[10], 16000, 1)], descuento=10)
        # finalizado, pago total — Faro SRL (RI, 5% desc)
        _crear_pedido(2, "finalizado", -20, 4,
                      [(eq[0], 45000, 1), (eq[3], 42000, 1), (eq[7], 18000, 2)],
                      pagado=400000, descuento=5)
        # cancelado — Martín
        _crear_pedido(3, "cancelado", -10, 1, [(eq[12], 11000, 1)])
        # reserva de estudio (presupuesto) — Santiago
        _crear_pedido(0, "presupuesto", 5, 0, [], tipo="estudio")

        conn.execute(
            "INSERT INTO app_settings (key, value, updated_by) VALUES (?, '1', 'demo-seed') "
            "ON CONFLICT (key) DO NOTHING",
            (MARCADOR,),
        )
        conn.commit()

        n_eq = conn.execute("SELECT count(*) AS n FROM equipos WHERE es_recurso_interno = FALSE").fetchone()["n"]
        n_cl = conn.execute("SELECT count(*) AS n FROM clientes").fetchone()["n"]
        n_pe = conn.execute("SELECT count(*) AS n FROM alquileres").fetchone()["n"]
        print(f"✓ Seed demo listo: {n_eq} equipos, {n_cl} clientes, {n_pe} pedidos.")
        print(f"  Cliente para el portal (dev-login): {CLIENTES[0][3]}")


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
