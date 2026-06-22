/**
 * EquipoSearchSheet — BottomSheet para buscar y agregar equipos al pedido.
 * Extraído de PedidoPage.tsx para ser reutilizado en el editor v2.
 */

import { useMemo, useState } from "react";
import { Search, Plus } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { BottomSheet } from "@/components/mobile";
import { adminApi, type Equipo } from "@/lib/admin/api";
import { fmtArs } from "@/lib/format";
import { filtrarOrdenar } from "@/lib/search/normalize";
import { EquipoThumb } from "./EquipoThumb";
import type { DraftItem } from "./usePedidoDraft";

export function EquipoSearchSheet({
  open,
  onOpenChange,
  existing,
  stockMap,
  onAdd,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  existing: DraftItem[];
  stockMap: Record<string, { cantidad: number; reservado: number }>;
  onAdd: (eq: Equipo) => void;
}) {
  const [q, setQ] = useState("");
  const equiposQ = useQuery({
    queryKey: ["admin", "equipos", "all"],
    queryFn: () => adminApi.listEquipos({ per_page: 500 }),
  });
  const categoriasQ = useQuery({
    queryKey: ["categorias"],
    queryFn: () => adminApi.listCategorias(),
    staleTime: 60_000,
  });

  const lista = useMemo(() => {
    const all = (equiposQ.data?.items ?? []).filter((e) => e.estado !== "fuera_servicio");
    // Motor de búsqueda compartido (espejo del backend): sin tildes, sin
    // guiones, multi-palabra y ordenado por relevancia.
    return filtrarOrdenar(all, q, (e) => ({
      nombre: e.nombre,
      extra: [e.nombre_publico ?? "", e.marca ?? "", e.modelo ?? ""].join(" "),
    }));
  }, [equiposQ.data, q]);

  const grupos = useMemo(() => {
    const SIN = "Sin categoría";
    const map = new Map<string, Equipo[]>();
    for (const eq of lista) {
      const cat = eq.etiquetas?.[0] ?? SIN;
      const arr = map.get(cat) ?? [];
      arr.push(eq);
      map.set(cat, arr);
    }
    const weight: Record<string, number> = {};
    const tree = categoriasQ.data ?? [];
    for (const root of tree) {
      const rp = root.prioridad ?? 999;
      weight[root.nombre] = rp * 1000;
      for (const c of root.children ?? []) {
        weight[c.nombre] = rp * 1000 + ((c as { prioridad?: number }).prioridad ?? 100);
      }
      (root.subtags ?? []).forEach((s, i) => {
        if (weight[s.nombre] == null) weight[s.nombre] = rp * 1000 + (i + 1) * 10;
      });
    }
    return Array.from(map.entries()).sort(([a], [b]) => {
      if (a === SIN) return 1;
      if (b === SIN) return -1;
      return (weight[a] ?? 999_000) - (weight[b] ?? 999_000) || a.localeCompare(b, "es");
    });
  }, [lista, categoriasQ.data]);

  return (
    <BottomSheet open={open} onOpenChange={onOpenChange} title="Agregar equipo" showClose>
      <div className="px-4 pt-3 pb-3 border-b hairline">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar…"
            className="pl-9 text-base sm:text-sm"
          />
        </div>
      </div>
      <div className="px-4 pb-4">
        {grupos.length === 0 && (
          <div className="py-8 text-center text-sm text-muted-foreground">Sin equipos.</div>
        )}
        {grupos.map(([cat, equipos]) => (
          <section key={cat} className="mb-2">
            <div className="sticky top-0 z-10 bg-background/95 backdrop-blur py-2 flex items-center justify-between border-b hairline">
              <h4 className="font-display text-sm text-ink">{cat}</h4>
              <span className="text-[11px] text-muted-foreground">{equipos.length}</span>
            </div>
            <ul className="divide-y hairline">
              {equipos.map((eq) => {
                const stock = stockMap[String(eq.id)];
                const inCart = existing.find((i) => i.equipo_id === eq.id);
                const max = stock ? Math.max(0, stock.cantidad - stock.reservado) : eq.cantidad;
                const disponible = max - (inCart?.cantidad ?? 0);
                return (
                  <li key={eq.id} className="flex items-center justify-between gap-2 py-3">
                    <EquipoThumb
                      src={eq.foto_url}
                      alt={eq.nombre_publico || eq.nombre}
                      className="h-10 w-10"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm text-ink truncate">
                        {eq.nombre_publico || eq.nombre}
                      </div>
                      <div className="text-xs text-muted-foreground truncate">
                        {[eq.marca, eq.modelo].filter(Boolean).join(" / ")}
                        {" · "}
                        <span className={disponible <= 0 ? "text-destructive" : ""}>
                          {disponible} libres
                        </span>
                        {eq.precio_jornada ? ` · ${fmtArs(eq.precio_jornada)}/día` : ""}
                      </div>
                    </div>
                    <Button
                      size="icon"
                      className="h-11 w-11 shrink-0"
                      disabled={disponible <= 0}
                      onClick={() => onAdd(eq)}
                      aria-label="Agregar"
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
    </BottomSheet>
  );
}
