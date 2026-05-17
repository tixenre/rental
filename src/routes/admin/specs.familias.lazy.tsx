import { createLazyFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import {
  Network, Plus, Pencil, Trash2, Loader2, ArrowUp, ArrowDown,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { adminApi } from "@/lib/admin/api";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/specs/familias")({
  component: FamiliasPage,
});

function FamiliasPage() {
  useDocumentTitle("Familias jerárquicas · Back Office");
  const qc = useQueryClient();
  const listQ = useQuery({
    queryKey: ["admin", "spec-familias"],
    queryFn: () => adminApi.listSpecFamilias(),
    staleTime: 30_000,
  });

  const [editing, setEditing] = useState<
    | { mode: "create"; familia: string }
    | { mode: "edit"; id: number; familia: string; valor: string; posicion: number }
    | null
  >(null);

  const createMut = useMutation({
    mutationFn: (input: { familia: string; valor: string; posicion: number }) =>
      adminApi.createSpecFamiliaItem(input),
    onSuccess: () => {
      toast.success("Item agregado");
      qc.invalidateQueries({ queryKey: ["admin", "spec-familias"] });
      setEditing(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, input }: { id: number; input: Record<string, unknown> }) =>
      adminApi.updateSpecFamiliaItem(id, input),
    onSuccess: () => {
      toast.success("Item actualizado");
      qc.invalidateQueries({ queryKey: ["admin", "spec-familias"] });
      setEditing(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => adminApi.deleteSpecFamiliaItem(id),
    onSuccess: () => {
      toast.success("Item borrado");
      qc.invalidateQueries({ queryKey: ["admin", "spec-familias"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const grupos = listQ.data?.items ?? [];

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-4xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office › Specs
        </div>
        <h1 className="font-display text-3xl text-ink flex items-center gap-2">
          <Network className="h-6 w-6 text-amber" />
          Familias jerárquicas
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          Cuando un valor de spec multi_enum tiene jerarquía
          (HDMI 1.4 → 2.0 → 2.1, SDI 3G → 6G → 12G), el motor de
          compatibilidad usa estas tablas para sugerir "ambos hablan
          la versión mínima común". Editable: agregá una versión nueva
          (HDMI 2.1a) o una familia entera (USB-C, DisplayPort) sin
          tocar código.
        </p>
      </header>

      {listQ.isLoading && (
        <div className="rounded-md border hairline px-4 py-6 text-center text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin mx-auto mb-1" />
          Cargando…
        </div>
      )}

      {!listQ.isLoading && grupos.length === 0 && (
        <div className="rounded-md border hairline border-dashed p-6 text-center text-sm text-muted-foreground">
          No hay familias todavía. Disparamos en la migración a5c2e4f8b1d6
          (HDMI/SDI) — si esta página está vacía, corré
          <code className="font-mono mx-1">alembic upgrade head</code>.
        </div>
      )}

      <div className="space-y-4">
        {grupos.map((g) => (
          <FamiliaSection
            key={g.familia}
            familia={g.familia}
            items={g.items}
            onAdd={() => setEditing({ mode: "create", familia: g.familia })}
            onEdit={(it) => setEditing({
              mode: "edit",
              id: it.id,
              familia: g.familia,
              valor: it.valor,
              posicion: it.posicion,
            })}
            onDelete={(id) => {
              if (window.confirm("¿Borrar este valor de la familia?")) {
                deleteMut.mutate(id);
              }
            }}
            onMove={(id, delta) => {
              const it = g.items.find((x) => x.id === id);
              if (!it) return;
              updateMut.mutate({ id, input: { posicion: it.posicion + delta } });
            }}
          />
        ))}
      </div>

      <Button
        size="sm"
        variant="outline"
        onClick={() => setEditing({ mode: "create", familia: "" })}
      >
        <Plus className="h-3.5 w-3.5 mr-1" />
        Nueva familia
      </Button>

      {editing && (
        <EditorModal
          editing={editing}
          onClose={() => setEditing(null)}
          onSave={(input) => {
            if (editing.mode === "create") {
              createMut.mutate(input);
            } else {
              updateMut.mutate({
                id: editing.id,
                input: {
                  familia: input.familia,
                  valor: input.valor,
                  posicion: input.posicion,
                },
              });
            }
          }}
          busy={createMut.isPending || updateMut.isPending}
        />
      )}
    </div>
  );
}

function FamiliaSection({
  familia,
  items,
  onAdd,
  onEdit,
  onDelete,
  onMove,
}: {
  familia: string;
  items: Array<{ id: number; valor: string; posicion: number; spec_def_id: number | null }>;
  onAdd: () => void;
  onEdit: (it: { id: number; valor: string; posicion: number }) => void;
  onDelete: (id: number) => void;
  onMove: (id: number, delta: number) => void;
}) {
  return (
    <section className="rounded-md border hairline overflow-hidden">
      <header className="bg-muted/30 px-3 py-2 border-b hairline flex items-center justify-between">
        <h2 className="font-mono text-sm uppercase tracking-wider text-ink">
          {familia}
        </h2>
        <Button size="sm" variant="outline" onClick={onAdd} className="h-7 px-2">
          <Plus className="h-3.5 w-3.5 mr-1" /> Agregar valor
        </Button>
      </header>
      <div className="divide-y hairline">
        {items.map((it, idx) => (
          <div key={it.id} className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted/20">
            <Badge variant="outline" className="text-[10px] w-10 justify-center">
              {it.posicion}
            </Badge>
            <span className="flex-1 font-mono">{it.valor}</span>
            <div className="flex items-center gap-0.5">
              <button
                type="button"
                onClick={() => onMove(it.id, -1)}
                disabled={idx === 0}
                className="p-1 rounded hover:bg-muted/50 disabled:opacity-30"
                title="Subir (menos capaz)"
              >
                <ArrowUp className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => onMove(it.id, 1)}
                disabled={idx === items.length - 1}
                className="p-1 rounded hover:bg-muted/50 disabled:opacity-30"
                title="Bajar (más capaz)"
              >
                <ArrowDown className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => onEdit({ id: it.id, valor: it.valor, posicion: it.posicion })}
                className="p-1 rounded hover:bg-muted/50"
                title="Editar"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => onDelete(it.id)}
                className="p-1 rounded hover:bg-destructive/10 text-destructive"
                title="Borrar"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function EditorModal({
  editing,
  onClose,
  onSave,
  busy,
}: {
  editing:
    | { mode: "create"; familia: string }
    | { mode: "edit"; id: number; familia: string; valor: string; posicion: number };
  onClose: () => void;
  onSave: (input: { familia: string; valor: string; posicion: number }) => void;
  busy: boolean;
}) {
  const [familia, setFamilia] = useState(editing.familia);
  const [valor, setValor] = useState(editing.mode === "edit" ? editing.valor : "");
  const [posicion, setPosicion] = useState(
    editing.mode === "edit" ? editing.posicion : 0,
  );

  function handleSave() {
    const f = familia.trim().toLowerCase();
    const v = valor.trim();
    if (!f || !v) {
      toast.error("Familia y valor son obligatorios");
      return;
    }
    onSave({ familia: f, valor: v, posicion });
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-lg bg-background border hairline shadow-lg p-4 space-y-3"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="border-b hairline pb-2">
          <div className="font-display text-base text-ink">
            {editing.mode === "create" ? "Nueva entry" : "Editar entry"}
          </div>
        </header>
        <div className="space-y-3">
          <div>
            <Label className="text-xs">Familia</Label>
            <Input
              value={familia}
              onChange={(e) => setFamilia(e.target.value)}
              placeholder="ej. hdmi, sdi, usb_c"
              className="font-mono"
            />
            <p className="text-[10px] text-muted-foreground mt-1">
              Lowercase. Si la familia es nueva (no aparece todavía), se crea
              automáticamente al guardar.
            </p>
          </div>
          <div>
            <Label className="text-xs">Valor</Label>
            <Input
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              placeholder="ej. HDMI 2.1"
              className="font-mono"
            />
          </div>
          <div>
            <Label className="text-xs">Posición</Label>
            <Input
              type="number"
              value={posicion}
              onChange={(e) => setPosicion(parseInt(e.target.value || "0", 10))}
            />
            <p className="text-[10px] text-muted-foreground mt-1">
              Mayor posición = versión más capaz. Ej: HDMI 1.4=0, 2.0=1, 2.1=2.
            </p>
          </div>
        </div>
        <footer className="flex justify-end gap-2 pt-2 border-t hairline">
          <Button size="sm" variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button size="sm" onClick={handleSave} disabled={busy}>
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Guardar"}
          </Button>
        </footer>
      </div>
    </div>
  );
}
