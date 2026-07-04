# arca-fe

Motor portable de facturación electrónica ARCA (ex-AFIP) — WSFEv1 (facturación), WSAA
(autenticación) y padrón (Constancia de Inscripción), en Python puro. **No depende de ningún
framework** (FastAPI, Django, psycopg, etc.) ni de `backend.*` — es una librería reusable, no
parte de la app de Rambla. El adapter específico de Rambla vive en `backend/services/facturacion/`.

## Instalación

Como parte del monorepo, ya está disponible al importar `arca_fe` desde `backend/`. Para instalarlo
aislado (por ejemplo, para probarlo en otro proyecto Python):

```bash
pip install -e backend/arca_fe
```

Extra opcional para renderizar el QR fiscal como SVG (si no lo necesitás, no hace falta instalarlo):

```bash
pip install -e "backend/arca_fe[qr]"
```

## Quickstart

```python
from datetime import date
from decimal import Decimal

from arca_fe import (
    Emisor, Receptor, ComprobanteRequest, CondicionIva, DocTipo, Concepto, IVA_21,
    WsfeClient, construir_tra, firmar_tra, login,
)

# 1. Armar el request (sin red — puro).
emisor = Emisor(cuit="20-30123456-3", punto_venta=3, condicion_iva=CondicionIva.RESPONSABLE_INSCRIPTO)
receptor = Receptor(doc_tipo=DocTipo.CUIT, doc_nro="20-30987654-2", condicion_iva=CondicionIva.RESPONSABLE_INSCRIPTO)
comprobante = ComprobanteRequest(
    emisor=emisor, receptor=receptor, concepto=Concepto.SERVICIOS,
    importe_neto=Decimal("1000.00"), alicuota=IVA_21, fecha=date.today(),
    fecha_serv_desde=date.today(), fecha_serv_hasta=date.today(), fecha_vto_pago=date.today(),
)

# 2. Autenticar contra WSAA (una vez, el TA dura ~12hs — el consumidor decide cómo cachearlo).
tra = construir_tra(servicio="wsfe")
cms = firmar_tra(tra, cert_pem=b"...", key_pem=b"...")
token, sign, expira_at = login(cms, endpoint="https://wsaahomo.afip.gov.ar/ws/services/LoginCms")

# 3. Pedir el CAE.
client = WsfeClient(endpoint="https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL",
                     cuit=20301234563, token=token, sign=sign)
ultimo = client.ultimo_autorizado(pto_vta=3, cbte_tipo=1)
resultado = client.solicitar_cae(comprobante, numero=ultimo + 1)
print(resultado.cae, resultado.cae_vto)
```

Nota: `Emisor.cuit`/`Receptor.doc_nro` toleran CUIT con o sin guiones ("20-30123456-3" y
"20301234563" son equivalentes) — se normalizan y se valida el dígito verificador al construir el
objeto; un CUIT mal formado levanta `ValueError` ahí mismo, no tres pasos después contra AFIP.

## Excepciones

Todo lo que el motor levanta hereda de `ArcaError` — `except ArcaError` atrapa cualquier falla:

| Excepción | Cuándo | ¿Reintentar? |
|---|---|---|
| `ArcaAuthError` | Login WSAA rechazado, cert vencido/inválido, relación no delegada | No — hay que resolver la causa |
| `ArcaNetworkError` | Timeout, HTTP, TLS, conexión caída | Sí, puede tener sentido (ver `arca_fe.retry.with_retry`) |
| `ArcaResponseError` | AFIP contestó algo que no se pudo interpretar (campo faltante, XML raro) | No — es un bug de parseo o un cambio del WSDL |
| `ArcaBusinessError` | AFIP entendió el pedido y lo RECHAZÓ por regla de negocio (CAE con Resultado='R') | No — cambiar algo del pedido, no reintentar igual |

Errores de INPUT del programador (CUIT mal formado, enum inválido) son `ValueError` de stdlib, no
`ArcaError` — son un bug del que llama, no "algo pasó hablando con ARCA".

## Robustez (opt-in, no automática)

- **Retry con backoff**: `arca_fe.with_retry(lambda: client.solicitar_cae(comprobante, numero))` —
  reintenta solo `ArcaNetworkError` por default (nunca `ArcaBusinessError`/`ArcaAuthError`, que dan
  lo mismo si se reintentan sin cambiar nada).
- **Timeout configurable**: `WsfeClient(..., timeout=45.0)` / `PadronClient(..., timeout=45.0)`
  (default 30s/20s).
- **Facade async**: `arca_fe.solicitar_cae_async`/`get_persona_async`/`login_async` — wrappers
  cooperativos vía `asyncio.to_thread`, no bloquean el event loop del consumidor. No son un
  cliente async nativo (siguen usando I/O sync por dentro, solo corren en otro thread).
- **Facturación por lote**: `WsfeClient.solicitar_cae_lote(comprobantes, numero_desde)` — pide CAE
  de varios comprobantes CONSECUTIVOS (mismo emisor/pto_vta/cbte_tipo) en una sola llamada SOAP
  (hasta 250 por lote). Devuelve un `CaeResult` por comprobante, en orden — AFIP puede aprobar unos
  y rechazar otros dentro del mismo lote.

## Trámites de AFIP necesarios para usar esto

Ver [`TRAMITES_AFIP.md`](TRAMITES_AFIP.md) — qué certificados/relaciones hay que dar de alta en el
portal de AFIP antes de poder facturar con esta librería (paso a paso, para no perderse en el
papeleo).

## Portabilidad

Este paquete **no importa nada de `backend.*` ni de ningún framework** — podés copiar el
directorio `arca_fe/` completo a otro proyecto Python y funciona igual (verificado por
`arca_fe/tests/test_portabilidad.py`, que falla si se cuela un import prohibido).

- **Otro backend Python** (Django, Flask, otro FastAPI): `pip install`/copiar el directorio e
  importar `arca_fe` directo — funciona igual, no hay nada específico de FastAPI acá.
- **Stacks NO-Python** (Node, Ruby, Go, etc.): no hay bridge directo — la vía es envolver esta
  librería en un microservicio HTTP propio (un FastAPI/Flask finito que exponga
  `POST /solicitar-cae`, `GET /padron/{cuit}`, etc.) y que cualquier stack lo consuma por
  REST/gRPC. No está construido en este repo — es una opción de arquitectura para cuando haga
  falta, no algo que haya que armar de antemano.

## Qué NO cubre (explícitamente fuera de alcance)

- **Factura E (exportación)** — webservice DISTINTO de AFIP (WSFEXv1, `FEXAuthorize`), con su
  propio modelo de datos. No es una extensión de este motor.
  Ver `## Backlog futuro` en el plan de la iniciativa que llevó esto a `0.3.0`.
- Vigencia de catálogos vivos de AFIP (¿este código de moneda/tributo existe HOY?) — la librería
  valida FORMATO (forma fija del campo) pero no vigencia; para eso, consultar
  `WsfeClient.param_tipos_monedas()`/`param_tipos_tributos()`/etc. en vivo.
