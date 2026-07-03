"""services/finanzas_flujo — fachada de solo lectura sobre los motores de plata.

Manual cruzado: `docs/SISTEMA_FINANZAS_FLUJO.md`. Origen: auditoría cruzada de plata
(2026-07-02), a pedido del dueño ante el miedo de "drift de plata" — muchos motores
tocan dinero (`services/precios`, `reportes/liquidacion`, `contabilidad`,
`services/facturacion`) sin un punto único de acceso.

Qué es: un facade — cada función de acá delega 1:1 en el motor dueño, nunca
reimplementa. Qué NO es: no reemplaza ningún motor, no escribe nada (las
mutaciones siguen pasando por cada motor directo: `create_pedido_retry`,
`contabilidad.commands.*`, las rutas de `alquiler_pagos`).

Submódulos (cada uno delega en su motor dueño):
- `precios`        → precio de un equipo (delega en `services.precios`).
- `pedido`         → desglose de un pedido (delega en `services.precios`).
- `liquidacion`    → reparto de comisiones del mes (delega en `reportes.liquidacion`).
- `contabilidad`   → saldos/ganancia (delega en `contabilidad.queries`).
- `facturacion`    → datos para emitir una factura (delega en `services.facturacion`).
- `reconciliacion` → el semáforo unificado (delega en `reportes`/`contabilidad`).

Candado: `tests/test_finanzas_flujo_source_scan.py` verifica que ningún consumer
externo (routes, PDF, frontend-facing serializers) importe `reportes.liquidacion`
o `contabilidad.queries.*` directo, ni reimplemente el desglose de un pedido —
todo pasa por acá.
"""
