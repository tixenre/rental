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
