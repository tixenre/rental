# PLAN.md — archivado (histórico, no es la fuente de verdad)

Este doc fue el **spec de implementación pre-código** del motor de facturación ARCA (tracking
#1139). Se archiva tal cual en el historial de git — no se actualiza en el lugar porque ya
divergió de la implementación real en varios puntos (ej. la DDL de `facturas` describía
`imp_neto`/`imp_iva`/`imp_total` como `INTEGER`, hoy `NUMERIC(12,2)` desde el fix de centavos
#1209; el emisor era un par fijo hardcodeado `'pablo'|'santini'`, hoy es la tabla administrable
`emisores_arca`; `pdf.py` del adapter pasó a `comprobante_render.py` al migrar el render a
`arca_fe`) — mantenerlo sincronizado sería una segunda fuente de verdad del "cómo funciona X",
justo lo que `docs/SISTEMA_FACTURACION.md` existe para evitar (_2026-06-25 — Manuales técnicos
por sistema_, `docs/MEMORIA.md`).

**Fuente de verdad actual del motor de facturación** → [`docs/SISTEMA_FACTURACION.md`](../../../docs/SISTEMA_FACTURACION.md).

Para ver el spec original (útil solo como contexto histórico de las Fases 0-6 y las decisiones de
diseño que se tomaron antes de escribir código): `git log -p -- backend/services/facturacion/PLAN.md`.
