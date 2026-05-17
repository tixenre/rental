import { cn } from "@/lib/utils";
import { useMemo, useState } from "react";
import { Search, LayoutGrid, ChevronRight } from "lucide-react";
import { CategoryIllustration } from "./illustrations/CategoryIllustration";
import { type Equipment, type Category, type CategoryRef } from "@/data/equipment";

const KNOWN_CATEGORIES: Category[] = [
  "Cámaras",
  "Lentes",
  "Iluminación",
  "Audio",
  "Soportes",
  "Accesorios",
  "Adaptadores",
  "Filtros",
];

/** Super-grupos visuales para el sidebar. Cada grupo es solo un header no
 *  clickeable arriba de sus roots — no filtran por sí mismos, son cosmética
 *  para asociar familias relacionadas (ej. todo lo de óptica junto). */
const CATEGORY_GROUPS: { name: string; children: Category[] }[] = [
  { name: "Óptica", children: ["Lentes", "Adaptadores", "Filtros"] },
];

/** Layout canónico del sidebar. Define el orden y los super-grupos. Roots
 *  que existen en la API pero no están acá caen al final como "extras"
 *  alfabéticos — así un admin que crea una root nueva la ve igual sin
 *  tener que tocar este archivo. */
type LayoutEntry =
  | { kind: "root"; name: Category }
  | { kind: "group"; name: string; children: Category[] };

const SIDEBAR_LAYOUT: LayoutEntry[] = [
  { kind: "root", name: "Cámaras" },
  { kind: "group", name: "Óptica", children: ["Lentes", "Adaptadores", "Filtros"] },
  { kind: "root", name: "Iluminación" },
  { kind: "root", name: "Audio" },
  { kind: "root", name: "Soportes" },
  { kind: "root", name: "Accesorios" },
];

export { CATEGORY_GROUPS };

type SubCat = { nombre: string; count: number };
type RootNode = { nombre: string; count: number; children: SubCat[] };

/** Construye el árbol root→sub a partir de la lista cruda de equipos. Para
 *  cada equipo, su lista `categorias` (vía M2M `equipo_categorias`) trae las
 *  refs con `parent_id`. Roots = parent_id null, subs = parent_id apuntando a
 *  un root. Los counts son #equipos donde aparece esa categoría. Equipos sin
 *  `categorias` (fallback inferido) entran solo como root por nombre. */
function buildTree(equipos: Equipment[]): RootNode[] {
  const rootById = new Map<number, string>();
  const subsByParent = new Map<number, Map<string, number>>();
  const rootCount = new Map<string, number>();
  const rootHasRef = new Set<string>();

  for (const eq of equipos) {
    const refs: CategoryRef[] = eq.categorias ?? [];

    // Equipos sin clasificación en backend: usar el `category` derivado por
    // inferencia (resolveCategory) como root virtual sin id.
    if (refs.length === 0) {
      const name = eq.category;
      rootCount.set(name, (rootCount.get(name) ?? 0) + 1);
      continue;
    }

    // Trackear qué roots y subs aparecen para este equipo, para no contarlo
    // dos veces si tiene múltiples refs bajo el mismo root.
    const seenRoots = new Set<string>();
    const seenSubs = new Set<string>(); // key: `${parent_id}::${nombre}`

    for (const r of refs) {
      if (r.parent_id == null) {
        rootById.set(r.id, r.nombre);
        rootHasRef.add(r.nombre);
        if (!seenRoots.has(r.nombre)) {
          seenRoots.add(r.nombre);
          rootCount.set(r.nombre, (rootCount.get(r.nombre) ?? 0) + 1);
        }
      } else {
        const key = `${r.parent_id}::${r.nombre}`;
        if (!seenSubs.has(key)) {
          seenSubs.add(key);
          let bucket = subsByParent.get(r.parent_id);
          if (!bucket) {
            bucket = new Map();
            subsByParent.set(r.parent_id, bucket);
          }
          bucket.set(r.nombre, (bucket.get(r.nombre) ?? 0) + 1);
        }
      }
    }

    // Un equipo asignado solo a una sub-cat también cuenta para su root.
    for (const r of refs) {
      if (r.parent_id != null) {
        const rootName = rootById.get(r.parent_id);
        if (rootName && !seenRoots.has(rootName)) {
          seenRoots.add(rootName);
          rootCount.set(rootName, (rootCount.get(rootName) ?? 0) + 1);
          rootHasRef.add(rootName);
        }
      }
    }
  }

  // Ensamblar. Orden: KNOWN_CATEGORIES primero, después extras alfabéticas.
  // (El layout final con super-grupos lo arma `renderLayout` abajo —
  // acá solo devolvemos una lista lineal de RootNodes ordenados.)
  const allRoots = Array.from(rootCount.keys());
  const known = KNOWN_CATEGORIES.filter((c) => rootCount.has(c));
  const extras = allRoots.filter((c) => !KNOWN_CATEGORIES.includes(c)).sort();
  const ordered = [...known, ...extras];

  // Mapa nombre→id para roots que sí tienen ref.
  const idByRootName = new Map<string, number>();
  for (const [id, name] of rootById) idByRootName.set(name, id);

  return ordered.map((rootName) => {
    const rootId = idByRootName.get(rootName);
    const childMap = rootId != null ? subsByParent.get(rootId) : undefined;
    const children: SubCat[] = childMap
      ? Array.from(childMap.entries())
          .map(([nombre, count]) => ({ nombre, count }))
          .sort((a, b) => a.nombre.localeCompare(b.nombre, "es"))
      : [];
    return {
      nombre: rootName,
      count: rootCount.get(rootName) ?? 0,
      children,
    };
  });
}

