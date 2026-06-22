# Auditoría UI multi-viewport — flujo de reserva (cliente)

> Tocar cada botón en muchos tamaños, ver si andan / son legibles / se lee el texto.
> Método: viewport exacto vía preview headless + medición de CSS computado
> (`getBoundingClientRect` para tap targets, `getComputedStyle` para font-size,
> `inspect` para contraste real) + screenshots + clicks reales. Datos reales (clon
> staging), cuenta verificada. Complementa `AUDIT_RESERVA_EDGE_CASES.md` (backend).
>
> **Gotcha de render:** en **mobile** la página scrollea en un **contenedor interno**
> (`div.flex-1.overflow-y-auto`), NO el document → `window.scrollTo` es no-op; hay que
> scrollear ese div. En **desktop** scrollea el document. (Por eso los screenshots
> headless salían en blanco antes.)
>
> Viewports: 320 · 360 · 375 · 414 · 640 · 768 · 1024 · 1280 · 1440 · 1920.
> Reglas: tap target ≥44×44 (HIG) · inputs ≥16px (anti-zoom iOS) · contraste AA 4.5:1
> (3:1 texto grande) · sin scroll horizontal · sin texto cortado ilegible.
> Sev: 🔴 roto/ilegible · 🟡 fricción · 🟢 menor · ✅ ok.

---

## Landing `/rental`

### Hallazgos (medición CSS)
| # | viewport | qué | medición | sev |
|---|----------|-----|----------|-----|
| L1 | todos | **Input de búsqueda font-size 14px** | <16px → iOS Safari hace zoom al enfocar | 🟡 |
| L2 | todos | **Botón favorito (corazón) tap target 22×22px** | <44×44 (verificar si hay hit-area por pseudo) | 🟡 |
| L3 | todos | Logo (R) tap target 40×40px | <44, menor | 🟢 |
| L4 | 375 | sin scroll horizontal (`hScroll:false`) | ✅ | ✅ |

### Layout / render
- ✅ **Sin scroll horizontal** en 320/360/375 (hero + catálogo). El hero (display gigante "con rambla, en mardel.") entra y se lee bien hasta 320.
- ✅ Hamburguesa (44px) abre nav full: cards rental/estudio/workshops (72px, hrefs OK `/rental`,`/estudio`,`/workshops`) + Inicio/Mis pedidos/Mi perfil/Salir + WhatsApp/FAQ/Términos (hrefs OK).
- 🟡 **Filas del menú nav = 40px** de alto (<44). Card "estudio" subtítulo blanco sobre naranja = **3.62:1** (falla AA 4.5). X de cerrar = 16px.

## Modal de fechas
- ✅ A 320 se adapta: muestra **1 mes** (no 2 lado a lado), no hay overflow, se lee.
- 🟡 **Celdas del calendario = 32×32px** (<44, apretado para tocar una fecha en mobile).
- 🟡 Selects de hora **font 14px** (<16); footer **Aplicar 40px / Limpiar 32px** (<44); flechas de mes ~32px.
- 🟡 Copy confuso en retiro/devolución mismo día: *"Devolvé a las 11:00 o antes para mantener 0 jornadas"* — pero el mínimo del sistema es 1 jornada → "0 jornadas" no debería existir.

## Catálogo (mobile)
- ✅ Lista full-width renderiza bien; tabs de categoría scrollean horizontal (intencional).
- 🟡 **Nombres se truncan** ("Anton/Bauer Kit Baterías V-...", "Zapatilla Eléctrica...") — no se lee el nombre completo sin expandir.
- 🟡 **Corazón de favorito 22×22px** (<<44).
- 🟡 Marca duplicada en nombres ("amaran Amaran 300C 300c") — dato, ya en #965.

## Carrito (mobile)
- 🔴 **Mini-bar muestra el total SIN descuento** (re-confirmado visual a 375: bar dice `$168.600` pero con el 50% de Tincho son ~$84.300). Ya en #965.
- (Drawer del carrito auditado en la 1ª pasada: CTA "Solicitar rental" vs desktop "Confirmar solicitud", línea "Depósito: A definir" sólo mobile, descuento por-línea distinto a portal.)

