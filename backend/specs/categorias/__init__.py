"""Una categoría = un módulo. Cada uno expone `CAT` (instancia de
CategoriaRegistry) con sus specs y sub-cats.

`specs.__init__` los combina en el REGISTRY global. Agregar una cat nueva:
crear `categorias/nueva.py` exportando `CAT`, y agregarlo al dict de
REGISTRY en `specs/__init__.py`.
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
