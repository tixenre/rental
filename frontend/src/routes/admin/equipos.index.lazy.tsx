import { createLazyFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Search,
  Pencil,
  Trash2,
  Eye,
  EyeOff,
  AlertCircle,
  MoreHorizontal,
  Wrench,
  History,
  Copy,
  BarChart3,
  RotateCcw,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Pill } from "@/design-system/ui/Pill";
import { Input } from "@/design-system/ui/input";
import { Checkbox } from "@/design-system/ui/checkbox";
import { cn } from "@/lib/utils";
import { useUsdRate, calcularPrecioJornada } from "@/hooks/useSettings";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/design-system/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/design-system/ui/alert-dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/design-system/ui/dropdown-menu";

import { adminApi, type Equipo, type EquipoInput, type FaltaField } from "@/lib/admin/api";
import { stashEquiposReturnSearch } from "@/lib/admin/equiposReturnSearch";
import { AdminPage } from "@/components/admin/AdminPage";
import { useConfirm } from "@/components/admin/useConfirm";
import { ActionMenu } from "@/components/mobile";
import { MantenimientoEquipoDialog } from "@/components/admin/MantenimientoEquipoDialog";
import { HistorialEquipoDialog } from "@/components/admin/HistorialEquipoDialog";
import { DashboardUsoDialog } from "@/components/admin/DashboardUsoDialog";
import { ComboBuilderDialog } from "@/components/admin/ComboBuilderDialog";
import { useDocumentTitle } from "@/lib/use-document-title";
import {
  StockInline,
  RoiInline,
  PrecioJornadaInline,
  CategoriaInline,
  KpiCard,
  FaltaBanner,
} from "@/components/admin/equipos-mgmt/EquiposTableHelpers";

export const Route = createLazyFileRoute("/admin/equipos/")({
  component: EquiposPage,
});

// ── Filtros en URL search params (#233) ──────────────────────────────
// Antes vivían solo en useState — refrescar perdía el filtro. Ahora viajan
// en la URL: shareable, sobreviven refresh, back button funciona.
type EquiposSearch = {
  q?: string;
  /** Nombre de categoría raíz (matchea descendientes vía CTE recursiva). */
  categoria?: string;
  /** Nombre exacto de marca. */
  marca?: string;
  solo_incompletos?: boolean;
  vista_papelera?: boolean;
  /** Filtra equipos sin un campo dado (#350 — CTA desde dashboard de calidad). */
  falta?: FaltaField;
};

