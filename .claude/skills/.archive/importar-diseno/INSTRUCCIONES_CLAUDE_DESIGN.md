# Contrato Claude Design ↔ Claude Code — Rambla Rental

> **Fuente de verdad de este flujo.** Vive en el repo `tixenre/rental` y se versiona acá. El dueño lo
> **sincroniza al proyecto de Claude Design** cuando cambia (Claude Design puede reemplazar con esto su
> `CLAUDE_DESIGN_PROTOCOL.md`). Lado Claude Code: el skill [`SKILL.md`](./SKILL.md) lo consume; el molde
> técnico para implementar está en [`referencia-repo.md`](./referencia-repo.md).

Define cómo Claude Design empaqueta un diseño para que Claude Code lo implemente **sin desincronización
y sin duplicar** componentes, tokens, fuentes ni reglas. Resumen del flujo:

```
Claude Design (diseño)  →  handoff slim  →  Claude Code (implementación en el repo)
   "¿cómo debería verse?"                      "así lo construyo, reusando la librería"
```

---

## Regla de verdad (una sola, por plano)

- **El HTML manda para la fidelidad visual** — cómo se ve (layout, jerarquía, espaciados, estados, mobile).
- **El TSX manda para estructura / lógica / implementación** — cómo se construye (componentes y tokens
  del repo, props, comportamiento).

No se contradicen: son planos distintos. El markup del HTML es Tailwind CDN + mocks → **no se copia** a
producción; se traduce a los componentes/tokens reales del repo.

---

## Fase 1 — Leer el repo antes de diseñar

Antes de trazar un píxel, explorar `tixenre/rental` (con GitHub MCP):

- **La librería del design system** vive EN LA APP, en `src/`: la **fuente canónica** de tokens,
  primitivos y piezas reusables. Es lo que tenés que reusar. Mirá:
  - `src/components/{ui,kit,rental}/` → qué piezas existen (primitivos shadcn + piezas de marca).
  - `src/design-system/styles/tokens/*` → **tokens canónicos** (colores, tipografía, sombras, motion); entry
    `src/design-system/ds-styles.css`, cableado desde `src/styles.css`.
  - `docs/DESIGN_SYSTEM.md` → el design system en prosa (voz, patterns, reglas).
  - Referencia visual: renderizá la app real con `render.mjs` (rutas) / `render-doc.py` (PDFs).
- `src/routes/` → ¿la ruta existe? Si existe, el diseño es un **patch**, no una pantalla nueva.
- `src/components/*` → cómo la app **usa hoy** esas piezas. Útil para ver props/uso reales.
- `backend/routes/` → qué endpoints existen antes de diseñar flujos con datos.

---

## Fase 2 — Diseñar pensando en el backend y en la librería

### Reuse-first (innegociable)

- **Reusar antes que crear.** Si el primitivo ya existe en el repo (`Button`, `EstadoBadge`,
  `StatCard`, `PriceBlock`, `StepperPill`, `FavButton`, `formatARS()`, `cn()`…) → usarlo.
- Si el diseño necesita un primitivo **nuevo reutilizable** → diseñarlo como **componente de librería**
  (no inline en la página) y documentarlo en el README del handoff.

### Datos

- Usar solo campos que **ya existen** en los tipos del repo.
- Si falta un dato/endpoint → marcar `TODO:` en el TSX y documentarlo en el README, indicando si es
  **lectura simple** (Claude Code lo crea full-stack) o **sensible** (migración de schema, escritura de
  pagos/estados/permisos, o disponibilidad/reservas) → en ese caso **el diseño se entrega marcado para
  PARAR y validar**, no se asume.

### Máquina de estados / flujos (si la pantalla tiene)

- Si el diseño tiene una máquina de estados (ej. estados de pedido), **copiá las reglas REALES del
  backend**: leé `ESTADOS_VALIDOS` + las precondiciones en `backend/routes/*.py` y espejalas. **No
  inventes un grafo de transiciones.** El backend valida _estado-válido + precondición_ (no un grafo);
  un grafo inventado queda **más restrictivo** y desorienta al implementar (caso testigo: Pedidos).
