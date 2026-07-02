# Sistema ARCA / AFIP — Facturación Electrónica

> Manual técnico de integración con los webservices de ARCA (ex-AFIP): WSAA + WSFEv1.
> El **porqué** de cada decisión vive en `MEMORIA.md`/`DECISIONES.md`. Este doc describe el **cómo**.
>
> Código: `backend/arca_fe/` (portable, sin estado, sin I/O de BD).
> Adapter con caché y BD: `backend/services/facturacion/`.

---

## 1. Arquitectura general

```
backend/
├── arca_fe/               ← librería portable (sin estado)
│   ├── wsaa.py            ← cliente WSAA (autenticación)
│   ├── wsfe.py            ← cliente WSFEv1 (facturación)
│   └── modelos.py         ← tipos de datos (CaeResult, etc.)
└── services/facturacion/
    ├── wsaa_cache.py      ← caché del Ticket de Acceso en afip_ta
    ├── config.py          ← credenciales del emisor (cert/key/endpoint)
    └── ...
```

El flujo de emisión de una factura:

```
facturar_pedido()
  → wsaa_cache.get_ta()      → afip_ta (cache)
    → wsaa.login_con_cert()  → WSAA AFIP (HTTPS/SOAP)
  → wsfe.solicitar_cae()     → WSFEv1 AFIP (HTTPS/SOAP)
  → guardar CAE en BD
```

---

## 2. WSAA — Autenticación

### Cómo funciona

1. Construir un **TRA** (Ticket de Requerimiento de Autenticación) en XML.
2. Firmarlo con **CMS/PKCS#7** usando el cert + clave privada del emisor.
3. Enviarlo al endpoint `LoginCms` del WSAA (SOAP).
4. AFIP devuelve un **Ticket de Acceso** (token + sign) con validez de hasta 24 h.

### Gotchas de producción (descubiertos en 2026-06)

#### ① CMS debe ser ATTACHED (no detached)

```python
# ✅ correcto — data embebida en el CMS
cms = PKCS7SignatureBuilder().set_data(tra).add_signer(...).sign(DER, [])

# ❌ incorrecto — AFIP devuelve: ns1:cms.sign.invalid
cms = PKCS7SignatureBuilder().set_data(tra).add_signer(...).sign(DER, [DetachedSignature])
```

La opción `DetachedSignature` produce un CMS separado del contenido. AFIP espera que el TRA esté embebido en el blob CMS.

#### ② Timestamps del TRA en hora argentina (UTC-3), con offset explícito

```python
# ✅ correcto — AFIP interpreta el timestamp según la zona horaria incluida
_AR = timezone(timedelta(hours=-3))
gen_time = (ahora - timedelta(minutes=10)).astimezone(_AR)
exp_time = (ahora + timedelta(seconds=ttl)).astimezone(_AR)
# Produce: "2026-06-30T17:00:00-03:00"

# ❌ incorrecto — AFIP interpreta UTC naive como hora local → aparece 3h en el futuro
gen_time = ahora.strftime("%Y-%m-%dT%H:%M:%S")  # sin tz → ns1:xml.generationTime.invalid
```

AFIP no convierte zonas horarias: asume que el tiempo sin offset es hora local de Argentina (UTC-3). Un timestamp UTC sin offset aparece como si fuera 3 horas en el futuro.

#### ③ TTL máximo del TRA: 24 h — usar 12 h

```python
_TRA_TTL_SECONDS = 12 * 3600  # 12 h — usar 12h (máx aceptado: 24h)
# TTL > 24h → ns1:xml.expirationTime.invalid: "vencimiento en más de 24 horas"
```

#### ④ La respuesta del WSAA tiene XML escapado dentro del SOAP

El SOAP envelope de AFIP contiene `<loginCmsReturn>` con el `loginTicketResponse` como **texto XML escapado**, no como nodos hijos. Hay que parsearlo en dos pasos:

```python
# El SOAP viene así:
# <loginCmsReturn>&lt;loginTicketResponse&gt;...&lt;/loginTicketResponse&gt;</loginCmsReturn>

soap_root = ET.fromstring(xml_text)
cms_return_text = find(soap_root, "loginCmsReturn")  # texto escapado
inner = ET.fromstring(cms_return_text.strip())        # segundo parseo
token = find(inner, "token")
sign  = find(inner, "sign")
```

