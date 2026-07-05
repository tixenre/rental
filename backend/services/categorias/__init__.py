"""services/categorias — barrel público del motor de categorías.

Re-exporta commands/ (escritura) y queries/ (lectura). Ver CLAUDE.md de este
paquete para la estructura completa y las reglas de uso. `__all__` es la
lista de lo que el resto del backend debería importar de acá — si una función
no está ahí, es un detalle interno del paquete (o quedó desactualizado el
`__all__`, avisar).
"""

from .queries.validation import (
    validar_profundidad,
    detectar_ciclo,
    validar_nombre_unico,
    validar_existe,
)
from .queries.ancestry import (
    expandir_a_ancestros,
    expandir_a_ancestros_por_equipo,
    expandir_a_descendientes,
    root_of_categoria,
    sql_filtro_categoria,
    sql_filtro_equipos_por_categoria,
    buscar_id_por_nombre,
    categoria_ids_de_equipo,
    categorias_de_equipos,
    query_categorias_de_equipos,
    shape_categorias_de_equipos_rows,
)
from .queries.audit import (
    equipos_sin_categoria,
    categorias_sin_equipos,
)
from .queries.read import (
    categoria_por_id,
    categoria_por_nombre,
    categorias_por_ids,
    categoria_nombres_por_ids,
    listar_categorias_flat,
)
from .commands.crud import (
    crear,
    actualizar,
    eliminar,
    reordenar,
    actualizar_ranking,
    crear_si_no_existe,
    asignar_padre_si_no_tiene,
)
from .commands.assignment import (
    asignar_categorias,
    set_categoria_masivo,
    add_categoria_masivo,
    remove_categoria_masivo,
    copiar_categorias,
)
from .queries.tree import (
    listar_arbol_publico,
    listar_arbol_publico_flat,
    listar_arbol_admin,
)

__all__ = [
    "validar_profundidad",
    "detectar_ciclo",
    "validar_nombre_unico",
    "expandir_a_ancestros",
    "expandir_a_ancestros_por_equipo",
    "expandir_a_descendientes",
    "root_of_categoria",
    "buscar_id_por_nombre",
    "categoria_ids_de_equipo",
    "categorias_de_equipos",
    "query_categorias_de_equipos",
    "shape_categorias_de_equipos_rows",
    "sql_filtro_categoria",
    "sql_filtro_equipos_por_categoria",
    "categoria_por_id",
    "categoria_por_nombre",
    "categorias_por_ids",
    "categoria_nombres_por_ids",
    "listar_categorias_flat",
    "equipos_sin_categoria",
    "categorias_sin_equipos",
    "crear",
    "actualizar",
    "eliminar",
    "reordenar",
    "validar_existe",
    "actualizar_ranking",
    "crear_si_no_existe",
    "asignar_padre_si_no_tiene",
    "asignar_categorias",
    "set_categoria_masivo",
    "add_categoria_masivo",
    "remove_categoria_masivo",
    "copiar_categorias",
    "listar_arbol_publico",
    "listar_arbol_publico_flat",
    "listar_arbol_admin",
]
