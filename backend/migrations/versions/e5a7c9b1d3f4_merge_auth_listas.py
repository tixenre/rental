"""merge — unifica los dos heads que quedaron al juntar el stack de auth con dev.

Dos ramas avanzaron desde `f9a1c3e5b7d2`:
  · auth:  a1f2b3c4d5e6 (passkey) → b2c4d6e8f0a1 (auth_sessions)
  · dev:   c1a5d7e9f3b2 (cliente_listas) → d4f2a8b1c6e3 (carritos_compartidos)

Esta migración no crea nada — solo reúne ambos heads en uno para que `upgrade head`
tenga un único destino (las tablas ya las crean sus propias migraciones + init_db).

Revision ID: e5a7c9b1d3f4
Revises: b2c4d6e8f0a1, d4f2a8b1c6e3
Create Date: 2026-06-29
"""
from typing import Sequence, Union

revision: str = "e5a7c9b1d3f4"
down_revision: Union[str, Sequence[str], None] = ("b2c4d6e8f0a1", "d4f2a8b1c6e3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
