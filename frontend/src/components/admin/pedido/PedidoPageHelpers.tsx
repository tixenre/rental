import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Building2, Check, ChevronLeft, GripVertical, Tag, X } from "lucide-react";
import { toast } from "sonner";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { Button } from "@/design-system/ui/button";
import { IconButton } from "@/design-system/ui/icon-button";
import { Input } from "@/design-system/ui/input";
import { DraftNumberInput } from "@/design-system/ui/draft-number-input";
import { QtyInput } from "@/design-system/ui/qty-input";
import { cn } from "@/lib/utils";
import { adminApi } from "@/lib/admin/api";
import { formatARS, formatFechaCorta, fmtArs } from "@/lib/format";
import { type DraftItem, subtotalDraftItem } from "@/components/admin/pedido/usePedidoDraft";
import { EquipoThumb } from "@/components/admin/pedido/EquipoThumb";

export function PagoRow({
  pago,
  pedidoId,
}: {
  pago: {
    id: number;
    monto: number;
    concepto: string | null;
    fecha: string;
    anulado?: boolean;
    anulado_motivo?: string | null;
  };
  pedidoId: number;
}) {
  const qc = useQueryClient();
  const delMut = useMutation({
    mutationFn: (motivo: string) => adminApi.anularPago(pedidoId, pago.id, motivo),
    onSuccess: () => {
      toast.success("Pago anulado");
      qc.invalidateQueries({ queryKey: ["admin", "pedido", pedidoId] });
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div
      className={cn("flex items-center justify-between text-xs mt-1", pago.anulado && "opacity-50")}
    >
      <span className="text-muted-foreground">
        <span className={cn(pago.anulado && "line-through")}>
          {pago.concepto || "Pago"} · {formatFechaCorta(pago.fecha)}
        </span>
        {pago.anulado && pago.anulado_motivo && (
          <span className="text-destructive"> · Anulado: {pago.anulado_motivo}</span>
        )}
      </span>
      <div className="flex items-center gap-1">
        <span className={cn("font-mono", pago.anulado && "line-through")}>
          {formatARS(pago.monto)}
        </span>
        {!pago.anulado && (
          <IconButton
            aria-label="Anular pago"
            size="xs"
            onClick={() => {
              const motivo = window.prompt("Motivo de la anulación del pago:");
              if (motivo && motivo.trim()) delMut.mutate(motivo.trim());
            }}
            disabled={delMut.isPending}
            className="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
          >
            <X className="h-3 w-3" />
          </IconButton>
        )}
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
  /** Libres del equipo tras TODO el draft (backend, expansión de kits incluida).
   *  Con signo: negativo = faltan unidades. undefined = sin dato (sin fechas). */
  stock?: number;
  jornadas: number;
  updateItem: (uid: string, patch: Partial<DraftItem>) => void;
  removeItem: (uid: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: it.uid,
  });
  const esLibre = it.equipo_id == null;
  // El backend ya descontó el draft completo (incluida esta línea y los kits
  // que consumen sus componentes) — acá NO se resta nada más.
  const disponible = stock;
  const overstock = disponible !== undefined && disponible < 0;
  const subtotal = subtotalDraftItem(it, jornadas);

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
        <IconButton
          aria-label="Reordenar línea"
          size="lg"
          className="-ml-2 w-9 shrink-0 text-muted-foreground/60 hover:text-ink cursor-grab touch-none active:cursor-grabbing"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-4 w-4" />
        </IconButton>
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
              <div className="mt-0.5 flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
                {it.marca && <span className="truncate">{it.marca}</span>}
                {disponible !== undefined && (
                  <span
                    className={cn(
                      "inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-2xs",
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
        <QtyInput
          value={it.cantidad}
          onChange={(v) => updateItem(it.uid, { cantidad: v })}
          min={1}
          error={overstock}
        />

        {/* Precio editable por jornada */}
        <div className="flex items-center gap-1">
          <DraftNumberInput
            min={0}
            value={it.precio_jornada}
            ariaLabel="Precio por jornada"
            onCommit={(v) => updateItem(it.uid, { precio_jornada: v })}
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
              <option value="jornada">/jornada</option>
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
        <IconButton
          aria-label="Quitar línea"
          onClick={() => removeItem(it.uid)}
          className="shrink-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
        >
          <X className="h-4 w-4" />
        </IconButton>
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
    saved: { tx: "Guardado", cls: "text-verde-ink" },
    dirty: { tx: "Sin guardar", cls: "text-muted-foreground" },
    error: { tx: "Error al guardar", cls: "text-destructive" },
    idle: { tx: "", cls: "" },
  };
  const s = map[status] ?? map.idle;
  if (!s.tx) return null;
  return (
    <span className={cn("inline-flex items-center gap-1 font-mono text-xs", s.cls)}>
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

/** "Facturar a nombre de" (#1251) — el renter sigue siendo `cliente_id`; esto
 * solo elige a quién se factura: la cuenta default, un perfil fiscal personal,
 * o una productora vinculada al cliente. Mismo patrón que el selector del
 * checkout (`CheckoutResumen.tsx`), reusado acá para el admin. Solo se
 * renderiza si el pedido tiene cliente Y ese cliente tiene más de una opción
 * (si no hay nada para elegir, no tiene sentido mostrar el selector). */
export function FacturacionTargetSection({
  clienteId,
  perfilFiscalId,
  productoraId,
  onChange,
}: {
  clienteId: number | null;
  perfilFiscalId: number | null;
  productoraId: number | null;
  onChange: (v: { perfilFiscalId: number | null; productoraId: number | null }) => void;
}) {
  const q = useQuery({
    queryKey: ["admin", "cliente-perfiles-fiscales", clienteId],
    queryFn: () => adminApi.getClientePerfilesFiscales(clienteId!),
    enabled: !!clienteId,
  });
  const perfiles = q.data?.perfiles ?? [];
  // Excluye productoras BORRADOR (sin CUIT, #1251 Fase 3) — no son facturables,
  // mismo criterio que `productoras_vinculadas(solo_facturables=True)` del checkout.
  const productoras = (q.data?.productoras ?? []).filter((pr) => pr.cuit);
  if (!clienteId || perfiles.length + productoras.length === 0) return null;

  return (
    <Section icon={Building2} title="Facturar a nombre de">
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm text-ink">
          <input
            type="radio"
            name="pedido-facturacion-target"
            checked={!perfilFiscalId && !productoraId}
            onChange={() => onChange({ perfilFiscalId: null, productoraId: null })}
          />
          Cuenta del cliente (default)
        </label>
        {perfiles.map((p) => (
          <label key={`perfil-${p.id}`} className="flex items-center gap-2 text-sm text-ink">
            <input
              type="radio"
              name="pedido-facturacion-target"
              checked={perfilFiscalId === p.id}
              onChange={() => onChange({ perfilFiscalId: p.id, productoraId: null })}
            />
            {p.etiqueta || p.razon_social || p.cuit}
          </label>
        ))}
        {productoras.map((pr) => (
          <label key={`productora-${pr.id}`} className="flex items-center gap-2 text-sm text-ink">
            <input
              type="radio"
              name="pedido-facturacion-target"
              checked={productoraId === pr.id}
              onChange={() => onChange({ perfilFiscalId: null, productoraId: pr.id })}
            />
            {pr.nombre || pr.razon_social || pr.cuit}
          </label>
        ))}
      </div>
    </Section>
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
      <span className="block t-eyebrow mb-1">{label}</span>
      {children}
    </label>
  );
}

export function RailSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="t-eyebrow mb-2">{label}</div>
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
