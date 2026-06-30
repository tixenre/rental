"""Adapter Rambla del motor de facturación ARCA.

Pegamento entre el core portable `arca_fe` y la app: mapea pedidos a modelos
fiscales, persiste en `facturas`/`afip_ta`, sube PDFs a R2.
No importa de `arca_fe` en init para no cargar zeep/cryptography en boot.
"""
