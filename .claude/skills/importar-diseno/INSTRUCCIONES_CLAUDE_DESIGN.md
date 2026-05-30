# Instrucciones para Claude Design — formato de handoff de Rambla Rental

> **Para qué es este doc.** Es el **contrato de entrega**: define exactamente cómo Claude Design
> tiene que empaquetar un diseño para que el lado de Claude Code lo importe sin fricción con el
> skill [`importar-diseno`](./SKILL.md). Si seguís este formato, la implementación es directa.
>
> **Cómo usarlo:** pegale este documento entero a Claude Design al arrancar una pantalla/feature
> (o referencialo si ya lo tiene en su proyecto). Las reglas de abajo son obligatorias.

---

## Tu rol y tu entregable

Sos **Claude Design**: diseñás la UI, la maquetás en HTML y la traducís a un TSX que usa los
componentes y tokens reales del repo. Tu entregable es un **bundle**: **una carpeta por
pantalla/feature** con tres piezas, que el equipo deja caer en `docs/handoffs/<feature>/` del repo.

Quien recibe el bundle (Claude Code) **completa el borrador y conecta la lógica real**. Tu trabajo
es darle una especificación visual ejecutable + un borrador de implementación lo más cercano
posible a lo que ya existe en el repo.

## Estructura exacta del bundle

```
docs/handoffs/<feature-kebab>/
├── <Feature>.html        # referencia visual (1 pantalla, self-contained)
├── <Feature>.tsx         # borrador de implementación (la VERDAD del handoff)
├── HANDOFF.md            # specs + checklist de implementación
└── components/           # (opcional) sub-componentes TSX si la pantalla es grande
    └── <SubComponente>.tsx
```

- **Una carpeta = una pantalla/feature.** Nombre en `kebab-case` (ej. `portal-pedidos`,
  `catalogo-filtros`).
- Los archivos comparten el **mismo nombre base** en `PascalCase` (ej. `PortalPedidos.html` +
  `PortalPedidos.tsx`) para que el par HTML↔TSX sea evidente.
- Si hay varios sub-componentes, dividí el `.tsx` y poné los hijos en `components/`. Igual entregá
  **un** HTML que muestre la pantalla completa armada.

---

## 1. El HTML — referencia visual

Es la **maqueta que se mira**, no código de producción. Reglas:

- **Self-contained:** abre con doble click (`file://`). **Tailwind por CDN** + estilos inline.
  Nada de imports a `node_modules` ni build.
- **Datos mock realistas** (nombres, precios en formato local `$ 24.500`, fechas, estados reales
  del dominio — ver glosario abajo). No "lorem ipsum".
- **Una sola pantalla** por archivo, armada y completa (con sus estados visibles si aplica:
  vacío, error, cargando — podés mostrarlos apilados o anotados).
- **Responsive de verdad — mobile-first.** Tiene que verse bien **tanto en 375px (mobile) como en
  1280px (desktop)**. Nada de grillas de columnas fijas que no reflowean: usá
  `grid-template-columns: repeat(auto-fit, minmax(...))` o breakpoints. (El skill renderiza el HTML
  en **ambos** viewports y compara — un layout que se rompe en mobile se detecta enseguida.)
- **Refleja la intención visual** (jerarquía, espaciados, tokens de color/tipografía). Replicá los
  tokens del design system (ver `docs/DESIGN_SYSTEM.md` y `docs/design-kit/`).

> El HTML **puede quedar desfasado** del TSX y está bien: es aproximación. Pero hacé el esfuerzo
> de que sea fiel, porque es lo que se usa para *ver* la intención.

## 2. El TSX — borrador de implementación (la VERDAD)

Es tu entregable más importante: **si el HTML y el TSX difieren, gana el TSX**. Reglas:

- **Importá los componentes reales del repo**, no recrees primitivas:
  - UI base: `src/components/ui/*` — `button`, `card`, `dialog`, `alert`, `badge`, `input`,
    `dropdown-menu`, `accordion`, `calendar`, etc. (estilo shadcn).
  - Kit del catálogo: `src/components/kit/*` — `AddonPills`, `EstadoBadge`, `PriceBlock`,
    `StatCard`, `ViewToggle`, `EmptyState`, `Input`. Tipos en `kit/types.ts`.
  - **Tokens, nunca valores sueltos:** usá las clases/variables del design system (definidas en
    `src/styles.css` y documentadas en `docs/DESIGN_SYSTEM.md`). Nada de hex/px ad-hoc si ya hay
    token. Ej.: `text-destructive`, no `text-red-600`.
  - Si necesitás un componente que **no existe**, marcalo en el HANDOFF como "componente nuevo
    propuesto" — no lo des por hecho.
