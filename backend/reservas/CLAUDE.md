# `backend/reservas/` — motor único de reservas (CORE SAGRADO)

> Invariantes locales. El _por qué_ completo: `docs/DECISIONES.md` _2026-05-30_ y _2026-05-31_.

**Este es el core sagrado: cero overlap de pedidos, disponibilidad siempre correcta.** Todo cálculo
de disponibilidad / chequeo de stock / overlap del sistema pasa por acá (`estados.py`, `semantics.py`,
`disponibilidad.py`, `gate.py`). **No** se recrea ni duplica lógica de reservas en los routes.

Reglas que NO se rompen:

- **Una sola pieza de expansión:** toda expansión de composición (demanda hacia abajo `componentes_de`
  y consumo hacia arriba `parientes_de`) es **recursiva hasta las hojas** vía `_expandir_mult` en
  `semantics.py`. Lectura y gate usan la MISMA pieza → no pueden divergir. No reintroducir expansión
  inline de 1 nivel ni "otra función parecida". `reservado_total` reemplazó a `directo + via_kit`.
- **El candado es determinístico:** el gate (`gate.py::validar_stock`) lockea en **`ORDER BY id`**
  (sin deadlock). El `FOR UPDATE` / la transacción / el commit son **byte-idénticos** — no se tocan.
- **`esencial` propaga conjuntivo:** lectura con `solo_esenciales=True`, gate estricto con `False`.
- **El Estudio reusa este motor sin tocarlo** (columna `tipo`, equipo centinela; buffer aplicado
  expandiendo el rango **afuera** del motor, nunca adentro). Ver `docs/DECISIONES.md` _2026-05-27_.

**Alto radio de explosión → trabajar en Opus.** Red de seguridad (tests opt-in con Postgres real):
`test_reservas_concurrency_db.py`, `test_reservas_nested_db.py`, `test_gate_caracterizacion_c4.py`.