## 🔑 Hallazgo SISTÉMICO — tap targets < 44px (contra la propia regla del DS)
La MEMORIA 2026-06-05 manda **≥44×44** (`h-11 w-11`). En la práctica muchos controles quedan por debajo:
corazón favorito **22**, celdas calendario **32**, flechas de mes **32**, X cerrar **16**, logo **40**,
filas de menú **40**, Aplicar/footer **40**, selects de hora 80×44 pero **font 14px**, input de búsqueda **14px**.
→ Revisar como **pasada transversal** (no caso por caso): muchos por 4-12px. Algunos pueden tener hit-area por
pseudo-elemento (ej. el stepper usa `::before` 44px sobre botón visual 34px) → **verificar hit-area real** antes de cambiar visual.

## Resultados del harness Playwright (matriz completa 8 rutas × 10 viewports)
Corrido con `node ../.claude/skills/auditoria-profunda/ui-audit.mjs` (Chrome real). 80 screenshots
en `docs/audit-ui-screenshots/full/` + `_report.json`. Rutas: /rental, /equipo/$slug, /estudio,
/cliente/portal, /cliente/login, /preguntas-frecuentes, /terminos, /privacidad.

- ✅ **CERO scroll horizontal y CERO overflow de elementos** en TODAS las rutas a TODO ancho (320→1920).
  El layout responsive es **robusto** — no se rompe en ningún tamaño. (Gran positivo.)
- 🔑 🟡 **SISTÉMICO — tap targets <44 en TODAS las páginas** (la propia regla del DS es 44). Foco: el **FOOTER**
  (en cada página): WhatsApp 28, Catálogo **14**, Estudio/Talleres/FAQ/Instagram 16, Privacidad/Términos **15**,
  dirección/mail 17, teléfono/handles 20, "Consultanos por WhatsApp" 36. Header: logo 28, "Elegir fechas" 38,
  "Carrito" 36. Catálogo desktop: dots de carrusel **6×6**, flechas 32, "Ver sólo X" **15** (font **10**), compartir 22,
  corazón 22. Modales: "Close" 16. Portal: tabs 40, "Todos/Activos/Historial" 30, "Ver pedido" 32, "Entendido" 36.
- 🟡 **Fonts chicos**: footer Privacidad/Términos **10px**, "Ver sólo X" **10px**, search 13-14px, selects de hora 14px.
- 🟡 **Contraste** (verificar a mano, parser no mide sobre imagen): "Grid" toggle **1.66:1**; "Conocé el estudio" 1.06 = texto sobre foto.
- 🟡 **Truncación + marca duplicada** en nombres ("Avenger Avenger A2030D", "DJI Sistema… DJI").

> El harness es **re-ejecutable** (`LABEL=before` / `LABEL=after`) → screenshots comparables antes/después del fix.

## WEB COMPLETA — 14 pantallas × 10 viewports (`docs/audit-ui-screenshots/full-site/`)
Hub · rental-grid · rental-list · estudio · workshops · talleres · equipo-detail · login · registro · portal · perfil · faq · terminos · privacidad. Evidencia: 140 PNG `<pantalla>__<viewport>.png` + `_INDEX.md` (mapa screenshot→flags).

- ✅ **Layout sólido en TODA la web**: cero scroll horizontal / overflow en las 140 combinaciones (320→1920). `hub /` = 0 issues. `login`/`registro` (deslogueado) = limpias.
- 🔑 **Footer = fix de mayor palanca** (chrome compartido, en TODAS las páginas): links 14-20px + fonts 10px (WhatsApp, Catálogo, Estudio, Talleres, FAQ, Instagram, Privacidad/Términos, dirección, teléfono, mail, handles). Header idem (logo 28, "Elegir fechas" 38, "Carrito" 36).
- **Propios por pantalla:**
  - `rental-grid`: dots carrusel **6×6**, play/pause 20, "Ver sólo X" **10px**, search 14px, contraste toggle 1.66.
  - `rental-list`: + "Ocultar" **9px**, "Ver ficha completa" 10px.
  - `perfil`: **inputs del form 14px** (dirección/CUIL/teléfono → zoom iOS), selector fiscal 34px, "Mis pedidos" 10px.
  - `estudio` (reserva): steppers de hora **36×36**, "Reservar" 40, select de horas 14px.
  - `equipo-detail`: CTA **"Agregar" 40**, pills categoría 10px, "Volver al catálogo" 16.
  - `portal`: tabs 30-40, "Ver pedido" 32, "Entendido" 36, search 13px, "Close" 16.
  - `faq/terminos/privacidad/workshops/talleres`: sólo chrome (+ "Volver al catálogo" / WhatsApp).
- Método: `login`/`registro` redirigen al portal si hay sesión → se auditan con `NOLOGIN=1`. El harness **mergea** corridas del mismo LABEL (subsets no pisan el resto).

