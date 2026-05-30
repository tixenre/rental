"""Estados de pedido que reservan stock activamente.

Fuente ÚNICA de la lista que va en los `IN (...)` de las queries de reserva.
Es una constante interna (nunca se deriva de input) → segura para interpolar en
SQL como `... p.estado IN {ESTADOS_RESERVADO}`. Antes estaba duplicada literal en
`routes/alquileres.py` y `routes/equipos.py`.
"""

# Formato literal para cláusulas SQL `IN`. NO interpolar nada de fuera acá.
ESTADOS_RESERVADO = "('presupuesto','confirmado','retirado')"
