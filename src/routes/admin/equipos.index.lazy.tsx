import { createLazyFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Pencil, Trash2, Eye, EyeOff, Sparkles, AlertCircle, MoreHorizontal, Wrench, History, Copy, RotateCcw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useUsdRate, calcularPrecioJornada } from "@/hooks/useSettings";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

import { adminApi, type Equipo, type EquipoInput } from "@/lib/admin/api";
import { ActionMenu } from "@/components/mobile";
import { EquipoFormDialogV2 as EquipoFormDialog } from "@/components/admin/equipo-form-v2/EquipoFormDialogV2";
import { AutocompletarEquipoDialog } from "@/components/admin/autocompletar";
import { BatchAutocompletarDialog } from "@/components/admin/BatchAutocompletarDialog";
import { MantenimientoEquipoDialog } from "@/components/admin/MantenimientoEquipoDialog";
import { HistorialEquipoDialog } from "@/components/admin/HistorialEquipoDialog";

export const Route = createLazyFileRoute("/admin/equipos/")({
  component: EquiposPage,
});

function EquiposPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [etiqueta, setEtiqueta] = useState<string>("");
  const [soloIncompletos, setSoloIncompletos] = useState(false);
  const [vistaPapelera, setVistaPapelera] = useState(false);
  const [openForm, setOpenForm] = useState(false);
  const [editing, setEditing] = useState<Equipo | null>(null);
  const [deleting, setDeleting] = useState<Equipo | null>(null);
  const [enriching, setEnriching] = useState<Equipo | null>(null);
  const [menuEquipo, setMenuEquipo] = useState<Equipo | null>(null);
  const [openBatch, setOpenBatch] = useState(false);
  const [mantenimientoEquipo, setMantenimientoEquipo] = useState<Equipo | null>(null);
  const [historialEquipo, setHistorialEquipo] = useState<Equipo | null>(null);

  const equiposQ = useQuery({
    queryKey: ["admin", "equipos", { q, etiqueta, soloIncompletos, vistaPapelera }],
    queryFn: () => adminApi.listEquipos({
      q: q || undefined,
      etiqueta: etiqueta || undefined,
      solo_incompletos: soloIncompletos || undefined,
      solo_eliminados: vistaPapelera || undefined,
    }),
  });
  const etiquetasQ = useQuery({
    queryKey: ["admin", "etiquetas"],
    queryFn: () => adminApi.listEtiquetas(),
  });
  // Banner de calidad de inventario: equipos sin serie. Issue #91.
  const sinSerieQ = useQuery({
    queryKey: ["admin", "equipos-sin-serie"],
    queryFn: () => adminApi.getEquiposSinSerie(),
    staleTime: 60_000,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
    qc.invalidateQueries({ queryKey: ["admin", "etiquetas"] });
    // También refrescamos el catálogo público (useEquipos / useCategorias)
    // para que la ficha y la foto recién aplicadas aparezcan sin recargar.
    qc.invalidateQueries({ queryKey: ["equipos"] });
    qc.invalidateQueries({ queryKey: ["categorias"] });
  };

  // El form maneja TODO el ciclo de guardado (foto, ficha, ficha extendida,
  // categorías) y también el toast final + cierre del dialog. Acá sólo
  // hacemos el create/update + tags y refrescamos las queries — sin toast
  // ni close (esos los emite el form recién cuando todo el flow terminó,
  // así evitamos que el dialog se cierre mientras todavía hay requests
  // en vuelo, y que aparezcan errores parciales después del cierre).
  const saveMut = useMutation({
    mutationFn: async ({ data, etiquetas }: { data: EquipoInput; etiquetas: string[] }) => {
      const eq = editing
        ? await adminApi.updateEquipo(editing.id, data)
        : await adminApi.createEquipo(data);
      await adminApi.setEtiquetas(eq.id, etiquetas);
      return eq;
    },
    onSettled: () => invalidate(),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => adminApi.deleteEquipo(id),
    onSuccess: () => {
      toast.success("Equipo eliminado");
      setDeleting(null);
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const duplicateMut = useMutation({
    mutationFn: (id: number) => adminApi.duplicateEquipo(id),
    onSuccess: (eq) => {
      toast.success(`Duplicado: "${eq.nombre}"`);
      invalidate();
      // Abrir el form del duplicado para que el admin lo termine de configurar.
      setEditing(eq);
      setOpenForm(true);
    },
    onError: (e: Error) => toast.error(`No se pudo duplicar: ${e.message}`),
  });

  const toggleVisibleMut = useMutation({
    mutationFn: (eq: Equipo) =>
      adminApi.updateEquipo(eq.id, { visible_catalogo: eq.visible_catalogo ? 0 : 1 }),
    onSuccess: () => invalidate(),
    onError: (e: Error) => toast.error(e.message),
  });

  const restoreMut = useMutation({
    mutationFn: (id: number) => adminApi.restoreEquipo(id),
    onSuccess: () => {
      toast.success("Equipo restaurado");
      invalidate();
    },
    onError: (e: Error) => toast.error(`No se pudo restaurar: ${e.message}`),
  });

  const items = equiposQ.data?.items ?? [];
  const total = equiposQ.data?.total ?? 0;

  const etiquetasOpts = useMemo(
    () => (etiquetasQ.data ?? []).filter((e) => (e.total ?? 0) > 0),
    [etiquetasQ.data],
  );

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-7xl mx-auto">
      <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Back-office
          </div>
          <h1 className="font-display text-3xl text-ink">Equipos</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {equiposQ.isLoading ? "Cargando…" : `${total} equipos`}
          </p>
        </div>
        <div className="flex gap-1.5">
          <Button variant="outline" onClick={() => setOpenBatch(true)} title="Buscar specs en bulk para los equipos con link de fuente">
            <Sparkles className="h-4 w-4 mr-1" /> Batch specs
          </Button>
          <Button onClick={() => { setEditing(null); setOpenForm(true); }}>
            <Plus className="h-4 w-4 mr-1" /> Nuevo equipo
          </Button>
        </div>
      </header>

      <div className="flex flex-col md:flex-row gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar (nombre, marca, modelo, serie, specs, keywords…)"
            className="pl-9 text-base sm:text-sm"
          />
        </div>
        <Select value={etiqueta || "__all"} onValueChange={(v) => setEtiqueta(v === "__all" ? "" : v)}>
          <SelectTrigger className="md:w-56"><SelectValue placeholder="Todas las etiquetas" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__all">Todas las etiquetas</SelectItem>
            {etiquetasOpts.map((e) => (
              <SelectItem key={e.nombre} value={e.nombre}>
                {e.nombre} {e.total ? `(${e.total})` : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          type="button"
          variant={soloIncompletos ? "default" : "outline"}
          size="sm"
          onClick={() => setSoloIncompletos((v) => !v)}
          title="Filtrar equipos cuya ficha aún no marcaste como completa"
          className="md:w-auto"
        >
          {soloIncompletos ? "✓ Solo incompletos" : "Solo incompletos"}
        </Button>
        <Button
          type="button"
          variant={vistaPapelera ? "destructive" : "outline"}
          size="sm"
          onClick={() => setVistaPapelera((v) => !v)}
          title="Ver equipos dados de baja (soft-deleted)"
          className="md:w-auto"
        >
          {vistaPapelera ? <><Trash2 className="h-3.5 w-3.5 mr-1" /> Papelera</> : "Papelera"}
        </Button>
      </div>

      {equiposQ.error && (
        <div className="rounded-md border hairline border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          Error: {(equiposQ.error as Error).message}
        </div>
      )}

      {/* Banner: equipos sin serie cargada (calidad inventario, issue #91) */}
      {sinSerieQ.data && sinSerieQ.data.total > 0 && (
        <div className="flex items-start gap-2.5 rounded-md border hairline border-amber/40 bg-amber-soft/30 px-3 py-2 text-sm">
          <AlertCircle className="h-4 w-4 mt-0.5 text-amber shrink-0" />
          <div className="flex-1">
            <span className="font-medium text-ink">
              {sinSerieQ.data.total} equipo
              {sinSerieQ.data.total === 1 ? "" : "s"} sin número de serie
            </span>
            <span className="text-muted-foreground"> · cargá la serie desde el form de cada equipo (botón <span className="font-mono">N/A</span> si no aplica).</span>
          </div>
        </div>
      )}

      <div className="rounded-lg border hairline overflow-hidden bg-background">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-14"></TableHead>
              <TableHead>Nombre</TableHead>
              <TableHead className="hidden md:table-cell">Marca / Modelo</TableHead>
              <TableHead className="text-right">Stock</TableHead>
              <TableHead className="text-right hidden sm:table-cell">Precio/día</TableHead>
              <TableHead className="text-right hidden sm:table-cell w-24">ROI %</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 && !equiposQ.isLoading && (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-muted-foreground py-10">
                  Sin equipos.{" "}
                  {(q || etiqueta) && (
                    <button
                      type="button"
                      onClick={() => { setQ(""); setEtiqueta(""); }}
                      className="underline hover:text-ink"
                    >
                      Limpiar filtros
                    </button>
                  )}
                </TableCell>
              </TableRow>
            )}
            {items.map((eq) => (
              <TableRow key={eq.id} className={eq.visible_catalogo ? "" : "opacity-60"}>
                <TableCell>
                  {eq.foto_url ? (
                    <img
                      src={eq.foto_url}
                      alt=""
                      loading="lazy"
                      className="h-10 w-10 rounded object-cover bg-muted/30"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.opacity = "0.2";
                      }}
                    />
                  ) : (
                    <div className="h-10 w-10 rounded bg-muted/40 grid place-items-center text-[10px] text-muted-foreground">
                      —
                    </div>
                  )}
                </TableCell>
                <TableCell className="font-medium">
                  <div className="flex items-center gap-1.5">
                    <span>{eq.nombre}</span>
                    {!eq.ficha_completa && (
                      <span
                        className="text-[10px] text-amber-700 bg-amber-soft/40 px-1 py-0.5 rounded shrink-0"
                        title="Ficha pendiente — marcala como completa en el form cuando termines de cargarla"
                      >
                        pendiente
                      </span>
                    )}
                  </div>
                </TableCell>
                <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                  {[eq.marca, eq.modelo].filter(Boolean).join(" / ") || "—"}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  <StockInline equipo={eq} onSaved={() => qc.invalidateQueries({ queryKey: ["admin", "equipos"] })} />
                </TableCell>
                <TableCell className="text-right hidden sm:table-cell w-32">
                  <PrecioJornadaInline equipo={eq} onSaved={() => qc.invalidateQueries({ queryKey: ["admin", "equipos"] })} />
                </TableCell>
                <TableCell className="text-right hidden sm:table-cell w-24">
                  <RoiInline equipo={eq} onSaved={() => qc.invalidateQueries({ queryKey: ["admin", "equipos"] })} />
                </TableCell>
                <TableCell>
                  <Badge variant={eq.estado === "operativo" ? "default" : "outline"}>
                    {eq.estado === "en_mantenimiento" ? "Mantenim." : eq.estado === "fuera_servicio" ? "Fuera" : "OK"}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  {/* Mobile: un botón → ActionMenu */}
                  <Button size="icon" variant="ghost" className="sm:hidden" onClick={() => setMenuEquipo(eq)}>
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                  {/* Desktop: botones individuales */}
                  <div className="hidden sm:inline-flex gap-1">
                    <Button
                      size="icon" variant="ghost"
                      title={eq.visible_catalogo ? "Ocultar del catálogo" : "Mostrar en catálogo"}
                      onClick={() => toggleVisibleMut.mutate(eq)}
                    >
                      {eq.visible_catalogo ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                    </Button>
                    <Button size="icon" variant="ghost" title="Auto-completar info (B&H/Adorama)" onClick={() => setEnriching(eq)}>
                      <Sparkles className="h-4 w-4 text-amber" />
                    </Button>
                    <Button size="icon" variant="ghost" title="Historial de alquileres" onClick={() => setHistorialEquipo(eq)}>
                      <History className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost" title="Mantenimiento" onClick={() => setMantenimientoEquipo(eq)}>
                      <Wrench className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost" title="Editar" onClick={() => { setEditing(eq); setOpenForm(true); }}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      size="icon" variant="ghost"
                      title="Duplicar (clona ficha, categorías y kit — serie vacía)"
                      onClick={() => duplicateMut.mutate(eq.id)}
                      disabled={duplicateMut.isPending}
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                    {eq.eliminado_at ? (
                      <Button
                        size="icon" variant="ghost"
                        title="Restaurar"
                        onClick={() => restoreMut.mutate(eq.id)}
                        disabled={restoreMut.isPending}
                      >
                        <RotateCcw className="h-4 w-4 text-amber" />
                      </Button>
                    ) : (
                      <Button size="icon" variant="ghost" onClick={() => setDeleting(eq)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <ActionMenu
        open={!!menuEquipo}
        onOpenChange={(v) => { if (!v) setMenuEquipo(null); }}
        title={menuEquipo?.nombre}
        actions={[
          {
            label: menuEquipo?.visible_catalogo ? "Ocultar del catálogo" : "Mostrar en catálogo",
            icon: menuEquipo?.visible_catalogo ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />,
            onClick: () => toggleVisibleMut.mutate(menuEquipo!),
          },
          {
            label: "Auto-completar info",
            icon: <Sparkles className="h-4 w-4" />,
            onClick: () => setEnriching(menuEquipo!),
          },
          {
            label: "Historial de alquileres",
            icon: <History className="h-4 w-4" />,
            onClick: () => setHistorialEquipo(menuEquipo!),
          },
          {
            label: "Mantenimiento",
            icon: <Wrench className="h-4 w-4" />,
            onClick: () => setMantenimientoEquipo(menuEquipo!),
          },
          {
            label: "Editar",
            icon: <Pencil className="h-4 w-4" />,
            onClick: () => { setEditing(menuEquipo!); setOpenForm(true); },
          },
          {
            label: "Duplicar equipo",
            icon: <Copy className="h-4 w-4" />,
            onClick: () => duplicateMut.mutate(menuEquipo!.id),
          },
          {
            label: "Eliminar equipo",
            icon: <Trash2 className="h-4 w-4" />,
            variant: "destructive" as const,
            onClick: () => setDeleting(menuEquipo!),
          },
        ]}
      />

      {openForm && (
        <EquipoFormDialog
          open={openForm}
          onOpenChange={(v) => { setOpenForm(v); if (!v) setEditing(null); }}
          initial={editing}
          saving={saveMut.isPending}
          onSubmit={(data, etiquetas) => saveMut.mutateAsync({ data, etiquetas })}
        />
      )}

      {openBatch && (
        <BatchAutocompletarDialog
          equipos={items}
          open={openBatch}
          onOpenChange={setOpenBatch}
        />
      )}

      {mantenimientoEquipo && (
        <MantenimientoEquipoDialog
          equipo={mantenimientoEquipo}
          open={!!mantenimientoEquipo}
          onOpenChange={(v) => { if (!v) setMantenimientoEquipo(null); }}
        />
      )}

      {historialEquipo && (
        <HistorialEquipoDialog
          equipo={historialEquipo}
          open={!!historialEquipo}
          onOpenChange={(v) => { if (!v) setHistorialEquipo(null); }}
        />
      )}


      {enriching && (
        <AutocompletarEquipoDialog
          equipo={enriching}
          open={!!enriching}
          onOpenChange={(v) => { if (!v) setEnriching(null); }}
          onApplied={invalidate}
        />
      )}

      <AlertDialog open={!!deleting} onOpenChange={(v) => { if (!v) setDeleting(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar “{deleting?.nombre}”</AlertDialogTitle>
            <AlertDialogDescription>
              Esta acción no se puede deshacer. Si el equipo tiene pedidos
              históricos, mejor marcalo como “Fuera de servicio” en lugar de borrarlo.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleting && deleteMut.mutate(deleting.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}


/**
 * Editor inline del ROI %. Al cambiar:
 *  - Calcula el nuevo precio_jornada con el USD rate actual.
 *  - PATCHea ambos campos al backend.
 *  - Optimistic UI: actualiza el state local al toque, revierte si falla.
 *
 * No commitea hasta blur o Enter (evita una request por cada keystroke).
 */
/**
 * Editor inline del stock (cantidad). Click → input numérico → Enter/blur guarda.
 * Esc descarta. Vacío = 0 (no permite null).
 */
function StockInline({
  equipo,
  onSaved,
}: {
  equipo: Equipo;
  onSaved: () => void;
}) {
  const [value, setValue] = useState<string>(String(equipo.cantidad));
  const initialRef = useRef(equipo.cantidad);

  useEffect(() => {
    setValue(String(equipo.cantidad));
    initialRef.current = equipo.cantidad;
  }, [equipo.id, equipo.cantidad]);

  const saveMut = useMutation({
    mutationFn: (n: number) => adminApi.updateEquipo(equipo.id, { cantidad: n }),
    onSuccess: () => onSaved(),
    onError: (e: Error) => {
      toast.error(`No se pudo actualizar stock: ${e.message}`);
      setValue(String(initialRef.current));
    },
  });

  const commit = () => {
    const n = Math.max(0, Math.floor(Number(value.trim() || "0")));
    if (!Number.isFinite(n)) {
      setValue(String(initialRef.current));
      return;
    }
    if (n === initialRef.current) return;
    saveMut.mutate(n);
  };

  return (
    <Input
      type="number"
      min={0}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        else if (e.key === "Escape") {
          setValue(String(initialRef.current));
          (e.target as HTMLInputElement).blur();
        }
      }}
      disabled={saveMut.isPending}
      className="h-7 w-14 ml-auto text-right text-xs tabular-nums px-2 py-0"
    />
  );
}


function RoiInline({
  equipo,
  onSaved,
}: {
  equipo: Equipo;
  onSaved: () => void;
}) {
  const { rate: usdRate } = useUsdRate();
  const [value, setValue] = useState<string>(
    equipo.roi_pct != null ? String(equipo.roi_pct) : "",
  );
  const initialRef = useRef(equipo.roi_pct);

  // Si el equipo cambia (ej. recarga), sincronizar el input.
  useEffect(() => {
    setValue(equipo.roi_pct != null ? String(equipo.roi_pct) : "");
    initialRef.current = equipo.roi_pct;
  }, [equipo.id, equipo.roi_pct]);

  const saveMut = useMutation({
    mutationFn: async (newRoi: number) => {
      // Actualiza ROI; si tenemos USD, también recalcula precio_jornada
      // y lo manda en el mismo PATCH para que ambos cambien atómicamente.
      // Editar el ROI = volver a la fórmula → marcar precio como AUTO
      // (precio_jornada_manual = false). Esto deja el equipo elegible
      // para futuros recálculos masivos.
      const patch: Partial<EquipoInput> = { roi_pct: newRoi };
      if (equipo.precio_usd) {
        const nuevoPrecio = calcularPrecioJornada(equipo.precio_usd, usdRate, newRoi);
        if (nuevoPrecio !== null) {
          patch.precio_jornada = nuevoPrecio;
          patch.precio_jornada_manual = false;
        }
      }
      return adminApi.updateEquipo(equipo.id, patch);
    },
    onSuccess: () => {
      onSaved();
    },
    onError: (e: Error) => {
      toast.error(`No se pudo actualizar ROI: ${e.message}`);
      // Revertir al valor original.
      setValue(initialRef.current != null ? String(initialRef.current) : "");
    },
  });

  const commit = () => {
    const trimmed = value.trim();
    if (trimmed === "") {
      // Vacío → null (saca el ROI). Lo permitimos pero no recalcula precio.
      if (initialRef.current != null) {
        adminApi.updateEquipo(equipo.id, { roi_pct: null }).then(onSaved).catch((e) => {
          toast.error(`No se pudo limpiar ROI: ${e instanceof Error ? e.message : ""}`);
        });
      }
      return;
    }
    const num = Number(trimmed);
    if (!Number.isFinite(num) || num < 0) {
      toast.error("ROI debe ser un número >= 0");
      setValue(initialRef.current != null ? String(initialRef.current) : "");
      return;
    }
    if (num === initialRef.current) return;   // sin cambio, evitar request
    saveMut.mutate(num);
  };

  return (
    <Input
      type="number"
      min={0}
      step="0.1"
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          (e.target as HTMLInputElement).blur();
        } else if (e.key === "Escape") {
          setValue(initialRef.current != null ? String(initialRef.current) : "");
          (e.target as HTMLInputElement).blur();
        }
      }}
      placeholder="—"
      disabled={saveMut.isPending}
      className="h-7 w-16 ml-auto text-right text-xs tabular-nums px-2 py-0"
    />
  );
}


/**
 * Editor inline del precio de jornada en pesos. Espejo de RoiInline:
 *  - Editás precio → calcula nuevo ROI = precio / (precio_usd × usd_rate) × 100
 *  - PATCHea ambos campos atómicamente
 *  - Optimistic UI con rollback si falla
 *
 * No fuerza redondeo a múltiplos de 100 al tipear (es input MANUAL — el
 * admin manda). El redondeo a 100 solo aplica al cálculo automático
 * desde ROI o al recálculo masivo desde Settings.
 *
 * Si el equipo no tiene `precio_usd`, el ROI no se puede calcular: se
 * guarda solo el precio.
 */
function PrecioJornadaInline({
  equipo,
  onSaved,
}: {
  equipo: Equipo;
  onSaved: () => void;
}) {
  const { rate: usdRate } = useUsdRate();
  const [value, setValue] = useState<string>(
    equipo.precio_jornada != null ? String(equipo.precio_jornada) : "",
  );
  const initialRef = useRef(equipo.precio_jornada);

  useEffect(() => {
    setValue(equipo.precio_jornada != null ? String(equipo.precio_jornada) : "");
    initialRef.current = equipo.precio_jornada;
  }, [equipo.id, equipo.precio_jornada]);

  const saveMut = useMutation({
    mutationFn: async (newPrecio: number | null) => {
      // Editar el precio directo = override manual → flag = TRUE.
      // Esto evita que el próximo recálculo masivo (al cambiar el USD)
      // pise el precio que el admin acaba de definir a mano.
      const patch: Partial<EquipoInput> = {
        precio_jornada: newPrecio,
        precio_jornada_manual: true,
      };
      // Si tenemos USD y el nuevo precio no es null, derivamos el ROI
      // implícito y lo persistimos también para que la fórmula quede
      // coherente. Si el equipo no tiene USD, no podemos calcular ROI.
      if (newPrecio !== null && equipo.precio_usd && usdRate > 0) {
        const newRoi = (newPrecio / (equipo.precio_usd * usdRate)) * 100;
        // Redondear a 2 decimales para evitar 3.0399999999...
        patch.roi_pct = Math.round(newRoi * 100) / 100;
      }
      return adminApi.updateEquipo(equipo.id, patch);
    },
    onSuccess: () => {
      onSaved();
    },
    onError: (e: Error) => {
      toast.error(`No se pudo actualizar precio: ${e.message}`);
      setValue(initialRef.current != null ? String(initialRef.current) : "");
    },
  });

  const commit = () => {
    const trimmed = value.trim();
    if (trimmed === "") {
      // Vacío → null (saca el precio). Permitido pero no toca ROI.
      if (initialRef.current != null) saveMut.mutate(null);
      return;
    }
    const num = Number(trimmed);
    if (!Number.isFinite(num) || num < 0) {
      toast.error("Precio debe ser un número >= 0");
      setValue(initialRef.current != null ? String(initialRef.current) : "");
      return;
    }
    if (num === initialRef.current) return;
    saveMut.mutate(num);
  };

  const isManual = !!equipo.precio_jornada_manual;

  return (
    <div className="relative ml-auto w-28">
      <span className="absolute left-2 top-1/2 -translate-y-1/2 text-[11px] text-muted-foreground pointer-events-none">
        $
      </span>
      <Input
        type="number"
        min={0}
        step="100"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            (e.target as HTMLInputElement).blur();
          } else if (e.key === "Escape") {
            setValue(initialRef.current != null ? String(initialRef.current) : "");
            (e.target as HTMLInputElement).blur();
          }
        }}
        placeholder="—"
        disabled={saveMut.isPending}
        title={
          isManual
            ? "Precio fijado manualmente — no se actualiza al recalcular masivo"
            : "Precio automático (calculado desde USD × ROI%)"
        }
        className={
          "h-7 text-right text-xs tabular-nums pl-5 pr-2 py-0 " +
          (isManual ? "border-amber/60 bg-amber-soft/30" : "")
        }
      />
      {isManual && (
        <span
          className="absolute -top-1.5 -right-1 rounded-full bg-amber px-1 text-[8px] font-mono uppercase tracking-wide text-ink"
          title="Manual"
        >
          M
        </span>
      )}
    </div>
  );
}
