"""Tests del wiring extras → specs persistibles en `_build_result`.

La ficha técnica se nutre del bucket curado (`specs`) + la cola larga del
parser (`extras`). Sólo se promueven las keys de `extras` que correspondan a
un spec del registry de la categoría: así nada parseado se pierde, y los datos
sin spec (homeless) no generan ruido.
"""

import pytest

pytestmark = pytest.mark.unit

from services.equipo_html_extractor import _build_result


def _labels(result: dict) -> set[str]:
    # Después de Fase 1, los items llevan spec_key como campo canónico.
    return {s["spec_key"] for s in result["specs"]}


def test_extras_que_matchean_registry_se_promueven():
    specs = {"camera_subtipo": "Cinema", "lens_mount": "E"}
    extras = {
        "white_balance": "Auto / Manual",   # registry string
        "time_code": "SMPTE",               # registry string
        "battery": "NP-FZ100",              # key alineada
        "video_io": "HDMI / SDI",           # key alineada
    }
    r = _build_result(
        marca="Sony", modelo="FX6", specs=specs, extras=extras,
        image=None, url="http://x", title="Sony FX6",
        secciones={}, categoria_sugerida="Cámaras",
    )
    labels = _labels(r)
    for k in ("white_balance", "time_code", "battery", "video_io"):
        assert k in labels, f"{k} debería promoverse a specs persistibles"


def test_extras_sin_spec_en_registry_se_descartan():
    specs = {"camera_subtipo": "Cinema"}
    extras = {"sensor_size": "35.6 x 23.8mm", "viewfinder_coverage": "100%"}
    r = _build_result(
        marca="Sony", modelo="FX6", specs=specs, extras=extras,
        image=None, url="http://x", title="Sony FX6",
        secciones={}, categoria_sugerida="Cámaras",
    )
    labels = _labels(r)
    assert "sensor_size" not in labels
    assert "viewfinder_coverage" not in labels


def test_bucket_curado_gana_en_colision():
    # Si una key está en specs y en extras, gana el valor curado.
    specs = {"video_io": "curado"}
    extras = {"video_io": "extra"}
    r = _build_result(
        marca="X", modelo="Y", specs=specs, extras=extras,
        image=None, url="http://x", title="X Y",
        secciones={}, categoria_sugerida="Cámaras",
    )
    vals = {s["spec_key"]: s["value"] for s in r["specs"]}
    assert vals["video_io"] == "curado"
