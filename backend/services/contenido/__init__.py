"""Paquete `services.contenido` — puerta única de "qué incluye un producto".

Fuente única de la lista de componentes de un kit/combo para MOSTRAR (catálogo,
ficha, documentos, detalle de pedido), derivada de la MISMA tabla `kit_componentes`
que el motor de reservas usa para reservar → lo mostrado no se desincroniza de lo
reservado. Ver `contenido.py` para la semántica y `docs/SISTEMA_CONTENIDO.md`.
"""
from services.contenido.contenido import contenido_de, contenido_de_batch
from services.contenido.modelos import ComponenteContenido

__all__ = [
    "ComponenteContenido",
    "contenido_de",
    "contenido_de_batch",
]
