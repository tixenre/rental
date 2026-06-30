# Sistema de facturación electrónica ARCA

> **Manual técnico vivo.** Describe la arquitectura, flujo y puntos de entrada del sistema
> de facturación ARCA (ex-AFIP). El **por qué** de cada decisión vive en
> [`MEMORIA.md`](MEMORIA.md) / [`DECISIONES.md`](DECISIONES.md) y se **linkea**, no se copia.

---

## 1. Arquitectura en dos capas

```
backend/arca_fe/                  ← Core portable (librería, SemVer)
backend/services/facturacion/     ← Adapter Rambla (persistencia, PDF, routes)
```

### Core portable `backend/arca_fe/`

Zero imports de `backend.*` / FastAPI / psycopg. Puede extraerse a un paquete pip propio sin
cambios. Exporta su contrato público en `__init__.py` (`__all__`).

| Módulo | Responsabilidad |
|---|---|
| `modelos.py` | Enums y dataclasses fiscales (`CbteTipo`, `CondicionIva`, `ComprobanteRequest`, `CaeResult`, …) |
| `comprobante.py` | `tipo_comprobante`, `calcular_importes`, `armar_fecae` |
| `qr.py` | `armar_qr` → URL AFIP-QR embebida en el PDF |
| `wsaa.py` | `login_con_cert` → obtiene el Ticket de Autorización (TA) |
| `wsfe.py` | `WsfeClient` → `ultimo_autorizado`, `solicitar_cae`, `consultar` (idempotencia) |
| `tests/` | Tests unitarios del core (sin IO ni DB) |

### Adapter Rambla `backend/services/facturacion/`

| Módulo | Responsabilidad |
|---|---|
| `config.py` | Lee CUIT/PtoVta de `app_settings` + cert/clave de ENV → `CredARCA`. **Gating aquí.** |
| `emisores.py` | `emisor_para(perfil_impuestos)` → `'pablo'` o `'santini'` |
| `wsaa_cache.py` | Caché de TA en tabla `afip_ta` (evita llamar WSAA en cada factura) |
| `comprobante_pedido.py` | Mapea un pedido + emisor → `ComprobanteRequest` (receptor, importe, concepto) |
| `engine.py` | `emitir_factura`, `emitir_nota_credito` — la orquestación completa |
| `repo.py` | DAL: `insert_factura`, `update_cae`, `update_error`, `list_facturas`, etc. |
| `pdf.py` | `factura_html` → HTML del PDF de la factura |

### Routes HTTP

`backend/routes/facturacion.py`:

| Método | Path | Quién lo llama |
|---|---|---|
| `GET` | `/api/admin/facturacion/estado` | Panel de config |
| `POST` | `/api/alquileres/{id}/facturar` | Admin — botón "Emitir factura" en pedido |
| `GET` | `/api/alquileres/{id}/facturas` | Admin — section Facturación en pedido |
| `POST` | `/api/facturas/{id}/nota-credito` | Admin — botón "Anular con NC" |
| `GET` | `/api/admin/facturas` | Admin — listado global `/admin/facturas` |
| `GET` | `/api/facturas/{id}/pdf` | Admin — descarga PDF desde R2 |

---

## 2. Flujo de emisión (`emitir_factura`)

```
emitir_factura(pedido_id)
  │
  ├─ 1. Valida estado pedido ≥ 'confirmado'
  ├─ 2. Resuelve emisor: emisor_para(perfil_impuestos) → 'pablo' | 'santini'
  ├─ 3. credenciales(emisor, conn) → CredARCA  [config.py — GATING aquí]
  ├─ 4. construir_comprobante(pedido, emisor) → ComprobanteRequest
  ├─ 5. pg_advisory_xact_lock(hash(pto_vta, cbte_tipo))  ← mantiene hasta commit
  ├─ 6. Idempotencia: si ya hay factura 'emitida' → devuelve la existente
  ├─ 7. INSERT facturas estado='pendiente'  ← ANTES de llamar al WS
  ├─ 8. get_ta(emisor) → (token, sign)  [wsaa_cache.py]
  ├─ 9. WsfeClient.ultimo_autorizado()  → consulta si hay timeout anterior
  ├─ 10. WsfeClient.solicitar_cae(fecae)
  │     ├─ Aprobado → update_cae(..., estado='emitida') + armar_qr()
  │     └─ Rechazado → update_error(..., errores=[...])  estado='error'
  └─ 11. PDF best-effort (_generar_pdf_background) → R2 / update_pdf_key()
```

