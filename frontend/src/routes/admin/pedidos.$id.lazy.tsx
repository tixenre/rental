import { createLazyFileRoute, useNavigate, useParams, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  User,
  Calendar,
  Box,
  FileText,
  Check,
  AlertTriangle,
  Coins,
  ArrowRight,
  Plus,
  Minus,
  X,
  Mail,
  Eye,
  Download,
  Info,
  Trash2,
  GripVertical,
  Tag,
  ShieldAlert,
  ShieldCheck,
  Copy,
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
import { cn } from "@/lib/utils";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { Textarea } from "@/design-system/ui/textarea";
import { Skeleton } from "@/design-system/ui/skeleton";
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
import { EstadoBadge } from "@/design-system/kit/EstadoBadge";
import { WhatsAppButton } from "@/components/admin/WhatsAppButton";
import {
  adminApi,
  ESTADO_LABEL,
  pedidoPdfUrl,
  type Pedido,
  type PedidoEstado,
  type Equipo,
} from "@/lib/admin/api";
import {
  usePedidoDraft,
  nuevoUidLinea,
  type DraftItem,
} from "@/components/admin/pedido/usePedidoDraft";
import { ClienteAutocomplete } from "@/components/admin/pedido/ClienteAutocomplete";
import { ClienteAvatar } from "@/design-system/kit/ClienteAvatar";
import { EquipoThumb } from "@/components/admin/pedido/EquipoThumb";
import { DateRangePickerModal } from "@/components/rental/DateRangePickerModal";
import { computeJornadas, parseDateTimeParts, toLocalISO } from "@/lib/rental-dates";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { useCotizacion } from "@/lib/cotizacion";
import { useDocumentTitle } from "@/lib/use-document-title";
import { formatARS, formatFechaCorta, fmtArs } from "@/lib/format";
import { nombreCliente } from "@/lib/cliente-nombre";
import { EquipoComboSearch } from "@/components/admin/pedido/EquipoComboSearch";
import { EnviarDocsDialog, DOCS_PEDIDO } from "@/components/admin/pedido/EnviarDocsDialog";
import { RegistrarPagoModal } from "@/components/admin/pedido/RegistrarPagoModal";
import { FLOW, transiciones, nextStep } from "@/lib/pedido-estados";
import {
  PagoRow,
  ItemRow,
  BackLink,
  SaveIndicator,
  Section,
  FieldLabel,
  RailSection,
  BdRow,
} from "@/components/admin/pedido/PedidoPageHelpers";

export const Route = createLazyFileRoute("/admin/pedidos/$id")({
  component: PedidoEditorPage,
});

// La máquina de estados (FLOW / transiciones / blockReason / nextStep) vive en
// @/lib/pedido-estados — fuente única compartida con el panel de detalle de la lista.

// ── Página ───────────────────────────────────────────────────────────────────

function PedidoEditorPage() {
  const { id } = useParams({ from: "/admin/pedidos/$id" });
  const navigate = useNavigate();
  const pedidoId = Number(id);
  useDocumentTitle("Pedido · Back-office");

  const pedidoQ = useQuery({
    queryKey: ["admin", "pedido", pedidoId],
    queryFn: () => adminApi.getPedido(pedidoId),
  });
  const p = pedidoQ.data;
  // keepDateTime: el selector de fechas+horas escribe datetime (con hora) en
  // fecha_desde/fecha_hasta; sin esto el draft las recortaría a date-only y se
  // perdería la hora en el round-trip del autosave.
  const draft = usePedidoDraft(p, { mode: "admin", keepDateTime: true });
  const [openDateModal, setOpenDateModal] = useState(false);

  // Sensores del drag-reorder de líneas (#806). Hook → antes de cualquier
  // early return para no violar las reglas de hooks.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  // Disponibilidad (stock) — enabled cuando hay ambas fechas
  const dispoQ = useQuery({
    queryKey: [
      "admin",
      "disponibilidad",
      draft.datos?.fecha_desde,
      draft.datos?.fecha_hasta,
      pedidoId,
    ],
    queryFn: () =>
      adminApi.getDisponibilidad(draft.datos!.fecha_desde, draft.datos!.fecha_hasta, pedidoId),
    enabled: !!p && !!draft.datos?.fecha_desde && !!draft.datos?.fecha_hasta,
  });

  // Cotización en vivo (useCotizacion) — recalcula al editar items/fechas/descuento
  const cotizacionQ = useCotizacion({
    items: (draft.items ?? []).map((it) => ({
      equipoId: it.equipo_id,
      cantidad: it.cantidad,
      precioJornada: it.precio_jornada,
      cobroModo: it.cobro_modo,
    })),
    fechaDesde: draft.datos?.fecha_desde || null,
    fechaHasta: draft.datos?.fecha_hasta || null,
    clienteId: p?.cliente_id ?? null,
    descuentoPct: draft.datos?.descuento_pct ?? null,
  });

  // Modales
  const [openPagoModal, setOpenPagoModal] = useState(false);
  const [openMailDialog, setOpenMailDialog] = useState(false);
  const [askDelete, setAskDelete] = useState(false);
  const [askCancel, setAskCancel] = useState(false);
  const [askVerif, setAskVerif] = useState(false);
  const [pendingEstado, setPendingEstado] = useState<PedidoEstado | null>(null);
  const [linkVerif, setLinkVerif] = useState<string | null>(null);
  const [generandoLink, setGenerandoLink] = useState(false);
  const [copiadoLink, setCopiadoLink] = useState(false);

  const qc = useQueryClient();
  const deleteMut = useMutation({
    mutationFn: () => adminApi.deletePedido(pedidoId),
    onSuccess: () => {
      toast.success("Pedido eliminado");
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
      navigate({ to: "/admin/pedidos" });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (pedidoQ.isError) {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <BackLink onClick={() => navigate({ to: "/admin/pedidos" })} />
        <div className="mt-4 rounded-md border hairline border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          No se pudo cargar el pedido: {(pedidoQ.error as Error).message}
        </div>
      </div>
    );
  }
  if (pedidoQ.isLoading || !p || !draft.datos || !draft.items) {
    return (
      <div className="p-6 space-y-4 max-w-5xl mx-auto">
        <Skeleton className="h-7 w-64" />
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5">
          <Skeleton className="h-96 w-full rounded-xl" />
          <Skeleton className="h-96 w-full rounded-xl" />
        </div>
      </div>
    );
  }

  const { datos, setDatos, items, setItems, saveStatus, estadoMut } = draft;
  const ns = nextStep(p);

  const clienteSinVerificar = !!p.cliente_id && !p.cliente_dni_validado_at;
  const ESTADOS_CON_AVISO: PedidoEstado[] = ["confirmado", "retirado"];

  const handleNextStep = (target: PedidoEstado) => {
    if (clienteSinVerificar && ESTADOS_CON_AVISO.includes(target)) {
      setPendingEstado(target);
      setAskVerif(true);
    } else {
      estadoMut.mutate(target);
    }
  };

  const handleGenerarLink = async () => {
    if (!p.cliente_id) return;
    setGenerandoLink(true);
    try {
      const r = await adminApi.generarLinkVerificacion(p.cliente_id);
      setLinkVerif(r.url);
    } catch {
      toast.error("No se pudo generar el link de verificación");
    } finally {
      setGenerandoLink(false);
    }
  };

  // Fechas+horas derivadas del draft (vivo). datos.fecha_desde/_hasta vienen
  // como datetime ISO (keepDateTime) o, en pedidos viejos sin hora, date-only
  // → default 09:00. El selector lee de acá y recombina al escribir.
  const { date: startDate, time: startTime } = parseDateTimeParts(datos.fecha_desde);
  const { date: endDate, time: endTime } = parseDateTimeParts(datos.fecha_hasta);

  // Jornadas con el mismo criterio que el carrito (devolver más tarde = +1).
  const jornadas = computeJornadas(startDate, endDate, startTime, endTime);

  // ── Handlers del selector de fechas (modo admin) ──────────────────────
  // Recombinan día+hora a datetime con toLocalISO y persisten vía autosave.
  // Mantienen el clamp fecha_hasta ≥ fecha_desde.
  const handleDatesChange = (start?: Date, end?: Date) => {
    setDatos((d) => {
      if (!d) return d;
      const fecha_desde = start ? toLocalISO(start, startTime) : "";
      let fecha_hasta = end ? toLocalISO(end, endTime) : "";
      if (fecha_desde && fecha_hasta && fecha_hasta < fecha_desde) fecha_hasta = fecha_desde;
      return { ...d, fecha_desde, fecha_hasta };
    });
  };
  const handleStartTimeChange = (t: string) => {
    setDatos((d) => (d && startDate ? { ...d, fecha_desde: toLocalISO(startDate, t) } : d));
  };
  const handleEndTimeChange = (t: string) => {
    setDatos((d) => {
      if (!d || !endDate) return d;
      let fecha_hasta = toLocalISO(endDate, t);
      if (datos.fecha_desde && fecha_hasta < datos.fecha_desde) fecha_hasta = datos.fecha_desde;
      return { ...d, fecha_hasta };
    });
  };

  // Totales vivos desde useCotizacion
  const totales = cotizacionQ.data;
  const total = totales.total;
  const pagadoMonto = p.monto_pagado ?? 0;
  const restante = Math.max(0, total - pagadoMonto);

  // stockMap: { equipo_id → { cantidad: libres, reservado: 0 } }
  const stockMap: Record<string, { cantidad: number; reservado: number }> = Object.fromEntries(
    Object.entries(dispoQ.data ?? {}).map(([k, v]) => [
      k,
      { cantidad: Number(v) || 0, reservado: 0 },
    ]),
  );

  const hasOverstock = items.some((it) => {
    const s = stockMap[String(it.equipo_id)];
    if (!s) return false;
    return it.cantidad > Math.max(0, s.cantidad - s.reservado);
  });

  // Las líneas se identifican por `uid` (las personalizadas no tienen equipo_id).
  const updateItem = (uid: string, patch: Partial<DraftItem>) =>
    setItems((its) => (its ?? []).map((it) => (it.uid === uid ? { ...it, ...patch } : it)));

  const removeItem = (uid: string) => setItems((its) => (its ?? []).filter((it) => it.uid !== uid));

  // Agregar equipo del catálogo (desde el buscador inline). Si ya está en el
  // pedido, suma +1; si no, lo agrega como línea nueva. No cierra el buscador
  // → se pueden cargar varios seguidos.
  const handleAddEquipo = (eq: Equipo) => {
    const display = eq.nombre_publico || eq.nombre;
    const existing = items.find((i) => i.equipo_id === eq.id);
    if (existing) {
      updateItem(existing.uid, { cantidad: existing.cantidad + 1 });
      toast.success(`+1 ${display}`);
    } else {
      setItems((its) => [
        ...(its ?? []),
        {
          uid: `e${eq.id}`,
          equipo_id: eq.id,
          cantidad: 1,
          precio_jornada: eq.precio_jornada ?? 0,
          nombre: eq.nombre,
          marca: eq.marca,
          nombre_publico: eq.nombre_publico ?? null,
          foto_url: eq.foto_url ?? null,
          cobro_modo: "jornada",
        },
      ]);
      toast.success(`Agregado: ${display}`);
    }
  };

  // Agregar línea personalizada (#805): ítem de texto libre, fuera del catálogo.
  const addLineaLibre = () =>
    setItems((its) => [
      ...(its ?? []),
      {
        uid: nuevoUidLinea(),
        equipo_id: null,
        cantidad: 1,
        precio_jornada: 0,
        nombre: "",
        marca: null,
        nombre_libre: "",
        cobro_modo: "jornada",
      },
    ]);

  // Drag-reorder de líneas (#806). El nuevo orden viaja en el array de items;
  // el autosave lo persiste (el backend asigna `orden` por posición). `sensors`
  // es un hook → vive arriba con el resto (declarado antes de los early returns).
  const handleItemsDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    setItems((its) => {
      if (!its) return its;
      const oldIndex = its.findIndex((it) => it.uid === active.id);
      const newIndex = its.findIndex((it) => it.uid === over.id);
      if (oldIndex < 0 || newIndex < 0) return its;
      return arrayMove(its, oldIndex, newIndex);
    });
  };

  const goList = () => navigate({ to: "/admin/pedidos" });

  return (
    <div className="flex flex-col min-h-0">
      {/* Topbar del editor */}
      <header className="flex items-center gap-3 px-4 md:px-6 py-3 border-b hairline bg-surface-elevated">
        <BackLink onClick={goList} />
        <div className="min-w-0 flex items-center gap-2">
          <span className="font-display text-lg text-ink truncate">
            {p.cliente_nombre || "Sin cliente"}
          </span>
          <span className="font-mono text-xs text-muted-foreground">
            #{p.numero_pedido ?? p.id}
          </span>
          <EstadoBadge estado={p.estado} label={ESTADO_LABEL[p.estado]} />
        </div>
        <div className="ml-auto flex items-center gap-2">
          <SaveIndicator status={saveStatus} />
          <WhatsAppButton pedido={p} phone={p.cliente_telefono} variant="icon" />
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-0 lg:gap-0 min-h-0">
        {/* ── Columna de trabajo ── */}
        <div className="px-4 md:px-6 py-5 space-y-5 lg:border-r hairline pb-28 lg:pb-5">
          {/* Banner solicitud pendiente (deferido — solo aviso read-only) */}
          {p.tiene_solicitud_pendiente && (
            <div className="flex items-start gap-2 rounded-lg border border-amber/40 bg-amber/5 px-3 py-2.5 text-sm">
              <Info className="h-4 w-4 text-ink shrink-0 mt-0.5" />
              <div className="min-w-0">
                <span className="font-medium text-ink">Hay una solicitud de cambio pendiente.</span>{" "}
                <Link to="/admin/solicitudes" className="underline text-muted-foreground">
                  Revisarla en Solicitudes
                </Link>
                .
              </div>
            </div>
          )}

          {/* Cliente */}
          <Section icon={User} title="Cliente">
            {/* Buscar ficha existente: al elegirla, el contacto y el descuento
                se completan solos. También se puede tipear a mano abajo (pedido
                sin ficha vinculada). */}
            {datos.cliente_id ? (
              // Cliente vinculado: tarjeta clara de QUIÉN está seleccionado.
              <div className="mb-3 flex items-center gap-3 rounded-lg border border-verde/30 bg-verde/[0.06] px-3 py-2.5">
                <ClienteAvatar nombre={datos.cliente_nombre} className="h-9 w-9 text-sm" />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate font-medium text-ink">
                      {datos.cliente_nombre || "Cliente sin nombre"}
                    </span>
                    <span
                      className={cn(
                        "inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 font-mono text-2xs",
                        p.cliente_dni_validado_at
                          ? "bg-verde/10 text-verde-ink"
                          : "bg-amber/15 text-ink",
                      )}
                    >
                      {p.cliente_dni_validado_at ? (
                        <ShieldCheck className="h-3 w-3" />
                      ) : (
                        <ShieldAlert className="h-3 w-3" />
                      )}
                      {p.cliente_dni_validado_at ? "Verificado" : "Sin verificar"}
                    </span>
                  </div>
                  <div className="mt-0.5 truncate font-mono text-xs text-muted-foreground">
                    {[datos.cliente_email, datos.cliente_telefono].filter(Boolean).join(" · ") ||
                      "sin contacto"}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setDatos((d) => d && { ...d, cliente_id: null })}
                  className="shrink-0 rounded-md border hairline px-2.5 py-1 text-xs text-muted-foreground hover:border-ink hover:text-ink"
                >
                  Desvincular
                </button>
              </div>
            ) : (
              // Sin ficha: buscar una, o cargar el contacto a mano abajo.
              <div className="mb-3">
                <ClienteAutocomplete
                  placeholder="Buscar cliente por nombre, email o teléfono…"
                  onPick={(c) =>
                    setDatos((d) =>
                      d
                        ? {
                            ...d,
                            cliente_id: c.id,
                            cliente_nombre: nombreCliente(c),
                            cliente_email: c.email ?? "",
                            cliente_telefono: c.telefono ?? "",
                            // El descuento sigue al cliente: si el nuevo no tiene
                            // uno propio, se resetea a 0.
                            descuento_pct: c.descuento ?? 0,
                          }
                        : d,
                    )
                  }
                />
                <p className="mt-1.5 font-mono text-xs text-muted-foreground">
                  O cargá el contacto a mano abajo (pedido sin ficha vinculada).
                </p>
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <FieldLabel label="Nombre">
                <Input
                  value={datos.cliente_nombre}
                  onChange={(e) => setDatos((d) => d && { ...d, cliente_nombre: e.target.value })}
                />
              </FieldLabel>
              <FieldLabel label="Teléfono">
                <Input
                  value={datos.cliente_telefono}
                  onChange={(e) => setDatos((d) => d && { ...d, cliente_telefono: e.target.value })}
                />
              </FieldLabel>
              <FieldLabel label="Email" className="sm:col-span-2">
                <Input
                  value={datos.cliente_email}
                  placeholder="—"
                  onChange={(e) => setDatos((d) => d && { ...d, cliente_email: e.target.value })}
                />
              </FieldLabel>
            </div>
          </Section>

          {/* Fechas — editables con re-validación de stock */}
          <Section
            icon={Calendar}
            title="Fechas del alquiler"
            aside={
              !datos.fecha_desde || !datos.fecha_hasta ? (
                <span className="inline-flex items-center gap-1 font-mono text-2xs uppercase tracking-[0.2em] text-destructive">
                  <AlertTriangle className="h-3 w-3" /> sin fechas
                </span>
              ) : hasOverstock ? (
                <span className="inline-flex items-center gap-1 font-mono text-2xs uppercase tracking-[0.2em] text-destructive">
                  <AlertTriangle className="h-3 w-3" /> revisar stock
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 font-mono text-2xs uppercase tracking-[0.2em] text-verde-ink">
                  <Check className="h-3 w-3" /> stock OK
                </span>
              )
            }
          >
            {/* Píldora retiro→devolución — abre el selector de fechas+horas */}
            <button
              type="button"
              onClick={() => setOpenDateModal(true)}
              className="flex w-full items-center gap-3 rounded-lg border hairline bg-surface-elevated px-3.5 py-2.5 text-left transition hover:border-ink min-h-[44px]"
            >
              {startDate && endDate ? (
                <>
                  <Calendar className="h-4 w-4 text-muted-foreground shrink-0" />
                  <div className="min-w-0 flex-1 flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-sm tabular-nums text-ink">
                      {format(startDate, "dd MMM yyyy", { locale: es })} · {startTime}
                    </span>
                    <ArrowRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span className="font-mono text-sm tabular-nums text-ink">
                      {format(endDate, "dd MMM yyyy", { locale: es })} · {endTime}
                    </span>
                  </div>
                  <span className="ml-auto rounded-md border hairline bg-background px-2.5 py-1 text-center shrink-0">
                    <span className="font-mono text-base font-semibold leading-none">
                      {jornadas}
                    </span>
                    <span className="t-eyebrow ml-1">
                      {jornadas === 1 ? "jornada" : "jornadas"}
                    </span>
                  </span>
                </>
              ) : (
                <>
                  <Calendar className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span className="text-sm text-muted-foreground">
                    Elegí las fechas de retiro y devolución…
                  </span>
                </>
              )}
            </button>
          </Section>

          {/* Equipos */}
          <Section icon={Box} title={`Equipos · ${items.length}`}>
            {/* Buscador inline: resultados en dropdown debajo (no tapa el form) */}
            <EquipoComboSearch
              existing={items}
              stockMap={stockMap}
              onAdd={handleAddEquipo}
              className="mb-2"
            />

            {items.length === 0 ? (
              <ul className="divide-y hairline">
                <li className="py-4 text-sm text-muted-foreground">
                  Sin equipos. Agregá al menos uno para confirmar.
                </li>
              </ul>
            ) : (
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={handleItemsDragEnd}
              >
                <SortableContext
                  items={items.map((it) => it.uid)}
                  strategy={verticalListSortingStrategy}
                >
                  <ul className="divide-y hairline">
                    {items.map((it) => (
                      <ItemRow
                        key={it.uid}
                        it={it}
                        stock={it.equipo_id != null ? stockMap[String(it.equipo_id)] : undefined}
                        jornadas={jornadas}
                        updateItem={updateItem}
                        removeItem={removeItem}
                      />
                    ))}
                  </ul>
                </SortableContext>
              </DndContext>
            )}

            {/* Agregar línea personalizada (#805): ítem libre fuera del catálogo */}
            <button
              type="button"
              onClick={addLineaLibre}
              className="mt-2 flex w-full items-center gap-2.5 px-3 py-2.5 rounded-md border border-dashed hairline text-sm text-muted-foreground hover:bg-muted/30 transition"
            >
              <Plus className="h-4 w-4 shrink-0" />
              <span>Agregar línea personalizada (flete, servicio, etc.)</span>
            </button>
          </Section>

          {/* Notas */}
          <Section icon={FileText} title="Notas internas">
            <Textarea
              value={datos.notas}
              placeholder="Notas para el equipo de Rambla…"
              onChange={(e) => setDatos((d) => d && { ...d, notas: e.target.value })}
              className="min-h-[88px] resize-y"
            />
          </Section>
        </div>

        {/* ── Rail ── (visible en lg en el lado derecho; en mobile fluye debajo) */}
        <aside className="px-4 md:px-5 py-5 space-y-4 bg-surface/40 lg:border-t-0 border-t hairline pb-28 lg:pb-5">
          {/* Estado */}
          <RailSection label="Estado del pedido">
            <FlowStrip estado={p.estado} />
            {ns && (
              <Button
                variant={ns.blocked ? "outline" : "amber"}
                className="w-full"
                disabled={!!ns.blocked || estadoMut.isPending}
                title={ns.blocked ?? ""}
                onClick={() => !ns.blocked && handleNextStep(ns.target)}
              >
                <ArrowRight className="h-4 w-4 mr-1" />
                {ns.blocked ? `Falta: ${ns.blocked}` : ns.label}
              </Button>
            )}
          </RailSection>

          {/* Identidad del cliente (solo cuando tiene ficha vinculada sin verificar) */}
          {clienteSinVerificar && (
            <RailSection label="Identidad del cliente">
              <div className="flex items-center gap-1.5 text-ink text-sm mb-2">
                <ShieldAlert className="h-4 w-4 shrink-0" />
                <span>Sin verificar</span>
              </div>
              {linkVerif ? (
                <div className="space-y-1.5">
                  <p className="text-xs text-muted-foreground">Mandá este link al cliente:</p>
                  <div className="flex items-center gap-2">
                    <Input
                      readOnly
                      value={linkVerif}
                      className="flex-1 font-mono text-xs truncate"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        void navigator.clipboard.writeText(linkVerif);
                        setCopiadoLink(true);
                        setTimeout(() => setCopiadoLink(false), 2000);
                      }}
                      className="flex items-center gap-1 rounded-md border hairline bg-surface px-2.5 py-1.5 text-xs text-ink hover:bg-accent/30 transition-colors shrink-0 h-[30px]"
                    >
                      {copiadoLink ? (
                        <Check className="h-3.5 w-3.5 text-verde-ink" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                      {copiadoLink ? "Copiado" : "Copiar"}
                    </button>
                  </div>
                </div>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  disabled={generandoLink}
                  onClick={() => void handleGenerarLink()}
                >
                  <ShieldCheck className="h-4 w-4 mr-1" />
                  {generandoLink ? "Generando…" : "Generar link de verificación"}
                </Button>
              )}
            </RailSection>
          )}

          {/* Desglose — vivo via useCotizacion */}
          <RailSection label="Desglose">
            <div className="space-y-1 text-sm">
              <BdRow
                l={`Bruto · ${jornadas} jornada${jornadas !== 1 ? "s" : ""}`}
                v={fmtArs(totales.subtotal)}
              />
              {totales.descuentoPct > 0 && (
                <BdRow
                  l={`Descuento ${totales.descuentoPct}%`}
                  v={`– ${fmtArs(totales.descuentoMonto)}`}
                  neg
                />
              )}
              <BdRow l="Neto" v={fmtArs(totales.totalNeto)} />
              <BdRow
                l={`IVA ${totales.conIva ? "21%" : ""}`}
                v={totales.conIva ? fmtArs(totales.iva) : "— sin IVA"}
              />
              <div className="border-t hairline my-1" />
              <BdRow l="Total" v={fmtArs(total)} strong />
            </div>
            <FieldLabel label="Descuento manual" className="mt-3 max-w-[140px]">
              <div className="relative">
                <Input
                  type="number"
                  min={0}
                  max={100}
                  value={datos.descuento_pct}
                  className="pr-7"
                  onChange={(e) =>
                    setDatos(
                      (d) =>
                        d && {
                          ...d,
                          descuento_pct: Math.max(0, Math.min(100, Number(e.target.value) || 0)),
                        },
                    )
                  }
                />
                <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                  %
                </span>
              </div>
            </FieldLabel>
          </RailSection>

          {/* Cobranza */}
          <RailSection label="Cobranza">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-muted-foreground">
                {fmtArs(pagadoMonto)} de {fmtArs(total)}
                {pagadoMonto === 0 ? " · sin seña" : ""}
              </span>
              <span
                className={cn(
                  "font-mono text-xs font-semibold",
                  pagadoMonto >= total && total > 0 ? "text-verde-ink" : "text-destructive",
                )}
              >
                {pagadoMonto >= total && total > 0 ? "pagado" : `resta ${fmtArs(restante)}`}
              </span>
            </div>
            <div className="mt-1.5 h-1.5 rounded-full bg-muted overflow-hidden">
              <div
                className={cn(
                  "h-full transition-colors",
                  pagadoMonto >= total && total > 0 ? "bg-verde" : "bg-amber",
                )}
                style={{ width: `${total ? Math.min(100, (pagadoMonto / total) * 100) : 0}%` }}
              />
            </div>
            {(p.pagos ?? []).map((pago) => (
              <PagoRow key={pago.id} pago={pago} pedidoId={p.id} />
            ))}
            {!(pagadoMonto >= total && total > 0) && (
              <Button
                variant="outline"
                size="sm"
                className="w-full mt-2"
                disabled={p.estado === "cancelado"}
                onClick={() => setOpenPagoModal(true)}
              >
                <Coins className="h-4 w-4 mr-1" /> Registrar pago
              </Button>
            )}
          </RailSection>

          {/* Documentos */}
          <RailSection label="Documentos">
            <div className="flex flex-wrap gap-1.5">
              {DOCS_PEDIDO.map((doc) => (
                <div key={doc.kind} className="flex items-center gap-0.5">
                  <a
                    href={`${pedidoPdfUrl(p.id, doc.kind)}?format=html`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 rounded-md border hairline px-2 py-1 font-mono text-xs text-muted-foreground hover:text-ink hover:border-ink"
                    title={`Ver ${doc.label}`}
                  >
                    <Eye className="h-3 w-3" />
                    {doc.label}
                  </a>
                  <a
                    href={pedidoPdfUrl(p.id, doc.kind)}
                    className="inline-flex items-center justify-center h-7 w-7 rounded-md border hairline text-muted-foreground hover:text-ink hover:border-ink"
                    title={`Descargar ${doc.label} PDF`}
                  >
                    <Download className="h-3 w-3" />
                  </a>
                </div>
              ))}
            </div>
            <Button
              variant="outline"
              size="sm"
              className="w-full mt-2"
              onClick={() => setOpenMailDialog(true)}
            >
              <Mail className="h-4 w-4 mr-1" /> Enviar por mail
            </Button>
          </RailSection>

          {/* Eliminar pedido */}
          <RailSection label="Zona peligrosa">
            {transiciones(p.estado).includes("cancelado") && (
              <Button
                variant="outline"
                size="sm"
                className="w-full border-destructive/30 text-destructive hover:bg-destructive/10 hover:text-destructive"
                disabled={estadoMut.isPending}
                onClick={() => setAskCancel(true)}
              >
                <X className="h-4 w-4 mr-1" /> Cancelar pedido
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              className="w-full border-destructive/30 text-destructive hover:bg-destructive/10 hover:text-destructive"
              onClick={() => setAskDelete(true)}
            >
              <Trash2 className="h-4 w-4 mr-1" /> Eliminar pedido
            </Button>
          </RailSection>
        </aside>
      </div>

      {/* Barra inferior sticky (mobile) */}
      <div className="lg:hidden fixed bottom-0 inset-x-0 z-40 flex items-center gap-2 px-4 py-2.5 border-t hairline bg-surface-elevated safe-b">
        <div>
          <div className="t-eyebrow">Total</div>
          <div className="font-mono text-base font-semibold tabular-nums">{fmtArs(total)}</div>
        </div>
        <SaveIndicator status={saveStatus} />
        <div className="ml-auto flex items-center gap-2">
          <WhatsAppButton pedido={p} phone={p.cliente_telefono} variant="icon" />
          {ns && (
            <Button
              variant={ns.blocked ? "outline" : "amber"}
              size="sm"
              disabled={!!ns.blocked || estadoMut.isPending}
              onClick={() => !ns.blocked && handleNextStep(ns.target)}
            >
              {ns.blocked ?? ns.label}
            </Button>
          )}
        </div>
      </div>

      {/* Modales */}
      <DateRangePickerModal
        open={openDateModal}
        onOpenChange={setOpenDateModal}
        startDate={startDate}
        endDate={endDate}
        startTime={startTime}
        endTime={endTime}
        onDatesChange={handleDatesChange}
        onStartTimeChange={handleStartTimeChange}
        onEndTimeChange={handleEndTimeChange}
        options={{ allowPast: true, respectHorarios: false }}
      />
      <RegistrarPagoModal
        pedidoId={p.id}
        total={total}
        pagado={pagadoMonto}
        open={openPagoModal}
        onOpenChange={setOpenPagoModal}
      />
      <EnviarDocsDialog
        pedidoId={p.id}
        clienteEmail={p.cliente_email ?? ""}
        open={openMailDialog}
        onOpenChange={setOpenMailDialog}
      />
      <AlertDialog open={askVerif} onOpenChange={setAskVerif}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-ink shrink-0" />
              Cliente sin identidad verificada
            </AlertDialogTitle>
            <AlertDialogDescription>
              {p.cliente_nombre} no verificó su identidad (DNI + selfie). Podés generar un link de
              verificación para mandárselo, o continuar de todas formas.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (pendingEstado) estadoMut.mutate(pendingEstado);
                setAskVerif(false);
                setPendingEstado(null);
              }}
            >
              {pendingEstado === "confirmado"
                ? "Confirmar de todas formas"
                : "Continuar de todas formas"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <AlertDialog open={askCancel} onOpenChange={setAskCancel}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancelar pedido #{p.numero_pedido ?? p.id}</AlertDialogTitle>
            <AlertDialogDescription>
              El pedido pasa a estado <strong>Cancelado</strong> y libera el stock reservado. Queda
              en el historial (no se borra). Podés volver a eliminarlo definitivamente si hace
              falta.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Volver</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                estadoMut.mutate("cancelado");
                setAskCancel(false);
              }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Cancelar pedido
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <AlertDialog open={askDelete} onOpenChange={setAskDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar pedido #{p.numero_pedido ?? p.id}</AlertDialogTitle>
            <AlertDialogDescription>
              Se borran también sus ítems y pagos. No se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMut.mutate()}
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

function FlowStrip({ estado }: { estado: PedidoEstado }) {
  if (estado === "cancelado") {
    return (
      <div className="flex items-center">
        <span className="inline-flex items-center gap-1 rounded-md border border-destructive/40 bg-destructive/5 px-2 py-1 font-mono text-2xs text-destructive">
          Cancelado
        </span>
      </div>
    );
  }
  const idx = FLOW.indexOf(estado);
  return (
    <div className="flex items-center gap-1 flex-wrap">
      {FLOW.map((e, i) => (
        <span key={e} className="inline-flex items-center gap-1">
          <span
            className={cn(
              "font-mono text-2xs",
              i < idx && "text-verde-ink",
              i === idx && "text-ink font-semibold",
              i > idx && "text-muted-foreground/60",
            )}
            title={ESTADO_LABEL[e]}
          >
            {ESTADO_LABEL[e].slice(0, 5)}
          </span>
          {i < FLOW.length - 1 && <span className="text-muted-foreground/40 text-2xs">›</span>}
        </span>
      ))}
    </div>
  );
}