/** Aplica SIDEBAR_LAYOUT al árbol de roots. Cada root del tree se asigna a
 *  un slot del layout (root suelto o miembro de grupo). Roots que no aparecen
 *  en el layout caen al final como sección "extras". */
type RenderEntry =
  | { kind: "root"; node: RootNode }
  | { kind: "group"; name: string; nodes: RootNode[] };

function applyLayout(tree: RootNode[]): RenderEntry[] {
  const byName = new Map(tree.map((n) => [n.nombre, n]));
  const consumed = new Set<string>();
  const out: RenderEntry[] = [];

  for (const entry of SIDEBAR_LAYOUT) {
    if (entry.kind === "root") {
      const node = byName.get(entry.name);
      if (node) {
        out.push({ kind: "root", node });
        consumed.add(entry.name);
      }
    } else {
      const nodes = entry.children
        .map((c) => byName.get(c))
        .filter((n): n is RootNode => !!n);
      if (nodes.length > 0) {
        out.push({ kind: "group", name: entry.name, nodes });
        for (const n of nodes) consumed.add(n.nombre);
      }
    }
  }

  // Extras: roots presentes en la API que el layout no cubre. Van al final.
  const extras = tree.filter((n) => !consumed.has(n.nombre));
  for (const node of extras) out.push({ kind: "root", node });

  return out;
}

