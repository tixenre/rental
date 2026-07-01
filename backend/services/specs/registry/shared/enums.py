"""Enum options compartidos entre categorías.

Estos enums se usan en specs `tipo="enum"` (formato, lens_mount, montura_luz).
Definirlos una sola vez evita inconsistencias entre cats — todos los `lens_mount`
del registry usan exactamente esta lista. Si hay que agregar una nueva montura,
se agrega acá y aplica cross-cat (Cámaras, Lentes, Adaptadores).
"""

from __future__ import annotations

# Formato de sensor / cobertura óptica. Ordenado de menor a mayor — el motor
# de compatibilidad "jerarquia" usa este orden para matchear:
# lente (contenedor) ≥ formato_sensor (contenido).
FORMATO_ENUM: list[str] = [
    "1\"", "MFT", "APS-C", "Super 35", "Full-frame", "Medium Format",
]

# Bayoneta de cámara/lente. Sin alias (E ≠ FE — mismo mount pero distinto label
# en el catálogo público; resolvemos el alias en los parsers, no acá).
LENS_MOUNT_ENUM: list[str] = [
    "E", "RF", "EF", "L", "Z", "X", "MFT", "PL", "BMD", "B4", "M42",
]

# Acople entre luz y modificador (Bowens-style speed rings). MISMA lista en
# Iluminación.montura_luz y Modificadores.montura_luz — el motor de compat
# matchea por igualdad exacta del value.
MONTURA_LUZ_ENUM: list[str] = [
    "Bowens", "Elinchrom", "Profoto",
    "Propietario", "Sin montura",
]
