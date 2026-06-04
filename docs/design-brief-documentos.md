# Brief de diseño — Documentos (PDF) de Rambla Rental

> **Para qué sirve esto:** es el *brief* que se abre desde **Claude Design** para
> generar el **handoff** del rediseño de marca de los documentos. NO es el handoff.
> El flujo es: este brief → Claude Design (mockups) → `design_handoff_documentos/`
> en el repo → se implementa con el skill `importar-diseno`.
>
> **Decisión del dueño (2026-06-04):** los documentos están desactualizados y fuera
> de marca; se rediseñan con la identidad de Rambla, vía un handoff de Claude Design.

---

## Qué se rediseña (Fase 1 — los 5 documentos)

Los 5 son PDF A4 que se generan al vuelo en `backend/pdf.py` (un builder de HTML por
documento + `_render_pdf` que rasteriza con Playwright). Se ven/descargan desde el
detalle de pedido (`/admin/pedidos/{id}` → sección Documentos) y, el reporte, desde
Estadísticas → Reportes.

| Documento | Builder actual | Qué muestra | Tono |
|---|---|---|---|
| **Remito** | `_pedido_html` | Items del pedido con foto, cantidad, precio/jornada, subtotal; datos del cliente; fechas; total | Comercial, claro |
| **Albarán** | `_albaran_html` | Items con Nº de serie y valor de reposición; firma de retiro/devolución | Operativo, formal |
| **Contrato** | `_contrato_html` | Cláusulas de alquiler, datos del locador/locatario, fechas, total, firmas | **Legal/formal** (sobrio) |
| **Packing list** | `_packing_list_html` | Checklist de equipos (#, foto, equipo, cant., **checkboxes Salida/Retorno**) + barra de progreso | **Interactivo en pantalla** + imprimible |
| **Reporte de liquidación** | `_liquidacion_html` | Tarjetas por beneficiario + total; grilla mes×beneficiario; detalle por dueño | Financiero, prolijo (ya es el más nuevo) |

**Inconsistencia actual a resolver:** cada uno usa fuentes y acentos distintos
(Space Mono, Nunito, Helvetica; `#F9B92E`/`#111`/`#333`). Ninguno usa la identidad real.
El objetivo es **una base visual compartida** (header con wordmark, paleta, tipografías,
números en mono) reusada por los 5 — no 5 estilos sueltos.

---

## Identidad de marca a aplicar

Fuente canónica: [`docs/DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md). Resumen para el handoff:

### Color
- **Acento:** amber `#FAB428` (el único acento; barra/header/CTA). Paso claro `#FFCC55`.
- **Texto/ink:** casi negro cálido (`ink` ≈ `oklch(0.14 0.01 60)` → ~`#211c14`). Para print fuerte, `#000`.
- **Fondo hoja:** blanco. Superficies suaves: bone/`surface` (`#faf8f3` aprox).
- **Bordes/hairline:** ink al 12%.
- **Texto secundario:** muted (`#8a8378`/`#6b6457`).
- **Disciplina de un solo acento:** nada de paletas multicolores. Status (verde/azul/rojo)
  solo si un dato lo exige semánticamente (ej. estados de pedido).

### Tipografía
- **TT Commons** → headings de UI (Title Case) y body. Vendoreada en `src/assets/fonts/`.
- **Champ Black** → SOLO el wordmark/display, **en minúsculas** (ej. el logo "rambla").
- **JetBrains Mono** → eyebrows, números, IDs, fechas, totales (uppercase, tracking ancho,
  `tabular-nums`). Disponible en Google Fonts.
- Números **siempre tabulares** (precios, fechas, counts).

### Forma
- Radios 8–12px. Hairlines finos. Aire generoso. Header con barra de acento amber.

---

## La hoja: A4 (no negociable)

- Todos los documentos son **A4** (210×297mm). Ya hay un helper único
  `pdf._a4_page(margin)` que declara `@page { size: A4; ... }` — el handoff debe diseñar
  **a proporción A4**, con márgenes consistentes (referencia: 14–18mm).
- El render real lo hace `_render_pdf` con `format="A4"`. El HTML tiene que verse bien
  tanto **en el PDF** como en el **preview en pantalla** (el packing y el reporte se ven
  en un iframe; usar `@media screen` para que el preview se adapte al ancho y `@media print`
  para la hoja A4 — patrón ya usado en `_liquidacion_html`).

---

## Restricciones técnicas (para que el handoff sea implementable)

El PDF se rasteriza con **Playwright `set_content()`** (base `about:blank`). Implica:

1. **Imágenes:** los paths relativos no resuelven. Las fotos se pasan por
   `_abs_image_url()` (usa `FRONTEND_BASE_URL`). El diseño puede asumir fotos cuadradas
   chicas (~36–48px) con placeholder "—" cuando no hay.
2. **Fuentes:** JetBrains Mono entra por `@import` de Google. **TT Commons / Champ Black**
   están vendoreadas en el front → para el PDF hay que **servirlas en una URL absoluta o
   embeberlas (base64 `@font-face`)**. Esto lo resuelvo yo en la implementación; el handoff
   solo tiene que **especificar** qué fuente va en cada rol.
3. **Email-safe NO aplica a los PDF** (son HTML completo con `<style>`, no tablas inline).
   Pero el **packing** es interactivo en pantalla (checkboxes + barra de progreso) → mantener
   ese comportamiento; el branding no debe romper la interacción.
4. **Contrato:** priorizar legibilidad legal sobre branding — header branded sí, pero el
   cuerpo sobrio y denso.

---

## Formato del handoff esperado (para `importar-diseno`)

Carpeta `design_handoff_documentos/` con:
- un **HTML de referencia visual** por documento (o uno que los muestre a todos),
- opcionalmente `.tsx`/snippets si aplica,
- un **README** con specs (medidas, tokens usados, notas por documento).

Ver el skill `importar-diseno` para el detalle del formato.

---

## Fase 2 (opcional, a confirmar) — Emails

Los 4 mails (`pedido_creado_cliente`, `pedido_confirmado_cliente`, `pedido_creado_admin`,
`recordatorio_retiro`) tienen su propio shell branded en
`backend/services/email/service.py::_wrap_email_html` (header con logo + barra amber + footer)
y el contenido editable en `backend/services/email/default_templates.py`. Si se incluyen,
el handoff de mails debe respetar **HTML email-safe** (tablas, estilos inline, ancho ~600px)
— es un contexto distinto al de los PDF. **Pendiente de definición del dueño** si entran en
esta tanda o en una segunda.
