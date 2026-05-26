"""Tests Fase 6c-iii — factories compartidas: coating, diametro_filtro,
estabilizacion, autofocus, montura_luz, beam_angle.

Verifica:
- Cada factory produce spec con key/tipo/unidad/label correctos.
- La unión de aliases cubre los aliases que tenía cada call-site original
  (ninguna categoría pierde cobertura de match).
- El override de prioridad funciona.
- Las specs producidas son idénticas en tipo a las que tenían inline
  (test_shared_keys_consistentes_entre_cats del registry sigue verde).
"""

import pytest

pytestmark = pytest.mark.unit


# ── coating ────────────────────────────────────────────────────────────────────


def test_coating_key_tipo():
    from specs.shared.optica import coating
    s = coating(prioridad=48)
    assert s.key == "coating"
    assert s.tipo == "string"
    assert s.label == "Coating"


def test_coating_prioridad_override():
    from specs.shared.optica import coating
    assert coating(prioridad=48).prioridad == 48
    assert coating(prioridad=110).prioridad == 110


def test_coating_ayuda_override():
    from specs.shared.optica import coating
    s = coating(prioridad=48, ayuda="Ej: Multi-coated, Nano-X, IRND")
    assert s.ayuda == "Ej: Multi-coated, Nano-X, IRND"


# ── diametro_filtro ────────────────────────────────────────────────────────────


def test_diametro_filtro_key_tipo_unidad():
    from specs.shared.optica import diametro_filtro
    s = diametro_filtro()
    assert s.key == "diametro_filtro"
    assert s.tipo == "number"
    assert s.unidad == "mm"


def test_diametro_filtro_es_compatibilidad():
    from specs.shared.optica import diametro_filtro
    s = diametro_filtro()
    assert s.es_compatibilidad is True
    assert s.compatibilidad_modo == "exacta"


def test_diametro_filtro_aliases_union_filtros():
    """Aliases de Filtros: Thread Size, Filter Thread Size — ambas en la factory."""
    from specs.shared.optica import diametro_filtro
    aliases = set(diametro_filtro().aliases)
    assert "Filter Size" in aliases
    assert "Filter Diameter" in aliases
    assert "Thread Size" in aliases
    assert "Filter Thread Size" in aliases
    assert "Filter Thread" in aliases


def test_diametro_filtro_aliases_union_lentes():
    """Aliases de Lentes: Front Filter Size, Front Filter Diameter — ambas en la factory."""
    from specs.shared.optica import diametro_filtro
    aliases = set(diametro_filtro().aliases)
    assert "Front Filter Size" in aliases
    assert "Front Filter Diameter" in aliases


def test_diametro_filtro_flags_filtros():
    """Cuando se llama con los flags de Filtros, los campos quedan correctos."""
    from specs.shared.optica import diametro_filtro
    s = diametro_filtro(prioridad=20, en_card=True, en_nombre=True, destacado=True, obligatorio=True)
    assert s.prioridad == 20
    assert s.en_card is True
    assert s.en_nombre is True
    assert s.destacado is True
    assert s.obligatorio is True
    assert s.en_filtros is True


def test_diametro_filtro_flags_lentes():
    """Cuando se llama con los flags de Lentes, los campos quedan correctos."""
    from specs.shared.optica import diametro_filtro
    s = diametro_filtro(prioridad=55)
    assert s.prioridad == 55
    assert s.en_card is False
    assert s.en_nombre is False
    assert s.en_filtros is True


# ── estabilizacion ─────────────────────────────────────────────────────────────


def test_estabilizacion_key_tipo():
    from specs.shared.optica import estabilizacion
    s = estabilizacion()
    assert s.key == "estabilizacion"
    assert s.tipo == "bool"
    assert s.en_filtros is True


def test_estabilizacion_aliases_union():
    """Aliases de Cámaras ganan cobertura en Lentes (y viceversa)."""
    from specs.shared.optica import estabilizacion
    aliases = set(estabilizacion().aliases)
    assert "Image Stabilization" in aliases
    assert "In-Body Image Stabilization" in aliases
    assert "IBIS" in aliases


def test_estabilizacion_prioridad_override():
    from specs.shared.optica import estabilizacion
    assert estabilizacion(prioridad=75).prioridad == 75
    assert estabilizacion(prioridad=80).prioridad == 80


# ── autofocus ──────────────────────────────────────────────────────────────────


def test_autofocus_key_tipo():
    from specs.shared.optica import autofocus
    s = autofocus()
    assert s.key == "autofocus"
    assert s.tipo == "bool"
    assert s.en_filtros is True


def test_autofocus_aliases_union():
    """Aliases de Cámaras ganan cobertura en Lentes."""
    from specs.shared.optica import autofocus
    aliases = set(autofocus().aliases)
    assert "Auto Focus" in aliases
    assert "Autofocus System" in aliases
    assert "Focus System" in aliases


def test_autofocus_prioridad_override():
    from specs.shared.optica import autofocus
    assert autofocus(prioridad=80).prioridad == 80
    assert autofocus(prioridad=90).prioridad == 90


# ── montura_luz ────────────────────────────────────────────────────────────────


def test_montura_luz_key_tipo():
    from specs.shared.lighting import montura_luz
    s = montura_luz()
    assert s.key == "montura_luz"
    assert s.tipo == "enum"
    assert s.en_filtros is True


def test_montura_luz_es_compatibilidad():
    from specs.shared.lighting import montura_luz
    s = montura_luz()
    assert s.es_compatibilidad is True
    assert s.compatibilidad_modo == "exacta"


def test_montura_luz_aliases_iluminacion():
    """Aliases exclusivos de Iluminación: Mount Standard, Strobe Mount Type, Mounting System."""
    from specs.shared.lighting import montura_luz
    aliases = set(montura_luz().aliases)
    assert "Mount Standard" in aliases
    assert "Strobe Mount Type" in aliases
    assert "Mounting System" in aliases


