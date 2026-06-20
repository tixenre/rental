/**
 * Base editor de componentes reutilizado por KitEditor y ComboEditor.
 * Modo "combo" agrega las columnas descuento_pct y esencial.
 */

import { useEffect, useState } from "react";
import {
  Loader2,
  Plus,
  Trash2,
  Search,
  GripVertical,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
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

type Mode = "kit" | "combo";

type UpdatePatch = { cantidad?: number; descuento_pct?: number | null; esencial?: boolean };

const MODE_CONFIG = {
  kit: {
    errorPrefix: "Kit",
    placeholder: "Buscar componente por nombre, marca o modelo…",
    badgeText: "en kit",
  },
  combo: {
    errorPrefix: "Combo",
    placeholder: "Buscar equipo o kit para agregar al combo…",
    badgeText: "en combo",
  },
} as const;

export function KitComponentEditor({ equipoId, mode }: { equipoId: number; mode: Mode }) {
  const [items, setItems] = useState<KitComponente[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<Equipo[]>([]);
  const [searching, setSearching] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);

  const cfg = MODE_CONFIG[mode];

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const load = async () => {
    setLoading(true);
    try {
      setItems(await adminApi.getKit(equipoId));
    } catch (e) {
      toast.error(`${cfg.errorPrefix}: ${e instanceof Error ? e.message : ""}`);
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
      await adminApi.addKitItem(
        equipoId,
        componente_id,
        1,
        null,
        mode === "combo" ? true : undefined,
      );
      await load();
      setSearch("");
      setResults([]);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(null);
    }
  };

  const update = async (cid: number, patch: UpdatePatch) => {
    const item = items.find((i) => i.componente_id === cid);
    if (!item) return;
    const cantidad = patch.cantidad ?? item.cantidad;
    if (cantidad < 1) return;
    setBusy(cid);
    try {
      if (mode === "combo") {
        const descuento_pct =
          "descuento_pct" in patch ? patch.descuento_pct : (item.descuento_pct ?? null);
        const esencial = "esencial" in patch ? (patch.esencial ?? true) : (item.esencial ?? true);
        await adminApi.addKitItem(equipoId, cid, cantidad, descuento_pct, esencial);
      } else {
        await adminApi.addKitItem(equipoId, cid, cantidad);
      }
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
          placeholder={cfg.placeholder}
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
                  loading="lazy"
                  decoding="async"
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
                  {cfg.badgeText}
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
        {mode === "combo" && (
          <p className="text-[11px] text-muted-foreground mt-0.5 mb-2">
            <strong>Esencial</strong>: si falta, el combo no está disponible.{" "}
            <strong>Best-effort</strong>: si falta, el combo igual se puede reservar.
          </p>
        )}

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
                  <SortableItem
                    key={it.componente_id}
                    item={it}
                    mode={mode}
                    busy={busy}
                    onUpdate={update}
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

function SortableItem({
  item,
  mode,
  busy,
  onUpdate,
  onRemove,
}: {
  item: KitComponente;
  mode: Mode;
  busy: number | null;
  onUpdate: (id: number, patch: UpdatePatch) => void;
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

  const esencial = item.esencial ?? true;
  const descuento = item.descuento_pct ?? 0;

  if (mode === "kit") {
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
            loading="lazy"
            decoding="async"
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
            onUpdate(item.componente_id, {
              cantidad: Math.max(1, parseInt(e.target.value || "1", 10)),
            })
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

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="rounded-md border hairline px-2 py-1.5 bg-background space-y-1.5"
    >
      {/* Row 1: drag + foto + nombre + remove */}
      <div className="flex items-center gap-2">
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
            loading="lazy"
            decoding="async"
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

        <Button
          type="button"
          size="icon"
          variant="ghost"
          onClick={() => onRemove(item.componente_id)}
          disabled={busy === item.componente_id}
          className="shrink-0"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Row 2: cantidad + descuento + esencial */}
      <div className="flex items-center gap-2 pl-6">
        <div className="flex items-center gap-1">
          <span className="text-[11px] text-muted-foreground w-14">Cant.</span>
          <Input
            type="number"
            min={1}
            value={item.cantidad}
            className="w-16 h-7 text-center text-sm"
            onChange={(e) =>
              onUpdate(item.componente_id, {
                cantidad: Math.max(1, parseInt(e.target.value || "1", 10)),
              })
            }
            disabled={busy === item.componente_id}
          />
        </div>

        <div className="flex items-center gap-1">
          <span className="text-[11px] text-muted-foreground w-16">Descuento</span>
          <div className="flex items-center gap-0.5">
            <Input
              type="number"
              min={0}
              max={100}
              step={1}
              value={descuento}
              className="w-16 h-7 text-center text-sm"
              onChange={(e) =>
                onUpdate(item.componente_id, {
                  descuento_pct: Math.max(0, Math.min(100, parseFloat(e.target.value || "0"))),
                })
              }
              disabled={busy === item.componente_id}
            />
            <span className="text-xs text-muted-foreground">%</span>
          </div>
        </div>

        <button
          type="button"
          title={
            esencial
              ? "Esencial — click para cambiar a best-effort"
              : "Best-effort — click para cambiar a esencial"
          }
          onClick={() => onUpdate(item.componente_id, { esencial: !esencial })}
          disabled={busy === item.componente_id}
          className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] border hairline hover:bg-accent transition-colors disabled:opacity-50"
        >
          {esencial ? (
            <>
              <ShieldCheck className="h-3.5 w-3.5 text-verde" />
              <span className="text-verde font-medium">Esencial</span>
            </>
          ) : (
            <>
              <ShieldAlert className="h-3.5 w-3.5 text-amber" />
              <span className="text-amber font-medium">Best-effort</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
