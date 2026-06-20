/**
 * EquipoComboSearch — buscador de equipos inline para el editor de pedidos.
 *
 * Reemplaza al `EquipoSearchSheet` full-screen: los resultados aparecen en un
 * dropdown DEBAJO del input (patrón de `ClienteAutocomplete`), sin tapar el
 * formulario. Combina ese patrón inline con el motor de búsqueda compartido
 * (`filtrarOrdenar`, espejo del backend) y la carga client-side del catálogo
 * (per_page 500, cacheada) para filtrado instantáneo.
 *
 * Al agregar NO cierra ni limpia el input → se pueden cargar varios equipos
 * seguidos. El stock disponible se recalcula en vivo desde `existing` + `stockMap`.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { Search, Plus } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { adminApi, type Equipo } from "@/lib/admin/api";
import { fmtArs } from "@/lib/format";
import { filtrarOrdenar } from "@/lib/search/normalize";
import { EquipoThumb } from "./EquipoThumb";
import type { DraftItem } from "./usePedidoDraft";

/** Tope de filas visibles sin query (evita renderizar las ~500 del catálogo). */
const MAX_VISIBLE = 50;

export function EquipoComboSearch({
  existing,
  stockMap,
  onAdd,
  placeholder = "Buscar para añadir equipos…",
  className,
}: {
  existing: DraftItem[];
  stockMap: Record<string, { cantidad: number; reservado: number }>;
  onAdd: (eq: Equipo) => void;
  placeholder?: string;
  className?: string;
}) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  // Cerrar al clickear afuera (el dropdown se mantiene abierto mientras se
  // agregan equipos, así que no alcanza con onBlur del input).
  useEffect(() => {
    if (!open) return;
    const h = (ev: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(ev.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);

  const equiposQ = useQuery({
    queryKey: ["admin", "equipos", "all"],
    queryFn: () => adminApi.listEquipos({ per_page: 500 }),
  });

  const matches = useMemo(() => {
    const all = (equiposQ.data?.items ?? []).filter((e) => e.estado !== "fuera_servicio");
    // Motor de búsqueda compartido (espejo del backend): sin tildes, sin
    // guiones, multi-palabra y ordenado por relevancia.
    return filtrarOrdenar(all, q, (e) => ({
      nombre: e.nombre,
      extra: [e.nombre_publico ?? "", e.marca ?? "", e.modelo ?? ""].join(" "),
    }));
  }, [equiposQ.data, q]);

  const visibles = matches.slice(0, MAX_VISIBLE);
  const overflow = matches.length - visibles.length;

  /** Unidades libres restantes para este equipo (descuenta lo ya cargado en el pedido). */
  const disponibleDe = (eq: Equipo): number => {
    const stock = stockMap[String(eq.id)];
    const max = stock ? Math.max(0, stock.cantidad - stock.reservado) : eq.cantidad;
    const inCart = existing.find((i) => i.equipo_id === eq.id);
    return max - (inCart?.cantidad ?? 0);
  };

  return (
    <div ref={wrapRef} className={cn("relative", className)}>
      <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground pointer-events-none" />
      <Input
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder={placeholder}
        className="pl-9 text-base sm:text-sm"
      />

      {open && (
        <div className="absolute z-30 left-0 right-0 mt-1 rounded-lg border hairline bg-surface-elevated shadow-[var(--shadow-md)] max-h-80 overflow-auto">
          {equiposQ.isLoading ? (
            <div className="p-3 text-xs text-muted-foreground">Cargando catálogo…</div>
          ) : matches.length === 0 ? (
            <div className="p-3 text-xs text-muted-foreground">
              {q.trim() ? `Sin resultados para "${q.trim()}".` : "No hay equipos."}
            </div>
          ) : (
            <ul className="divide-y hairline">
              {visibles.map((eq) => {
                const disponible = disponibleDe(eq);
                const sinStock = disponible <= 0;
                return (
                  <li key={eq.id}>
                    <button
                      type="button"
                      disabled={sinStock}
                      // onMouseDown + preventDefault: agregar sin perder el foco
                      // del input → el dropdown queda abierto para cargar más.
                      onMouseDown={(e) => {
                        e.preventDefault();
                        if (!sinStock) onAdd(eq);
                      }}
                      className={cn(
                        "flex w-full items-center gap-3 px-3 py-2 text-left transition-colors",
                        sinStock ? "cursor-not-allowed opacity-50" : "hover:bg-amber-soft",
                      )}
                    >
                      <EquipoThumb
                        src={eq.foto_url}
                        alt={eq.nombre_publico || eq.nombre}
                        className="h-10 w-10 shrink-0"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm text-ink truncate">
                          {eq.nombre_publico || eq.nombre}
                        </div>
                        <div className="font-mono text-[11px] text-muted-foreground truncate">
                          {[eq.marca, eq.modelo].filter(Boolean).join(" / ")}
                          {eq.precio_jornada ? ` · ${fmtArs(eq.precio_jornada)}/día` : ""}
                        </div>
                      </div>
                      <span
                        className={cn(
                          "shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px]",
                          sinStock
                            ? "bg-destructive/10 text-destructive"
                            : "bg-muted text-muted-foreground",
                        )}
                      >
                        {sinStock ? "sin stock" : `${disponible} libres`}
                      </span>
                      <Plus
                        className={cn(
                          "h-4 w-4 shrink-0",
                          sinStock ? "text-muted-foreground/40" : "text-ink",
                        )}
                      />
                    </button>
                  </li>
                );
              })}
              {overflow > 0 && (
                <li className="px-3 py-2 text-center font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                  +{overflow} más · seguí escribiendo para afinar
                </li>
              )}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