## BACK-OFFICE `/admin/*` — 30 pantallas × 10 viewports (`GROUP=admin`, screenshots en `admin/`)
310 capturas, 0 errores. Auth: sesión del dueño (is_admin=true). Detalle en **issue #968**.
- ✅ **Prioritario mobile OK**: `/admin/pedidos` (lista de cards) y `/admin` (dashboard) usables en celu; sin scroll horizontal de página en ninguna.
- 🟡 **Desktop-first → rompe responsive**: overflow de controles en `admin-equipos` (toolbar a 320-768), `admin-pedido-detalle` (acciones a **1024**), `admin-equipos-calidad`/`admin-email-templates` (a 320).
- 🟡 **Contraste < AA real**: números de pago `#395/#371` a **1.73:1** (admin-pagos / conta-movimientos), botones destructivos ~3.8 (Eliminar/Cancelar pedido, Borrar clientes).
- 🟡 Tap targets <44 densos en todas (26-41/pantalla); sidebar nav = chrome compartido.
> Prioridad sugerida: contraste de pagos (legibilidad aun en desktop) + responsive de equipos/pedido-detalle.

## Estados interactivos (harness `ui-states.mjs`, screenshots en `states/`)
Modal de fechas · sheet de filtros/marca · carrito abierto · card expandida · pedido del portal. Nuevos:
- 🟡 **Sheet "Marca": TODAS las marcas dicen "DESTACADA"** (RED/Sony/Aputure/Carl Zeiss/Avenger/Canon/Arri/DJI…) → label sin sentido; revisar dato/render.
- 🟡 **Popup "documentos nuevos disponibles" abruma**: en sesión nueva lista TODOS los contratos/albaranes históricos (decenas de filas), intercepta la carga del portal ("visto" = localStorage → device nuevo = todo nuevo).
- ✅ **Carrito (drawer) muestra el total CON descuento correcto** ($168.600 → −50% → $84.300) → confirma que el bug es **sólo del mini-bar** (muestra bruto).
- 🟡 Detalle de equipo: brand-dup en título ("Avenger Avenger A2030D"), tag "A2016D" en un A2030D (dato).

## Estados de error / vacío / dinámicos (`ui-edge.mjs`, screenshots en `edge/`)
Forzados con route-interception de Playwright (sin tocar el backend):
- 🔴/🟡 **Catálogo en BLANCO si `/api/equipos` 500 o `{items:[]}`** — DOM vacío (sin header/hero/mensaje), 375 y 1280. No dispara `isError` (rental.tsx:698) ni RootErrorBoundary. La búsqueda client-side vacía SÍ muestra "Sin resultados" → el gap es el error/vacío **de servidor**. (Síntoma verificado por DOM; mecanismo a confirmar en el fix — alto impacto si pasa en prod.)
- 🟡 **Onboarding 1ª visita** "¿Cómo querés ver el catálogo? (Grilla/Lista)" — intersticial antes de navegar. + popup "documentos nuevos" → pueden encadenarse.
- ✅ **Portal vacío**: "Sin pedidos aún · Explorar catálogo". **Verificación**: banner portal + panel carrito presentes/claros.

## ✅ Verify-before-report (falsas alarmas evitadas)
- "Equipo no encontrado" en `/equipo/<slug>` → **NO es bug**: la ruta fetchea por **id** (espera `/equipo/<slug>-<id>` o `/equipo/<id>`); un slug crudo sin id da "no encontrado" (correcto). Era el harness usando mal el slug → corregido a `/equipo/213`.
- Contraste automático "1.06/1.08" → falsos (texto sobre imagen / parser). Se mide con canvas y se saltea sobre-imagen; igual marcar a mano los dudosos.

## ⚠️ Nota de método (tooling)
- **Mobile (≤414):** el preview headless renderiza y mide perfecto (viewport exacto 320/375).
- **Desktop (≥768) screenshots:** el headless devuelve **crema/blanco** aunque el contenido esté en el DOM
  (reveal `whileInView` + compositor headless) → **las capturas visuales de desktop necesitan Chrome real**
  (que sí renderizó bien en la 1ª pasada). Las **mediciones** (overflow/tap/font) sí son fiables headless a todo ancho.
- Algunos controles son `div` con `onClick` (no `<button>`) → click real (Chrome) los abre; eval/headless es inconsistente.
- **Contraste automático no confiable** (colores oklch de Tailwind v4 rompen el parser rgb) → medir con `inspect` puntual o a ojo.
