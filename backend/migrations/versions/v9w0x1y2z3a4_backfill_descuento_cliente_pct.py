"""Backfill: alquileres.descuento_pct histórico → descuento_cliente_pct
(Fase C-1, #1219) — preserva el display congelado de pedidos preexistentes.

Antes de C-1, `descuento_pct` competía por tamaño contra `descuento_jornadas_pct`
(max() no acumulativo) — sin distinguir si el valor venía de copiar el
descuento del cliente o de una edición manual del admin (esa distinción no
existía). La jerarquía nueva trata CUALQUIER `descuento_pct` histórico ≠0
como un override MANUAL que gana OUTRIGHT, ignorando jornadas — para un
pedido donde jornadas había sido el ganador histórico (valor mayor), el
desglose MOSTRADO divergiría de `monto_total` ya persistido/congelado
(hallazgo del supervisor, PR #1220 — exactamente la clase de bug "dos
cálculos del mismo número" #405 que esta iniciativa dice estar cerrando).

Fix: para toda fila EXISTENTE con `descuento_pct != 0`, se mueve ese valor a
`descuento_cliente_pct` (el slot del fallback de 2 vías) y se resetea
`descuento_pct` a 0 (= "sin override"). Es una identidad algebraica exacta:

    old_pct = max(descuento_pct, descuento_jornadas_pct)
    new_pct = max(descuento_cliente_pct := old_descuento_pct, descuento_jornadas_pct)
              (manual=0 → cae al fallback)

→ mismo NÚMERO y mismo origen mostrado ("cliente", igual que devolvía
`calcular_descuento_origen` antes de C-1) para el 100% de los pedidos ya
creados, sin necesidad de adivinar intención. Aplica a confirmados y abiertos
por igual — la identidad es válida en ambos casos (y para presupuestos
abiertos además restaura el comportamiento pre-C-1: `descuento_pct` volvía a
sobreescribirse solo con el descuento en vivo del cliente).

Data-only, corre UNA VEZ — no va en `init_db()` (que corre en cada arranque;
repetir este UPDATE tras un override manual genuino posterior a este deploy
lo pisaría a 0 de nuevo).

Revision ID: v9w0x1y2z3a4
Revises: t3u4v5w6x7y8
Create Date: 2026-07-03
"""
from typing import Sequence, Union
from alembic import op

revision: str = "v9w0x1y2z3a4"
down_revision: Union[str, Sequence[str], None] = "t3u4v5w6x7y8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE alquileres
        SET descuento_cliente_pct = descuento_pct,
            descuento_pct = 0
        WHERE descuento_pct IS NOT NULL AND descuento_pct != 0
    """)


def downgrade() -> None:
    # Irreversible con precisión (no se puede distinguir qué
    # `descuento_cliente_pct` vino de este backfill vs. de un recálculo
    # posterior) — no-op documentado, mismo criterio que otros backfills.
    pass