Si se busca `token`/`sign` directo en el SOAP root, no se encuentran (están en el texto escapado).

#### ⑤ Endpoint WSAA (no agregar el path si ya está)

```python
# AFIP espera: https://wsaa.afip.gov.ar/ws/services/LoginCms
# No duplicar el path si el usuario ya lo pasa completo
```

---

## 3. WSFEv1 — Facturación

### SSL: DH_KEY_TOO_SMALL en servidores de producción

Los servidores de AFIP producción (`servicios1.afip.gov.ar`) usan parámetros Diffie-Hellman cortos. Python con OpenSSL 3 los rechaza por defecto (`DH_KEY_TOO_SMALL`).

Fix: adapter de requests con `SECLEVEL=1` (acepta DH corto sin bajar verificación de cert):

```python
class _AfipSSLAdapter(HTTPAdapter):
    def init_poolmanager(self, num_pools, maxsize, block=False):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        self.poolmanager = urllib3.PoolManager(
            num_pools=num_pools, maxsize=maxsize, block=block, ssl_context=ctx,
        )

session = requests.Session()
session.mount("https://", _AfipSSLAdapter())
transport = zeep.transports.Transport(session=session)
client = zeep.Client(wsdl, transport=transport)
```

### Endpoints oficiales

| Ambiente      | WSAA                                              | WSFEv1 WSDL                                              |
|---------------|---------------------------------------------------|----------------------------------------------------------|
| Homologación  | `https://wsaahomo.afip.gov.ar/ws/services/LoginCms` | `https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL`  |
| Producción    | `https://wsaa.afip.gov.ar/ws/services/LoginCms`   | `https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL` |

**Importante:** el cert de producción **no funciona** en el endpoint de homologación (error `cms.cert.untrusted`). Son CAs distintas.

### Idempotencia post-timeout: consultar el PRÓXIMO número, nunca el último (bug de prod)

`emitir_factura` inserta la fila `pendiente` y recién después llama a ARCA — si la
respuesta de `FECAESolicitar` se pierde por timeout de nuestro lado, un reintento no
puede simplemente volver a pedir el mismo número (ARCA ya lo tiene autorizado y
rechaza el duplicado). Antes de reintentar, se consulta con `FECompConsultar` si el
número que estamos por pedir ya fue autorizado:

```python
# ✅ correcto — consultar el PRÓXIMO número (el que estamos por pedir)
ultimo = wsfe.ultimo_autorizado(pto_vta, cbte_tipo)
numero_a_emitir = ultimo + 1
consultado = wsfe.consultar(pto_vta, cbte_tipo, numero_a_emitir)
if consultado and consultado["Resultado"] == "A":
    ...  # nuestro propio reintento ya se autorizó: recuperar ese CAE

# ❌ incorrecto — consultar `ultimo` (el ÚLTIMO ya autorizado)
consultado = wsfe.consultar(pto_vta, cbte_tipo, ultimo)
if consultado and consultado["Resultado"] == "A":  # SIEMPRE True: "último autorizado"
    ...                                             # por definición ya está autorizado
```

`ultimo_autorizado` devuelve, por definición, un comprobante **ya autorizado** — no es
"nuestro", es el de la factura anterior (de otro pedido). Consultarlo directamente
hace que la condición sea siempre verdadera, así que después de la primera factura
real el sistema nunca vuelve a llamar `FECAESolicitar`: le copia a cada pedido nuevo
el número y el CAE de la factura anterior. Encontrado en prod: dos pedidos distintos
con el mismo `00002-00000001` y el mismo CAE. Fix + regresión en `services/facturacion/engine.py` (`emitir_factura`/`emitir_nota_credito`) y `tests/test_facturacion_engine.py`.

### Timeout en las llamadas WSFE (zeep no lo aplica por defecto)

