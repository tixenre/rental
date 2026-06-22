import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, ChevronLeft, GripVertical, Minus, Plus, Tag, X } from "lucide-react";
import { toast } from "sonner";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { cn } from "@/lib/utils";
import { adminApi } from "@/lib/admin/api";
import { formatARS, formatFechaCorta, fmtArs } from "@/lib/format";
import { type DraftItem } from "@/components/admin/pedido/usePedidoDraft";
import { EquipoThumb } from "@/components/admin/pedido/EquipoThumb";

export function PagoRow({
  pago,
  pedidoId,
}: {
  pago: { id: number; monto: number; concepto: string | null; fecha: string };
  pedidoId: number;
}) {
  const qc = useQueryClient();
  const delMut = useMutation({
    mutationFn: () => adminApi.deletePago(pedidoId, pago.id),
    onSuccess: () => {
      toast.success("Pago eliminado");
      qc.invalidateQueries({ queryKey: ["admin", "pedido", pedidoId] });
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="flex items-center justify-between text-xs mt-1">
      <span className="text-muted-foreground">
        {pago.concepto || "Pago"} · {formatFechaCorta(pago.fecha)}
      </span>
      <div className="flex items-center gap-1">
        <span className="font-mono">{formatARS(pago.monto)}</span>
        <button
          type="button"
          onClick={() => delMut.mutate()}
          disabled={delMut.isPending}
          className="rounded p-1 text-muted-foreground hover:text-destructive transition"
          aria-label="Eliminar pago"
        >
          <X className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}

/** Fila de línea del pedido, arrastrable para reordenar (#806). El handle (grip)
 * lleva los listeners del drag; el resto queda libre para editar. Soporta líneas
 * de catálogo (equipo_id) y líneas personalizadas (#805, equipo_id null): nombre
 * libre + toggle de modo de cobro (fijo / por jornada). */
export function ItemRow({
  it,
  stock,
  jornadas,
  updateItem,
  removeItem,
}: {
  it: DraftItem;
  stock?: { cantidad: number; reservado: number };
  jornadas: number;
  updateItem: (uid: string, patch: Partial<DraftItem>) => void;
  removeItem: (uid: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: it.uid,
  });
  const esLibre = it.equipo_id == null;
  const fijo = (it.cobro_modo ?? "jornada") === "fijo";
  const max = stock ? Math.max(0, stock.cantidad - stock.reservado) : it.cantidad;
  const disponible = max - it.cantidad;
  const overstock = it.cantidad > max && !!stock;
  // Subtotal: las líneas 'fijo' no multiplican por jornadas (espeja bruto_linea del backend).
  const subtotal = it.precio_jornada * it.cantidad * (fijo ? 1 : Math.max(1, jornadas));

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(
        "flex flex-wrap items-center gap-x-3 gap-y-2 py-2.5 bg-surface",
        isDragging && "opacity-60",
      )}
    >
      {/* Identidad: grip + foto + nombre/meta (crece y ocupa el ancho sobrante) */}
      <div className="flex min-w-[200px] flex-1 items-center gap-2">
        <button
          type="button"
          aria-label="Reordenar línea"
          className="inline-flex h-11 w-9 -ml-2 shrink-0 items-center justify-center text-muted-foreground/60 hover:text-ink cursor-grab touch-none active:cursor-grabbing"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-4 w-4" />
        </button>
        {esLibre ? (
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-dashed hairline text-muted-foreground/60">
            <Tag className="h-4 w-4" />
          </div>
        ) : (
          <EquipoThumb
            src={it.foto_url}
            alt={it.nombre_publico || it.nombre}
            className="h-10 w-10 shrink-0"
          />
        )}
        <div className="min-w-0 flex-1">
          {esLibre ? (
            <Input
              value={it.nombre_libre ?? ""}
              placeholder="Descripción (ej. Flete, Operador…)"
              onChange={(e) => updateItem(it.uid, { nombre_libre: e.target.value })}
              className="h-8 text-sm"
            />
          ) : (
            <>
              <div className="text-sm text-ink truncate">{it.nombre_publico || it.nombre}</div>
              <div className="mt-0.5 flex items-center gap-1.5 font-mono text-[11px] text-muted-foreground">
                {it.marca && <span className="truncate">{it.marca}</span>}
                {stock && (
                  <span
                    className={cn(
                      "inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[10px]",
                      disponible <= 0
                        ? "bg-destructive/10 text-destructive"
                        : "bg-muted text-muted-foreground",
                    )}
                  >
                    {disponible <= 0 ? `${disponible} restante` : `${disponible} libres`}
                  </span>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Controles: cantidad · precio · subtotal · quitar (alineados en columna) */}
      <div className="ml-auto flex flex-wrap items-center justify-end gap-x-2 gap-y-1.5">
        {/* Stepper de cantidad */}
        <div className="flex items-center gap-1">
          <Button
            size="icon"
            variant="outline"
            className="h-9 w-9"
            aria-label="Restar uno"
            onClick={() => updateItem(it.uid, { cantidad: Math.max(1, it.cantidad - 1) })}
          >
            <Minus className="h-3 w-3" />
          </Button>
          <Input
            type="number"
            min={1}
            value={it.cantidad}
            aria-label="Cantidad"
            onChange={(e) => updateItem(it.uid, { cantidad: parseInt(e.target.value) || 1 })}
            className={cn(
              "h-9 w-11 text-center text-sm p-0",
              overstock && "border-destructive text-destructive",
            )}
          />
          <Button
            size="icon"
            variant="outline"
            className="h-9 w-9"
            aria-label="Sumar uno"
            onClick={() => updateItem(it.uid, { cantidad: it.cantidad + 1 })}
          >
            <Plus className="h-3 w-3" />
          </Button>
        </div>

        {/* Precio editable por jornada */}
        <div className="flex items-center gap-1">
          <Input
            type="number"
            min={0}
            value={it.precio_jornada}
            aria-label="Precio por jornada"
            onChange={(e) => updateItem(it.uid, { precio_jornada: parseInt(e.target.value) || 0 })}
            className="h-9 w-24 text-sm"
          />
          {esLibre ? (
            <select
              value={it.cobro_modo ?? "jornada"}
              onChange={(e) =>
                updateItem(it.uid, { cobro_modo: e.target.value as "jornada" | "fijo" })
              }
              className="h-9 rounded-md border hairline bg-surface-elevated px-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
              aria-label="Modo de cobro"
            >
              <option value="jornada">/día</option>
              <option value="fijo">fijo</option>
            </select>
          ) : (
            <span className="text-xs text-muted-foreground whitespace-nowrap">/día</span>
          )}
        </div>

        {/* Subtotal de la línea */}
        <div className="w-24 text-right font-mono text-sm font-semibold tabular-nums text-ink">
          {fmtArs(subtotal)}
        </div>

        {/* Quitar */}
        <button
          type="button"
          onClick={() => removeItem(it.uid)}
          aria-label="Quitar línea"
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:text-destructive"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </li>
  );
}

export function BackLink({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-ink shrink-0"
    >
      <ChevronLeft className="h-4 w-4" /> Pedidos
    </button>
  );
}

export function SaveIndicator({ status }: { status: string }) {
  const map: Record<string, { tx: string; cls: string }> = {
    saving: { tx: "Guardando…", cls: "text-muted-foreground" },
    saved: { tx: "Guardado", cls: "text-verde" },
    dirty: { tx: "Sin guardar", cls: "text-muted-foreground" },
    error: { tx: "Error al guardar", cls: "text-destructive" },
    idle: { tx: "", cls: "" },
  };
  const s = map[status] ?? map.idle;
  if (!s.tx) return null;
  return (
    <span className={cn("inline-flex items-center gap-1 font-mono text-[11px]", s.cls)}>
      {status === "saved" && <Check className="h-3 w-3" />}
      {s.tx}
    </span>
  );
}

export function Section({
  icon: Icon,
  title,
  aside,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border hairline bg-surface-elevated">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b hairline">
        <Icon className="h-4 w-4 text-muted-foreground" />
        <span className="font-medium text-sm text-ink">{title}</span>
        {aside && <span className="ml-auto">{aside}</span>}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

export function FieldLabel({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <label className={cn("block", className)}>
      <span className="block font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
        {label}
      </span>
      {children}
    </label>
  );
}

export function RailSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
        {label}
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

export function BdRow({
  l,
  v,
  neg,
  strong,
}: {
  l: string;
  v: string;
  neg?: boolean;
  strong?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className={cn("text-muted-foreground", strong && "text-ink font-medium")}>{l}</span>
      <span
        className={cn(
          "font-mono tabular-nums",
          neg && "text-destructive",
          strong && "text-ink font-semibold text-base",
        )}
      >
        {v}
      </span>
    </div>
  );
}