def test_montura_luz_aliases_modificadores():
    """Aliases exclusivos de Modificadores: Strobe Mount, Mount Type, Mounting Type."""
    from specs.shared.lighting import montura_luz
    aliases = set(montura_luz().aliases)
    assert "Strobe Mount" in aliases
    assert "Mount Type" in aliases
    assert "Mounting Type" in aliases


def test_montura_luz_aliases_comunes():
    from specs.shared.lighting import montura_luz
    aliases = set(montura_luz().aliases)
    assert "Bowens Mount" in aliases
    assert "Light Mount" in aliases


def test_montura_luz_flags_iluminacion():
    from specs.shared.lighting import montura_luz
    s = montura_luz(prioridad=100)
    assert s.prioridad == 100
    assert s.en_card is False
    assert s.destacado is False


def test_montura_luz_flags_modificadores():
    from specs.shared.lighting import montura_luz
    s = montura_luz(prioridad=40, en_card=True, destacado=True)
    assert s.prioridad == 40
    assert s.en_card is True
    assert s.destacado is True


# ── beam_angle ─────────────────────────────────────────────────────────────────


def test_beam_angle_key_tipo_unidad():
    from specs.shared.lighting import beam_angle
    s = beam_angle()
    assert s.key == "beam_angle"
    assert s.tipo == "rango"
    assert s.unidad == "°"
    assert s.en_filtros is True


def test_beam_angle_aliases_union():
    """Illumination Angle era exclusivo de Iluminación; ahora presente en la factory."""
    from specs.shared.lighting import beam_angle
    aliases = set(beam_angle().aliases)
    assert "Beam Angle" in aliases
    assert "Spread Angle" in aliases
    assert "Field Angle" in aliases
    assert "Beam Spread" in aliases
    assert "Illumination Angle" in aliases


def test_beam_angle_prioridad_override():
    from specs.shared.lighting import beam_angle
    assert beam_angle(prioridad=135).prioridad == 135
    assert beam_angle(prioridad=75).prioridad == 75


# ── Registry: las specs producidas por factories son consistentes ──────────────


def test_registry_diametro_filtro_tipo_consistente():
    """Filtros y Lentes producen diametro_filtro con tipo=number y unidad=mm."""
    from specs import REGISTRY
    for cat_nombre in ("Filtros", "Lentes"):
        cat = REGISTRY.get(cat_nombre)
        assert cat is not None, f"{cat_nombre} no está en el registry"
        spec = cat.get_spec("diametro_filtro")
        assert spec is not None, f"{cat_nombre} debe tener diametro_filtro"
        assert spec.tipo == "number", f"{cat_nombre}.diametro_filtro tipo incorrecto"
        assert spec.unidad == "mm", f"{cat_nombre}.diametro_filtro unidad incorrecta"


def test_registry_diametro_filtro_aliases_completos_en_ambas_cats():
    """Filtros y Lentes tienen la unión completa de aliases (ninguna pierde cobertura)."""
    from specs import REGISTRY
    expected = {
        "Filter Size", "Filter Diameter", "Thread Size",
        "Filter Thread Size", "Filter Thread",
        "Front Filter Size", "Front Filter Diameter",
    }
    for cat_nombre in ("Filtros", "Lentes"):
        cat = REGISTRY.get(cat_nombre)
        spec = cat.get_spec("diametro_filtro")
        assert spec is not None
        aliases = set(spec.aliases)
        faltantes = expected - aliases
        assert not faltantes, (
            f"{cat_nombre}.diametro_filtro no tiene aliases: {faltantes}"
        )


def test_registry_estabilizacion_aliases_en_lentes():
    """Lentes ahora tiene los aliases de estabilizacion que antes solo tenían Cámaras."""
    from specs import REGISTRY
    cat = REGISTRY.get("Lentes")
    spec = cat.get_spec("estabilizacion")
    assert spec is not None
    aliases = set(spec.aliases)
    assert "Image Stabilization" in aliases
    assert "IBIS" in aliases


def test_registry_autofocus_aliases_en_lentes():
    """Lentes ahora tiene los aliases de autofocus que antes solo tenían Cámaras."""
    from specs import REGISTRY
    cat = REGISTRY.get("Lentes")
    spec = cat.get_spec("autofocus")
    assert spec is not None
    aliases = set(spec.aliases)
    assert "Auto Focus" in aliases
    assert "Focus System" in aliases


def test_registry_montura_luz_aliases_completos_en_ambas_cats():
    """Iluminación y Modificadores tienen la unión completa de aliases de montura_luz."""
    from specs import REGISTRY
    expected = {
        "Bowens Mount", "Light Mount",
        "Mount Standard", "Strobe Mount Type", "Mounting System",
        "Strobe Mount", "Mount Type", "Mounting Type",
    }
    for cat_nombre in ("Iluminación", "Modificadores"):
        cat = REGISTRY.get(cat_nombre)
        spec = cat.get_spec("montura_luz")
        assert spec is not None, f"{cat_nombre} debe tener montura_luz"
        aliases = set(spec.aliases)
        faltantes = expected - aliases
        assert not faltantes, (
            f"{cat_nombre}.montura_luz no tiene aliases: {faltantes}"
        )


def test_registry_beam_angle_illumination_angle_en_modificadores():
    """Modificadores ahora tiene 'Illumination Angle' que antes solo tenía Iluminación."""
    from specs import REGISTRY
    cat = REGISTRY.get("Modificadores")
    spec = cat.get_spec("beam_angle")
    assert spec is not None
    assert "Illumination Angle" in spec.aliases
