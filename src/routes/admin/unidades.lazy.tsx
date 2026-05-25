/**
 * Catálogo global de unidades (lm, K, V, etc.).
 *
 * El dueño edita acá una sola vez y todas las specs tabla con columnas
 * `valor_unidad` pueden referenciar este catálogo para mostrar listas
 * cerradas en el form de carga.
 */

import { createLazyFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Ruler, Search, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import { adminApi, type Unidad, type UnidadInput } from "@/lib/admin/api";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/unidades")({
  component: UnidadesPage,
});

function UnidadesPage() {
  useDocumentTitle("Unidades · Back Office");
  const qc = useQueryClient();
  const [editing, setEditing] = useState<Unidad | "new" | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<Unidad | null>(null);
  const [search, setSearch] = useState("");

  const listQ = useQuery({
    queryKey: ["admin", "unidades"],
    queryFn: () => adminApi.listUnidades(),
    staleTime: 30_000,
  });

  const delMut = useMutation({
    mutationFn: (id: number) => adminApi.deleteUnidad(id),
    onSuccess: () => {
      toast.success("Unidad borrada");
      qc.invalidateQueries({ queryKey: ["admin", "unidades"] });
      setConfirmDelete(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const items = listQ.data?.items ?? [];

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (u) =>
        u.simbolo.toLowerCase().includes(q) ||
        u.nombre.toLowerCase().includes(q) ||
        (u.dimension ?? "").toLowerCase().includes(q),
    );
  }, [items, search]);

  // Agrupar por dimensión para visualización.
  const grupos = useMemo(() => {
    const map = new Map<string, Unidad[]>();
    for (const u of filtered) {
      const d = u.dimension?.trim() || "_otras";
      const arr = map.get(d) ?? [];
      arr.push(u);
      map.set(d, arr);
    }
    return Array.from(map.entries())
      .sort(([a], [b]) => {
        if (a === "_otras") return 1;
        if (b === "_otras") return -1;
        return a.localeCompare(b);
      })
      .map(([dim, us]) => ({
        dimension: dim === "_otras" ? "Otras" : dim,
        unidades: us.slice().sort((a, b) => a.simbolo.localeCompare(b.simbolo)),
      }));
  }, [filtered]);

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-4xl mx-auto">
      <header className="flex items-end justify-between gap-3">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Back-office › Specs
          </div>
          <h1 className="font-display text-3xl text-ink flex items-center gap-2">
            <Ruler className="h-6 w-6 text-amber" />
            Unidades
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            Catálogo global de unidades (lm, K, V…). Las specs tipo tabla con columnas valor+unidad
            pueden referenciar este catálogo para mostrar listas cerradas en lugar de input libre.
          </p>
        </div>
        <Button onClick={() => setEditing("new")}>
          <Plus className="h-4 w-4 mr-1" /> Nueva unidad
        </Button>
      </header>

      {listQ.isLoading && <div className="text-sm text-muted-foreground">Cargando…</div>}

      {!listQ.isLoading && items.length === 0 && (
        <div className="rounded-md border hairline border-dashed p-6 text-center text-sm text-muted-foreground">
          No hay unidades todavía. Creá la primera con "Nueva unidad".
        </div>
      )}

      {items.length > 0 && (
        <div className="space-y-3">
          <div className="relative max-w-md">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar por símbolo, nombre o dimensión…"
              className="pl-7 h-8 text-xs"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch("")}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-ink"
                aria-label="Limpiar"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {grupos.length === 0 && (
            <div className="rounded-md border hairline border-dashed p-6 text-center text-sm text-muted-foreground">
              Ningún resultado con esa búsqueda.
            </div>
          )}

          {grupos.map((g) => (
            <div key={g.dimension} className="rounded-md border hairline overflow-hidden">
              <header className="bg-muted/40 px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                {g.dimension} ({g.unidades.length})
              </header>
              <div className="divide-y hairline">
                {g.unidades.map((u) => (
                  <div
                    key={u.id}
                    className="grid grid-cols-[80px_1fr_120px_72px] items-center gap-2 px-3 py-2 text-sm hover:bg-muted/20"
                  >
                    <span className="font-mono text-ink">{u.simbolo}</span>
                    <span className="text-muted-foreground">{u.nombre}</span>
                    <span className="text-[11px] text-muted-foreground italic">
                      {u.dimension ?? "—"}
                    </span>
                    <div className="flex justify-end gap-1">
                      <button
                        onClick={() => setEditing(u)}
                        className="rounded p-1 hover:bg-muted/50"
                        title="Editar"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => setConfirmDelete(u)}
                        className="rounded p-1 hover:bg-destructive/10 text-destructive"
                        title="Borrar"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {editing && (
        <UnidadFormModal
          key={editing === "new" ? "new" : `u-${editing.id}`}
          unidad={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            qc.invalidateQueries({ queryKey: ["admin", "unidades"] });
            setEditing(null);
          }}
        />
      )}

      {confirmDelete && (
        <AlertDialog open={true} onOpenChange={(o) => !o && setConfirmDelete(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Borrar unidad</AlertDialogTitle>
              <AlertDialogDescription>
                ¿Borrar la unidad <strong>{confirmDelete.simbolo}</strong> ({confirmDelete.nombre})?
                Si alguna spec la estaba usando, queda como string huérfano (no se rompe nada, pero
                el dropdown deja de ofrecerla).
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancelar</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => delMut.mutate(confirmDelete.id)}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                Borrar
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </div>
  );
}

function UnidadFormModal({
  unidad,
  onClose,
  onSaved,
}: {
  unidad: Unidad | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isNew = unidad == null;
  const [form, setForm] = useState<UnidadInput>({
    simbolo: unidad?.simbolo ?? "",
    nombre: unidad?.nombre ?? "",
    dimension: unidad?.dimension ?? "",
  });
  const [busy, setBusy] = useState(false);

  async function handleSave() {
    const simbolo = form.simbolo.trim();
    const nombre = form.nombre.trim();
    if (!simbolo || !nombre) {
      toast.error("Símbolo y nombre son obligatorios");
      return;
    }
    setBusy(true);
    try {
      const payload: UnidadInput = {
        simbolo,
        nombre,
        dimension: form.dimension?.trim() || null,
      };
      if (isNew) {
        await adminApi.createUnidad(payload);
      } else {
        await adminApi.updateUnidad(unidad!.id, payload);
      }
      toast.success(isNew ? "Unidad creada" : "Unidad actualizada");
      onSaved();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-lg bg-background border hairline shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="border-b hairline px-4 py-3">
          <div className="font-display text-base text-ink">
            {isNew ? "Nueva unidad" : "Editar unidad"}
          </div>
        </header>

        <div className="p-4 space-y-3">
          <div className="grid grid-cols-[100px_1fr] gap-3">
            <div>
              <Label className="text-xs">Símbolo</Label>
              <Input
                value={form.simbolo}
                onChange={(e) => setForm({ ...form, simbolo: e.target.value })}
                placeholder="lm, K, V"
                className="font-mono"
              />
            </div>
            <div>
              <Label className="text-xs">Nombre</Label>
              <Input
                value={form.nombre}
                onChange={(e) => setForm({ ...form, nombre: e.target.value })}
                placeholder="Lumen, Kelvin, Voltio"
              />
            </div>
          </div>
          <div>
            <Label className="text-xs">Dimensión (opcional)</Label>
            <Input
              value={form.dimension ?? ""}
              onChange={(e) => setForm({ ...form, dimension: e.target.value })}
              placeholder="luminosidad, temperatura, voltaje…"
            />
            <p className="text-[10px] text-muted-foreground mt-1">
              Sirve para agrupar visualmente las unidades en la pantalla.
            </p>
          </div>
        </div>

        <footer className="border-t hairline px-4 py-3 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancelar
          </Button>
          <Button onClick={handleSave} disabled={busy}>
            {busy ? "Guardando…" : isNew ? "Crear" : "Guardar"}
          </Button>
        </footer>
      </div>
    </div>
  );
}
