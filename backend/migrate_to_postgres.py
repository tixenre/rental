#!/usr/bin/env python3
"""
Script para migrar datos de SQLite (JSON) a PostgreSQL.
Uso: python migrate_to_postgres.py
"""

import json
import os
from database import get_db, get_connection_params

def migrate():
    """Lee db_backup.json e inserta los datos en PostgreSQL."""

    # Leer backup
    if not os.path.exists("db_backup.json"):
        print("❌ db_backup.json no encontrado. Corre primero:")
        print("   python backup_sqlite.py")
        return

    with open("db_backup.json", "r") as f:
        backup = json.load(f)

    print(f"📦 Datos cargados: {len(backup)} tablas")

    # Conectar a PostgreSQL
    try:
        conn = get_db()
        cur = conn.cursor()
        print(f"✅ Conectado a PostgreSQL: {get_connection_params()['database']}")
    except Exception as e:
        print(f"❌ Error conectando a PostgreSQL: {e}")
        print(f"   Parámetros: {get_connection_params()}")
        return

    # Deshabilitar constraints temporalmente
    cur.execute("SET CONSTRAINTS ALL DEFERRED")

    try:
        # 1. Insertar etiquetas (sin dependencias)
        if backup.get("etiquetas"):
            print("→ Migrando etiquetas...")
            for row in backup["etiquetas"]:
                cur.execute(
                    "INSERT INTO etiquetas (id, nombre) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (row["id"], row["nombre"])
                )
            print(f"  ✓ {len(backup['etiquetas'])} etiquetas")

        # 2. Insertar equipos
        if backup.get("equipos"):
            print("→ Migrando equipos...")
            for row in backup["equipos"]:
                cur.execute("""
                    INSERT INTO equipos
                    (id, nombre, marca, modelo, cantidad, precio_jornada, precio_usd,
                     roi_pct, valor_reposicion, foto_url, fecha_compra, serie, bh_url,
                     dueno, visible_catalogo, estado, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    row.get("id"),
                    row.get("nombre"),
                    row.get("marca"),
                    row.get("modelo"),
                    row.get("cantidad", 1),
                    row.get("precio_jornada"),
                    row.get("precio_usd"),
                    row.get("roi_pct"),
                    row.get("valor_reposicion"),
                    row.get("foto_url"),
                    row.get("fecha_compra"),
                    row.get("serie"),
                    row.get("bh_url"),
                    row.get("dueno", "Rambla"),
                    row.get("visible_catalogo", 1),
                    row.get("estado", "ok"),
                    row.get("created_at"),
                    row.get("updated_at"),
                ))
            print(f"  ✓ {len(backup['equipos'])} equipos")

        # 3. Insertar clientes
        if backup.get("clientes"):
            print("→ Migrando clientes...")
            for row in backup["clientes"]:
                cur.execute("""
                    INSERT INTO clientes
                    (id, nombre, apellido, telefono, email, direccion, cuit,
                     descuento, perfil_impuestos, notas, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    row.get("id"),
                    row.get("nombre"),
                    row.get("apellido"),
                    row.get("telefono"),
                    row.get("email"),
                    row.get("direccion"),
                    row.get("cuit"),
                    row.get("descuento", 0),
                    row.get("perfil_impuestos", "consumidor_final"),
                    row.get("notas"),
                    row.get("created_at"),
                    row.get("updated_at"),
                ))
            print(f"  ✓ {len(backup['clientes'])} clientes")

        # 4. Insertar alquileres
        if backup.get("alquileres"):
            print("→ Migrando alquileres...")
            for row in backup["alquileres"]:
                cur.execute("""
                    INSERT INTO alquileres
                    (id, cliente_id, cliente_nombre, cliente_email, cliente_telefono,
                     notas, estado, fecha_desde, fecha_hasta, monto_total, monto_pagado,
                     descuento_pct, fuente, numero_remito, numero_pedido, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    row.get("id"),
                    row.get("cliente_id"),
                    row.get("cliente_nombre"),
                    row.get("cliente_email"),
                    row.get("cliente_telefono"),
                    row.get("notas"),
                    row.get("estado", "presupuesto"),
                    row.get("fecha_desde"),
                    row.get("fecha_hasta"),
                    row.get("monto_total", 0),
                    row.get("monto_pagado", 0),
                    row.get("descuento_pct", 0),
                    row.get("fuente", "sistema"),
                    row.get("numero_remito"),
                    row.get("numero_pedido"),
                    row.get("created_at"),
                    row.get("updated_at"),
                ))
            print(f"  ✓ {len(backup['alquileres'])} alquileres")

        # 5. Insertar etiquetas de equipos
        if backup.get("equipo_etiquetas"):
            print("→ Migrando etiquetas de equipos...")
            for row in backup["equipo_etiquetas"]:
                cur.execute("""
                    INSERT INTO equipo_etiquetas (equipo_id, etiqueta_id, orden)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    row.get("equipo_id"),
                    row.get("etiqueta_id"),
                    row.get("orden", 0),
                ))
            print(f"  ✓ {len(backup['equipo_etiquetas'])} relaciones equipo-etiqueta")

        # 6. Insertar usuarios
        if backup.get("usuarios"):
            print("→ Migrando usuarios...")
            for row in backup["usuarios"]:
                cur.execute("""
                    INSERT INTO usuarios (id, email, nombre, password_hash, creado_en)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    row.get("id"),
                    row.get("email"),
                    row.get("nombre"),
                    row.get("password_hash"),
                    row.get("creado_en"),
                ))
            print(f"  ✓ {len(backup['usuarios'])} usuarios")

        conn.commit()
        print("\n✅ Migración completada exitosamente!")
        print(f"   Equipos: {len(backup.get('equipos', []))}")
        print(f"   Clientes: {len(backup.get('clientes', []))}")
        print(f"   Alquileres: {len(backup.get('alquileres', []))}")

        cur.close()
        conn.close()

    except Exception as e:
        conn.rollback()
        print(f"❌ Error durante migración: {e}")
        import traceback
        traceback.print_exc()
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
