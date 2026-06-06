"""Tests del setup de logging — modos dev/prod + request_id."""

import json
import logging

import pytest

import logging_config


pytestmark = pytest.mark.unit


def test_setup_dev_mode_es_texto(capsys, monkeypatch):
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    monkeypatch.delenv("LOG_FORMAT", raising=False)

    logging_config.setup_logging()
    log = logging.getLogger("test.dev")
    log.warning("hola dev")

    captured = capsys.readouterr()
    # Modo dev: texto plano, NO empieza con '{'
    assert "hola dev" in captured.out + captured.err
    output = captured.out + captured.err
    assert not output.strip().startswith("{")


def test_setup_prod_mode_es_json(capsys, monkeypatch):
    monkeypatch.setenv("LOG_FORMAT", "json")

    logging_config.setup_logging()
    log = logging.getLogger("test.prod")
    log.warning("hola prod")

    captured = capsys.readouterr()
    output = captured.out + captured.err

    # Buscar la línea JSON que contiene "hola prod"
    json_line = None
    for line in output.strip().split("\n"):
        if line.strip().startswith("{") and "hola prod" in line:
            json_line = line.strip()
            break
    assert json_line is not None, f"No se encontró línea JSON con 'hola prod' en: {output!r}"

    parsed = json.loads(json_line)
    assert parsed["message"] == "hola prod"
    assert parsed["level"] == "WARNING"
    assert "timestamp" in parsed
    assert parsed["logger"] == "test.prod"


def test_request_id_se_incluye_en_json(capsys, monkeypatch):
    monkeypatch.setenv("LOG_FORMAT", "json")
    logging_config.setup_logging()

    logging_config.request_id_var.set("req_test_abc123")
    log = logging.getLogger("test.rid")
    log.info("con request_id")

    captured = capsys.readouterr()
    output = captured.out + captured.err

    json_line = next(
        (line.strip() for line in output.strip().split("\n")
         if line.strip().startswith("{") and "con request_id" in line),
        None,
    )
    assert json_line is not None
    parsed = json.loads(json_line)
    assert parsed["request_id"] == "req_test_abc123"


def test_request_id_no_se_incluye_si_no_se_setea(capsys, monkeypatch):
    monkeypatch.setenv("LOG_FORMAT", "json")
    logging_config.setup_logging()

    # Reset del context var a None
    logging_config.request_id_var.set(None)

    log = logging.getLogger("test.no_rid")
    log.info("sin request_id")

    captured = capsys.readouterr()
    output = captured.out + captured.err

    json_line = next(
        (line.strip() for line in output.strip().split("\n")
         if line.strip().startswith("{") and "sin request_id" in line),
        None,
    )
    assert json_line is not None
    parsed = json.loads(json_line)
    assert "request_id" not in parsed
