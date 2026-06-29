"""Modelos (forma del dato) del módulo de carrito.

`SeleccionItem` es la forma canónica de UN renglón de la selección del carrito
(equipo + cantidad, SIN precio: la plata la pone el motor de precios, no el cliente).
Consolida las tres formas hoy divergentes — `CartItem` (routes/carritos.py),
`CompartirItemIn` (routes/compartir.py) y `ListaItemIn` (routes/cliente_portal/listas.py).

Solo la FORMA — la lógica vive en `seleccion.py` (funciones que reciben `conn`, no
objetos con estado), igual que el resto del repo. Ver `docs/SISTEMA_CARRITO.md`.
"""
from pydantic import BaseModel

# Caps de seguridad (cotas sanas, NO invariantes de negocio). Fuente ÚNICA — antes
# copiadas en routes/compartir.py y routes/cliente_portal/listas.py.
CANTIDAD_MAX = 99
MAX_ITEMS = 200


class SeleccionItem(BaseModel):
    """Un renglón de la selección del carrito: qué equipo y cuántas unidades."""

    equipo_id: int
    cantidad: int = 1
