import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Pencil, Trash2, Eye, EyeOff, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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
import { EquipoFormDialog } from "@/components/admin/EquipoFormDialog";
import { EnriquecerEquipoDialog } from "@/components/admin/EnriquecerEquipoDialog";

export const Route = createFileRoute("/admin/equipos")({
  component: EquiposPage,
});

function EquiposPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [etiqueta, setEtiqueta] = useState<string>("");
  const [openForm, setOpenForm] = useState(false);
  const [editing, setEditing] = useState<Equipo | null>(null);
  const [deleting, setDeleting] = useState<Equipo | null>(null);
  const [enriching, setEnriching] = useState<Equipo | null>(null);

  const equiposQ = useQuery({
    queryKey: ["admin", "equipos", { q, etiqueta }],
    queryFn: () => adminApi.listEquipos({ q: q || undefined, etiqueta: etiqueta || undefined }),
  });
  const etiquetasQ = useQuery({
    queryKey: ["admin", "etiquetas"],
    queryFn: () => adminApi.listEtiquetas(),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
    qc.invalidateQueries({ queryKey: ["admin", "etiquetas"] });
    // También refrescamos el catálogo público (useEquipos / useCategorias)
    // para que la ficha y la foto recién aplicadas aparezcan sin recargar.
    qc.invalidateQueries({ queryKey: ["equipos"] });
    qc.invalidateQueries({ queryKey: ["categorias"] });
  };

  const saveMut = useMutation({
    mutationFn: async ({ data, etiquetas }: { data: EquipoInput; etiquetas: string[] }) => {
      const eq = editing
        ? await adminApi.updateEquipo(editing.id, data)
        : await adminApi.createEquipo(data);
      await adminApi.setEtiquetas(eq.id, etiquetas);
      return eq;
    },
    onSuccess: () => {
      toast.success(editing ? "Equipo actualizado" : "Equipo creado");
      setOpenForm(false);
      setEditing(null);
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
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

  const toggleVisibleMut = useMutation({
    mutationFn: (eq: Equipo) =>
      adminApi.updateEquipo(eq.id, { visible_catalogo: eq.visible_catalogo ? 0 : 1 }),
    onSuccess: () => invalidate(),
    onError: (e: Error) => toast.error(e.message),
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
        <Button onClick={() => { setEditing(null); setOpenForm(true); }}>
          <Plus className="h-4 w-4 mr-1" /> Nuevo equipo
        </Button>
      </header>

      <div className="flex flex-col md:flex-row gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar por nombre, marca, modelo…"
            className="pl-9"
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
      </div>

      {equiposQ.error && (
        <div className="rounded-md border hairline border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          Error: {(equiposQ.error as Error).message}
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
              <TableHead className="hidden lg:table-cell">Etiquetas</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 && !equiposQ.isLoading && (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-muted-foreground py-10">
                  Sin equipos.
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
                <TableCell className="font-medium">{eq.nombre}</TableCell>
                <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                  {[eq.marca, eq.modelo].filter(Boolean).join(" / ") || "—"}
                </TableCell>
                <TableCell className="text-right tabular-nums">{eq.cantidad}</TableCell>
                <TableCell className="text-right tabular-nums hidden sm:table-cell">
                  {eq.precio_jornada ? `$${eq.precio_jornada.toLocaleString("es-AR")}` : "—"}
                </TableCell>
                <TableCell className="hidden lg:table-cell">
                  <div className="flex flex-wrap gap-1">
                    {(eq.etiquetas ?? []).slice(0, 3).map((t) => (
                      <Badge key={t} variant="secondary" className="text-[10px]">{t}</Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant={eq.estado === "operativo" ? "default" : "outline"}>
                    {eq.estado === "en_mantenimiento" ? "Mantenim." : eq.estado === "fuera_servicio" ? "Fuera" : "OK"}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <div className="inline-flex gap-1">
                    <Button
                      size="icon" variant="ghost"
                      title={eq.visible_catalogo ? "Ocultar del catálogo" : "Mostrar en catálogo"}
                      onClick={() => toggleVisibleMut.mutate(eq)}
                    >
                      {eq.visible_catalogo
                        ? <Eye className="h-4 w-4" />
                        : <EyeOff className="h-4 w-4" />}
                    </Button>
                    <Button
                      size="icon" variant="ghost"
                      title="Enriquecer con IA (B&H/Adorama)"
                      onClick={() => setEnriching(eq)}
                    >
                      <Sparkles className="h-4 w-4 text-amber" />
                    </Button>
                    <Button
                      size="icon" variant="ghost"
                      onClick={() => { setEditing(eq); setOpenForm(true); }}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      size="icon" variant="ghost"
                      onClick={() => setDeleting(eq)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {openForm && (
        <EquipoFormDialog
          open={openForm}
          onOpenChange={(v) => { setOpenForm(v); if (!v) setEditing(null); }}
          initial={editing}
          saving={saveMut.isPending}
          onSubmit={(data, etiquetas) => saveMut.mutateAsync({ data, etiquetas })}
        />
      )}

      {enriching && (
        <EnriquecerEquipoDialog
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
