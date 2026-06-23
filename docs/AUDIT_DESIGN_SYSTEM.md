# Auditoría del Design System — Rambla Rental

> Auditoría **a nivel design-system** (tokens, componentes, reuso, gobernanza, contraste
> sistémico) — el **companion** de los audits a nivel pantalla (`AUDIT_UI_MULTIVIEWPORT.md`,
> `AUDIT_RESERVA_EDGE_CASES.md`). Tres lentes: **(1) DS audit** (estructura/tokens/componentes),
> **(2) design critique** (UX/jerarquía/consistencia), **(3) a11y review** (WCAG 2.1 AA).
> Método: lectura del código real + **contraste computado** sobre los tokens (OKLab→sRGB→WCAG,
> con compositing de opacidades). Read-only.
>
> Hecho: **2026-06-21**, re-validado contra `dev` el **2026-06-22**.
> **Los hallazgos son hipótesis con fecha de vencimiento** (memoria, commit 2ad1539): entre el
> audit y la re-validación corrió la ola a11y "Fases 3-4" (#970–#980) que ya arregló varios.
> Sev: 🔴 crítico/roto · 🟡 mayor/fricción · 🟢 menor · ✅ ok.

---

## 1. Delta — qué cambió entre el audit y `dev` (la verdad accionable)

### ✅ Ya arreglado por la ola #970–#980 (NO re-hacer)
| Finding original | Fix | Verificado hoy |
| --- | --- | --- |
| Pill `success` (verde) sobre tinte = 3.2:1 ❌ | **#980** — token `--color-verde-ink` (oklch 0.48); `Pill.success` usa `text-verde-ink`, aplicado a todos los chips verde-sobre-tint | **5.26:1** ✅ |
| Landing hub card "estudio" naranja, texto blanco 2.3–2.5:1 ❌ | **#980** — blanco → ink opaco (no se tocó `--color-naranja`) | 5.19:1 ✅ |
| Pill `danger` / rojo destructive | **#971** — `--color-destructive` oklch L 0.62→0.55 | **4.57:1** ✅ (al filo) |
| Tap targets <44px | **#970** utilidades `.hit-area-44`/`.hit-area-inline` + **#975**/**#979** | mecanismo OK, rollout parcial (~10 usos) |
| Inputs <16px (zoom iOS) | **#972** — anti-zoom global | ✅ |

### 🔴 Sigue ABIERTO (confirmado contra `dev` el 2026-06-22)
| # | Finding | Evidencia | Sev |
| --- | --- | --- | --- |
| O1 | **Magic font-sizes / escala tipográfica sin enforcement** (el dominante) | **633** `text-[Npx]` inline; **317** = `text-[10px]`; **92** sub-10px ilegibles. Recetas `.t-h1/h2/h3`, `.t-body`, `.t-small`, `.t-eyebrow`, `.t-display-*` = **0 usos** (solo `.t-mono` 104 y `.tabular` 61 viven). | 🔴 |
| O2 | **Pill `info` (azul) contraste** — único pill que sigue fallando | `info: bg-azul/10 text-azul`; `#1097db` da **2.91:1** ❌. Fix = espejo de #980: `--color-azul-ink` L≈0.48 → 5.57:1 | 🔴 |
| O3 | **PagoBadge ausente del portal cliente** | 0 usos en `cliente.portal.tsx`/`ClientePortal*` (sí está en `admin/pedidos.index`). El patrón de referencia "estado+plata" no se aplica donde más importa. | 🔴 |
| O4 | **Sin primitivo de loading** | `Loader2` inline en **34** archivos; no hay `<Spinner>`/`<Button loading>`. | 🟡 |
| O5 | **`PriceBlock` local recreado** | `routes/equipo.$slug.tsx:629` define su propio `PriceBlock` (no importa el shared) → jerarquía de precio distinta entre card y detalle, y usa `font-display` que el shared documentó como error. | 🟡 |
| O6 | **CTAs crudos en el carrito** | `CartDrawer.tsx` no usa el `Button` canónico (variantes `primary`/`amber` existen para esto). | 🟡 |
| O7 | **Tokens de motion muertos** | `--duration-*`/`--ease-*` = 0 usos en tsx, 1 en CSS. `FlyToCartLayer` hardcodea `0.55` que el token dice espejar. | 🟡 |
| O8 | **`/kit-preview` no existe** | el "storybook" que el doc publicita es ficción → no hay superficie de inspección del DS. | 🟡 |
| O9 | **Drift del doc `DESIGN_SYSTEM.md`** | ver §5. | 🟡 |

### Transparencia — lo que el audit erró
- El finding "escala `.t-*` muerta = **0 usos**" tuvo un **falso positivo de medición**: el grep `t-display`
  matcheaba el substring de **`fon`**`t-display`. La verdad: `.t-mono` (104) y `.tabular` (61) **sí** se usan;
  el resto de recetas no. El problema de fondo (633 magic-sizes) **igual es real** — pero el método se corrige:
  **verificar antes de afirmar**, los hallazgos son hipótesis.

---

## 2. Tokens & color

**Arquitectura (fortaleza):** tokens modulares en `frontend/src/design-system/styles/tokens/*` (colors/typography/
shadows/motion/z-index), OKLCH, sombras tintadas con ink cálido, dark-mode completo (sin toggle hoy).
**Disciplina de color enforced (fortaleza real):** `no-restricted-syntax` en `eslint.config.js` bloquea
escalas genéricas de Tailwind → solo 9 hex en todo el repo (excepciones documentadas) + 2 `eslint-disable`
controlados.

**Contraste — estado HOY (computado, compositing real de opacidades):**
| Par | Ratio | Req | ¿Pasa? |
| --- | --- | --- | --- |
| Pill `success` (verde-ink/verde@10) | 5.26:1 | 4.5 | ✅ |
| Pill `danger` (destr L0.55/@10) | 4.57:1 | 4.5 | ✅ |
| **Pill `info` (azul/azul@10)** | **2.91:1** | 4.5 | ❌ **abierto (O2)** |
| Pill `warning` (ink/amber@15) | 18.2:1 | 4.5 | ✅ |
| ink / amber (doc dice 7.2) | **11.0:1** | 4.5 | ✅ (doc subestima) |
| ink / bone (doc dice 16.4) | **19.1:1** | 4.5 | ✅ (doc subestima) |
| muted-foreground / bone | 8.12:1 | 4.5 | ✅ |
| texto `/40` (ink@40 / bone) | 2.71:1 | 4.5 | ❌ (usar muted-foreground) |

> Nota: el contraste blanco/naranja y los tap targets a nivel pantalla viven en `AUDIT_UI_MULTIVIEWPORT.md`.

---

## 3. Componentes — reuso y completitud

**Fortalezas:** fuente única real — `Pill` → del que derivan `EstadoBadge` y `PagoBadge`; `ClienteAvatar`
determinístico; `RentalDateModal` = wrapper fino sobre `DateRangePickerModal` (core reusable, NO duplicado);
`Button` maduro (8 variantes + 4 sizes + eje `shape`).

**Gaps abiertos:** sin primitivo de **loading** (O4, 34 Loader2 inline); `PriceBlock` **local** en el
detalle contradice el shared (O5); carrito con **CTAs crudos** en vez de `Button` (O6); **PagoBadge** no
se usa en el portal cliente donde el patrón de referencia (estado+plata visible) más importa (O3).

---

## 4. Escala tipográfica (el hueco dominante — O1)

No hay escala tipográfica con enforcement. La canónica (`.t-h1/h2/h3`, `.t-body`, `.t-eyebrow`,
`.t-display-*`) **existe pero no se usa** (0); en su lugar **633** tamaños mágicos `text-[Npx]` inline,
de los cuales **92 son sub-10px** (legibilidad). El eyebrow (mono 10px uppercase tracking) está hardcodeado
~317 veces en vez de `.t-eyebrow`/`.t-mono`. **Decisión pendiente:** adoptar las recetas (+ lint que marque
`text-[Npx]` suelto en headings/labels) **o** retirarlas y documentar honestamente que el type-system es
Tailwind utilities. Es el fix de mayor leverage — toca todo el front.

---

## 5. Gobernanza — drift del doc `DESIGN_SYSTEM.md` (O9)

Confirmado vigente:
- **Ubicaciones mal:** el doc dice que `EmptyState/PriceBlock/ViewToggle/StatCard/AddonPills/Input` viven en
  `kit/` → en realidad están en `rental/` (y `equipment/shared/`). `kit/` solo tiene Pill/EstadoBadge/
  PagoBadge/ClienteAvatar/types.
- **Componentes fantasma:** `SearchInput` y `FieldLabel` no existen.
- **CSS prometido inexistente:** `.skeleton`, `.card-interactive`, el press-state global `button:active`,
  el stagger `.catalog-grid` — ninguno está en CSS.
- **Valores desfasados:** focus ring doc=3px / real=**2px**; `.t-display-2` doc=40px/6vw/72px / real=36/5/64.
- **Path:** "Tokens en `src/styles.css`" → ya viven en `styles/tokens/*`.

→ El "source-of-truth ladder" del doc dice que el supervisor evita el drift; igual hay drift. **Sincronizar
el doc con el código (o generarlo desde el código) es el fix de gobernanza de mayor ROI.**

---

## 6. Backlog priorizado → encolado en issues existentes

No se crea cola paralela: se foldea en **epic #936** + **#967** (UI cliente) + **#968** (admin).

1. **Escala tipográfica / matar magic-sizes (O1)** — el de mayor leverage. Corte transversal (issue nuevo).
2. **Pill `info` azul → `--color-azul-ink` (O2)** — un token + Pill; espeja #980.
3. **PagoBadge en filas del portal (O3)** — pieza ya hecha; #967.
4. **Sync del doc DESIGN_SYSTEM.md (O9)** — va junto al reorg del DS (carpeta `design-system/`).
5. **Primitivo de loading (O4)**, **decisión motion tokens (O7)**, **`/kit-preview` vivo (O8)**.
6. **`PriceBlock` shared en detalle (O5)** — toca plata visible → rama+PR. **CTAs `Button` en carrito (O6)**.

---

## 7. Pasada fina post-prod (2026-06-22) — el delta tras #981–#986

> Re-auditoría **después** de shippear la ola #981–#986 a prod (DS reorg + azul-ink + PagoBadge
> portal + Spinner/Button-loading + kit-preview + escala tipográfica + tap targets #986). Método:
> grep exhaustivo + 2 agents de lectura completa (drift doc · estados/reuse) + harness multi-viewport
> (`ds-audit`, 320/768/1280) + **contraste recomputado del token** (OKLab→sRGB→WCAG). El "20% que
> falta" ya **no es a11y roto** (eso se cerró) — es **adopción incompleta del DS**.

### O1–O9: estado tras la ola
✅ **Cerrados:** O2 (azul-ink, #982) · O3 (PagoBadge portal, #982) · O4 (Spinner/Button-loading, #984) ·
O5 (PriceBlock shared, `5cabf3f2`) · O6 (CTAs carrito, `5d8a7934` — **solo el carrito**) · O8 (/kit-preview, #984).
🟡 **A medias:** O1 (#985 mató los `text-[Npx]` pero **quedan 52 `text-[Nrem]`** — ver N2) · O7 (motion movido
a `@theme` pero adopción mínima — ver N5) · O9 (drift del doc **sigue** — ver N7).

### Hallazgos NUEVOS / residuales (confirmados, no falsos positivos)
| # | Hallazgo | Evidencia (recomputada/leída) | Sev | Ruteo |
| --- | --- | --- | --- | --- |
| **N1** | **Chip "Visible" admin sin contraste AA** | `equipos.index.lazy.tsx:748` `bg-verde/15 text-verde` = **2.80:1** (token recomputado). Reincidencia de O2/verde que no llegó a este span inline. Fix conocido: `text-verde-ink` → **4.57:1** | 🔴 | trivial (1 línea) |
| **N2** | **Gap del guardrail tipográfico #985** | el regex era `text-\[\d+px\]` (solo px). **52 `text-[Nrem]`** escaparon (ej. `text-[0.6875rem]`=11px, `text-[1.0625rem]`=17px). El guardrail no los frena → O1 quedó a medias | 🟡 | normal |
| **N3** | **~19 CTAs crudos replican `<Button variant=primary/amber>`** | confirmado leyendo: 13 `bg-ink…hover:bg-amber` + 6 `bg-amber…`. Concentración: `CatalogoMovilHelpers`(4), `ClientePortalPedido`(3), `estudio.lazy`(3), `ClientePortalHelpers`(2). Varios desvían el token (`hover:brightness` en vez de `hover:bg-amber-hot`). O6 cerró **solo** el carrito | 🔴 | normal (lo ve el cliente → rama+PR) |
| **N4** | **~7 pills de estado a mano** | replican `kit/Pill`. Match exacto: `EquipmentCard.tsx:138` (danger), `ClientePortalPedido.tsx:417` (warning). Deberían derivar de `<Pill tone>` | 🟡 | normal |
| **N5** | **Motion: adopción mínima** (O7) | **3** usos de tokens (`button`+`spinner`) vs **47** transiciones hardcoded (`duration-200`/`transition-all`/`ease-in-out`). Decisión pendiente con datos: adoptar masivo **o** retirar y documentar honesto | 🟡 | decisión + normal |
| **N6** | **Focus ring: ancho inconsistente** | `ring-1` (shadcn primitivos) vs `ring-2` (Rambla). **El color SÍ está unificado** (amber vía `--ring`/`--sidebar-ring`/`ring-amber` = mismo hue — no es caos). + `button.tsx` no define `active:` (press-scale vive fuera, replicado ad-hoc) + 2-3 `focus:` crudo (`select.tsx:22`) vs `focus-visible:` | 🟡 | normal |
| **N7** | **Drift del doc `DESIGN_SYSTEM.md`** (O9 sigue) | 🔴 del doc: `.skeleton`/shimmer inexistente (real = `<Skeleton>` animate-pulse), `SearchInput` fantasma, `FieldLabel` duplicado 3× inline, componentes del kit listados en `kit/` pero viven en `rental/`, `button:active` global inexistente. 🟡: paths `src/styles.css`, focus 3px→2px, `.card-interactive`/`.catalog-grid` inexistentes, `/kit-preview` "admin-only" pero **público**, `--radius` base inexistente, `.grain` 40%→5%, `--ease-out`→`--ease-out-brand`, tokens huérfanos sin documentar (`--azul-ink`, escala `text-2xs/3xs/15/22`) | 🟡 | doc-sync |

### Falsos positivos descartados (honestidad > actividad)
- **ViewToggle "Grid/Lista" c:1.66** → recomputado **11.03:1** (amber sobre el sliding-indicator `bg-ink`; el parser no vio el stacking). ✅
- **"Conocé el estudio" c:1.06** → texto sobre **imagen** (hero estudio); el skill manda saltearlo (no medible vs sólido).
- **`font_lt_min` del harness** → todos `undefinedpx` = el parser no leyó el px (placeholders de input + footer links). Ruido.
- **5 hex "crudos"** → colores de marca de **terceros** (Google `#4285F4`, WhatsApp `#25D366`) + preview de mail. Legítimos por convención (no se tematizan).
- **`z-[60]/z-[61]` en `CatalogoMovilHelpers`** → coinciden con `--z-scrim`/`--z-drawer`; cosmético (podrían usar el token, no es bug).
- **harness `hub` = 0 flags** en 320/768/1280; los `tap<44` son mayormente footer text-links + elementos con `hit-area-44` (el harness no descuenta el `::before`).

### Veredicto
El DS está **sólido en lo que se shippeó** (a11y multi-viewport, tap targets reales, contraste de marca,
kit `Pill`→badges, estados de `switch`/`calendar`/`input`). El delta es **adopción y prolijidad**, no
roturas: **N1** (trivial, contraste real) y **N3** (lo ve el cliente) son los de mayor valor; **N2/N5/N7**
cierran huecos que la ola dejó a medias. Ninguno toca el core de reservas.

### Addendum — destapado al implementar PR1 (el render-compare paga)
- **N1 creció:** al migrar los chips a `<Pill>` aparecieron **2 contrastes rotos más** (no solo el admin):
  `equipo.$slug:397` "parcialmente disponible" `text-amber`/amber@10 = **1.61:1**, y `DateRangePicker:357`
  "+1 J" `text-naranja`/naranja@20 = **2.56:1**. Ambos por desviarse del estándar `text-ink`. Arreglados en PR1.
- **Badge "Presupuesto/Solicitado" (`EstadoBadge`)** usaba `text-azul` **brillante** (rgb 16,151,219 → **2.91:1**) —
  no tomó el `azul-ink` de #982 porque está en su `cls` map, no en el `tone="info"`. Visible en portal + admin.
  Arreglado en PR1 (`text-azul-ink` → 5.57:1). Confirmado en vivo en `/kit-preview`.
- **N8 (NUEVO, encolado — PR aparte):** `text-verde` **brillante** sobre fondo normal (bone/white/surface) =
  **3.32–3.62:1** (<AA texto normal). ~49 usos = montos de plata "positivos" (CartDrawer, CatalogoMovil,
  liquidación admin) + íconos. `verde-ink` daría 5.59:1. **Ojo:** los montos grandes/bold pasan a 3:1 (large
  text) → revisar caso por caso (no es mecánico). No entra en PR1 (scope: PR1 = chips de estado).