**Invariante de lock:** el `pg_advisory_xact_lock` cubre toda la llamada SOAP para que dos
requests simultáneos para el mismo (pto_vta, cbte_tipo) no generen huecos en la numeración.
Namespace distinto al lock de pedidos (`_LOCK_NS = 0xFA0C0000`).

**Nunca DELETE:** toda factura es inmutable. Si falla → `estado='error'` (reintentable).
Anulación = Nota de Crédito (ver §3).

---

## 3. Nota de crédito (`emitir_nota_credito`)

Igual a emisión pero con `es_nota_credito=True` y `CbteAsoc` apuntando a la factura original.
Al aprobar la NC:
- La NC pasa a `estado='emitida'`.
- La factura original pasa a `estado='anulada'` (`marcar_anulada`).
- La relación se guarda en `facturas.nota_credito_de = factura_id`.

---

## 4. Routing de emisor

```
clientes.perfil_impuestos == 'responsable_inscripto'  →  Pablo (RI) → Factura A (cbte_tipo=1)
                          cualquier otro              →  Santini (MT) → Factura C (cbte_tipo=11)
```

Fuente única: `services/facturacion/emisores.py::emisor_para`. Mismo resolver que usa el
motor de contratos (`#1138`). No duplicar esta lógica.

---

## 5. Gating de ambiente (default-deny)

**Regla:** emite en **producción** solo si `config.settings.is_production is True`.
Ante cualquier duda → homologación. INVERSO a GA4 (que expone en prod).

```python
# config.py
ambiente = "produccion" if app_settings.is_production else "homologacion"
```

Secretos **solo en ENV de Railway** (nunca en `app_settings`, que tiene GET público y se copia
al clon de staging):

```
AFIP_PABLO_CERT   / AFIP_PABLO_KEY     ← cert + clave PEM de Pablo
AFIP_SANTINI_CERT / AFIP_SANTINI_KEY   ← cert + clave PEM de Santini
```

Si faltan → `ValueError` descriptivo antes de tocar ARCA (no 500 críptico).

Test de regresión: `backend/tests/test_facturacion_gating.py`.

---

## 6. Schema de base de datos

### Tabla `facturas`

| Columna | Tipo | Notas |
|---|---|---|
| `id` | SERIAL PK | |
| `pedido_id` | INTEGER FK → alquileres | CASCADE delete |
| `emisor` | TEXT | `'pablo'` \| `'santini'` |
| `ambiente` | TEXT | `'homologacion'` \| `'produccion'` |
| `cbte_tipo` | INTEGER | 1=FA, 3=NCA, 6=FB, 8=NCB, 11=FC, 13=NCC |
| `pto_vta` | INTEGER | Punto de venta habilitado ante ARCA |
| `cbte_nro` | INTEGER | Número asignado por ARCA (null hasta autorizado) |
| `cae` | TEXT | 14 dígitos, null hasta autorizado |
| `cae_vto` | DATE | |
| `doc_tipo` / `doc_nro` | INTEGER / TEXT | CUIT del receptor |
| `condicion_iva_receptor` | INTEGER | 1=RI, 4=Ex, 5=CF, 6=MT |
| `concepto` | INTEGER | 1=Productos, 2=Servicios, 3=Ambos |
| `imp_neto` / `imp_iva` / `imp_total` | INTEGER | **Pesos enteros ARS** (sin centavos) |
| `moneda` | TEXT | Siempre `'PES'` |
| `cliente_cuit` / `razon_social` | TEXT | Snapshot del receptor |
| `qr_payload` | TEXT | URL AFIP-QR embebida en el PDF |
| `pdf_key` | TEXT | Key en R2 (null hasta generado) |
| `estado` | TEXT | `pendiente` \| `emitida` \| `error` \| `anulada` |
| `nota_credito_de` | INTEGER FK → facturas | Self-ref; null para facturas originales |
| `raw_request` / `raw_response` / `errores` | JSONB | Debug + mensajes ARCA |
| `fecha_emision` | TIMESTAMPTZ | Seteado al persistir el CAE |
| `created_at` / `created_by` | TIMESTAMPTZ / TEXT | |