- Diseñá el **flujo feliz** —qué avance ofrecer en cada estado, qué deshabilitar y por qué
  (`blockReason`)— y dejá explícito en el README que **la validación de transiciones la dueña es el
  backend**, no la UI.

### Tokens / tipografía / copy (reglas duras del repo)

- **Solo tokens del sistema**, nunca hex (`bg-amber`, `text-ink`, `border-hairline`, …). El guardrail
  ESLint rompe el CI con colores fuera del sistema.
- **Champ Black (`font-display`) solo display/wordmark** — nunca UI funcional, IDs, labels, precios.
  Precios/IDs/fechas/eyebrows en `font-mono`; body/UI en `font-sans`.
- Precios vía `formatARS()` (nunca `.toLocaleString()`). Iconos `lucide-react` import individual.
  `dvh` no `vh` + `.safe-*` en sticky bars. Targets táctiles ≥ 44px. Voz **"vos"** (reservá, elegí,
  confirmá). Precios `$ 24.500`. Fechas `lun 2 jun.`.
- **Mapeá cada elemento a su token/fuente exactos en el README** — no solo "la paleta general". Una
  mini-tabla elemento→token: "fila seleccionada = `bg-amber-soft`", "total = `font-mono`", "nombre del
  cliente = `font-bold`", "eyebrow = `font-mono text-muted-foreground`". Claude Code traduce tu
  `proto.css` a tokens del repo **a partir de ese mapa**; sin él lo infiere a ojo y se cuelan sutilezas
  (caso testigo: una ronda entera de pulido de fidelidad en Pedidos por tokens no explicitados).

---

## Fase 3 — Exportar: handoff **slim**

Una carpeta por feature. **Solo el diseño** — el repo ya tiene reglas, tokens, fuentes y componentes.

```
design_handoff_<feature>/
├── <Feature>.html          ← referencia visual (interactiva, todos los estados) · import-time
├── assets/                 ← (opcional) render-deps del .html: fuentes, proto.css · import-time, NO se commitea
├── src/<path-real>.tsx     ← TSX base; espeja el path real del repo (file-based: una ruta = un archivo)
│                              (varios .tsx si es módulo de componentes)
└── README.md               ← qué es · secciones + mapa elemento→token · componentes a reusar (tabla)
                              · datos/TODO (tabla: marca → dato → endpoint → tipo) · máquina de estados
                              (reglas del backend) · checklist
```

> **Durable vs import-time:** lo que se commitea al repo y queda como registro = `README` + `src/`
> scaffolds (+ `proto/*` si los hay). El `.html` + `assets/` son **solo para rasterizar durante el
> import** — no se commitean (ver "Peso muerto vs. dependencias de render").

`MASTER_HANDOFF.md` (orden de implementación + dependencias entre handoffs) va **una sola vez** en el
root del export cuando se manda más de un handoff.

### Entrega — cómo el handoff llega a Claude Code (clave)

El **link del visor** de Claude Design (`api.anthropic.com/v1/design/h/...`) **NO es fetcheable** por la
sesión de Claude Code que implementa: está atado a la sesión del browser del dueño → da **404**
server-side. El handoff se entrega **como archivos en el repo**, no como URL:

1. El dueño **exporta/descarga** la carpeta `design_handoff_<feature>/` desde Claude Design.
2. La **deja en el repo** del lado de Claude Code, en `docs/handoffs/<feature>/` (puede acortar el
   nombre), y la commitea/pushea (o la sube a la sesión).
3. Le pasa a Claude Code la ruta: `/importar-diseno docs/handoffs/<feature>/`.

Claude Code rasteriza el `.html` (desktop + mobile), lee el README + los `.tsx`, e implementa reusando
la librería. **Pegar solo la URL del visor no alcanza** — los archivos tienen que aterrizar en el repo.

