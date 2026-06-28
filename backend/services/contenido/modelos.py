"""Modelos (forma del dato) del módulo de contenido de producto.

`ComponenteContenido` es la forma canónica de UN componente directo (1 nivel) de
un kit/combo, pensada para MOSTRAR (catálogo, ficha, documentos, detalle de
pedido). Es un superset: los campos extendidos son opcionales porque no todos los
consumidores los usan (el catálogo no necesita `valor_reposicion`, el remito sí).

Esto es solo la FORMA del dato — la lógica vive en `contenido.py`, igual que el
resto del repo (funciones que reciben `conn`, no objetos con estado).
"""
from typing import Optional

from pydantic import BaseModel


class ComponenteContenido(BaseModel):
    """Un componente DIRECTO (1 nivel) de un kit/combo, decorado para mostrar.

    `componente_id`/`cantidad`/`esencial` son la arista de la receta (lo que el
    gate también lee, vía `reservas.semantics.componentes_de`). El resto son campos
    de presentación del equipo componente.
    """
    componente_id: int
    cantidad: int
    esencial: bool = True
    orden: Optional[int] = None
    descuento_pct: Optional[float] = None
    nombre: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    serie: Optional[str] = None
    valor_reposicion: Optional[float] = None
    foto_url: Optional[str] = None
    foto_url_sm: Optional[str] = None
    foto_url_thumb: Optional[str] = None
    nombre_publico: Optional[str] = None
    nombre_publico_largo: Optional[str] = None
    visible_catalogo: Optional[int] = None
    stock_total: Optional[int] = None
    kc_id: Optional[int] = None
