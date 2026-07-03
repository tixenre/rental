"""Tests para `services/specs/registry/` — registry como single source of truth.

Reemplaza al viejo test_seed_split_tipo.py que validaba el split en una
arquitectura intermedia (8 cats viejas). Ahora el contrato es:

1. Registry tiene 6 cats (Cámaras/Lentes/Iluminación/Modificadores/
   Adaptadores/Filtros) con sus specs únicos.
2. No hay spec_key "tipo" colisionando — cada subtipo usa su prefix de cat.
3. Shared keys (lens_mount, formato, peso_g, diametro_filtro) están
   declaradas IDÉNTICAMENTE en las cats que las usan (mismo tipo, mismas
   enum_options canónicas).
4. Specs `es_compatibilidad=True` tienen `compatibilidad_modo` y, si modo
   es "jerarquia", las cats con la spec tienen rol_compatibilidad.
5. Los datasets `docs/<cat>.json` validan contra el registry.
"""

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

from services.specs import (
    FORMATO_ENUM,
    LENS_MOUNT_ENUM,
    REGISTRY,
    get_categoria,
    get_spec,
    validate_dataset,
)

DOCS = Path(__file__).resolve().parent.parent.parent / "docs"

EXPECTED_CATEGORIAS = {
    "Cámaras", "Lentes", "Iluminación", "Modificadores", "Adaptadores", "Filtros",
}


def test_registry_tiene_las_categorias_activas():
    assert set(REGISTRY.categorias.keys()) == EXPECTED_CATEGORIAS


def test_ninguna_cat_declara_spec_key_tipo():
    """`tipo` solo causaba colisión cross-cat. Cada cat usa <cat>_subtipo."""
    for nombre, cat in REGISTRY.categorias.items():
        keys = [s.key for s in cat.specs]
        assert "tipo" not in keys, (
            f"Categoría '{nombre}' declara spec_key='tipo'. "
            f"Usar '<cat>_subtipo' (camera_subtipo, etc.)"
        )


EXPECTED_SUBTIPOS = {
    "Cámaras":     "camera_subtipo",
    "Iluminación": "iluminacion_subtipo",
    "Adaptadores": "adaptador_subtipo",
    "Filtros":     "filtro_subtipo",
}


def test_subtipos_canonicos_presentes():
    for cat_nombre, expected_key in EXPECTED_SUBTIPOS.items():
        cat = get_categoria(cat_nombre)
        assert cat is not None
        keys = {s.key for s in cat.specs}
        assert expected_key in keys, (
            f"'{cat_nombre}' debe declarar '{expected_key}'; "
            f"keys actuales: {sorted(keys)}"
        )


def test_shared_keys_consistentes_entre_cats():
    """lens_mount, formato, diametro_filtro, peso_g — donde aparecen
    deben tener tipo + enum_options canónicas idénticas."""
    expectations = {
        "lens_mount":      {"tipo": "enum", "enum_options": LENS_MOUNT_ENUM},
        "formato":         {"tipo": "enum", "enum_options": FORMATO_ENUM},
        "diametro_filtro": {"tipo": "number", "unidad": "mm"},
        "peso_g":          {"tipo": "number", "unidad": "g"},
    }
    for key, expected in expectations.items():
        seen_in_cats: list[tuple[str, dict]] = []
        for cat_nombre, cat in REGISTRY.categorias.items():
            spec = cat.get_spec(key)
            if spec:
                seen_in_cats.append((cat_nombre, {
                    "tipo": spec.tipo,
                    "enum_options": spec.enum_options,
                    "unidad": spec.unidad,
                }))
        # No se chequea presencia mínima — algunas cats no tienen peso_g, etc.
        for cat_nombre, observed in seen_in_cats:
            for prop, exp_val in expected.items():
                obs_val = observed.get(prop)
                assert obs_val == exp_val, (
                    f"'{key}' en '{cat_nombre}': {prop}={obs_val!r}, "
                    f"esperado {exp_val!r}"
                )


def test_compat_specs_tienen_modo_y_rol_si_jerarquia():
    for cat_nombre, cat in REGISTRY.categorias.items():
        for spec in cat.specs:
            if not spec.es_compatibilidad:
                continue
            assert spec.compatibilidad_modo in ("exacta", "jerarquia"), (
                f"{cat_nombre}.{spec.key}: compatibilidad_modo inválido"
            )
            if spec.compatibilidad_modo == "jerarquia":
                assert spec.rol_compatibilidad in ("contenedor", "contenido"), (
                    f"{cat_nombre}.{spec.key}: jerarquia requiere "
                    f"rol_compatibilidad (contenedor/contenido)"
                )


def test_formato_roles_lente_contenedor_camara_contenido():
    """Lente proyecta (contenedor); Cámara recibe (contenido)."""
    lente_formato = get_spec("Lentes", "formato")
    camara_formato = get_spec("Cámaras", "formato")
    assert lente_formato.rol_compatibilidad == "contenedor"
    assert camara_formato.rol_compatibilidad == "contenido"


def test_no_hay_keys_duplicadas_en_cat():
    """Pydantic ya lo enforcea pero lo testeamos explícito."""
    for cat in REGISTRY.categorias.values():
        keys = [s.key for s in cat.specs]
        assert len(keys) == len(set(keys)), (
            f"Categoría '{cat.nombre}' tiene keys duplicadas"
        )


def test_enum_options_no_vacios_si_tipo_enum():
    for cat in REGISTRY.categorias.values():
        for spec in cat.specs:
            if spec.tipo in ("enum", "multi_enum"):
                assert spec.enum_options, (
                    f"{cat.nombre}.{spec.key}: tipo={spec.tipo} sin enum_options"
                )


# ── Datasets validan contra el registry ─────────────────────────────────

DATASET_FILES = {
    "Cámaras":       "camaras.json",
    "Lentes":        "lentes.json",
    "Iluminación":   "iluminacion.json",
    "Modificadores": "modificadores.json",
    "Adaptadores":   "adaptadores.json",
    "Filtros":       "filtros.json",
}


@pytest.mark.parametrize("cat_raiz,fname", list(DATASET_FILES.items()))
def test_dataset_valida_contra_registry(cat_raiz: str, fname: str):
    """Cada docs/<cat>.json cumple el contrato del registry. Si rompe →
    el parser o el registry quedó desalineado; arreglar antes de seed.
    """
    path = DOCS / fname
    if not path.exists():
        pytest.skip(f"{fname} no existe")
    data = json.loads(path.read_text())
    errors = validate_dataset(cat_raiz, data.get("products", {}))
    assert not errors, (
        f"{cat_raiz} tiene {len(errors)} errores de validación:\n"
        + "\n".join(f"  {e}" for e in errors[:10])
    )