### Índice de idempotencia

```sql
CREATE UNIQUE INDEX uq_factura_vigente_por_pedido
  ON facturas (pedido_id)
  WHERE estado IN ('pendiente', 'emitida');
```

Garantiza que un pedido solo tenga una factura activa a la vez. La NC no viola esto (la
original pasa a `'anulada'` antes de que la NC pase a `'emitida'`, dentro de la misma TX).

### Tabla `afip_ta`

Caché del Ticket de Autorización (WSAA). PK = `(ambiente, emisor)`. Se renueva automáticamente
cuando expira (`wsaa_cache.py::get_ta`).

### En `database.py::init_db()` y en Alembic

Las dos tablas están en ambas capas (`a2b3c4d5e6f7_facturas_arca.py` + `d3e4f5a6b7c8_factura_a_fields.py`),
conforme a la regla _2026-06-03_.

---

## 7. Frontend

### Ruta `/admin/facturas`

Listado global de facturas con filtros por emisor, estado y rango de fechas.
Componente: `src/routes/admin/facturas.lazy.tsx`.
API: `facturacionApi.listFacturas(params)` → `GET /api/admin/facturas`.

### Sección Facturación en `/admin/pedidos/:id`

Componente `FacturacionRailSection` en `src/routes/admin/pedidos.$id.lazy.tsx`.

- Muestra la factura vigente del pedido: badge de estado, número, CAE, errores.
- Botón **"Emitir factura"** si el pedido está en estado facturable y no hay factura activa.
- Botón **"Anular con NC"** si la factura está emitida y no tiene NC.
- Link de descarga del PDF (cuando `pdf_key` está presente).
- Badge **"TEST"** si `ambiente == 'homologacion'`.

### Componente `FacturaBadge`

`src/components/kit/FacturaBadge.tsx` — badge de estado con colores del DS.
Importar de ahí; no recrear variantes.

---

## 8. Configuración inicial en Railway

1. **Variables de entorno** (tab Variables del servicio de producción):
   ```
   AFIP_PABLO_CERT=<contenido PEM del certificado de Pablo>
   AFIP_PABLO_KEY=<contenido PEM de la clave privada de Pablo>
   AFIP_SANTINI_CERT=<contenido PEM del certificado de Santini>
   AFIP_SANTINI_KEY=<contenido PEM de la clave privada de Santini>
   ```

2. **CUIT y Punto de Venta** (Back-office → Settings → Facturación ARCA):
   - `afip_pablo_cuit` / `afip_pablo_ptovta`
   - `afip_santini_cuit` / `afip_santini_ptovta`

3. **Homologación primero:** con las certs de homologación y `is_production=False` (staging)
   se pueden emitir facturas de prueba sin afectar la numeración real. Las facturas de
   homologación quedan registradas en la tabla con `ambiente='homologacion'`.

4. **Producción:** setear las certs de producción en el ambiente `production` de Railway.
   El gating default-deny hace el resto.

---

## 9. Reglas invariantes (no violar)

1. **Nunca DELETE de una factura emitida** → anulación siempre por NC.
2. **Gating default-deny** → homologación si hay duda; producción solo con `is_production`.
3. **Secretos en ENV** → nunca en `app_settings` (GET público + clon de staging).
4. **No tocar el core de reservas** → `emitir_factura` hace SELECTs de lectura, sin locks del motor.
5. **Plata en enteros ARS** → `int(round(float(importes[...])))`, sin centavos.
6. **Emisor resuelto por `emisor_para`** → fuente única; no duplicar la regla RI→pablo.

El supervisor marca cualquier violación de estas reglas. Tracking: issue #1139.