### Tipos de handoff

- **Ruta nueva:** `src/routes/<ruta>.tsx` completo, con todos los `TODO:` marcados. **Espejá el patrón de
  ruteo del repo: file-based (TanStack Router), una ruta = un archivo.** Una vista master/detail que en
  realidad son dos rutas (lista + detalle/`$id`) se entrega como **dos archivos de ruta**, no como un
  componente monolítico con ruteo interno por estado (caso testigo: Pedidos vino monolítico y hubo que
  partirlo).
- **Patch:** comentarios `// CAMBIO N:` con el diff exacto sobre el archivo existente (no reemplaza la
  lógica).
- **Módulo:** `src/components/<path>/` con los `.tsx` + README **clase-por-clase** (mapa de tokens,
  anatomía por componente, tabla de errores comunes, checklist de 15-20 ítems).

### Peso muerto vs. dependencias de render (la distinción que importa)

La regla es por **intención**: ¿esto está acá para que Claude Code **lea reglas/tokens** de ahí, o solo
para que el **`.html` renderice**?

- ❌ **Como fuente de verdad** (drift): NO mandar reglas del repo duplicadas (`HANDOFF.md`/`CONTEXT.md`
  por carpeta), NI snapshots de tokens (`colors_and_type.css`, `CLAUDE_DESIGN_SYSTEM.md`), NI el `kit/`,
  NI `preview/`, HTML duplicados del root, screenshots. Los tokens/reglas canónicos viven en
  `src/design-system/styles/tokens/*` + `docs/DESIGN_SYSTEM.md` — Claude Code los lee de ahí, **nunca del bundle**.
- ✅ **Como dependencia de render del `.html`** (fuentes vendoreadas, `proto.css`): pueden viajar en el
  bundle bajo `assets/` si el `.html` las necesita para verse bien — pero son **import-time**: Claude
  Code rasteriza con ellas y **NO las commitea al repo** (pesan y son fuentes licenciadas, ~1 MB). Lo
  durable que se commitea es `README` + `proto/*` + scaffolds `src/`.
- Objetivo: que la **señal de implementación** (README + proto + scaffolds) sea **<1 MB / decenas de
  archivos**. Las fuentes pesadas son render-deps, no señal.

---

## Marcadores

- **`TODO:`** → dónde conectar el dato/endpoint real (con nota de QUÉ dato y de qué endpoint).
- **`// CAMBIO N:`** → en un patch, el diff puntual a aplicar.

## Checklist pre-handoff

- [ ] Leí la librería del DS (`src/components/` + `src/design-system/styles/`; render visual con `render.mjs`) y el código de la ruta/componente existente (si existe).
- [ ] Apliqué reuse-first: identifiqué qué componentes del repo reuso; los nuevos son de librería.
- [ ] Verifiqué que los datos ya los da la API; marqué `TODO:` lo que falta (lectura simple vs sensible).
- [ ] Si hay máquina de estados, espeja las reglas **reales** del backend (`ESTADOS_VALIDOS` + precondiciones), sin inventar un grafo.
- [ ] El HTML está completo (todos los estados) y se ve bien en **mobile (375) y desktop**.
- [ ] El README mapea **elemento → token/fuente exactos** (no solo la paleta general).
- [ ] El README tiene tabla de componentes a reusar + tabla de datos/TODO + checklist.
- [ ] Las rutas nuevas espejan el **ruteo file-based** del repo (una ruta = un archivo), no un componente monolítico.
- [ ] **NO embarqué como fuente de verdad** reglas del repo (`HANDOFF`/`CONTEXT`), snapshots de tokens (`colors_and_type.css`, `kit`), `preview` ni screenshots. (Fuentes/`proto.css` del `.html` van en `assets/` solo como render-deps.)
- [ ] grep en los `.tsx`: `font-display` solo en display/wordmark · `toLocaleString` → 0 · hex → 0.