export function CategorySidebar({
  activeCategory,
  activeBrand,
  allEquipos,
  onCategory,
  onBrand,
}: {
  activeCategory: string;
  activeBrand: string | null;
  allEquipos: Equipment[];
  onCategory: (c: string) => void;
  onBrand: (b: string | null) => void;
}) {
  const [brandQuery, setBrandQuery] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const tree = useMemo(() => buildTree(allEquipos), [allEquipos]);
  const layout = useMemo(() => applyLayout(tree), [tree]);

  // Marcas derivadas de la data real de la API (filtrando nulls/vacíos)
  const brands = useMemo(
    () => Array.from(new Set(allEquipos.map((e) => e.brand).filter(Boolean))).sort(),
    [allEquipos],
  );

  const filteredBrands = brands.filter((b) =>
    (b ?? "").toLowerCase().includes(brandQuery.toLowerCase()),
  );

  // Una root está "activa" cuando el activeCategory coincide con su nombre o
  // con cualquiera de sus sub-cats — así el highlight viaja para arriba.
  const isRootActive = (n: RootNode) =>
    activeCategory === n.nombre || n.children.some((s) => s.nombre === activeCategory);

  const toggleExpanded = (rootName: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(rootName)) next.delete(rootName);
      else next.add(rootName);
      return next;
    });
  };

  return (
    <aside className="hidden lg:flex w-64 shrink-0 flex-col gap-8 border-r hairline px-6 py-8 sticky top-[68px] h-[calc(100vh-68px)] overflow-y-auto">
      <div>
        <div className="mb-4 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Categorías
        </div>
        <ul className="space-y-1">
          <li>
            <button
              onClick={() => onCategory("Todos")}
              className={cn(
                "group flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-sm transition",
                activeCategory === "Todos"
                  ? "bg-amber-soft text-ink"
                  : "text-foreground/80 hover:bg-surface hover:text-foreground",
              )}
            >
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-md text-foreground/40 group-hover:text-foreground/70">
                <LayoutGrid className="h-4 w-4" strokeWidth={2} />
              </span>
              <span className="font-display text-base flex-1 text-left">Todos</span>
              <span className="font-mono text-[10px] tabular text-muted-foreground">
                {allEquipos.length}
              </span>
            </button>
          </li>

          {layout.map((entry, idx) => {
            if (entry.kind === "root") {
              return (
                <RootItem
                  key={entry.node.nombre}
                  node={entry.node}
                  activeCategory={activeCategory}
                  isActive={isRootActive(entry.node)}
                  isOpen={expanded.has(entry.node.nombre) || isRootActive(entry.node)}
                  onCategory={onCategory}
                  onToggle={() => toggleExpanded(entry.node.nombre)}
                />
              );
            }
            return (
              <li key={`group-${entry.name}-${idx}`} className="pt-2">
                <div className="px-2 pb-1 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground/70">
                  {entry.name}
                </div>
                <ul className="space-y-1">
                  {entry.nodes.map((node) => (
                    <RootItem
                      key={node.nombre}
                      node={node}
                      activeCategory={activeCategory}
                      isActive={isRootActive(node)}
                      isOpen={expanded.has(node.nombre) || isRootActive(node)}
                      onCategory={onCategory}
                      onToggle={() => toggleExpanded(node.nombre)}
                    />
                  ))}
                </ul>
              </li>
            );
          })}
        </ul>
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Marcas
          </span>
          {activeBrand && (
            <button
              onClick={() => onBrand(null)}
              className="font-mono text-[10px] uppercase tracking-widest text-amber hover:underline"
            >
              limpiar
            </button>
          )}
        </div>
        <div className="relative mb-3">
          <Search className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" />
          <input
            value={brandQuery}
            onChange={(e) => setBrandQuery(e.target.value)}
            placeholder="Buscar marca…"
            className="w-full rounded-md border hairline bg-surface py-1.5 pl-7 pr-2 text-xs placeholder:text-muted-foreground focus:border-amber/40 focus:outline-none"
          />
        </div>
        <ul className="space-y-0.5">
          {filteredBrands.map((b) => {
            const active = activeBrand === b;
            return (
              <li key={b}>
                <button
                  onClick={() => onBrand(active ? null : b)}
                  className={cn(
                    "block w-full text-left text-sm transition py-1 px-2 rounded",
                    active
                      ? "text-amber"
                      : "text-foreground/70 hover:text-foreground",
                  )}
                >
                  {b}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
}

function RootItem({
  node,
  activeCategory,
  isActive,
  isOpen,
  onCategory,
  onToggle,
}: {
  node: RootNode;
  activeCategory: string;
  isActive: boolean;
  isOpen: boolean;
  onCategory: (c: string) => void;
  onToggle: () => void;
}) {
  const hasChildren = node.children.length > 0;
  return (
    <li>
      <div className="flex items-stretch">
        <button
          onClick={() => onCategory(node.nombre)}
          className={cn(
            "group flex flex-1 items-center gap-3 rounded-md px-2 py-1.5 text-sm transition",
            isActive
              ? "bg-amber-soft text-ink"
              : "text-foreground/80 hover:bg-surface hover:text-foreground",
          )}
        >
          <span
            className={cn(
              "grid h-7 w-7 shrink-0 place-items-center rounded-md transition",
              isActive ? "text-ink" : "text-foreground/40 group-hover:text-foreground/70",
            )}
          >
            <CategoryIllustration
              category={
                KNOWN_CATEGORIES.includes(node.nombre as Category)
                  ? (node.nombre as Category)
                  : "Accesorios"
              }
              className="h-6 w-6"
            />
          </span>
          <span className="font-display text-base flex-1 text-left">{node.nombre}</span>
          <span className="font-mono text-[10px] tabular text-muted-foreground">
            {node.count}
          </span>
        </button>
        {hasChildren && (
          <button
            onClick={onToggle}
            aria-label={isOpen ? "Colapsar" : "Expandir"}
            className="ml-1 grid w-6 shrink-0 place-items-center rounded-md text-foreground/40 hover:bg-surface hover:text-foreground/80"
          >
            <ChevronRight
              className={cn("h-3.5 w-3.5 transition-transform", isOpen && "rotate-90")}
            />
          </button>
        )}
      </div>

      {hasChildren && isOpen && (
        <ul className="mt-0.5 mb-1 ml-9 space-y-0.5 border-l hairline pl-2">
          {node.children.map((sub) => {
            const subActive = activeCategory === sub.nombre;
            return (
              <li key={sub.nombre}>
                <button
                  onClick={() => onCategory(sub.nombre)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs transition",
                    subActive ? "text-amber" : "text-foreground/70 hover:text-foreground",
                  )}
                >
                  <span className="flex-1 text-left">{sub.nombre}</span>
                  <span className="font-mono text-[10px] tabular text-muted-foreground">
                    {sub.count}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </li>
  );
}
