"""services.facturacion.diagnostico — diagnóstico de configuración de un emisor.

Un emisor nuevo (CUIT/cert/punto de venta) hoy se prueba a ciegas: recién se descubre que falta
delegar una relación, que el certificado venció, o que el punto de venta no está habilitado para
factura electrónica AL INTENTAR FACTURAR de verdad. Este módulo arma un chequeo previo, en dos
capas — mismo criterio "middleman" del resto de la iniciativa: barato primero, red después, y
solo cuando la capa barata no garantiza ya el fracaso.

Capa 1 (local, siempre corre, sin red): todo lo que ya sabemos desde nuestra propia base —
CUIT con dígito verificador válido, certificado cargado, certificado no vencido, punto de venta
asignado. Si el certificado falta o está vencido, se CORTA acá — un login WSAA con eso fallaría
con certeza, no tiene sentido gastar la llamada.

Capa 2 (AFIP, solo si el certificado pasó la capa 1): ¿el servicio "wsfe" está delegado y el
punto de venta está habilitado? (reusa `services.facturacion.puntos_venta.consultar_puntos_venta`,
no lo reimplementa); ¿la relación de padrón está delegada? (un `get_persona` sobre el propio CUIT
del emisor). Mismo patrón que `padron.py::resolver_persona` — probar la operación real y traducir
la falla a un motivo legible, nunca adivinar ni tragar el error.

`arca_fe` no participa de la orquestación (sigue 100% sin estado) — este módulo es el adapter que
decide qué emisor, cuándo pegarle a AFIP, y arma la lista de chequeos; solo usa las piezas
portables que `arca_fe` ya expone (`cuit_valido`, `WsfeClient`/`PadronClient`, `wsaa`)."""
from __future__ import annotations

from datetime import datetime, timezone


def cert_info(cert_pem: bytes) -> dict:
    """Metadata de un certificado (Subject, Nº de serie, vigencia) — NUNCA el PEM/clave privada.
    Función pura, sin I/O — usada tanto por `routes.facturacion.info_cert_emisor` como por el
    chequeo `cert_vigente` de acá abajo (una sola forma de parsear el cert, no duplicada)."""
    from cryptography import x509

    cert = x509.load_pem_x509_certificate(cert_pem)
    return {
        "subject": cert.subject.rfc4514_string(),
        "numero_serie": format(cert.serial_number, "X"),
        "vigente_desde": cert.not_valid_before_utc,
        "vigente_hasta": cert.not_valid_after_utc,
    }


