"""Tests del motor único de búsqueda (backend/busqueda) — parte pura, sin DB.

Cubre:
- `normalizar`: contra el corpus compartido con el front (mismo JSON).
- `construir`: forma del predicado e invariante de ordenamiento de params
  (la cantidad de placeholders `?` debe igualar la cantidad de params, o el
  SQL se desalinea silenciosamente).
"""

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

from busqueda import construir, normalizar, tokenizar

_CORPUS = json.loads(
    (Path(__file__).parent / "data" / "normalizacion_corpus.json").read_text("utf-8")
)


@pytest.mark.parametrize("caso", _CORPUS["casos"], ids=lambda c: c["in"] or "<empty>")
def test_normalizar_corpus_compartido(caso):
    """La normalización de Python debe coincidir con el corpus que también
    corre el front (src/lib/search/normalize.test.ts)."""
    assert normalizar(caso["in"]) == caso["out"]


def test_tokenizar_parte_en_palabras():
    assert tokenizar("Sony A7-III") == ["sony", "a7", "iii"]
    assert tokenizar("  ") == []


def test_construir_vacio_inactivo():
    pred = construir(["e.nombre"], "")
    assert pred.activo is False
    pred = construir(["e.nombre"], "   ")
    assert pred.activo is False


def test_construir_sin_campos_inactivo():
    assert construir([], "sony").activo is False


def _contar_placeholders(sql: str) -> int:
    return sql.count("?")


def test_construir_invariante_de_params():
    """Cada `?` del WHERE/score debe tener su param correspondiente, en orden."""
    pred = construir(["e.nombre", "e.modelo"], "sony fx3")
    assert pred.activo is True
    assert _contar_placeholders(pred.where) == len(pred.where_params)
    assert _contar_placeholders(pred.score) == len(pred.score_params)


def test_construir_un_campo_sin_greatest():
    """Con un solo campo no se usa GREATEST (que requiere ≥2 args)."""
    pred = construir(["c.email"], "juan")
    assert "GREATEST" not in pred.score
    assert _contar_placeholders(pred.score) == len(pred.score_params)


def test_construir_multi_token_and():
    """Multi-palabra: un clause por token (AND), cada uno OR entre campos."""
    pred = construir(["c.nombre", "c.apellido"], "santiago perez")
    # 2 tokens × 2 campos = 4 LIKE de tokens; + fuzzy 2 campos × (qnorm, umbral).
    likes = pred.where.count("LIKE")
    assert likes == 4
    # Los params de los tokens van como %tok% (substring).
    assert "%santiago%" in pred.where_params
    assert "%perez%" in pred.where_params


def test_construir_token_corto_sin_fuzzy():
    """Términos < 3 chars no activan la red fuzzy (typos en 1-2 chars = ruido)."""
    pred = construir(["e.nombre"], "a7")
    assert "word_similarity" not in pred.where
