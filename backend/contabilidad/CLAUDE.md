# `backend/contabilidad/` — motor único de la plata "de adentro"

> Invariantes locales. El _por qué_ completo: `docs/DECISIONES.md` _2026-06-07 — `backend/contabilidad/`_.

**Toda la plata interna del negocio vive acá** (cajas/cuentas, libro de movimientos, saldos,
rendición entre socios, ganancia/P&L, cierre contable, reconciliación); los routes son solo
transporte HTTP. No re-implementar plata interna ad-hoc en un route.

Reglas que NO se rompen:

- **Los ingresos por alquiler DERIVAN de `alquiler_pagos`** (única fuente del cobro): el saldo de la
  caja de un cobrador se calcula sumando sus pagos por `destinatario`. **Nunca** recargar un movimiento
  por un cobro de cliente → cero doble-contabilización por construcción.
- **La plata no se borra:** anular un movimiento es **soft-delete con motivo** (deja de contar para los
  saldos pero queda trazable). Auditoría `created_by/updated_by/anulado_por`.
- **Enteros ARS** en todo el cálculo (no `NUMERIC`).
- **Multi-moneda no se mezcla:** cada caja tiene `moneda` (ARS/USD); saldos por moneda; transferencia/
  ajuste exigen misma moneda (sin conversión automática); P&L en ARS. La **moneda es inmutable tras
  crear** — NO "arreglar" eso como si fuera bug.
- **Devengado (P&L) ≠ percibido (saldo de caja)** a propósito: pueden no coincidir mes a mes.
- **Cobradores en la constante única `COBRADORES`** (Pablo/Tincho/Rambla; Rambla = cobrador por
  defecto) + `SOCIOS_HUMANOS` (Pablo/Tincho). **No duplicar** esos valores fuera de la constante.
- **Socios (Pablo/Tincho) = cuenta corriente, NO caja:** su saldo es `arranque + cobró − su parte ±
  rendiciones` (>0 DEUDOR le debe a Rambla, <0 ACREEDOR Rambla le debe, 0 saldado); `su parte` sale de
  la liquidación (`reportes/`). **No** suman al total disponible y una **negativa (acreedor) NO es
  error** de reconciliación. Solo **Rambla/Fondo Rambla** es caja de plata real (su parte no se resta).
- **Candado de mes cerrado:** crear/editar/anular pasa por el motor (`_exigir_mes_abierto`) — un
  endpoint que escriba `movimientos` por fuera se saltearía el candado. La rendición reusa `SALDADO_CTE`
  (mismo universo de pedidos que el reporte). Esquema en dos capas (`init_db()` + migración) para toda tabla nueva.