def diagnosticar_emisor(emisor_id: int, conn) -> dict:
    """Devuelve `{"chequeos": [...], "listo": bool}` — mismo shape que
    `engine._chequeos_previos`/`previsualizar_factura` (`{check, ok, bloqueante, mensaje}`), para
    que el front reuse el mismo renderer que ya existe para el preview de facturas.

    Raises:
        ValueError: emisor no encontrado (mapea a 400 en el route)."""
    from arca_fe import cuit_valido
    from services.facturacion.emisores_repo import get_by_id, get_cert_pem

    emisor = get_by_id(emisor_id, conn)
    if emisor is None:
        raise ValueError(f"Emisor {emisor_id} no encontrado")

    chequeos: list[dict] = []

    # ── Capa 1: local, siempre corre, sin red ──────────────────────────────
    chequeos.append(
        {
            "check": "emisor_activo",
            "ok": emisor.activo,
            "bloqueante": True,
            "mensaje": "Emisor activo" if emisor.activo else "Emisor desactivado (soft-delete)",
        }
    )
    cuit_ok = cuit_valido(emisor.cuit)
    chequeos.append(
        {
            "check": "cuit_valido",
            "ok": cuit_ok,
            "bloqueante": True,
            "mensaje": (
                "CUIT con dígito verificador válido"
                if cuit_ok
                else f"El CUIT ({emisor.cuit}) tiene el dígito verificador mal — ARCA lo va a rechazar"
            ),
        }
    )
    chequeos.append(
        {
            "check": "cert_cargado",
            "ok": emisor.cert_cargado,
            "bloqueante": True,
            "mensaje": (
                "Certificado digital cargado"
                if emisor.cert_cargado
                else "Sin certificado cargado — subilo desde Facturación ARCA → Emisores"
            ),
        }
    )

    cert_vencido = False
    if emisor.cert_cargado:
        cert_pem, _ = get_cert_pem(emisor_id, conn)
        info = cert_info(cert_pem)
        ahora = datetime.now(timezone.utc)
        cert_vigente = info["vigente_hasta"] > ahora
        cert_vencido = not cert_vigente
        chequeos.append(
            {
                "check": "cert_vigente",
                "ok": cert_vigente,
                "bloqueante": True,
                "mensaje": (
                    f"Certificado vigente hasta {info['vigente_hasta'].date().isoformat()}"
                    if cert_vigente
                    else f"Certificado VENCIDO el {info['vigente_hasta'].date().isoformat()}"
                ),
            }
        )

    pto_vta_asignado = bool(emisor.pto_vta and emisor.pto_vta > 0)
    chequeos.append(
        {
            "check": "punto_venta_asignado",
            "ok": pto_vta_asignado,
            "bloqueante": True,
            "mensaje": (
                f"Punto de venta {emisor.pto_vta} asignado"
                if pto_vta_asignado
                else "Sin punto de venta asignado"
            ),
        }
    )

    # ── Corte temprano: emisor inactivo, sin cert, o cert vencido — un login
    # WSAA con eso fallaría con certeza, no tiene sentido gastar la llamada
    # (y evita rotular un "emisor desactivado" como si fuera una falla de AFIP).
    if not emisor.activo or not emisor.cert_cargado or cert_vencido:
        if not emisor.activo:
            motivo = "el emisor está desactivado"
        elif not emisor.cert_cargado:
            motivo = "sin certificado cargado"
        else:
            motivo = "el certificado está vencido"
        chequeos.append(
            {
                "check": "afip_no_verificado",
                "ok": False,
                "bloqueante": True,
                "mensaje": f"No se pudo verificar contra AFIP: {motivo}.",
            }
        )
        return {"chequeos": chequeos, "listo": _listo(chequeos)}

    # ── Capa 2: AFIP, solo si el cert pasó la capa 1 ───────────────────────
    try:
        from services.facturacion.puntos_venta import consultar_puntos_venta

        resultado = consultar_puntos_venta(emisor.nombre, conn)
    except Exception as exc:
        chequeos.append(
            {
                "check": "wsfe_habilitado",
                "ok": False,
                "bloqueante": True,
                "mensaje": f"AFIP no respondió para 'wsfe': {exc}",
            }
        )
    else:
        chequeos.append(
            {
                "check": "wsfe_habilitado",
                "ok": True,
                "bloqueante": True,
                "mensaje": "Servicio 'wsfe' delegado y respondiendo",
            }
        )
        habilitados = {p["nro"] for p in resultado["habilitados"]}
        excluido = next(
            (e for e in resultado["excluidos"] if e["nro"] == emisor.pto_vta), None
        )
        pto_vta_ok = emisor.pto_vta in habilitados
        chequeos.append(
            {
                "check": "punto_venta_habilitado",
                "ok": pto_vta_ok,
                "bloqueante": True,
                "mensaje": (
                    f"Punto de venta {emisor.pto_vta} habilitado para factura electrónica"
                    if pto_vta_ok
                    else (
                        f"Punto de venta {emisor.pto_vta} excluido en AFIP ({excluido['motivo']})"
                        if excluido
                        else f"Punto de venta {emisor.pto_vta} no aparece entre los de AFIP"
                    )
                ),
            }
        )

    try:
        from arca_fe.padron import PadronClient, WSAA_SERVICIO
        from services.facturacion.config import credenciales
        from services.facturacion.padron import _PADRON_HOMO, _PADRON_PROD
        from services.facturacion.wsaa_cache import get_ta

        cred = credenciales(emisor.nombre, conn)
        token, sign = get_ta(emisor.nombre, conn, servicio=WSAA_SERVICIO)
        endpoint_padron = _PADRON_PROD if cred.ambiente == "produccion" else _PADRON_HOMO
        padron = PadronClient(
            endpoint=endpoint_padron, cuit_representada=cred.cuit, token=token, sign=sign
        )
        padron.get_persona(str(emisor.cuit))
    except Exception as exc:
        guia = (
            "Estás en HOMOLOGACIÓN: la base de prueba de AFIP solo conoce unos pocos CUIT de "
            "test, así que el propio CUIT del emisor puede dar 'no existe' sin ser un error real."
            if not _es_produccion()
            else "Revisá que la relación 'Consulta Constancia de Inscripción' esté delegada en el "
            "Administrador de Relaciones de Clave Fiscal."
        )
        chequeos.append(
            {
                "check": "padron_habilitado",
                "ok": False,
                # NO bloqueante: el padrón nunca es crítico para facturar (ver padron.py) — y
                # cualquier OTRO emisor activo con la relación delegada ya cubre la necesidad
                # del sistema completo, esto es solo informativo para ESTE emisor puntual.
                "bloqueante": False,
                "mensaje": f"Relación de padrón no verificada: {exc}. {guia}",
            }
        )
    else:
        chequeos.append(
            {
                "check": "padron_habilitado",
                "ok": True,
                "bloqueante": False,
                "mensaje": "Relación de padrón ('Consulta Constancia de Inscripción') delegada",
            }
        )

    return {"chequeos": chequeos, "listo": _listo(chequeos)}


def _listo(chequeos: list[dict]) -> bool:
    return all(c["ok"] or not c["bloqueante"] for c in chequeos)


def _es_produccion() -> bool:
    from config import settings

    return bool(settings.is_production)
