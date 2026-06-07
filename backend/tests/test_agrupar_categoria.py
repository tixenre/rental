"""Agrupación de ítems por categoría para los documentos de check físico (#814).

Tests de la parte PURA `_ordenar_items_en_grupos` (sin DB): orden de grupos por
prioridad, orden manual preservado dentro del grupo, y el bucket 'Otros' (sin
categoría + líneas personalizadas #805) siempre al final.
"""
import pytest

from routes.alquileres import _ordenar_items_en_grupos

pytestmark = pytest.mark.unit


def test_grupos_ordenados_por_prioridad():
    items = [
        {"equipo_id": 1, "nombre": "A"},  # Luces (prioridad 20)
        {"equipo_id": 2, "nombre": "B"},  # Cámaras (prioridad 10)
    ]
    cat = {1: (20, "Luces"), 2: (10, "Cámaras")}
    grupos = _ordenar_items_en_grupos(items, cat)
    assert [g["categoria"] for g in grupos] == ["Cámaras", "Luces"]


def test_orden_manual_preservado_dentro_del_grupo():
    items = [
        {"equipo_id": 1, "nombre": "primero"},
        {"equipo_id": 2, "nombre": "segundo"},
        {"equipo_id": 3, "nombre": "tercero"},
    ]
    cat = {1: (10, "Cámaras"), 2: (10, "Cámaras"), 3: (10, "Cámaras")}
    grupos = _ordenar_items_en_grupos(items, cat)
    assert len(grupos) == 1
    assert [i["nombre"] for i in grupos[0]["items"]] == ["primero", "segundo", "tercero"]


def test_sin_categoria_va_a_otros_al_final():
    items = [
        {"equipo_id": 1},  # sin categoría
        {"equipo_id": 2},  # Cámaras
    ]
    cat = {2: (10, "Cámaras")}
    grupos = _ordenar_items_en_grupos(items, cat)
    assert [g["categoria"] for g in grupos] == ["Cámaras", "Otros"]
    assert grupos[-1]["items"][0]["equipo_id"] == 1


def test_linea_personalizada_va_a_otros():
    # Línea libre (#805): equipo_id None → 'Otros'.
    items = [
        {"equipo_id": None, "nombre_libre": "Flete"},
        {"equipo_id": 2},  # Cámaras
    ]
    cat = {2: (10, "Cámaras")}
    grupos = _ordenar_items_en_grupos(items, cat)
    assert grupos[-1]["categoria"] == "Otros"
    assert any(i.get("nombre_libre") == "Flete" for i in grupos[-1]["items"])


def test_otros_siempre_ultimo_aunque_prioridad_baja():
    # Aunque haya una categoría con prioridad muy alta (numéricamente grande),
    # 'Otros' va después (prioridad infinita).
    items = [{"equipo_id": 1}, {"equipo_id": 2}]
    cat = {1: (999, "Misceláneos")}
    grupos = _ordenar_items_en_grupos(items, cat)
    assert [g["categoria"] for g in grupos] == ["Misceláneos", "Otros"]
