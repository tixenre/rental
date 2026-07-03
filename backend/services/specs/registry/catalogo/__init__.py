"""Una categoría = un módulo. Cada uno expone `CAT` (instancia de
CategoriaRegistry) con sus specs, anclada por nombre a una categoría raíz
real del catálogo.

`services/specs/registry/__init__.py` los combina en el REGISTRY global.
Agregar una cat nueva: crear `catalogo/nueva.py` exportando `CAT`, y
agregarlo al dict de REGISTRY ahí.
"""

from .adaptadores import CAT as ADAPTADORES
from .camaras import CAT as CAMARAS
from .filtros import CAT as FILTROS
from .iluminacion import CAT as ILUMINACION
from .lentes import CAT as LENTES
from .modificadores import CAT as MODIFICADORES

__all__ = [
    "CAMARAS", "LENTES", "ILUMINACION",
    "MODIFICADORES", "ADAPTADORES", "FILTROS",
]
