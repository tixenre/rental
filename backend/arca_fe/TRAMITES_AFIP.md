# Trámites de AFIP necesarios para facturar con `arca_fe`

Esta librería habla con AFIP, pero **no puede hacer el papeleo por vos** — antes de poder pedir un
CAE, hay una serie de trámites administrativos que se hacen una sola vez (por CUIT emisor) en el
portal de AFIP con Clave Fiscal. Esta guía es la fuente de verdad de **qué hay que hacer y en qué
orden** — vive acá, en la librería, para que cualquier consumidor (Rambla hoy, otro proyecto
mañana) sepa exactamente qué habilitar antes de escribir una línea de código.

## 1. Tener CUIT y Clave Fiscal

Requisito de base — si ya facturás manualmente desde el sitio de AFIP, ya lo tenés. Si no, es el
primer paso en [afip.gob.ar](https://www.afip.gob.ar) (trámite "Clave Fiscal").

## 2. Generar el certificado digital (par clave privada + CSR)

AFIP autentica cada llamada con un **certificado digital**, no con usuario/contraseña. Hay que:

1. Generar un par de claves (privada + pública) y un CSR (Certificate Signing Request) — con
   `openssl`, por ejemplo:
   ```bash
   openssl genrsa -out privada.key 2048
   openssl req -new -key privada.key -subj "/CN=NombreDeTuAlias/O=TuRazonSocial/serialNumber=CUIT 20301234563/C=AR" -out solicitud.csr
   ```
2. Subir el CSR en el portal de AFIP: **Administración de Certificados Digitales** (buscalo en el
   buscador del sitio de AFIP con Clave Fiscal) → "Agregar Alias" → subir `solicitud.csr`.
3. AFIP devuelve el **certificado firmado** (`.crt`/`.pem`) — descargalo.
4. Guardá `privada.key` + el certificado firmado — son los `key_pem`/`cert_pem` que le pasás a
   `arca_fe.wsaa.firmar_tra`. **La clave privada NUNCA se manda a AFIP ni sale de tu infraestructura.**

**Homologación vs. producción**: son certificados DISTINTOS, con portales de alta separados
(`wsaahomo.afip.gov.ar` para homologación/testing, `wsaa.afip.gov.ar` para producción real). No se
puede probar en homologación con el certificado de producción ni viceversa.

## 3. Delegar los servicios web al alias del certificado

Tener el certificado no alcanza — hay que decirle a AFIP **para qué servicios** ese alias puede
actuar en tu nombre. Esto se hace en **Administrador de Relaciones de Clave Fiscal** (buscalo en el
buscador de AFIP), sección "Nueva Relación" → elegís el servicio → el alias del certificado (paso
2) → confirmás.

Los servicios que esta librería usa:

| Servicio a buscar en AFIP | Para qué | Usado por |
|---|---|---|
| **"wsfe" / Facturación Electrónica** | Emitir comprobantes (CAE), consultar puntos de venta/tipos de comprobante | `arca_fe.wsfe.WsfeClient` |
| **"Consulta Constancia de Inscripción"** (⚠️ el nombre viejo "Padrón" ya no aparece en el buscador de AFIP — es el mismo servicio, renombrado) | Autocompletar razón social/domicilio/condición IVA de un CUIT | `arca_fe.padron.PadronClient` |
| **"Comprobantes de Exportación" (WSFEXv1)** ⚠️ nombre EXACTO a confirmar en el buscador de AFIP al momento de delegar — no asumir que es igual al de "wsfe" | Emitir Facturas de Exportación (CAE de exportación) | `arca_fe.wsfex.WsfexClient` |

Sin esta delegación, cada llamada a `WsaaLogin` para ese servicio falla — el error típico de AFIP
es algo del estilo "no se encontró una relación entre el certificado y el CUIT solicitante para el
servicio solicitado". **Los tres servicios se delegan POR SEPARADO** — tener "wsfe" habilitado NO
habilita automáticamente WSFEXv1 (son relaciones de servicio independientes, aunque compartan el
mismo CUIT/certificado); un emisor que factura doméstico pero no exportación no necesita este paso.

## 4. (Solo si vas a emitir Factura A) Punto de venta habilitado

Los puntos de venta se dan de alta en el sistema de **Comprobantes en línea** de AFIP (o vía
`WsfeClient.param_puntos_venta()` para CONSULTAR los que ya existen — no para crearlos, eso es
100% manual en el portal). Sin al menos un punto de venta habilitado, `FECAESolicitar` rechaza
todo.

## Checklist resumido

- [ ] CUIT + Clave Fiscal.
- [ ] Certificado digital generado (CSR → subido a AFIP → certificado firmado descargado) — **uno
      para homologación, otro para producción**.
- [ ] Servicio **"wsfe"** delegado al alias del certificado (Administrador de Relaciones).
- [ ] Servicio **"Consulta Constancia de Inscripción"** delegado (si vas a usar `PadronClient` —
      autocompletar datos de un CUIT).
- [ ] Servicio de **Comprobantes de Exportación (WSFEXv1)** delegado (si vas a usar `WsfexClient` —
      facturar al exterior; no es automático por tener "wsfe" ya delegado).
- [ ] Al menos un punto de venta habilitado en Comprobantes en línea.

## Errores comunes y a qué trámite de arriba corresponden

| Error de AFIP | Causa probable | Trámite a revisar |
|---|---|---|
| "no se encontró una relación..." al hacer login WSAA | El servicio no está delegado al alias | Paso 3 |
| CUIT real que "no existe" en el padrón | Relación de "Consulta Constancia de Inscripción" no delegada — o estás en homologación (que solo conoce CUITs de prueba) | Paso 3, u homologación vs. producción |
| Certificado rechazado / `cms.sign.invalid` | Cert vencido, o de homologación usado contra producción (o viceversa) | Paso 2 |
| `FECAESolicitar` rechaza con "punto de venta inexistente" | Punto de venta no habilitado | Paso 4 |
| `FEXAuthorize` falla con "no se encontró una relación..." aunque "wsfe" sí funcione | Servicio de exportación NO delegado — son relaciones independientes | Paso 3 (Comprobantes de Exportación) |

## Validador automático de estos trámites — patrón ya resuelto (en el consumidor, no en la librería)

AFIP no expone un endpoint directo de "¿tengo la relación X delegada?" — la única forma de saberlo es
PROBAR la operación real y traducir el resultado/excepción a un chequeo legible. `arca_fe` se
mantiene sin estado (no sabe de tu base de datos ni de tus emisores guardados) a propósito, así que
este validador vive del lado de quien la consume — en Rambla,
`services/facturacion/diagnostico.py::diagnosticar_emisor`, construido enteramente sobre piezas
portables de acá:

- **Capa 1** (local, sin red, corta temprano si ya garantiza el fracaso): `cuit_valido`, certificado
  cargado/vigente, punto de venta asignado.
- **Capa 2** (contra AFIP, solo si la capa 1 pasó): `WsfeClient.param_puntos_venta()` — ¿"wsfe" está
  delegado y el punto de venta habilitado?; `PadronClient.get_persona()` sobre el propio CUIT del
  emisor — ¿la relación de padrón está delegada?

Si vas a construir tu propio validador sobre `arca_fe`, este es el patrón: probar, nunca adivinar.
