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
- `src/routes/` → ¿la ruta existe? Si existe, el diseño es un **patch**, no una pantalla nueva.
- `src/components/` (`ui/`, `kit/`, `rental/`, `rental/equipment/shared/`) → **qué reusar** (ver
  abajo: reuse-first).
- `docs/DESIGN_SYSTEM.md` y `src/styles.css` → tokens canónicos (la **verdad** de tokens vive acá).
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

### Tokens / tipografía / copy (reglas duras del repo)
- **Solo tokens del sistema**, nunca hex (`bg-amber`, `text-ink`, `border-hairline`, …). El guardrail
  ESLint rompe el CI con colores fuera del sistema.
- **Champ Black (`font-display`) solo display/wordmark** — nunca UI funcional, IDs, labels, precios.
  Precios/IDs/fechas/eyebrows en `font-mono`; body/UI en `font-sans`.
- Precios vía `formatARS()` (nunca `.toLocaleString()`). Iconos `lucide-react` import individual.
  `dvh` no `vh` + `.safe-*` en sticky bars. Targets táctiles ≥ 44px. Voz **"vos"** (reservá, elegí,
  confirmá). Precios `$ 24.500`. Fechas `lun 2 jun.`.

---

## Fase 3 — Exportar: handoff **slim**

Una carpeta por feature. **Solo el diseño** — el repo ya tiene reglas, tokens, fuentes y componentes.

```
design_handoff_<feature>/
├── <Feature>.html          ← referencia visual (interactiva, todos los estados)
├── src/<path-real>.tsx     ← TSX base; espeja el path real del repo
│                              (varios .tsx si es módulo de componentes)
└── README.md               ← qué es · secciones+tokens · componentes a reusar (tabla)
                              · datos/TODO (tabla: marca → dato → endpoint → tipo) · checklist
```

`MASTER_HANDOFF.md` (orden de implementación + dependencias entre handoffs) va **una sola vez** en el
root del export cuando se manda más de un handoff.

### Tipos de handoff
- **Ruta nueva:** `src/routes/<ruta>.tsx` completo, con todos los `TODO:` marcados.
- **Patch:** comentarios `// CAMBIO N:` con el diff exacto sobre el archivo existente (no reemplaza la
  lógica).
- **Módulo:** `src/components/<path>/` con los `.tsx` + README **clase-por-clase** (mapa de tokens,
  anatomía por componente, tabla de errores comunes, checklist de 15-20 ítems).

### NO embarcar (peso muerto / fuente de drift)
- ❌ Reglas del repo duplicadas: **no** copiar `HANDOFF.md`/`CONTEXT.md` por carpeta — viven en el repo.
- ❌ Snapshots de tokens: **no** mandar `colors_and_type.css` ni `CLAUDE_DESIGN_SYSTEM.md` — Claude Code
  lee `src/styles.css` / `docs/DESIGN_SYSTEM.md` del repo.
- ❌ `fonts/`, `assets/`, `kit/`, `preview/`, HTML duplicados del root, screenshots.
- Objetivo: un export de **<1 MB / decenas de archivos**, no cientos de MB.

---

## Marcadores

- **`TODO:`** → dónde conectar el dato/endpoint real (con nota de QUÉ dato y de qué endpoint).
- **`// CAMBIO N:`** → en un patch, el diff puntual a aplicar.

## Checklist pre-handoff
- [ ] Leí el código de la ruta/componente existente (si existe) y `src/styles.css`.
- [ ] Apliqué reuse-first: identifiqué qué componentes del repo reuso; los nuevos son de librería.
- [ ] Verifiqué que los datos ya los da la API; marqué `TODO:` lo que falta (lectura simple vs sensible).
- [ ] El HTML está completo (todos los estados) y se ve bien en **mobile (375) y desktop**.
- [ ] El README tiene tabla de componentes a reusar + tabla de datos/TODO + checklist.
- [ ] **NO embarqué** reglas del repo, snapshots de tokens, fuentes, assets, kit ni preview.
- [ ] grep en los `.tsx`: `font-display` solo en display/wordmark · `toLocaleString` → 0 · hex → 0.
