"""
backend/clientes/ — cuenta del cliente (identidad resuelta, historial de
pedidos, perfiles fiscales/productoras), consultado por AMBOS lados: admin
(`routes/clientes.py`) y portal self-service (`routes/cliente_portal/`).

No es un motor de identidad — eso vive en `identity/` (KYC, verificación,
merge) y este paquete lo CONSULTA, no lo duplica. Tampoco es el motor de
reservas/pedidos — `historial.py` da un resumen liviano para la ficha admin;
el detalle rico de "mis pedidos" del portal sigue siendo dominio de pedidos
(`routes/cliente_portal/pedidos.py`), no se movió acá.
"""
