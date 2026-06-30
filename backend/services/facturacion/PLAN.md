# Plan de implementación — Motor de facturación electrónica ARCA

> **Ejecución mecánica (Sonnet).** Este es el spec completo: cada fase = un PR scoped a
> `claude/facturacion-arca`. Diseño decidido en Opus (tracking #1139). No re-decidir; si algo no encaja,
> parar y avisar. Invariantes abajo NO se violan.

## Principios e invariantes (no se violan)
- **Core portable `backend/arca_fe/`**: cero imports de `backend.*` / FastAPI / psycopg. Solo data plana +
  (en wsaa/wsfe) `zeep` + `cryptography`. Versionado SemVer (`__version__`). Se extrae a librería pip sin tocarlo.
- **Adapter `backend/services/facturacion/`**: el pegamento Rambla (mapea pedido→core, persiste, R2, mail, endpoints).
- **El que usa no calcula plata**: el neto/IVA/total los da `services/precios.calcular_total`; el core valida y
  formatea, no inventa precios. El front solo muestra.
- **Gating ARCA = default-deny** (INVERSO a GA4): emite real SÓLO si `is_production` Y cert de prod. Ante la duda → homologación.
- **Secretos (cert+clave) en ENV de Railway**, nunca en `app_settings` (GET público sin auth + se copia a staging).
- **Factura inmutable**: nunca DELETE de una emitida; anulación = nota de crédito.
- **No tocar** el core de reservas ni `_make_session_response`.
- DAL psycopg3 `%s`; esquema dos capas (`database/schema.py::init_db` + Alembic); enteros ARS internos.

## Prerequisito del dueño (manual, fuera del código)
En el portal ARCA, para **Pablo (RI)** y **Santini (Monotributo)**: generar certificado de **homologación**
(WSASS), asociarlo al WS `wsfe`, y dar de alta el **Punto de Venta para Web Services**. (Prod: ídem al final, Fase 6.)

---

## CORE PORTABLE `backend/arca_fe/` (ya iniciado: `__init__.py`, `modelos.py`)

### `modelos.py` ✅ (hecho)
Enums fiscales (`CondicionIva`, `DocTipo`, `CbteTipo`, `Concepto`), `AlicuotaIva` + tabla (IVA_21=Id 5, etc.),
`Emisor`, `Receptor`, `CbteAsoc`, `ComprobanteRequest`, `CaeResult`. Todo `@dataclass(frozen=True)`.

### `comprobante.py` (Fase 0 — pura, testeable sin ARCA)
- `tipo_comprobante(req) -> CbteTipo`: emisor MONOTRIBUTO→C; RI + receptor RI→A; RI + resto→B (NC: 13/3/8).
- `calcular_importes(req) -> {neto, iva, total}` en `Decimal` 2 decimales `ROUND_HALF_UP`; iva=0 si `alicuota
  is None`; **assert total == neto + iva** (cuadre al centavo).
- `armar_fecae(req, numero) -> dict`: arma `{FeCabReq, FeDetReq:[det]}`. Det con DocTipo/DocNro,
  CbteDesde=Hasta=numero, CbteFch=`req.fecha`(YYYYMMDD), Imp* como str 2 dec, MonId 'PES'/MonCotiz 1,
  **CondicionIVAReceptorId** (obligatorio RG5616). Concepto 2/3 → FchServDesde/Hasta/VtoPago. A/B con alícuota
  >0 → array `Iva:[{Id,BaseImp,Importe}]`; C → sin Iva, ImpNeto=ImpTotal, ImpIVA=0. NC → `CbtesAsoc`.

### `qr.py` (Fase 0 — pura)
- `armar_qr(*, cuit_emisor, pto_vta, cbte_tipo, nro_cmp, importe_total, doc_tipo_rec, doc_nro_rec, cae, fecha,
  moneda='PES', ctz=1, ver=1) -> str`: JSON RG4892 → base64 → `https://www.afip.gob.ar/fe/qr/?p=<b64>`.

### `wsaa.py` (Fase 2 — necesita cert, testeable la firma sin red)
- `construir_tra(servicio='wsfe', ahora) -> bytes`: XML LoginTicketRequest (uniqueId/genTime/expTime, +/-10min).
- `firmar_tra(tra, cert_pem, key_pem) -> bytes`: CMS/PKCS#7 con `cryptography` (`pkcs7.PKCS7SignatureBuilder`). ✅ probado en el spike.
- `login(tra_cms, endpoint) -> (token, sign, expira_at)`: POST a LoginCms, parsea XML. **No cachea acá** (lo hace el adapter en `afip_ta`).
- Sin estado/IO: recibe cert/key como bytes, devuelve datos. El cache (BD) lo pone el adapter.

### `wsfe.py` (Fase 2 — cliente SOAP zeep)
- `class WsfeClient(endpoint, cuit, token, sign)`: `ultimo_autorizado(pto_vta, cbte_tipo) -> int`,
  `consultar(pto_vta, cbte_tipo, numero) -> dict|None` (**FECompConsultar**), `solicitar_cae(fecae) -> CaeResult`
  (parsea Resultado A/R + CAE + CAEFchVto + Observaciones + Errores; NUNCA asume éxito), `param_*` (validar PtoVta).
  WSDL cacheado local.

### `tests/` (package-local, viajan con el core)
`test_comprobante.py`, `test_qr.py`, `test_wsaa_firma.py` (firma CMS con cert de test), `test_portabilidad.py`
(escanea `arca_fe/*.py`: **falla si hay `import backend` / `from backend`**).

---

## ADAPTER RAMBLA `backend/services/facturacion/`

- `config.py` — `credenciales(emisor: 'pablo'|'santini') -> CredARCA`: resuelve ambiente por `is_production`
  (default-deny), CUIT/PtoVta de `app_settings`, cert/clave de ENV (`AFIP_{PABLO|SANTINI}_{CERT|KEY}`),
  condición fija (Pablo=RI, Santini=Mono). Un punto que devuelve (endpoints, cert, key, cuit, ptovta) coherentes.
- `emisores.py` — **resolver único compartido con firma #1138**: `emisor_para(perfil_impuestos_receptor) ->
  'pablo'|'santini'`. RI→pablo; resto→santini. (La firma lo usa para el Locador del contrato.)
- `wsaa_cache.py` — `get_ta(emisor) -> (token, sign)`: lee `afip_ta` por (ambiente, emisor); si vencido,
  `arca_fe.wsaa.login` y persiste. Refresh serializado (no pedir 2 TA simultáneos).
- `comprobante_pedido.py` — mapea un pedido Rambla → `arca_fe.ComprobanteRequest`: receptor de
  `_enriquecer_pedido_con_cliente_fiscal` (perfil/CUIT/razón social), neto/iva de `precios.calcular_total`
  (NO recalcula), alícuota IVA_21 si emisor RI / None si Mono, concepto SERVICIOS, fechas (CbteFch=`now_ar()`,
  FchServDesde/Hasta=fechas del pedido, FchVtoPago=FchServHasta).
- `engine.py` — orquestador `emitir_factura(conn, pedido_id) -> Factura` y `emitir_nota_credito(conn, factura_id)`.
  Secuencia robusta (ver Fase 3).
- `pdf.py` — `factura_html(factura, pedido) -> str` (delega en `pdf_templates._factura_html`).
- `repo.py` — DAL (`%s`): `insert_factura`, `update_cae`, `get_factura_vigente(pedido_id)`, `list_facturas(filtros)`,
  `get_by_id`. Nunca DELETE de emitida.

---

## FASES (cada una = un PR)

### Fase 0 — Core puro (sin ARCA) — **EN CURSO**
- Hecho: `__init__.py`, `modelos.py`. Falta: `comprobante.py`, `qr.py`, `tests/{test_comprobante,test_qr,test_portabilidad}.py`.
- **Aceptación:** `pytest backend/arca_fe/tests/` verde; tipo de comprobante correcto (mono→C, RI+RI→A, RI+CF→B);
  importes cuadran al centavo; QR decodifica al payload esperado; el guard de portabilidad pasa.

### Fase 1 — Esquema + credenciales en el back-office (sin emitir)
- `database/schema.py::init_db`: `CREATE TABLE facturas` + `afip_ta` (DDL abajo), idempotente.
- `migrations/versions/<rev>_facturas_arca.py`: misma DDL (molde `d3e4f5a6b7c8`/`alquiler_pagos`).
- `config.py` + `emisores.py`. `routes/settings.py`: agregar a las keys editables (NO secretas):
  `afip_pablo_cuit`, `afip_pablo_ptovta`, `afip_santini_cuit`, `afip_santini_ptovta`.
- `routes/facturacion.py`: `GET /admin/facturacion/estado` → por emisor: {cuit, ptovta, cert_cargado: bool, ambiente}.
- Front `components/admin/settings/FacturacionSection.tsx` (molde `GoogleAnalyticsSection.tsx`): carga no-secretos
  de los 2 emisores + indicador "cert cargado: sí/no" por emisor (nunca muestra el secreto).
- **Aceptación:** cargar CUIT/PtoVta y verlos persistir; ver cert sí/no; cero llamadas a ARCA.

### Fase 2 — Cliente WSAA + WSFEv1 contra HOMOLOGACIÓN (auth + lecturas) · sagrado/infra
- `requirements.txt`: agregar `zeep` (cryptography ya entra por pyjwt[crypto]).
- `arca_fe/wsaa.py`, `arca_fe/wsfe.py`, `services/facturacion/wsaa_cache.py`, `repo.py` (afip_ta).
- Tests: `arca_fe/tests/test_wsaa_firma.py` (firma TRA + cert de test); `test_facturacion_wsfe_param.py`
  (parseo A/R/Observaciones con fixtures XML). Smoke real contra homologación vía staging-login (manual).
- **Aceptación:** obtener TA de homologación (token+sign) y cachearlo en `afip_ta`; `ultimo_autorizado` y
  `param_*` responden; `consultar` de un número inexistente devuelve None. Sin emitir.

### Fase 3 — Emisión real (engine) + PDF fiscal con QR/CAE en R2 (HOMOLOGACIÓN) · sagrado/infra
**`engine.emitir_factura` — secuencia (orden obligatorio):**
1. Validar estado del pedido ≥ 'confirmado'.
2. Resolver emisor (`emisores.emisor_para`) + receptor; validar datos (Factura A exige CUIT; sólo-DNI→DocTipo 96).
   **Fallback de condición receptor:** RI sin CUIT → degradar a B/C con error claro (no romper).
3. neto/iva de `precios.calcular_total` (no recalcula) → `ComprobanteRequest` (CbteFch=`now_ar()`, FchVtoPago def).
4. **`pg_advisory_xact_lock` por (ptovta, cbte_tipo)** (namespace propio ≠ pedidos) y **sostenerlo durante TODA
   la llamada SOAP** (lock → consultar → solicitar → soltar; no soltar entre medio).
5. Idempotencia: si ya hay factura `emitida`/`pendiente` para el pedido (UNIQUE parcial) → devolverla.
6. Persistir `estado='pendiente'` ANTES de llamar.
7. `ultimo_autorizado(pv,tipo)`; **antes de re-emitir tras error/timeout: `consultar` el último número** para
   no duplicar (CAE obtenido pero no persistido).
8. `solicitar_cae`; al recibir respuesta, **persistir CAE+numero+raw_response en TX ATÓMICA PROPIA**.
9. Resultado 'R' o WS caído → `estado='error'/'pendiente'` con errores, reintentable, **nunca 500**.
10. **Best-effort fuera de la tx fiscal:** `factura_html`→`pdf._render_pdf` (async, fuera de la conexión DB,
    como `documentos.py`)→`media.put_private('facturas/{pedido}/{numero}.pdf')`; guardar `pdf_key`.
- `pdf_templates._factura_html(factura, pedido)`: molde `_contrato_html`+`ri_extra`; **UNA página**; datos del
  emisor (Pablo/Santini); "FACTURA A/C"; QR `<img>` data-uri; CAE+vto+leyendas; banner "HOMOLOGACIÓN" si no es prod.
- `routes/facturacion.py`: `POST /alquileres/{id}/facturar` (require_admin, transporte).
- Tests: `test_facturacion_engine.py` (idempotencia, importes, CAE en tx propia, fallback receptor),
  `test_facturacion_pdf_privado.py` (molde `test_f3_comprobantes_privados.py`).
- **Aceptación:** emitir contra homologación, factura 'emitida' con CAE+vto, PDF con QR en R2 privado.

### Fase 4 — Botón en el pedido + visualizador "como los pagos" + mail
- `routes/facturacion.py`: `GET /admin/facturas` (global, filtros — molde `list_all_pagos`); `GET
  /alquileres/{id}/facturas`; `GET /facturas/{id}/pdf` (presigned_url privado + registra acceso);
  `POST /alquileres/{id}/facturar/mail`.
- Front: `routes/admin/facturas.lazy.tsx` (clon de `pagos.lazy.tsx`); `design-system/kit/FacturaBadge.tsx`
  (clon `PagoBadge`: pendiente/emitida/error/anulada); `components/admin/pedido/PedidoPageCards.tsx` →
  `FacturaSidebar` (botón **Facturar** idempotente con mutación+toast+invalidate; si emitida → **Ver factura**;
  **Enviar por mail**); `lib/admin/api.ts` (listFacturas, facturarPedido, enviarFacturaMail).
- Mail: clonar `enviar_documentos` (única boca de mail con adjunto) — `send_email`+`Attachment` con el PDF de R2.
- **Front no calcula plata**: muestra neto/IVA/total/CAE/estado que da el backend. Read-only, append-only.
- **Aceptación:** facturar desde el pedido, ver número+CAE, botón pasa a "Ver factura", abrir PDF, lista global
  con filtros, enviar por mail y que llegue.

### Fase 5 — Notas de crédito (anulación/devolución) · sagrado/infra
- `engine.emitir_nota_credito(conn, factura_id)`: CbteTipo 13/3/8 según emisor, `CbtesAsoc` a la original;
  misma serialización + idempotencia. La original pasa a `estado='anulada'` (su CAE sigue válido; la anulación
  ES la NC). `_factura_html` parametrizado para NC.
- `routes/facturacion.py`: `POST /facturas/{id}/nota-credito`. Front: acción "Anular con nota de crédito" en
  `FacturaSidebar` (con confirmación). Test `test_facturacion_nota_credito.py`.
- **Aceptación:** anular una factura de homologación genera NC que referencia la original; original→'anulada'.

### Fase 6 — Promoción a PRODUCCIÓN + manual + memoria
- `config.py`: gating final default-deny (triple: `is_production` Y modo Y cert de prod). `test_facturacion_gating.py`
  (staging NUNCA emite contra prod).
- `docs/SISTEMA_FACTURACION.md` (manual, molde `SISTEMA_CARRITO.md`). Entrada en `MEMORIA.md`+`DECISIONES.md` (OK del dueño).
- Pasos manuales del dueño: cert/PtoVta de PROD en el portal + ENV-secrets de prod + app_settings de prod.
- **Aceptación:** primera factura real (pedido chico) con CAE de verdad; gating verificado.

---

## DDL (Fase 1)

```sql
CREATE TABLE IF NOT EXISTS facturas (
  id              SERIAL PRIMARY KEY,
  pedido_id       INTEGER NOT NULL REFERENCES alquileres(id) ON DELETE CASCADE,
  emisor          TEXT NOT NULL,                 -- 'pablo' | 'santini'
  ambiente        TEXT NOT NULL,                 -- 'homologacion' | 'produccion'
  cbte_tipo       INTEGER NOT NULL,
  pto_vta         INTEGER NOT NULL,
  cbte_nro        INTEGER,                        -- null hasta CAE
  cae             TEXT,
  cae_vto         DATE,
  doc_tipo        INTEGER NOT NULL,
  doc_nro         TEXT NOT NULL,
  condicion_iva_receptor INTEGER NOT NULL,
  concepto        INTEGER NOT NULL,
  imp_neto        INTEGER NOT NULL,               -- enteros ARS
  imp_iva         INTEGER NOT NULL DEFAULT 0,
  imp_total       INTEGER NOT NULL,
  moneda          TEXT NOT NULL DEFAULT 'PES',
  cliente_cuit    TEXT,                           -- snapshot
  razon_social    TEXT,                           -- snapshot
  qr_payload      TEXT,
  pdf_key         TEXT,                           -- R2 privado
  estado          TEXT NOT NULL DEFAULT 'pendiente',  -- pendiente|emitida|error|anulada
  nota_credito_de INTEGER REFERENCES facturas(id),
  raw_request     JSONB,
  raw_response    JSONB,
  errores         JSONB,
  fecha_emision   TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by      TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_factura_vigente_por_pedido
  ON facturas (pedido_id) WHERE estado IN ('pendiente','emitida');
CREATE INDEX IF NOT EXISTS idx_facturas_pedido ON facturas (pedido_id);

CREATE TABLE IF NOT EXISTS afip_ta (
  ambiente   TEXT NOT NULL,
  emisor     TEXT NOT NULL,
  token      TEXT NOT NULL,
  sign       TEXT NOT NULL,
  expira_at  TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (ambiente, emisor)
);
```

## Decisiones (cerradas)
Multi-emisor (RI→A/Pablo, resto→C/Santini) · cliente SOAP in-house (zeep+cryptography) · cert/clave en ENV por
emisor · base=monto del pedido (devengado) · facturar desde 'confirmado'+ · 1 factura por pedido · página única ·
gating default-deny · Locador del contrato sigue al emisor (firma #1138). ⏳ Locador≠facturador → contador.
