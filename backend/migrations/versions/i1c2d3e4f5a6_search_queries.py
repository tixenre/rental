"""tabla search_queries — registro de búsquedas del catálogo público

Guarda CADA búsqueda asentada del buscador público para analítica interna
(qué busca la gente y, sobre todo, qué buscan y no encontramos).

Diseño raw + normalizado:
- `query_text`: el término tal cual lo tipeó el usuario (crudo, nada se pierde).
- `query_norm`: minúsculas, sin acentos, espacios colapsados → para agrupar
  variantes equivalentes en los reportes. El crudo queda intacto para poder
  re-agrupar más fino en el futuro (sinónimos/variantes) sin perder data.

Revision ID: i1c2d3e4f5a6
Revises: h1b2c3d4e5f6
Create Date: 2026-06-02
"""

from typing import Union

from alembic import op

revision: str = "i1c2d3e4f5a6"
down_revision: Union[str, None] = "h1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS search_queries (
            id           SERIAL PRIMARY KEY,
            query_text   VARCHAR(120) NOT NULL,
            query_norm   VARCHAR(120) NOT NULL,
            result_count INTEGER NOT NULL DEFAULT 0,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_search_queries_norm ON search_queries(query_norm)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_search_queries_created ON search_queries(created_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS search_queries")
