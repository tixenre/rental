/**
 * Kit editor del form V2 (drag-and-drop con dnd-kit).
 * Extraído del form principal para reducir su tamaño (#207).
 */

import { useEffect, useState } from "react";
import { Loader2, Plus, Trash2, Search, GripVertical } from "lucide-react";
import { toast } from "sonner";

import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

import { adminApi, type Equipo, type KitComponente } from "@/lib/admin/api";

export function KitEditor({ equipoId }: { equipoId: number }) {
  const [items, setItems] = useState<KitComponente[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<Equipo[]>([]);
  const [searching, setSearching] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const load = async () => {
    setLoading(true);
    try {
      setItems(await adminApi.getKit(equipoId));
    } catch (e) {
      toast.error(`Kit: ${e instanceof Error ? e.message : ""}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(); /* eslint-disable-next-line */
  }, [equipoId]);

  useEffect(() => {
    if (!search.trim() || search.trim().length < 2) {
      setResults([]);
      return;
    }
    const t = setTimeout(async () => {
      setSearching(true);
      try {
        const r = await adminApi.listEquipos({ q: search.trim(), per_page: 15 });
        setResults(r.items.filter((e) => e.id !== equipoId));
      } finally {
        setSearching(false);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [search, equipoId]);

  const add = async (componente_id: number) => {
    setBusy(componente_id);
    try {
      await adminApi.addKitItem(equipoId, componente_id, 1);
      await load();
      setSearch("");
      setResults([]);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(null);
    }
  };
  const updateQty = async (cid: number, cantidad: number) => {
    if (cantidad < 1) return;
    setBusy(cid);
    try {
      await adminApi.addKitItem(equipoId, cid, cantidad);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(null);
    }
  };
  const remove = async (cid: number) => {
    setBusy(cid);
    try {
      await adminApi.removeKitItem(equipoId, cid);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(null);
    }
  };
  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = items.findIndex((i) => i.componente_id === active.id);
    const newIdx = items.findIndex((i) => i.componente_id === over.id);
    if (oldIdx === -1 || newIdx === -1) return;
    const reordered = arrayMove(items, oldIdx, newIdx);
    setItems(reordered);
    try {
      await adminApi.reorderKit(
        equipoId,
        reordered.map((i) => i.componente_id),
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error al reordenar");
      await load();
    }
  };

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar componente por nombre, marca o modelo…"
          className="pl-8"
        />
        {searching && (
          <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 animate-spin text-muted-foreground" />
        )}
      </div>

      {results.length > 0 && (
        <div className="max-h-56 overflow-y-auto rounded-md border hairline divide-y shadow-sm">
          {results.map((r) => (
            <button
              key={r.id}
              type="button"
              className="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-accent text-left disabled:opacity-50"
              onClick={() => add(r.id)}
              disabled={busy === r.id || items.some((i) => i.componente_id === r.id)}
            >
              {r.foto_url ? (
                <img
                  src={r.foto_url}
                  alt=""
                  className="h-7 w-7 object-contain rounded bg-muted/30 shrink-0"
                />
              ) : (
                <div className="h-7 w-7 rounded bg-muted/30 shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <div className="text-sm truncate">{r.nombre}</div>
                <div className="text-[11px] text-muted-foreground truncate">
                  {[r.marca, r.modelo].filter(Boolean).join(" / ")} · stock {r.cantidad}
                </div>
              </div>
              {items.some((i) => i.componente_id === r.id) ? (
                <Badge variant="secondary" className="text-[10px]">
                  en kit
                </Badge>
              ) : (
                <Plus className="h-4 w-4 text-muted-foreground shrink-0" />
              )}
            </button>
          ))}
        </div>
      )}

      <div>
        <Label className="text-xs uppercase tracking-wide text-muted-foreground">
          Componentes ({items.length})
          {items.length > 1 && (
            <span className="ml-1.5 normal-case font-normal text-muted-foreground/60">
              · arrastrá para reordenar
            </span>
          )}
        </Label>

        {loading ? (
          <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Cargando…
          </div>
        ) : items.length === 0 ? (
          <p className="text-xs text-muted-foreground italic mt-2">
            Sin componentes. Usá el buscador de arriba.
          </p>
        ) : (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={items.map((i) => i.componente_id)}
              strategy={verticalListSortingStrategy}
            >
              <div className="space-y-1.5 mt-2">
                {items.map((it) => (
                  <SortableKitItem
                    key={it.componente_id}
                    item={it}
                    busy={busy}
                    onUpdateQty={updateQty}
                    onRemove={remove}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </div>
    </div>
  );
}

function SortableKitItem({
  item,
  busy,
  onUpdateQty,
  onRemove,
}: {
  item: KitComponente;
  busy: number | null;
  onUpdateQty: (id: number, qty: number) => void;
  onRemove: (id: number) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: item.componente_id,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 rounded-md border hairline px-2 py-1.5 bg-background"
    >
      <button
        type="button"
        className="cursor-grab active:cursor-grabbing text-muted-foreground/50 hover:text-muted-foreground touch-none"
        {...attributes}
        {...listeners}
        tabIndex={-1}
      >
        <GripVertical className="h-4 w-4" />
      </button>

      {item.foto_url ? (
        <img
          src={item.foto_url}
          alt=""
          className="h-8 w-8 object-contain rounded bg-muted/30 shrink-0"
        />
      ) : (
        <div className="h-8 w-8 rounded bg-muted/30 shrink-0" />
      )}

      <div className="flex-1 min-w-0">
        <div className="text-sm truncate">{item.nombre}</div>
        {item.marca && <div className="text-[11px] text-muted-foreground">{item.marca}</div>}
      </div>

      <Input
        type="number"
        min={1}
        value={item.cantidad}
        className="w-16 h-8 text-center"
        onChange={(e) =>
          onUpdateQty(item.componente_id, Math.max(1, parseInt(e.target.value || "1", 10)))
        }
        disabled={busy === item.componente_id}
      />
      <Button
        type="button"
        size="icon"
        variant="ghost"
        onClick={() => onRemove(item.componente_id)}
        disabled={busy === item.componente_id}
      >
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  );
}