function EquiposPage() {
  useDocumentTitle("Equipos · Back Office");
  const qc = useQueryClient();
  const confirm = useConfirm();

  const search = useSearch({ strict: false }) as EquiposSearch;
  const navigate = useNavigate();

  const q = search.q ?? "";
  const categoria = search.categoria ?? "";
  const marca = search.marca ?? "";
  const soloIncompletos = search.solo_incompletos ?? false;
  const vistaPapelera = search.vista_papelera ?? false;
  const falta = search.falta;

  function updateFilters(updates: Partial<EquiposSearch>) {
    navigate({
      search: (prev: Record<string, unknown>) => {
        const next: EquiposSearch = { ...(prev as EquiposSearch), ...updates };
        // Strip falsy values para mantener la URL limpia.
        if (!next.q) delete next.q;
        if (!next.categoria) delete next.categoria;
        if (!next.marca) delete next.marca;
        if (!next.solo_incompletos) delete next.solo_incompletos;
        if (!next.vista_papelera) delete next.vista_papelera;
        if (!next.falta) delete next.falta;
        return next;
      },
      replace: true,
    } as never);
  }

  const setQ = (v: string) => updateFilters({ q: v });
  const setCategoria = (v: string) => updateFilters({ categoria: v });
  const setMarca = (v: string) => updateFilters({ marca: v });
  const setSoloIncompletos = (v: boolean | ((prev: boolean) => boolean)) =>
    updateFilters({ solo_incompletos: typeof v === "function" ? v(soloIncompletos) : v });
  const setVistaPapelera = (v: boolean | ((prev: boolean) => boolean)) =>
    updateFilters({ vista_papelera: typeof v === "function" ? v(vistaPapelera) : v });

  const [deleting, setDeleting] = useState<Equipo | null>(null);
  const [menuEquipo, setMenuEquipo] = useState<Equipo | null>(null);
  const [mantenimientoEquipo, setMantenimientoEquipo] = useState<Equipo | null>(null);
  const [historialEquipo, setHistorialEquipo] = useState<Equipo | null>(null);
  const [openDashboard, setOpenDashboard] = useState(false);
  const [openComboBuilder, setOpenComboBuilder] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [tab, setTab] = useState<"todos" | "combos" | "sin-foto">("todos");

  const equiposQ = useQuery({
    queryKey: ["admin", "equipos", { q, categoria, marca, soloIncompletos, vistaPapelera, falta }],
    queryFn: () =>
      adminApi.listEquipos({
        q: q || undefined,
        categoria: categoria || undefined,
        marca: marca || undefined,
        solo_incompletos: soloIncompletos || undefined,
        solo_eliminados: vistaPapelera || undefined,
        falta,
        // Esta tabla no lee specs/kit/ficha de cada fila (ver EquiposTableHelpers) —
        // el backend los saltea, el detalle completo lo trae el modal de edición aparte.
        incluir_detalle: false,
      }),
  });
  const kpisQ = useQuery({
    queryKey: ["admin", "equipos", "kpis"],
    queryFn: () => adminApi.equiposKpis(),
    staleTime: 0,
  });
  // Categorías para el selector de bulk "set categoría" (issue #231).
  const categoriasQ = useQuery({
    queryKey: ["admin", "categorias"],
    queryFn: () => adminApi.listCategorias(),
    staleTime: 0,
  });
  const marcasQ = useQuery({
    queryKey: ["admin", "marcas-list"],
    queryFn: () => adminApi.adminListMarcas(),
    staleTime: 0,
  });
  // Banner de calidad de inventario: equipos sin serie. Issue #91.
  const sinSerieQ = useQuery({
    queryKey: ["admin", "equipos-sin-serie"],
    queryFn: () => adminApi.getEquiposSinSerie(),
    staleTime: 0,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
    // También refrescamos el catálogo público (useEquipos / useCategorias)
    // para que la ficha y la foto recién aplicadas aparezcan sin recargar.
    qc.invalidateQueries({ queryKey: ["equipos"] });
    qc.invalidateQueries({ queryKey: ["categorias"] });
  };

  // El form maneja TODO el ciclo de guardado (foto, ficha, ficha extendida,
  // categorías) y también el toast final + cierre del dialog. Acá sólo
  // hacemos el create/update y refrescamos las queries — sin toast
  // ni close (esos los emite el form recién cuando todo el flow terminó,
  // así evitamos que el dialog se cierre mientras todavía hay requests
  // en vuelo, y que aparezcan errores parciales después del cierre).
  const deleteMut = useMutation({
    mutationFn: (id: number) => adminApi.deleteEquipo(id),
    onSuccess: () => {
      toast.success("Equipo eliminado");
      setDeleting(null);
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Antes de navegar al editor, persistimos los search params actuales para
  // que el goBack los restaure (3 entrypoints: botón fila, menú móvil, duplicado).
  const stashReturnSearch = () => stashEquiposReturnSearch(search);

  const duplicateMut = useMutation({
    mutationFn: (id: number) => adminApi.duplicateEquipo(id),
    onSuccess: (eq) => {
      toast.success(`Duplicado: "${eq.nombre}"`);
      invalidate();
      // Ir al editor del duplicado para que el admin lo termine de configurar.
      stashReturnSearch();
      navigate({ to: "/admin/equipos/$id/editar", params: { id: String(eq.id) } });
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

  const bulkMut = useMutation({
    mutationFn: (payload: Parameters<typeof adminApi.bulkAction>[0]) =>
      adminApi.bulkAction(payload),
    onSuccess: (r) => {
      toast.success(
        `${r.affected} equipo${r.affected === 1 ? "" : "s"} actualizado${r.affected === 1 ? "" : "s"}`,
      );
      setSelectedIds(new Set());
      invalidate();
    },
    onError: (e: Error) => toast.error(`Bulk falló: ${e.message}`),
  });

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const toggleSelectAll = (allItems: Equipo[]) => {
    setSelectedIds((prev) => {
      if (prev.size === allItems.length) return new Set();
      return new Set(allItems.map((e) => e.id));
    });
  };

  const allItems = equiposQ.data?.items ?? [];
  const total = equiposQ.data?.total ?? 0;

  // Los combos son "otra cosa" (sin stock propio, precio derivado de componentes):
  // viven en su propio tab. El resto de los tabs operan sobre el inventario FÍSICO
  // (equipos + kits), sin combos.
  const esCombo = (eq: Equipo) => eq.tipo === "combo";
  const fisicos = allItems.filter((e) => !esCombo(e));
  const tabCounts = {
    todos: fisicos.length,
    combos: allItems.filter(esCombo).length,
    "sin-foto": fisicos.filter((e) => !e.foto_url).length,
  };
  const items =
    tab === "combos"
      ? allItems.filter(esCombo)
      : tab === "sin-foto"
        ? fisicos.filter((e) => !e.foto_url)
        : fisicos;

  /** Categorías raíz para el dropdown (no incluye hijos). El backend acepta
   *  el nombre de la raíz y matchea descendientes vía CTE recursiva. */
  const categoriasOpts = useMemo(
    () =>
      [...(categoriasQ.data ?? [])]
        .filter((c) => (c.parent_id ?? null) == null)
        .sort((a, b) => a.nombre.localeCompare(b.nombre)),
    [categoriasQ.data],
  );
  /** Marcas con al menos un equipo para el dropdown. */
  const marcasOpts = useMemo(
    () =>
      [...(marcasQ.data?.items ?? [])]
        .filter((m) => (m.total ?? 0) > 0)
        .sort((a, b) => a.nombre.localeCompare(b.nombre)),
    [marcasQ.data],
  );

  return (
    <AdminPage
      title="Equipos"
      maxW="max-w-7xl"
      description={equiposQ.isLoading ? "Cargando…" : `${kpisQ.data?.total ?? total} equipos`}
      actions={
        <>
          <Button
            variant="outline"
            onClick={() => setOpenDashboard(true)}
            title="Dashboard de uso (top alquilados, sin movimiento, revenue por categoría)"
          >
            <BarChart3 className="h-4 w-4 mr-1" /> Uso
          </Button>
          <Button variant="outline" onClick={() => setOpenComboBuilder(true)}>
            <Plus className="h-4 w-4 mr-1" /> Nuevo combo
          </Button>
          <Button
            onClick={() => {
              stashReturnSearch();
              navigate({ to: "/admin/equipos/nuevo" });
            }}
          >
            <Plus className="h-4 w-4 mr-1" /> Nuevo equipo
          </Button>
        </>
      }
    >
      <div className="space-y-6">
        {/* KPI strip (handoff): inventario de un vistazo. */}
        <div className="grid grid-cols-3 gap-2 sm:gap-3">
          <KpiCard label="Total" value={kpisQ.data?.total ?? total} meta="equipos en catálogo" />
          <KpiCard
            label="En uso hoy"
            value={kpisQ.data?.en_uso_hoy ?? 0}
            meta="unidades alquiladas ahora"
          />
          <KpiCard
            label="Mantenimiento"
            value={kpisQ.data?.mantenimiento ?? 0}
            meta="bloqueando stock hoy"
            warn={(kpisQ.data?.mantenimiento ?? 0) > 0}
          />
        </div>

        {falta && (
          <FaltaBanner
            falta={falta}
            total={total}
            loading={equiposQ.isLoading}
            onClear={() => updateFilters({ falta: undefined })}
          />
        )}

        <div className="flex flex-col md:flex-row md:flex-wrap gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Buscar (nombre, marca, modelo, serie, specs, keywords…)"
              className="pl-9 text-base sm:text-sm"
            />
          </div>
          <Select
            value={categoria || "__all"}
            onValueChange={(v) => setCategoria(v === "__all" ? "" : v)}
          >
            <SelectTrigger className="md:w-44">
              <SelectValue placeholder="Todas las categorías" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Todas las categorías</SelectItem>
              {categoriasOpts.map((c) => (
                <SelectItem key={c.nombre} value={c.nombre}>
                  {c.nombre} {c.total ? `(${c.total})` : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={marca || "__all"} onValueChange={(v) => setMarca(v === "__all" ? "" : v)}>
            <SelectTrigger className="md:w-40">
              <SelectValue placeholder="Todas las marcas" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Todas las marcas</SelectItem>
              {marcasOpts.map((m) => (
                <SelectItem key={m.id} value={m.nombre}>
                  {m.nombre} {m.total ? `(${m.total})` : ""}
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
            {vistaPapelera ? (
              <>
                <Trash2 className="h-3.5 w-3.5 mr-1" /> Papelera
              </>
            ) : (
              "Papelera"
            )}
          </Button>
          {(q || categoria || marca || soloIncompletos || falta) && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() =>
                updateFilters({
                  q: "",
                  categoria: "",
                  marca: "",
                  solo_incompletos: false,
                  falta: undefined,
                })
              }
              title="Limpiar todos los filtros (mantiene papelera)"
              className="md:w-auto text-muted-foreground hover:text-ink"
            >
              Limpiar filtros
            </Button>
          )}
        </div>

        {equiposQ.error && (
          <div className="rounded-md border hairline border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            Error: {(equiposQ.error as Error).message}
          </div>
        )}

        {/* Banner: equipos sin serie cargada (calidad inventario, issue #91) */}
        {sinSerieQ.data && sinSerieQ.data.total > 0 && (
          <div className="flex items-start gap-2.5 rounded-md border hairline border-amber/40 bg-amber-soft/30 px-3 py-2 text-sm">
            <AlertCircle className="h-4 w-4 mt-0.5 text-ink shrink-0" />
            <div className="flex-1">
              <span className="font-medium text-ink">
                {sinSerieQ.data.total} equipo
                {sinSerieQ.data.total === 1 ? "" : "s"} sin número de serie
              </span>
              <span className="text-muted-foreground">
                {" "}
                · cargá la serie desde el form de cada equipo (botón{" "}
                <span className="font-mono">N/A</span> si no aplica).
              </span>
            </div>
          </div>
        )}

        {/* Barra flotante de bulk actions */}
        {selectedIds.size > 0 && (
          <div className="sticky top-0 z-10 flex items-center gap-2 rounded-md border hairline bg-ink text-background px-3 py-2 shadow-md">
            <span className="text-sm font-medium flex-1">
              {selectedIds.size} seleccionado{selectedIds.size === 1 ? "" : "s"}
            </span>
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                bulkMut.mutate({ ids: [...selectedIds], action: "set_visible", visible: true })
              }
              disabled={bulkMut.isPending}
            >
              <Eye className="h-3.5 w-3.5 mr-1" /> Mostrar
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                bulkMut.mutate({ ids: [...selectedIds], action: "set_visible", visible: false })
              }
              disabled={bulkMut.isPending}
            >
              <EyeOff className="h-3.5 w-3.5 mr-1" /> Ocultar
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                bulkMut.mutate({
                  ids: [...selectedIds],
                  action: "set_ficha_completa",
                  ficha_completa: true,
                })
              }
              disabled={bulkMut.isPending}
              title="Marcar fichas como completas"
            >
              ✓ Completas
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                bulkMut.mutate({
                  ids: [...selectedIds],
                  action: "set_ficha_completa",
                  ficha_completa: false,
                })
              }
              disabled={bulkMut.isPending}
              title="Marcar fichas como pendientes"
            >
              ☐ Pendientes
            </Button>
            {/* Set categoría (#231): asigna categoría a los seleccionados.
              Reemplaza las categorías existentes (backend hace DELETE + INSERT). */}
            <Select
              value=""
              onValueChange={(v) => {
                const categoria_id = Number(v);
                if (!Number.isFinite(categoria_id)) return;
                bulkMut.mutate({
                  ids: [...selectedIds],
                  action: "set_categoria",
                  categoria_id,
                });
              }}
              disabled={bulkMut.isPending || !categoriasQ.data?.length}
            >
              <SelectTrigger className="h-8 w-44 bg-secondary text-secondary-foreground border-0">
                <SelectValue placeholder="Asignar categoría…" />
              </SelectTrigger>
              <SelectContent>
                {(categoriasQ.data ?? []).map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.nombre}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              size="sm"
              variant="destructive"
              onClick={async () => {
                // En papelera, "Eliminar" hace hard delete (delete_permanent).
                // En vista normal, soft delete (delete). #punto4
                const permanent = vistaPapelera;
                const n = selectedIds.size;
                const plural = n === 1 ? "" : "s";
                const ok = permanent
                  ? await confirm({
                      title: `¿Eliminar permanentemente ${n} equipo${plural}?`,
                      description: `Esta acción no se puede deshacer y borra ficha, kit y categorías asociadas.`,
                      danger: true,
                      confirmLabel: "Eliminar",
                    })
                  : await confirm({
                      title: `¿Eliminar ${n} equipo${plural}?`,
                      description: `Quedan en la papelera y se pueden restaurar.`,
                      danger: true,
                      confirmLabel: "Eliminar",
                    });
                if (ok) {
                  bulkMut.mutate({
                    ids: [...selectedIds],
                    action: permanent ? "delete_permanent" : "delete",
                  });
                }
              }}
              disabled={bulkMut.isPending}
            >
              <Trash2 className="h-3.5 w-3.5 mr-1" />
              {vistaPapelera ? "Eliminar permanente" : "Eliminar"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setSelectedIds(new Set())}
              className="text-background hover:text-background/70"
            >
              Cancelar
            </Button>
          </div>
        )}

        {/* Sub-tabs (handoff): filtros rápidos. */}
        <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none border-b hairline pb-px">
          {(
            [
              ["todos", "Todos"],
              ["combos", "Combos"],
              ["sin-foto", "Sin foto"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 font-sans text-sm whitespace-nowrap transition",
                tab === id
                  ? "bg-muted font-bold text-ink"
                  : "font-medium text-muted-foreground hover:text-ink",
              )}
            >
              {label}
              <span className="font-mono text-2xs tabular-nums opacity-70">{tabCounts[id]}</span>
            </button>
          ))}
        </div>

        <div className="rounded-lg border hairline overflow-hidden bg-background">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    checked={items.length > 0 && selectedIds.size === items.length}
                    onCheckedChange={() => toggleSelectAll(items)}
                    aria-label="Seleccionar todos"
                  />
                </TableHead>
                <TableHead className="w-14"></TableHead>
                <TableHead>Equipo</TableHead>
                <TableHead className="hidden lg:table-cell">Categoría</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead className="text-right">Stock</TableHead>
                <TableHead className="text-right hidden sm:table-cell">$ / jornada</TableHead>
                <TableHead
                  className="text-right hidden sm:table-cell w-24"
                  title="% del valor del equipo cobrado por día (nombre tentativo)"
                >
                  % día
                </TableHead>
                <TableHead className="text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.length === 0 && !equiposQ.isLoading && (
                <TableRow>
                  <TableCell colSpan={9} className="text-center text-muted-foreground py-10">
                    Sin equipos.{" "}
                    {q && (
                      <button
                        type="button"
                        onClick={() => setQ("")}
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
                    <Checkbox
                      checked={selectedIds.has(eq.id)}
                      onCheckedChange={() => toggleSelect(eq.id)}
                      aria-label={`Seleccionar ${eq.nombre}`}
                    />
                  </TableCell>
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
                      <div className="h-10 w-10 rounded bg-muted/40 grid place-items-center text-2xs text-muted-foreground">
                        —
                      </div>
                    )}
                  </TableCell>
                  <TableCell>
                    {eq.marca && (
                      <div className="t-eyebrow font-semibold leading-none mb-0.5">{eq.marca}</div>
                    )}
                    <div className="flex items-center gap-1.5 font-medium text-ink leading-tight">
                      <span>{eq.nombre}</span>
                      {!eq.ficha_completa && (
                        <span
                          className="inline-flex shrink-0"
                          title="Ficha pendiente — marcala como completa en el form cuando termines de cargarla"
                        >
                          <Pill tone="warning">pendiente</Pill>
                        </span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="hidden lg:table-cell w-40">
                    <CategoriaInline
                      equipo={eq}
                      categorias={categoriasQ.data ?? []}
                      onSaved={invalidate}
                    />
                  </TableCell>
                  <TableCell>
                    {eq.visible_catalogo ? (
                      <Pill
                        tone="success"
                        className="font-mono font-bold uppercase tracking-[0.1em]"
                      >
                        Visible
                      </Pill>
                    ) : (
                      <Pill
                        tone="neutral"
                        className="font-mono font-bold uppercase tracking-[0.1em]"
                      >
                        Oculto
                      </Pill>
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {eq.tipo === "combo" ? (
                      <span
                        className="font-mono text-2xs uppercase tracking-[0.1em] text-muted-foreground"
                        title="El stock de un combo se deriva de sus componentes (mín. de los esenciales)"
                      >
                        derivado
                      </span>
                    ) : (
                      <StockInline
                        equipo={eq}
                        onSaved={() => qc.invalidateQueries({ queryKey: ["admin", "equipos"] })}
                      />
                    )}
                  </TableCell>
                  <TableCell className="text-right hidden sm:table-cell w-32">
                    <PrecioJornadaInline
                      equipo={eq}
                      onSaved={() => qc.invalidateQueries({ queryKey: ["admin", "equipos"] })}
                    />
                  </TableCell>
                  <TableCell className="text-right hidden sm:table-cell w-24">
                    <RoiInline
                      equipo={eq}
                      onSaved={() => qc.invalidateQueries({ queryKey: ["admin", "equipos"] })}
                    />
                  </TableCell>
                  <TableCell className="text-right">
                    {/* Mobile: un botón → ActionMenu (bottom sheet) */}
                    <Button
                      size="icon"
                      variant="ghost"
                      className="sm:hidden"
                      aria-label="Más acciones"
                      onClick={() => setMenuEquipo(eq)}
                    >
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                    {/* Desktop: mismo menú, como dropdown (#DS pattern — ver MarcasSection) */}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="hidden sm:inline-flex"
                          aria-label={`Acciones de ${eq.nombre}`}
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-52">
                        <DropdownMenuItem onClick={() => toggleVisibleMut.mutate(eq)}>
                          {eq.visible_catalogo ? (
                            <EyeOff className="mr-2 h-4 w-4" />
                          ) : (
                            <Eye className="mr-2 h-4 w-4" />
                          )}
                          {eq.visible_catalogo ? "Ocultar del catálogo" : "Mostrar en catálogo"}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setHistorialEquipo(eq)}>
                          <History className="mr-2 h-4 w-4" />
                          Historial de alquileres
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setMantenimientoEquipo(eq)}>
                          <Wrench className="mr-2 h-4 w-4" />
                          Mantenimiento
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => {
                            stashReturnSearch();
                            navigate({
                              to: "/admin/equipos/$id/editar",
                              params: { id: String(eq.id) },
                            });
                          }}
                        >
                          <Pencil className="mr-2 h-4 w-4" />
                          Editar
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => duplicateMut.mutate(eq.id)}
                          disabled={duplicateMut.isPending}
                        >
                          <Copy className="mr-2 h-4 w-4" />
                          Duplicar
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        {eq.eliminado_at ? (
                          <DropdownMenuItem
                            onClick={() => restoreMut.mutate(eq.id)}
                            disabled={restoreMut.isPending}
                          >
                            <RotateCcw className="mr-2 h-4 w-4" />
                            Restaurar
                          </DropdownMenuItem>
                        ) : (
                          <DropdownMenuItem
                            onClick={() => setDeleting(eq)}
                            className="text-destructive focus:text-destructive"
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Eliminar
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <ActionMenu
          open={!!menuEquipo}
          onOpenChange={(v) => {
            if (!v) setMenuEquipo(null);
          }}
          title={menuEquipo?.nombre}
          actions={[
            {
              label: menuEquipo?.visible_catalogo ? "Ocultar del catálogo" : "Mostrar en catálogo",
              icon: menuEquipo?.visible_catalogo ? (
                <EyeOff className="h-4 w-4" />
              ) : (
                <Eye className="h-4 w-4" />
              ),
              onClick: () => toggleVisibleMut.mutate(menuEquipo!),
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
              onClick: () => {
                if (!menuEquipo) return;
                stashReturnSearch();
                navigate({
                  to: "/admin/equipos/$id/editar",
                  params: { id: String(menuEquipo.id) },
                });
              },
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

        {mantenimientoEquipo && (
          <MantenimientoEquipoDialog
            equipo={mantenimientoEquipo}
            open={!!mantenimientoEquipo}
            onOpenChange={(v) => {
              if (!v) setMantenimientoEquipo(null);
            }}
          />
        )}

        {historialEquipo && (
          <HistorialEquipoDialog
            equipo={historialEquipo}
            open={!!historialEquipo}
            onOpenChange={(v) => {
              if (!v) setHistorialEquipo(null);
            }}
          />
        )}

        {openDashboard && (
          <DashboardUsoDialog open={openDashboard} onOpenChange={setOpenDashboard} />
        )}

        <ComboBuilderDialog open={openComboBuilder} onOpenChange={setOpenComboBuilder} />

        <AlertDialog
          open={!!deleting}
          onOpenChange={(v) => {
            if (!v) setDeleting(null);
          }}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Eliminar “{deleting?.nombre}”</AlertDialogTitle>
              <AlertDialogDescription>
                Esta acción no se puede deshacer. Si el equipo tiene pedidos históricos, mejor
                marcalo como “Fuera de servicio” en lugar de borrarlo.
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
    </AdminPage>
  );
}
