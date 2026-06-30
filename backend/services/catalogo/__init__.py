"""Paquete `services.catalogo` — puerta única de proyección del equipo de display.

Orquesta los motores existentes para producir el payload del catálogo público:
lista paginada, detalle de equipo y seed de SSR/LCP. Nuevo miembro de la
familia motor-único (espeja services/contenido y services/carrito).

SUPERFICIE:
    proyectar_lista   — lista paginada con attach_*, precios y disponibilidad
    proyectar_uno     — detalle completo (+ fotos + kit)
    proyectar_seed    — subset liviano para el script __INITIAL__ (SSR/LCP)

Ver proyeccion.py para la implementación y CLAUDE.md para el contrato.
"""
from services.catalogo.proyeccion import (
    proyectar_lista,
    proyectar_uno,
    proyectar_seed,
)

__all__ = [
    "proyectar_lista",
    "proyectar_uno",
    "proyectar_seed",
]
