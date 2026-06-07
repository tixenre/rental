"""Módulo de contabilidad (#809) — motor único de la plata "de adentro".

Espeja el patrón de `backend/reportes/` (una dirección física por dominio de
plata): SQL → filas planas → función pura → JSON; el HTTP es transporte fino en
`routes/contabilidad.py`.

Principio rector (no negociar):
- Los **ingresos por alquiler NO se re-cargan a mano**: DERIVAN de
  `alquiler_pagos` (única fuente del cobro, #722). El saldo de la caja de un
  socio se calcula sumando sus pagos por `destinatario`.
- El **libro de movimientos** (`movimientos`) guarda solo lo manual
  (gasto/transferencia/retiro/aporte/ajuste). Cada movimiento mueve plata entre
  cuentas; el saldo de cada cuenta se deriva.

Fase 1 (esta entrega): `cuentas` (CRUD + validación) y `saldos` (derivación de
ingresos + cálculo de saldos por cuenta). Gastos, rendición, P&L y cierre llegan
en fases siguientes.
"""
