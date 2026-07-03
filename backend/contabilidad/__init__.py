"""Módulo de contabilidad (#809) — motor único de la plata "de adentro".

Organizado CQRS-lite (espeja `services/specs/` y `services/specs_ingesta/`):
`queries/` lee, nunca muta; `commands/` es la única puerta de mutación.
`commands/` puede importar de `queries/`; `queries/` NUNCA importa de
`commands/`. `constants.py` tiene lo que ambos lados necesitan (cobradores,
tipos de cuenta/movimiento, partes de la rendición) — vive fuera de
`queries/`/`commands/` justamente porque `queries/` lo necesita y no puede
importarlo desde el lado de escritura.

Principio rector (no negociar):
- Los **ingresos por alquiler NO se re-cargan a mano**: DERIVAN de
  `alquiler_pagos` (única fuente del cobro, #722). El saldo de la caja de un
  socio se calcula sumando sus pagos por `destinatario`.
- El **libro de movimientos** (`movimientos`) guarda solo lo manual
  (gasto/transferencia/retiro/aporte/ajuste). Cada movimiento mueve plata entre
  cuentas; el saldo de cada cuenta se deriva.

Detalle de la estructura + invariantes → `CLAUDE.md` de este paquete.
"""
