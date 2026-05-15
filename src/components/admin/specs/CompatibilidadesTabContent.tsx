/**
 * CompatibilidadesTabContent — tab "Compatibilidades" del form de equipo.
 *
 * Permite definir relaciones entre equipos: compatible / incompatible /
 * requiere_adaptador. Vista de admin solo (no se renderea en el catálogo
 * cliente todavía — eso vendría en una iteración futura).
 *
 * UX:
 *   - Lista las compatibilidades ya definidas, agrupadas por tipo.
 *   - Formulario inline para crear una nueva: search-as-you-type sobre
 *     equipos + selector tipo + (si requiere_adaptador) selector adaptador.
 *   - Click X para borrar.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Loader2, Plus, X, Check, AlertTriangle, Wrench, Sparkles, Crop, ChevronDown, ChevronRight,
} from "lucide-react";
import { toast } from "sonner";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  adminApi,
  type CompatibleEquipo,
  type CompatibleOverall,
  type Equipo,
} from "@/lib/admin/api";


type CompatTipo = "compatible" | "incompatible" | "requiere_adaptador";

const TIPO_LABEL: Record<CompatTipo, { label: string; icon: typeof Check; color: string }> = {
  compatible: { label: "Compatible", icon: Check, color: "text-emerald-700" },
  incompatible: { label: "Incompatible", icon: X, color: "text-destructive" },
  requiere_adaptador: { label: "Requiere adaptador", icon: Wrench, color: "text-amber" },
};

const AUTO_GROUP_META: Record<
  Exclude<CompatibleOverall, "sin_relacion">,
  { label: string; icon: typeof Check; color: string; bg: string }
> = {
  compatible: { label: "Compatibles", icon: Check, color: "text-emerald-700", bg: "bg-emerald-50/50 border-emerald-100" },
  compatible_con_crop: { label: "Compatible con crop", icon: Crop, color: "text-emerald-700", bg: "bg-emerald-50/30 border-emerald-100" },
  parcial: { label: "Parcial / viñetea", icon: AlertTriangle, color: "text-amber-700", bg: "bg-amber-soft/30 border-amber/30" },
  requiere_adaptador: { label: "Requiere adaptador", icon: Wrench, color: "text-amber", bg: "bg-amber-soft/30 border-amber/30" },
  incompatible: { label: "Incompatibles", icon: X, color: "text-destructive", bg: "bg-destructive/5 border-destructive/20" },
};


export function CompatibilidadesTabContent({ equipoId }: { equipoId: number }) {
  const qc = useQueryClient();

  const compatsQ = useQuery({
    queryKey: ["admin", "compatibilidades", equipoId],
    queryFn: () => adminApi.listarCompatibilidades(equipoId),
  });

  // Form de "agregar nueva"
  const [tipo, setTipo] = useState<CompatTipo>("compatible");
  const [busquedaB, setBusquedaB] = useState("");
  const [equipoB, setEquipoB] = useState<{ id: number; nombre: string } | null>(null);
  const [busquedaAdaptador, setBusquedaAdaptador] = useState("");
  const [adaptador, setAdaptador] = useState<{ id: number; nombre: string } | null>(null);
  const [nota, setNota] = useState("");

  // Buscador de equipos para B y adaptador (>= 2 chars).
  const busquedaActiva = (q: string) =>
    useQuery({
      queryKey: ["admin", "equipos-search", q],
      queryFn: () => adminApi.listEquipos({ q: q.trim(), per_page: 10 }),
      enabled: q.trim().length >= 2,
    });
  const resultadosB = busquedaActiva(busquedaB);
  const resultadosAd = busquedaActiva(busquedaAdaptador);

  const crearMut = useMutation({
    mutationFn: () =>
      adminApi.crearCompatibilidad(equipoId, {
        equipo_b_id: equipoB!.id,
        tipo,
        nota: nota.trim() || undefined,
        adaptador_id: tipo === "requiere_adaptador" ? adaptador?.id : undefined,
      }),
    onSuccess: () => {
      toast.success("Compatibilidad agregada");
      qc.invalidateQueries({ queryKey: ["admin", "compatibilidades", equipoId] });
      setEquipoB(null); setBusquedaB("");
      setAdaptador(null); setBusquedaAdaptador("");
      setNota("");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const borrarMut = useMutation({
    mutationFn: (id: number) => adminApi.borrarCompatibilidad(id),
    onSuccess: () => {
      toast.success("Compatibilidad eliminada");
      qc.invalidateQueries({ queryKey: ["admin", "compatibilidades", equipoId] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const items = compatsQ.data?.items ?? [];
  const byTipo: Record<CompatTipo, typeof items> = {
    compatible: items.filter((i) => i.tipo === "compatible"),
    requiere_adaptador: items.filter((i) => i.tipo === "requiere_adaptador"),
    incompatible: items.filter((i) => i.tipo === "incompatible"),
  };

  const puedeAgregar =
    equipoB &&
    equipoB.id !== equipoId &&
    (tipo !== "requiere_adaptador" || !!adaptador);

  return (
    <div className="space-y-4">
      <div className="rounded-md border hairline bg-muted/30 px-3 py-2 text-xs">
        Define relaciones con otros equipos. Solo visible en el backoffice — el
        cliente no las ve.
      </div>

      <AutoCompatibilidadesSection equipoId={equipoId} />

      <div className="px-1 text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
        Compat persistidas (manuales + asistidas por IA)
      </div>

      {/* Listado por tipo */}
      {compatsQ.isLoading ? (
        <div className="text-center py-6 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin mx-auto" />
        </div>
      ) : items.length === 0 ? (
        <p className="text-xs text-muted-foreground italic text-center py-3">
          No hay compatibilidades definidas.
        </p>
      ) : (
        <div className="space-y-2">
          {(["compatible", "requiere_adaptador", "incompatible"] as const).map((t) => {
            const list = byTipo[t];
            if (list.length === 0) return null;
            const meta = TIPO_LABEL[t];
            const Icon = meta.icon;
            return (
              <div key={t} className="rounded-md border hairline bg-background">
                <div className={"flex items-center gap-1.5 px-3 py-2 border-b hairline text-xs font-medium " + meta.color}>
                  <Icon className="h-3.5 w-3.5" /> {meta.label} ({list.length})
                </div>
                <ul className="divide-y hairline">
                  {list.map((c) => (
                    <li key={c.id} className="flex items-center gap-2 px-3 py-1.5 text-sm">
                      {c.otro_foto ? (
                        <img src={c.otro_foto} alt="" className="h-7 w-7 rounded object-cover bg-muted/30" />
                      ) : (
                        <div className="h-7 w-7 rounded bg-muted/40 grid place-items-center text-[10px] text-muted-foreground">—</div>
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="truncate text-ink">{c.otro_nombre}</span>
                          {c.auto_generado ? (
                            <span
                              className="inline-flex items-center gap-0.5 rounded px-1 py-0.5 text-[9px] bg-amber-soft/80 text-amber-800 border border-amber/30 shrink-0"
                              title={
                                (c.razon_ia ?? "Generada por el skill gear-compatibility") +
                                (c.confianza != null ? ` · confianza ${Math.round(c.confianza * 100)}%` : "")
                              }
                            >
                              <Sparkles className="h-2.5 w-2.5" /> IA
                            </span>
                          ) : (
                            <span
                              className="inline-flex items-center rounded px-1 py-0.5 text-[9px] bg-muted text-muted-foreground border hairline shrink-0"
                              title="Definida manualmente"
                            >
                              manual
                            </span>
                          )}
                        </div>
                        {c.adaptador_nombre && (
                          <div className="text-[11px] text-muted-foreground truncate">
                            <Wrench className="inline h-3 w-3 mr-0.5" />vía {c.adaptador_nombre}
                          </div>
                        )}
                        {c.nota && (
                          <div className="text-[11px] text-muted-foreground italic truncate">{c.nota}</div>
                        )}
                        {c.auto_generado && c.razon_ia && (
                          <div className="text-[11px] text-amber-700 italic truncate" title={c.razon_ia}>
                            {c.razon_ia}
                          </div>
                        )}
                      </div>
                      <Button
                        type="button" size="icon" variant="ghost"
                        onClick={() => borrarMut.mutate(c.id)}
                        disabled={borrarMut.isPending}
                        className="h-7 w-7"
                      >
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      )}

      {/* Form de agregar */}
      <div className="rounded-md border hairline bg-background">
        <div className="px-3 py-2 border-b hairline bg-muted/20">
          <Label className="text-xs uppercase tracking-wide text-muted-foreground">
            Agregar compatibilidad
          </Label>
        </div>
        <div className="p-3 space-y-2">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-[10px] uppercase tracking-wide text-muted-foreground">Tipo</Label>
              <Select value={tipo} onValueChange={(v) => setTipo(v as CompatTipo)}>
                <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="compatible">Compatible</SelectItem>
                  <SelectItem value="requiere_adaptador">Requiere adaptador</SelectItem>
                  <SelectItem value="incompatible">Incompatible</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-[10px] uppercase tracking-wide text-muted-foreground">
                {tipo === "requiere_adaptador" ? "Con (lente/equipo)" : "Otro equipo"}
              </Label>
              <BuscadorEquipo
                valor={equipoB}
                onPick={(eq) => { setEquipoB(eq); setBusquedaB(eq.nombre); }}
                busqueda={busquedaB}
                onBusqueda={(v) => { setBusquedaB(v); if (equipoB && v !== equipoB.nombre) setEquipoB(null); }}
                resultados={resultadosB.data?.items ?? []}
                excludeId={equipoId}
              />
            </div>
          </div>

          {tipo === "requiere_adaptador" && (
            <div className="space-y-1">
              <Label className="text-[10px] uppercase tracking-wide text-muted-foreground">
                Adaptador necesario
              </Label>
              <BuscadorEquipo
                valor={adaptador}
                onPick={(eq) => { setAdaptador(eq); setBusquedaAdaptador(eq.nombre); }}
                busqueda={busquedaAdaptador}
                onBusqueda={(v) => { setBusquedaAdaptador(v); if (adaptador && v !== adaptador.nombre) setAdaptador(null); }}
                resultados={resultadosAd.data?.items ?? []}
                excludeId={equipoId}
              />
            </div>
          )}

          <div className="space-y-1">
            <Label className="text-[10px] uppercase tracking-wide text-muted-foreground">Nota (opcional)</Label>
            <Input
              value={nota}
              onChange={(e) => setNota(e.target.value)}
              placeholder="Ej: funciona pero pierde autofocus en modo continuo"
              className="h-9 text-xs"
            />
          </div>

          <div className="flex justify-end">
            <Button
              type="button" size="sm"
              onClick={() => crearMut.mutate()}
              disabled={!puedeAgregar || crearMut.isPending}
            >
              {crearMut.isPending ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Plus className="h-3 w-3 mr-1" />}
              Agregar
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}


/** Sección "Compatibilidad automática" — derivada de las specs marcadas como
 *  driver de compatibilidad. Se calcula 100% en el backend; acá solo
 *  renderizamos agrupado por overall y con razones legibles. */
function AutoCompatibilidadesSection({ equipoId }: { equipoId: number }) {
  const [verIncompatibles, setVerIncompatibles] = useState(false);
  const autoQ = useQuery({
    queryKey: ["admin", "compatibles-auto", equipoId],
    queryFn: () => adminApi.listarCompatiblesAuto(equipoId),
    staleTime: 60_000,
  });

  if (autoQ.isLoading) {
    return (
      <div className="rounded-md border hairline px-3 py-4 text-center text-xs text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin mx-auto mb-1" />
        Calculando compatibilidades…
      </div>
    );
  }

  const items = autoQ.data?.items ?? [];
  if (items.length === 0) {
    return (
      <div className="rounded-md border hairline border-dashed px-3 py-3 text-center text-[11px] text-muted-foreground">
        <Sparkles className="inline h-3 w-3 mr-1 text-amber" />
        Sin compatibilidades automáticas. Marcá specs como "driver de
        compatibilidad" en el catálogo global para que aparezcan acá.
      </div>
    );
  }

  // Agrupar por overall. "sin_relacion" no aparece en la respuesta.
  const groups: Record<Exclude<CompatibleOverall, "sin_relacion">, CompatibleEquipo[]> = {
    compatible: [],
    compatible_con_crop: [],
    parcial: [],
    requiere_adaptador: [],
    incompatible: [],
  };
  for (const it of items) {
    if (it.overall === "sin_relacion") continue;
    groups[it.overall].push(it);
  }

  const order: Array<Exclude<CompatibleOverall, "sin_relacion">> = [
    "compatible",
    "compatible_con_crop",
    "requiere_adaptador",
    "parcial",
  ];
  const visibleGroups = order.filter((k) => groups[k].length > 0);
  const incompatCount = groups.incompatible.length;

  return (
    <div className="rounded-md border hairline overflow-hidden">
      <header className="px-3 py-2 border-b hairline bg-amber-soft/30 flex items-center gap-2">
        <Sparkles className="h-3.5 w-3.5 text-amber" />
        <span className="text-xs font-medium text-ink">Compatibilidad automática</span>
        <span className="text-[10px] text-muted-foreground ml-auto">
          {items.length} match{items.length === 1 ? "" : "es"}
        </span>
      </header>

      <div className="divide-y hairline">
        {visibleGroups.map((key) => (
          <AutoGroup key={key} overall={key} items={groups[key]} />
        ))}

        {incompatCount > 0 && (
          <div>
            <button
              type="button"
              onClick={() => setVerIncompatibles((v) => !v)}
              className="w-full flex items-center gap-2 px-3 py-2 text-[11px] text-muted-foreground hover:bg-muted/30"
            >
              {verIncompatibles ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              Ver incompatibles ({incompatCount})
            </button>
            {verIncompatibles && <AutoGroup overall="incompatible" items={groups.incompatible} />}
          </div>
        )}
      </div>
    </div>
  );
}

function AutoGroup({
  overall,
  items,
}: {
  overall: Exclude<CompatibleOverall, "sin_relacion">;
  items: CompatibleEquipo[];
}) {
  const meta = AUTO_GROUP_META[overall];
  const Icon = meta.icon;
  return (
    <div className={`${meta.bg} border-l-2`}>
      <div className={`flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium ${meta.color}`}>
        <Icon className="h-3 w-3" />
        {meta.label} ({items.length})
      </div>
      <ul className="divide-y hairline bg-background/60">
        {items.map((it) => (
          <AutoRow key={it.equipo_id} item={it} />
        ))}
      </ul>
    </div>
  );
}

function AutoRow({ item }: { item: CompatibleEquipo }) {
  const [open, setOpen] = useState(false);
  const tieneRazones = item.razones.length > 0;
  return (
    <li className="px-3 py-1.5 text-sm">
      <div className="flex items-center gap-2">
        {item.foto_url ? (
          <img src={item.foto_url} alt="" className="h-7 w-7 rounded object-cover bg-muted/30" />
        ) : (
          <div className="h-7 w-7 rounded bg-muted/40 grid place-items-center text-[10px] text-muted-foreground">—</div>
        )}
        <div className="flex-1 min-w-0">
          <div className="truncate text-ink">{item.nombre}</div>
          {item.marca && (
            <div className="text-[10px] text-muted-foreground truncate">{item.marca}</div>
          )}
          {item.adaptador && (
            <div className="text-[11px] text-muted-foreground truncate">
              <Wrench className="inline h-3 w-3 mr-0.5" />
              vía {item.adaptador.nombre}
            </div>
          )}
        </div>
        {tieneRazones && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="text-[10px] text-muted-foreground hover:text-ink"
          >
            {open ? "Ocultar" : `${item.razones.length} razon${item.razones.length === 1 ? "" : "es"}`}
          </button>
        )}
      </div>
      {open && tieneRazones && (
        <ul className="mt-1 ml-9 space-y-0.5 text-[11px] text-muted-foreground">
          {item.razones.map((r, i) => (
            <li key={i} className="flex items-start gap-1.5">
              <span className="font-mono text-[9px] uppercase tracking-wider mt-0.5 shrink-0">
                {r.status === "match" || r.status === "match_con_crop" ? "✓" :
                 r.status === "partial_vignette" || r.status === "partial" ? "≈" : "×"}
              </span>
              <span>{r.mensaje}</span>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

/** Buscador inline de equipos (search-as-you-type). */
function BuscadorEquipo({
  valor, busqueda, onPick, onBusqueda, resultados, excludeId,
}: {
  valor: { id: number; nombre: string } | null;
  busqueda: string;
  onPick: (eq: { id: number; nombre: string }) => void;
  onBusqueda: (v: string) => void;
  resultados: Equipo[];
  excludeId: number;
}) {
  const mostrar = busqueda.trim().length >= 2 && !valor;
  return (
    <div className="relative">
      <Input
        value={busqueda}
        onChange={(e) => onBusqueda(e.target.value)}
        placeholder="Buscar equipo (min 2 chars)"
        className="h-9 text-xs"
      />
      {mostrar && resultados.length > 0 && (
        <div className="absolute z-10 mt-1 w-full rounded-md border hairline bg-background shadow-md max-h-56 overflow-y-auto">
          {resultados
            .filter((r) => r.id !== excludeId)
            .slice(0, 8)
            .map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => onPick({ id: r.id, nombre: r.nombre })}
                className="w-full text-left px-3 py-1.5 hover:bg-accent text-xs flex items-center gap-2"
              >
                {r.foto_url && (
                  <img src={r.foto_url} alt="" className="h-6 w-6 rounded object-cover bg-muted/30" />
                )}
                <span className="truncate">{r.nombre}</span>
                {(r.marca || r.modelo) && (
                  <span className="text-muted-foreground text-[10px] ml-auto">
                    {[r.marca, r.modelo].filter(Boolean).join(" / ")}
                  </span>
                )}
              </button>
            ))}
        </div>
      )}
    </div>
  );
}
