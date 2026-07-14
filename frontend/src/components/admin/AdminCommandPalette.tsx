import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Search, CornerDownLeft, ClipboardList, type LucideIcon } from "lucide-react";

import { Dialog, DialogContent, DialogTitle } from "@/design-system/ui/dialog";
import { cn } from "@/lib/utils";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { adminApi, ESTADO_LABEL } from "@/lib/admin/api";
import { ADMIN_ROUTES } from "./adminNav";

/**
 * AdminCommandPalette — buscador global del back-office (⌘F / Ctrl+F).
 *
 * Indexa TODAS las rutas del admin desde `adminNav` (fuente única) Y busca
 * PEDIDOS en vivo (por nº o cliente) contra el mismo endpoint del listado
 * (`adminApi.listPedidos`, que ya usa el motor único de búsqueda + match por
 * número). Sin dependencia nueva: Dialog del DS + navegación por teclado
 * (↑↓ Enter Esc), el mismo patrón de los demás buscadores del repo.
 *
 * Se abre con ⌘F/Ctrl+F o despachando el evento `admin:cmdk` desde cualquier
 * botón (sidebar / header mobile) — así los triggers no necesitan prop-drilling.
 */

/** Normaliza para matchear sin tildes ni mayúsculas. */
const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

/** Ítem unificado de resultado: una ruta del admin o un pedido concreto. */
type Item = {
  key: string;
  url: string;
  title: string;
  group: string;
  Icon: LucideIcon;
  /** Texto secundario, muted (estado del pedido). */
  sub?: string;
};

export function AdminCommandPalette() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  // Abrir con ⌘F/Ctrl+F o con el evento custom de los triggers visibles.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "f") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    const onEvent = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("admin:cmdk", onEvent);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("admin:cmdk", onEvent);
    };
  }, []);

  // Reset al abrir/cerrar.
  useEffect(() => {
    if (!open) {
      setQ("");
      setActive(0);
    }
  }, [open]);

  const needle = norm(q.trim());

  // Pedidos en vivo: mismo endpoint que el listado; el backend matchea nombre
  // (motor único) + número de pedido. Debounced; solo con la paleta abierta y
  // ≥2 caracteres (evita disparar en cada tecla / con ruido de 1 letra).
  const debouncedQ = useDebouncedValue(q.trim(), 220);
  const pedidosQ = useQuery({
    queryKey: ["admin", "cmdk-pedidos", debouncedQ],
    queryFn: () => adminApi.listPedidos({ q: debouncedQ, per_page: 6 }),
    enabled: open && debouncedQ.length >= 2,
    staleTime: 15_000,
  });

  const matches = useMemo<Item[]>(() => {
    const routeItems: Item[] = (
      needle
        ? ADMIN_ROUTES.filter((r) => norm(`${r.group} ${r.title}`).includes(needle))
        : ADMIN_ROUTES
    ).map((r) => ({
      key: `route:${r.url}`,
      url: r.url,
      title: r.title,
      group: r.group,
      Icon: r.icon,
    }));

    // Sin query → solo el índice de rutas (comportamiento de siempre).
    if (!needle) return routeItems;

    const pedidoItems: Item[] = (pedidosQ.data?.items ?? []).map((p) => ({
      key: `pedido:${p.id}`,
      url: `/admin/pedidos/${p.id}`,
      title: `#${p.numero_pedido ?? p.id} · ${p.cliente_nombre || "Sin cliente"}`,
      group: "Pedidos",
      Icon: ClipboardList,
      sub: ESTADO_LABEL[p.estado] ?? p.estado,
    }));

    // Pedidos primero (lo que el dueño busca por número/cliente), luego rutas.
    return [...pedidoItems, ...routeItems];
  }, [needle, pedidosQ.data]);

  // Clamp del índice activo cuando cambian los resultados.
  useEffect(() => {
    setActive((a) => Math.min(a, Math.max(0, matches.length - 1)));
  }, [matches.length]);

  // Scroll al ítem activo.
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(`[data-idx="${active}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const go = (idx: number) => {
    const r = matches[idx];
    if (!r) return;
    setOpen(false);
    navigate({ to: r.url });
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, matches.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      go(active);
    }
  };

  // Buscando pedidos y todavía sin nada que mostrar (ni rutas ni pedidos).
  const buscandoPedidos = pedidosQ.isFetching && debouncedQ.length >= 2;

  // Para los headers de grupo: marcar dónde cambia el grupo en la lista plana.
  let lastGroup = "";

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-xl gap-0 overflow-hidden p-0" hideClose>
        <DialogTitle className="sr-only">Buscar en el back-office</DialogTitle>
        <div className="flex items-center gap-2 border-b hairline px-3">
          <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
          {/* eslint-disable-next-line no-restricted-syntax -- input custom borderless dentro de wrapper con border-b (command palette) */}
          <input
            autoFocus
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setActive(0);
            }}
            onKeyDown={onKeyDown}
            placeholder="Buscar pedidos (nº o cliente) o páginas…"
            className="flex-1 bg-transparent py-3 text-base outline-none placeholder:text-muted-foreground sm:text-sm"
          />
          <kbd className="hidden shrink-0 rounded border hairline px-1.5 py-0.5 font-mono text-2xs text-muted-foreground sm:block">
            esc
          </kbd>
        </div>

        <div ref={listRef} className="max-h-80 overflow-y-auto p-1.5">
          {matches.length === 0 ? (
            <div className="px-3 py-8 text-center text-sm text-muted-foreground">
              {buscandoPedidos ? "Buscando pedidos…" : `Sin resultados para “${q.trim()}”.`}
            </div>
          ) : (
            matches.map((r, idx) => {
              const showGroup = r.group !== lastGroup;
              lastGroup = r.group;
              const Icon = r.Icon;
              return (
                <div key={r.key}>
                  {showGroup && <div className="t-eyebrow px-2 pb-1 pt-2">{r.group}</div>}
                  <button
                    type="button"
                    data-idx={idx}
                    onMouseMove={() => setActive(idx)}
                    onClick={() => go(idx)}
                    className={cn(
                      "flex w-full items-center gap-2.5 rounded-md px-2 py-2 text-left text-sm transition-colors",
                      idx === active ? "bg-amber-soft text-ink" : "text-ink hover:bg-muted/60",
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="flex-1 truncate">{r.title}</span>
                    {r.sub && (
                      <span className="shrink-0 font-mono text-2xs uppercase tracking-wider text-muted-foreground">
                        {r.sub}
                      </span>
                    )}
                    {idx === active && (
                      <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                    )}
                  </button>
                </div>
              );
            })
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
