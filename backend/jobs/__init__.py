"""Jobs de fondo del backend (in-process).

Hoy: el scheduler de recordatorios de retiro (ver `scheduler.py` +
`recordatorios.py`, issue #735). Corre dentro del proceso del backend que ya
está prendido 24/7 — no es un servicio aparte. Decisión 2026-06-04.
"""
