# Bugs — roadmap de fixes

> Auditoría hecha el 2026-05-11. `[ ]` por hacer, `[x]` arreglado.

---

## CRÍTICO

- [ ] **Open Redirect vía FRONTEND_BASE** — `backend/routes/auth.py:107,349`. Si `FRONTEND_BASE_URL` es manipulada a un dominio externo, las redirecciones post-auth mandan al usuario a ese dominio. Sin validación del valor al arrancar. **Fix**: validar que `FRONTEND_BASE` empiece con el dominio propio o usar solo relative paths.

- [ ] **Sin validación de fechas en disponibilidad** — `backend/routes/alquileres.py:217-267`. Si el cliente envía `fecha_desde="invalid"`, el error de SQL/parse se propaga sin HTTPException clara (500 sin contexto). **Fix**: `try datetime.fromisoformat()` antes de usar en SQL, lanzar HTTPException(400).

---

## ALTO

- [ ] **Construcción dinámica de SET en UPDATE clientes** — `backend/routes/cliente_portal.py:177`. `f"UPDATE clientes SET {', '.join(sets)} ..."` — frágil aunque controlado hoy. Un refactor futuro puede introducir inyección. **Fix**: validar `sets` keys contra whitelist explícita antes de construir el SQL.

- [ ] **Cursor no cerrado en attach_specs_destacados si hay excepción** — `backend/database.py` (función `attach_specs_destacados`). Si el `execute()` tira, `cur.close()` no se llama. **Fix**: envolver en `try/finally`.

---

## MEDIO

- [ ] **Stock negativo en disponibilidad para equipos sin historial** — `backend/routes/alquileres.py:228-241`. Si un equipo existe pero nunca fue alquilado, puede devolver stock 0 en lugar del stock real. **Fix**: usar `if eid not in cantidad` guard antes de restar.

- [ ] **eliminar_pago silencia errores de recálculo** — `backend/routes/alquileres.py:685-688`. Si `_recalcular_monto_pagado()` falla, el rollback ocurre pero el cliente ya vio "pago eliminado". **Fix**: propagar la excepción en lugar de silenciarla.

- [ ] **Estado "solicitado" inválido en cliente_cancelar_pedido** — `backend/routes/cliente_portal.py:250`. Valida contra `("borrador", "presupuesto", "solicitado")` pero "solicitado" no existe en los estados reales del sistema. **Fix**: alinear con los estados reales definidos en alquileres.py.

---

## Sugerencia de orden de ataque

1. Críticos: fechas en disponibilidad (fix chico) + open redirect (fix chico con validación).
2. Altos: cursor en `attach_specs_destacados` + whitelist en UPDATE clientes.
3. Medios: los tres son fixes de 1-5 líneas, se pueden hacer en una tanda.
