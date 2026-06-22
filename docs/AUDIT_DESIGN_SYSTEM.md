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

**Arquitectura (fortaleza):** tokens modulares en `frontend/src/styles/tokens/*` (colors/typography/
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