- **Marcá los dos tipos de hueco** para que Claude Code sepa qué hacer:
  - `// KEEP` — bloques/sub-componentes que hay que **traer tal cual** del HTML/diseño (markup que
    ya está bien, no reinventarlo).
  - `// TODO` — **dónde se conecta el dato/endpoint real**, con una nota de QUÉ dato va ahí.
    Ej.: `// TODO: pedidos del cliente — GET /api/cliente/pedidos (lista de Pedido)`.
- **No inventes data fetching.** Dejá los datos como **props tipadas** o un mock claramente
  marcado con `// TODO`. La conexión real (hooks, queries, stores) la hace Claude Code.
- **Tipá las props** (TypeScript real). Si el dominio ya tiene un tipo (`Pedido`, `Equipo`,
  `EstadoPedido`…), referencialo en el HANDOFF para que Claude Code lo importe del repo.
- **Mobile-first** también en el TSX (clases responsive de Tailwind).
- El TSX es un **componente** (no un archivo de ruta). Claude Code lo monta en la ruta que digas en
  el HANDOFF (las rutas viven en `src/routes/`, file-based de TanStack Router).

## 3. HANDOFF.md — specs + checklist

El contrato escrito. Incluí, como mínimo:

```markdown
# <Feature> — handoff

## Qué es
1-2 líneas: qué pantalla/feature es y para quién (catálogo público / portal cliente / admin).

## Dónde va
- Ruta destino en la app: ej. `/cliente/portal` (archivo `src/routes/cliente.portal.tsx`).
  Las rutas son file-based de TanStack Router; confirmá el archivo real con Claude Code.
- Componente principal: `<Feature>.tsx`.

## Datos / endpoints (los // TODO del TSX)
Por cada // TODO: qué dato es, de qué endpoint/store sale, y qué tipo del repo usar.
| Marca en el TSX | Dato | Fuente | Tipo |
|---|---|---|---|
| `// TODO: lista` | pedidos del cliente | `GET /api/cliente/pedidos` | `Pedido[]` |

## Estados
Vacío / cargando / error / con datos — cuáles aplican y cómo se ven (referencia al HTML).

## Componentes usados
- Del repo: `Button`, `EstadoBadge`, `PriceBlock`, …
- Nuevos propuestos (si los hay): nombre + por qué no alcanza con lo existente.

## Responsive
Cómo cambia mobile (375) vs desktop (1280): qué reflowea, qué se oculta, breakpoints.

## Checklist de implementación
- [ ] Montar `<Feature>.tsx` en la ruta `...`
- [ ] Traer bloques `// KEEP`
- [ ] Conectar cada `// TODO` con su endpoint/tipo real
- [ ] Verificar mobile + desktop contra el HTML de referencia
- [ ] (lo que aplique)
```

---

## Reglas de oro (resumen)

1. **El TSX manda.** El HTML es solo referencia visual; si difieren, gana el TSX.
2. **Componentes y tokens del repo**, no primitivas ni estilos ad-hoc. Consultá
   `docs/DESIGN_SYSTEM.md`.
3. **`// KEEP`** = traer tal cual · **`// TODO`** = conectar dato real (con nota de qué dato).
4. **Mobile-first y responsive real** — el handoff se revisa en 375px y 1280px.
5. **Una carpeta por pantalla**, los 3 archivos con el mismo nombre base.

## Glosario de dominio (para mocks realistas)

- **Estados de pedido** (los 9 reales, ver `src/components/kit/types.ts` → `EstadoPedido`):
  Borrador · Presupuesto · Solicitado · Confirmado · Retirado · Entregado · Devuelto · Finalizado ·
  Cancelado. (Ojo: el kit portable de `docs/design-kit/` muestra estados viejos como "Atrasado"/
  "Perdido" que **ya no existen** — `DESIGN_SYSTEM.md` y el tipo real mandan.)
- **Superficies:** catálogo público (`/`), portal cliente (`/cliente/*`), back-office admin
  (`/admin/*`).
- **Moneda:** formato local `$ 24.500`. **Período:** "por jornada" (día de alquiler).
- Equipos audiovisuales (cámaras, luces, audio, etc.), con add-ons (batería, cargador, tarjetas).

## Auto-QA antes de entregar

- [ ] La carpeta tiene HTML + TSX + HANDOFF.md con el mismo nombre base.
- [ ] El HTML abre solo (file://) y se ve bien en mobile **y** desktop.
- [ ] El TSX importa de `src/components/ui/*` y `src/components/kit/*`, sin primitivas recreadas.
- [ ] Todo dato real está marcado con `// TODO` + nota; nada de fetching inventado.
- [ ] Los `// KEEP` señalan los bloques a portar tal cual.
- [ ] El HANDOFF lista ruta destino, datos/endpoints, estados, componentes y checklist.