A diferencia de WSAA (`httpx` con `timeout=30.0` explícito), el `Transport` de zeep no
tiene límite de tiempo salvo que se configure `operation_timeout`. Sin eso, si AFIP se
cuelga, la llamada espera indefinidamente sosteniendo el advisory lock del engine +
el `FOR UPDATE` de `afip_ta` — bloquea TODA la facturación de ese emisor hasta que el
proceso se reinicie. `arca_fe/wsfe.py::_afip_transport()` pasa `operation_timeout=30`.

### FECompConsultar "no existe": el código de error de AFIP NO es consistente

`10016` ("El comprobante consultado no existe") es el código documentado, pero AFIP
devuelve **`602`** ("No existen datos en nuestros registros para los parámetros
ingresados") cuando la combinación `(pto_vta, cbte_tipo)` no tiene **ningún**
historial todavía — típicamente la primera Nota de Crédito que se emite para un
punto de venta (la Factura y la NC son secuencias independientes). Sin contemplar
602, `consultar()` trataba esa respuesta como un error real → `RuntimeError` → 503
espurio, bloqueando la primera NC de cada punto de venta. `arca_fe/wsfe.py::consultar`
trata ambos códigos (`_CODES_NO_EXISTE = (10016, 602)`) como "no existe".

---

## 4. Requisitos externos en AFIP (resumen)

Ver guía paso a paso, con screenshots reales de cada pantalla: [`GUIA_ARCA_CERT.md`](GUIA_ARCA_CERT.md).
Dos relaciones independientes por emisor — un emisor puede tener una sin la otra:

**Parte A — cert + servicio `wsfe`** (bloquea facturar si falta):
1. Generar CSR (openssl) + subir al portal AFIP → descargar `.crt`
2. En "Administrador de Relaciones de Clave Fiscal": incorporar relación entre el CUIT del emisor y el servicio `wsfe` usando el cert.
3. Cargar el `.crt` + la clave privada (`.key`) en el back-office → Facturación → Emisores → Cargar cert.

**Parte B — "Consulta de constancia de inscripción"** (no bloquea; sin esto el
autocompletado de CUIT degrada a carga manual): adherir el servicio buscando
**"constancia"** (no "padron" — nombre deprecado) y autohabilitarlo para el
propio CUIT, eligiendo el mismo Computador Fiscal que ya usa `wsfe`.

### Padrón: AFIP renombró `ws_sr_padron_a5` → `ws_sr_constancia_inscripcion` (2026-07, PR #1188)

El WSDL (`personaServiceA5`) es el mismo de siempre — lo que cambió es el **id de
servicio que hay que usar al pedirle el Ticket de Acceso a WSAA** (verificado
contra el manual oficial "WS_SR_constancia_inscripcion" v3.7). Pedir el TA con el
id viejo hace que WSAA no autorice la relación → la consulta degrada
silenciosamente a "no se pudo autocompletar", **incluso con un CUIT real,
registrado y con la relación de padrón ya delegada bajo el nombre viejo**: hay que
re-delegarla en AFIP con el nombre nuevo (Parte B de la guía). `arca_fe/padron.py::WSAA_SERVICIO`
es la fuente única del id — no hardcodear el string en otro lado.

---

## 5. Caché del Ticket de Acceso

El TA (token + sign) se cachea en la tabla `afip_ta` con un margen de renovación de 30 minutos antes del vencimiento. La renovación está serializada por fila con `SELECT FOR UPDATE` (evita que dos workers pidan el TA simultáneamente).

```sql
SELECT token, sign, expira_at
  FROM afip_ta
 WHERE ambiente = %s AND emisor = %s
FOR UPDATE
```

---

## 6. Ideas para librería open-source

El paquete `backend/arca_fe/` está diseñado para ser portable:
- Sin estado propio
- Sin I/O de BD
- Sin dependencias del resto de la app
- Recibe cert/key como bytes PEM
- Devuelve tipos Python puros

Para publicarla como paquete independiente necesitaría:
- `pyproject.toml` con metadatos
- Tests unitarios con TRAs de ejemplo
- Documentación de los gotchas (este archivo es la base)
- Un WSDL local opcional para evitar la conexión SSL en tests

Dependencias actuales: `cryptography`, `httpx`, `zeep`, `requests`, `urllib3`.
