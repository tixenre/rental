# `backend/reportes/` — motor único de reportes financieros

> Invariantes locales. El _por qué_ completo: `docs/DECISIONES.md` _2026-06-03 — `backend/reportes/`_
> y _2026-06-03 — Cierre de mes + clean start_.

**Es lógica de plata: todo cálculo de reporte financiero vive acá, el route es solo transporte HTTP +
CSV.** Atribución, prorrateo, reparto de comisiones y agregación pasan por este paquete
(`comisiones.py` = modelo + reparto + validación; `liquidacion.py` = SQL de pedidos saldados +
prorrateo + `agregar` pura; `cierres.py`; `reconciliacion.py`). No re-implementar plata en routes.

Reglas que NO se rompen:

- **Pipeline partido SQL→filas→`agregar`** para testear la matemática sin DB. No mezclar.
- **Modelo de comisiones editable** desde el back-office (`app_settings.comisiones_modelo`); su
  default vive en `comisiones.DEFAULT_MODELO` — **no hardcodear** otra cosa.
- **Clean start = constante única `LIQUIDACION_INICIO`** (en `liquidacion.py`, embebida en
  `SALDADO_CTE`): pedidos con `fecha_desde` anterior **no cuentan** para la liquidación. **No duplicar
  ese valor** fuera de la constante. Es **fija en código a propósito, NO administrable**.
- **El clean start aplica SOLO a la liquidación.** El **Resumen general de estadísticas sigue mostrando
  el histórico completo** — no filtrarlo con el clean start.
- **Cerrar mes = foto inmutable** (`liquidacion_cierres`): mientras está cerrado, el reporte se sirve
  de la foto. Tabla en `init_db()` **+** migración (esquema en dos capas, `docs/DECISIONES.md` _2026-06-03_).
