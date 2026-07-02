"""Tests del wiring extras → specs persistibles en `build_result`.

La ficha técnica se nutre del bucket curado (`specs`) + la cola larga del
parser (`extras`). Sólo se promueven las keys de `extras` que correspondan a
un spec del registry de la categoría: así nada parseado se pierde, y los datos
sin spec (homeless) no generan ruido.
"""

import pytest

pytestmark = pytest.mark.unit

from services.specs_ingesta.queries.resultado import build_result


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
    r = build_result(
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
    r = build_result(
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
    r = build_result(
        marca="X", modelo="Y", specs=specs, extras=extras,
        image=None, url="http://x", title="X Y",
        secciones={}, categoria_sugerida="Cámaras",
    )
    vals = {s["spec_key"]: s["value"] for s in r["specs"]}
    assert vals["video_io"] == "curado"


# ── unmatched (#1203): panel admin de specs no reconocidas ───────────────────


def test_unmatched_expone_labels_sin_match_del_registry():
    """`secciones` (raw label→value del DOM) con un label que ningún spec_key/
    alias de Cámaras reconoce → aparece en `unmatched`, explícito."""
    r = build_result(
        marca="Sony", modelo="FX6", specs={}, extras={},
        image=None, url="http://x", title="Sony FX6",
        secciones={"Weight": "1050 g", "Campo Inventado XYZ": "un valor"},
        categoria_sugerida="Cámaras",
    )
    unmatched_labels = {p["label"] for p in r["unmatched"]}
    assert "Campo Inventado XYZ" in unmatched_labels
    assert "Weight" not in unmatched_labels, "Weight resuelve a peso_g — no es unmatched"


def test_unmatched_vacio_si_secciones_vacio():
    r = build_result(
        marca="X", modelo="Y", specs={}, extras={},
        image=None, url="http://x", title="X Y",
        secciones={}, categoria_sugerida="Cámaras",
    )
    assert r["unmatched"] == []
