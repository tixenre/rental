import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Search, CornerDownLeft } from "lucide-react";

import { Dialog, DialogContent, DialogTitle } from "@/design-system/ui/dialog";
import { cn } from "@/lib/utils";
import { ADMIN_ROUTES } from "./adminNav";

/**
 * AdminCommandPalette — buscador global del back-office (⌘K / Ctrl+K).
 *
 * Indexa TODAS las rutas del admin desde `adminNav` (fuente única) — sin lista
 * duplicada. Sin dependencia nueva: Dialog del DS + filtrado + navegación por
 * teclado (↑↓ Enter Esc), el mismo patrón de los demás buscadores del repo.
 *
 * Se abre con ⌘K/Ctrl+K o despachando el evento `admin:cmdk` desde cualquier
 * botón (sidebar / header mobile) — así los triggers no necesitan prop-drilling.
 */

/** Normaliza para matchear sin tildes ni mayúsculas. */
const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

export function AdminCommandPalette() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  // Abrir con ⌘K/Ctrl+K o con el evento custom de los triggers visibles.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
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

  const matches = useMemo(() => {
    const needle = norm(q.trim());
    if (!needle) return ADMIN_ROUTES;
    return ADMIN_ROUTES.filter((r) => norm(`${r.group} ${r.title}`).includes(needle));
  }, [q]);

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
            placeholder="Buscar páginas del back-office…"
            className="flex-1 bg-transparent py-3 text-base outline-none placeholder:text-muted-foreground sm:text-sm"
          />
          <kbd className="hidden shrink-0 rounded border hairline px-1.5 py-0.5 font-mono text-2xs text-muted-foreground sm:block">
            esc
          </kbd>
        </div>

        <div ref={listRef} className="max-h-80 overflow-y-auto p-1.5">
          {matches.length === 0 ? (
            <div className="px-3 py-8 text-center text-sm text-muted-foreground">
              Sin resultados para “{q.trim()}”.
            </div>
          ) : (
            matches.map((r, idx) => {
              const showGroup = r.group !== lastGroup;
              lastGroup = r.group;
              const Icon = r.icon;
              return (
                <div key={r.url}>
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
