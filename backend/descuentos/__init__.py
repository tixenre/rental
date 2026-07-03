"""Módulo de descuentos — motor único de "qué % de descuento gana".

Organizado CQRS-lite (espeja `backend/contabilidad/` y `services/specs/`):
`queries/` lee, nunca muta; `commands/` es la única puerta de mutación.
`commands/` puede importar de `queries/`; `queries/` NUNCA importa de
`commands/`.

Principio rector:
- Descuentos NO acumulativos: gana el de mayor valor entre las fuentes
  vigentes (`queries/decision.py::calcular_descuento_aplicable`).
- La firma toma una colección de fuentes con nombre (`{"cliente": pct,
  "jornadas": pct}`), no parámetros posicionales fijos — sumar una fuente
  nueva el día de mañana es agregar una key, no rediseñar la función.

Fuera de alcance a propósito: los descuentos de combo (`kit_componentes.
descuento_pct`, arma el precio BASE de un combo) son un dominio distinto,
sin cruce de código con este — ver `services/precios.py::precio_combo`.

Detalle de la estructura + invariantes → `CLAUDE.md` de este paquete.
"""
