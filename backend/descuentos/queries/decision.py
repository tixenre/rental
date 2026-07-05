"""descuentos/queries/decision.py — quién gana entre las fuentes de descuento.

Movido de `services/precios.py::descuento_aplicable` (move-verbatim en el
cálculo; la firma cambia de 2 floats posicionales a un dict con nombre — ver
`calcular_descuento_aplicable`). `calcular_descuento_origen` consolida una
reimplementación que vivía duplicada a mano en `routes/alquileres/
cotizacion.py`.
"""
from typing import Optional


def calcular_descuento_aplicable(fuentes: dict[str, Optional[float]]) -> float:
    """Descuentos NO acumulativos: gana la fuente de mayor %.

    `fuentes` = {"cliente": pct, "jornadas": pct, ...} — agregar una fuente
    nueva (ej. un futuro descuento estacional) es sumar una key, no tocar la
    firma. En empate gana la primera fuente declarada (hoy: "cliente") — es
    una atención manual del dueño; en el monto no cambia nada, los dos pcts
    son iguales en empate.

    Topa en 100: un descuento > 100% daría neto/total NEGATIVO. Solo lo
    podría setear un admin, pero acotamos para no perder plata por un typo.
    """
    if not fuentes:
        return 0.0
    normalizados = {k: max(0.0, float(v or 0)) for k, v in fuentes.items()}
    return min(100.0, max(normalizados.values()))


def calcular_descuento_origen(fuentes: dict[str, Optional[float]]) -> str:
    """Nombre de la fuente ganadora (la key de `fuentes`), o "ninguno" si
    todas son 0. Para el label de UI — "Descuento cliente" / "Descuento
    jornadas (N jornadas)". Usa el mismo dict normalizado que
    `calcular_descuento_aplicable`, así las dos funciones nunca divergen en
    el criterio de empate."""
    if not fuentes:
        return "ninguno"
    normalizados = {k: max(0.0, float(v or 0)) for k, v in fuentes.items()}
    if max(normalizados.values()) == 0:
        return "ninguno"
    return max(normalizados, key=normalizados.get)


def resolver_descuento_pedido(
    manual_pct: Optional[float],
    cliente_pct: Optional[float],
    jornadas_pct: Optional[float],
) -> float:
    """Jerarquía de 3 niveles (Fase C-1, #1219) — NO es una competencia plana.

    Si `manual_pct` está seteado (≠0, un override explícito del admin para
    ESE pedido puntual), gana OUTRIGHT — no compite por tamaño contra
    cliente/jornadas. Si es 0 ("sin override"), cae al 2-way de siempre entre
    cliente y jornadas (`calcular_descuento_aplicable`).

    Nota de diseño: `0` es el sentinel de "sin override" (no `NULL`). Limitación
    aceptada: no se puede forzar "cero descuento" en un pedido puntual de un
    cliente que normalmente tiene descuento (0 siempre cae al fallback). Se
    probó un flag `manual_activo` para eso (Fase C-4) pero se removió: en la
    práctica los descuentos se manejan por pedido con el override manual y no
    hay descuentos fijos por cliente, así que forzar 0% nunca hacía falta.
    """
    manual = max(0.0, float(manual_pct or 0))
    if manual:
        return min(100.0, manual)
    return calcular_descuento_aplicable({"cliente": cliente_pct, "jornadas": jornadas_pct})


def resolver_origen_pedido(
    manual_pct: Optional[float],
    cliente_pct: Optional[float],
    jornadas_pct: Optional[float],
) -> str:
    """Origen del descuento ganador bajo la jerarquía de `resolver_descuento_pedido`
    — "manual" si el override ganó outright, si no el mismo criterio que
    `calcular_descuento_origen` para el 2-way de fallback."""
    manual = max(0.0, float(manual_pct or 0))
    if manual:
        return "manual"
    return calcular_descuento_origen({"cliente": cliente_pct, "jornadas": jornadas_pct})


def resolver_descuento_monto_pedido(
    bruto: int,
    manual_tipo: Optional[str],
    manual_pct: Optional[float],
    manual_monto: Optional[float],
    cliente_pct: Optional[float],
    jornadas_pct: Optional[float],
) -> dict:
    """Descuento del pedido en PESOS — Fase C-2 (#1219): el override manual
    puede ser un % (de siempre) o un $ fijo, mismo campo de la UI con un
    selector al lado. Se compone SOBRE `resolver_descuento_pedido` (no la
    reemplaza) porque el caso "%" es exactamente ese cálculo; el caso "$"
    necesita `bruto` (que `resolver_descuento_pedido` no conoce, por diseño:
    es puramente de %) para capear el override y que el neto nunca sea
    negativo — por eso esta función vive un nivel más arriba, no adentro de
    la de C-1.

    Devuelve `{"monto": int, "pct": float}` — `pct` es el % EFECTIVO
    (derivado del monto cuando el override es "$"; el mismo valor de
    `resolver_descuento_pedido` sin redondeo extra cuando es "%", así el path
    "%" es byte-idéntico al cálculo previo a C-2).

    `manual_tipo` "monto" + `manual_monto` > 0 → gana OUTRIGHT (misma
    jerarquía C-1), capeado a `bruto`. `manual_monto` 0/None con
    `manual_tipo="monto"` es el mismo sentinel "sin override" que `pct=0` →
    cae al fallback cliente/jornadas.
    """
    bruto_i = max(0, int(bruto or 0))
    if (manual_tipo or "pct") == "monto":
        monto_manual = max(0.0, float(manual_monto or 0))
        if monto_manual:
            monto = min(bruto_i, int(round(monto_manual)))
            # 4 decimales (no 2): el toggle %/$ del builder convierte el
            # override al equivalente de la otra unidad usando este `pct` —
            # con solo 2 decimales, la ida y vuelta %→$→% perdía unos pesos
            # en el redondeo intermedio (ej. $50.000 → "6.32%" → $49.998).
            # Con 4, el redondeo intermedio pierde centavos, no pesos.
            pct_efectivo = round(monto / bruto_i * 100, 4) if bruto_i else 0.0
            return {"monto": monto, "pct": pct_efectivo}
    pct = resolver_descuento_pedido(manual_pct, cliente_pct, jornadas_pct)
    return {"monto": int(round(bruto_i * pct / 100)), "pct": pct}


def resolver_origen_pedido_monto(
    manual_tipo: Optional[str],
    manual_pct: Optional[float],
    manual_monto: Optional[float],
    cliente_pct: Optional[float],
    jornadas_pct: Optional[float],
) -> str:
    """Origen del descuento ganador bajo `resolver_descuento_monto_pedido` —
    tipo-aware (C-2): "manual" también cuando gana un override en $ fijo. Para
    el caso "%" delega en `resolver_origen_pedido` sin reimplementar el criterio."""
    if (manual_tipo or "pct") == "monto" and manual_monto:
        return "manual"
    return resolver_origen_pedido(manual_pct, cliente_pct, jornadas_pct)
