"""dataio/natural_keys.py — Resolvers de claves naturales → IDs SERIAL.

Cada import necesita resolver las FKs declaradas como claves naturales
(nombre, slug, path) a los `id` SERIAL reales de la DB.

Estrategia: cargar todos los IDs relevantes en memoria al inicio del
import por cada tabla padre, en dicts. Los lookups después son O(1).

Para `categorias`, además se reconstruye el path "padre" usando nombres
únicos (la columna `categorias.nombre` es UNIQUE globalmente, por lo que
un nombre identifica de forma única una categoría).
"""

from __future__ import annotations


class KeyResolver:
    """Cache de claves naturales → IDs por tabla. Se carga lazy al primer uso.

    Uso:
        resolver = KeyResolver(conn)
        marca_id = resolver.marca_id("Sony")
        cat_id = resolver.categoria_id("Cámaras")
        spec_def_id = resolver.spec_def_id("Cámaras", "sensor")
        equipo_id = resolver.equipo_id("sony-fx3")
    """

    def __init__(self, conn):
        self.conn = conn
        self._marcas: dict[str, int] | None = None
        self._categorias: dict[str, int] | None = None
        self._spec_defs: dict[tuple[str | None, str], int] | None = None
        self._equipos: dict[str, int] | None = None
        self._clientes: dict[str, int] | None = None
        self._alquileres: dict[int, int] | None = None

    # ── refresco / invalidación tras inserts ─────────────────────────────────

    def refresh(self) -> None:
        """Limpia el cache. Llamar después de un batch de inserts."""
        self._marcas = None
        self._categorias = None
        self._spec_defs = None
        self._equipos = None
        self._clientes = None
        self._alquileres = None

    def refresh_marcas(self) -> None:
        self._marcas = None

    def refresh_categorias(self) -> None:
        self._categorias = None
        # spec_defs depende de categorias para resolver categoria_raiz_id
        self._spec_defs = None

    def refresh_spec_defs(self) -> None:
        self._spec_defs = None

    def refresh_equipos(self) -> None:
        self._equipos = None

    def refresh_clientes(self) -> None:
        self._clientes = None

    def refresh_alquileres(self) -> None:
        self._alquileres = None

    # ── marcas ───────────────────────────────────────────────────────────────

    def _load_marcas(self) -> dict[str, int]:
        rows = self.conn.execute("SELECT id, nombre FROM marcas").fetchall()
        return {r["nombre"]: r["id"] for r in rows}

    def marca_id(self, nombre: str | None) -> int | None:
        if not nombre:
            return None
        if self._marcas is None:
            self._marcas = self._load_marcas()
        return self._marcas.get(nombre)

    # ── categorias ───────────────────────────────────────────────────────────

    def _load_categorias(self) -> dict[str, int]:
        from services.categorias import listar_categorias_flat
        cats = listar_categorias_flat(self.conn)
        return {c["nombre"]: c["id"] for c in cats}

    def categoria_id(self, nombre: str | None) -> int | None:
        if not nombre:
            return None
        if self._categorias is None:
            self._categorias = self._load_categorias()
        return self._categorias.get(nombre)

    # ── spec_definitions (composite key) ────────────────────────────────────

    def _load_spec_defs(self) -> dict[tuple[str | None, str], int]:
        rows = self.conn.execute("""
            SELECT sd.id, sd.spec_key, c.nombre AS categoria_raiz_nombre
            FROM spec_definitions sd
            LEFT JOIN categorias c ON c.id = sd.categoria_raiz_id
        """).fetchall()
        return {(r["categoria_raiz_nombre"], r["spec_key"]): r["id"] for r in rows}

    def spec_def_id(
        self, categoria_raiz_nombre: str | None, spec_key: str
    ) -> int | None:
        if self._spec_defs is None:
            self._spec_defs = self._load_spec_defs()
        return self._spec_defs.get((categoria_raiz_nombre, spec_key))

    # ── equipos ──────────────────────────────────────────────────────────────

    def _load_equipos(self) -> dict[str, int]:
        # slug es la clave natural; puede ser NULL durante la transición.
        # Solo cargamos los que ya tienen slug.
        rows = self.conn.execute(
            "SELECT id, slug FROM equipos WHERE slug IS NOT NULL"
        ).fetchall()
        return {r["slug"]: r["id"] for r in rows}

    def equipo_id(self, slug: str | None) -> int | None:
        if not slug:
            return None
        if self._equipos is None:
            self._equipos = self._load_equipos()
        return self._equipos.get(slug)

    # ── clientes ─────────────────────────────────────────────────────────────

    def _load_clientes(self) -> dict[str, int]:
        # Email lookup case-insensitive: el UNIQUE es sobre email tal cual,
        # pero la app usa LOWER(email) en queries (ver índice
        # idx_clientes_email_lower en database.py).
        rows = self.conn.execute(
            "SELECT id, LOWER(email) AS email FROM clientes WHERE email IS NOT NULL"
        ).fetchall()
        return {r["email"]: r["id"] for r in rows}

    def cliente_id(self, email: str | None) -> int | None:
        if not email:
            return None
        if self._clientes is None:
            self._clientes = self._load_clientes()
        return self._clientes.get(email.strip().lower())

    # ── alquileres ───────────────────────────────────────────────────────────

    def _load_alquileres(self) -> dict[int, int]:
        rows = self.conn.execute(
            "SELECT id, numero_pedido FROM alquileres WHERE numero_pedido IS NOT NULL"
        ).fetchall()
        return {int(r["numero_pedido"]): r["id"] for r in rows}

    def alquiler_id(self, numero_pedido: int | None) -> int | None:
        if numero_pedido is None:
            return None
        if self._alquileres is None:
            self._alquileres = self._load_alquileres()
        return self._alquileres.get(int(numero_pedido))
