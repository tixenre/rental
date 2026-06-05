import { createLazyFileRoute, useNavigate, useParams, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronDown,
  User,
  Calendar,
  Box,
  FileText,
  Check,
  AlertTriangle,
  Lock,
  Coins,
  ArrowRight,
  Plus,
  Minus,
  X,
  Search,
  Mail,
  Eye,
  Download,
  ShoppingCart,
  Info,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
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
import { EstadoBadge } from "@/components/kit/EstadoBadge";
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
  jornadasEntre,
  type DraftItem,
} from "@/components/admin/pedido/usePedidoDraft";
import { useCotizacion } from "@/lib/cotizacion";
import { useDocumentTitle } from "@/lib/use-document-title";
import { formatARS, formatFechaCorta } from "@/lib/format";
import { EquipoSearchSheet } from "@/components/admin/pedido/EquipoSearchSheet";
import { EnviarDocsDialog, DOCS_PEDIDO } from "@/components/admin/pedido/EnviarDocsDialog";
import { RegistrarPagoModal } from "@/components/admin/pedido/RegistrarPagoModal";

export const Route = createLazyFileRoute("/admin/pedidos-v2/$id")({
  component: PedidoV2EditorPage,
});

// ── Máquina de estados (espeja ESTADOS_VALIDOS del backend, alquileres.py) ────
// El back-office NO ofrece transiciones que el backend rechazaría.
const FLOW: PedidoEstado[] = ["presupuesto", "confirmado", "retirado", "devuelto", "finalizado"];
const TRANSICIONES: Partial<Record<PedidoEstado, PedidoEstado[]>> = {
  borrador: ["presupuesto", "cancelado"],
  presupuesto: ["confirmado", "cancelado"],
  solicitado: ["confirmado", "cancelado"], // estado del portal → se confirma igual
  confirmado: ["retirado", "cancelado"],
  retirado: ["devuelto", "cancelado"],
  entregado: ["devuelto", "cancelado"], // estado del portal
  devuelto: ["finalizado"],
  finalizado: [],
  cancelado: [],
};
const ALL_TARGETS: PedidoEstado[] = [
  "presupuesto",
  "confirmado",
  "retirado",
  "devuelto",
  "finalizado",
  "cancelado",
];
const NEXT_LABEL: Partial<Record<PedidoEstado, string>> = {
  borrador: "Presupuestar",
  presupuesto: "Confirmar pedido",
  solicitado: "Confirmar pedido",
  confirmado: "Marcar retirado",
  retirado: "Registrar devolución",
  entregado: "Registrar devolución",
  devuelto: "Cobrar saldo y finalizar",
};

const transiciones = (e: PedidoEstado): PedidoEstado[] => TRANSICIONES[e] ?? [];

/** Motivo por el que un destino está bloqueado (faltan fechas / sin equipos) — espeja la validación del backend. */
function blockReason(p: Pedido, target: PedidoEstado): string | null {
  const needs: PedidoEstado[] = ["confirmado", "retirado", "devuelto", "finalizado"];
  if (needs.includes(target)) {
    if (!p.fecha_desde || !p.fecha_hasta) return "faltan fechas";
    if (!p.items?.length) return "sin equipos";
  }
  return null;
}

function nextStep(
  p: Pedido,
): { target: PedidoEstado; label: string; blocked: string | null } | null {
  const t = transiciones(p.estado).filter((x) => x !== "cancelado");
  if (!t.length) return null;
  const target = t[0];
  return { target, label: NEXT_LABEL[p.estado] ?? "Avanzar", blocked: blockReason(p, target) };
}

const fmtArs = (n: number | null | undefined) => formatARS(n ?? 0);

// ── Página ───────────────────────────────────────────────────────────────────

function PedidoV2EditorPage() {
  const { id } = useParams({ from: "/admin/pedidos-v2/$id" });
  const navigate = useNavigate();
  const pedidoId = Number(id);
  useDocumentTitle("Pedido · Back-office v2");

  const pedidoQ = useQuery({
    queryKey: ["admin", "pedido", pedidoId],
    queryFn: () => adminApi.getPedido(pedidoId),
  });
  const p = pedidoQ.data;
  const draft = usePedidoDraft(p, { mode: "admin" });

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
    items: (draft.items ?? []).map((it) => ({ equipoId: it.equipo_id, cantidad: it.cantidad })),
    fechaDesde: draft.datos?.fecha_desde || null,
    fechaHasta: draft.datos?.fecha_hasta || null,
    clienteId: p?.cliente_id ?? null,
    descuentoPct: draft.datos?.descuento_pct ?? null,
  });

  // Modales
  const [openPagoModal, setOpenPagoModal] = useState(false);
  const [openMailDialog, setOpenMailDialog] = useState(false);
  const [openSearchSheet, setOpenSearchSheet] = useState(false);
  const [askDelete, setAskDelete] = useState(false);

  const qc = useQueryClient();
  const deleteMut = useMutation({
    mutationFn: () => adminApi.deletePedido(pedidoId),
    onSuccess: () => {
      toast.success("Pedido eliminado");
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
      navigate({ to: "/admin/pedidos-v2" });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (pedidoQ.isError) {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <BackLink onClick={() => navigate({ to: "/admin/pedidos-v2" })} />
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

  // Jornadas desde el draft (vivo, no el valor estático del servidor)
  const jornadas = jornadasEntre(datos.fecha_desde, datos.fecha_hasta);

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

  const updateItem = (equipoId: number, patch: Partial<DraftItem>) =>
    setItems((its) =>
      (its ?? []).map((it) => (it.equipo_id === equipoId ? { ...it, ...patch } : it)),
    );

  const removeItem = (equipoId: number) =>
    setItems((its) => (its ?? []).filter((it) => it.equipo_id !== equipoId));

  const goList = () => navigate({ to: "/admin/pedidos-v2" });

  return (
    <div className="flex flex-col min-h-0">
      {/* Topbar del editor */}
      <header className="flex items-center gap-3 px-4 md:px-6 py-3 border-b hairline bg-surface-elevated">
        <BackLink onClick={goList} />
        <div className="min-w-0 flex items-center gap-2">
          <span className="font-display text-lg text-ink truncate">
            {p.cliente_nombre || "Sin cliente"}
          </span>
          <span className="font-mono text-[11px] text-muted-foreground">
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
              <Info className="h-4 w-4 text-amber shrink-0 mt-0.5" />
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
                <span className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wide text-destructive">
                  <AlertTriangle className="h-3 w-3" /> sin fechas
                </span>
              ) : hasOverstock ? (
                <span className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wide text-destructive">
                  <AlertTriangle className="h-3 w-3" /> revisar stock
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wide text-verde">
                  <Check className="h-3 w-3" /> stock OK
                </span>
              )
            }
          >
            <div className="flex items-end gap-3 flex-wrap">
              <FieldLabel label="Retiro">
                <Input
                  type="date"
                  value={datos.fecha_desde}
                  onChange={(e) => {
                    const v = e.target.value;
                    if (datos.fecha_hasta && datos.fecha_hasta < v) {
                      setDatos((d) => d && { ...d, fecha_desde: v, fecha_hasta: v });
                    } else {
                      setDatos((d) => d && { ...d, fecha_desde: v });
                    }
                  }}
                  className="h-11 sm:h-9 font-mono text-base sm:text-sm tabular-nums"
                />
              </FieldLabel>
              <FieldLabel label="Devolución">
                <Input
                  type="date"
                  value={datos.fecha_hasta}
                  min={datos.fecha_desde || undefined}
                  onChange={(e) => {
                    const v = e.target.value;
                    if (datos.fecha_desde && v < datos.fecha_desde) {
                      setDatos((d) => d && { ...d, fecha_hasta: datos.fecha_desde });
                    } else {
                      setDatos((d) => d && { ...d, fecha_hasta: v });
                    }
                  }}
                  className="h-11 sm:h-9 font-mono text-base sm:text-sm tabular-nums"
                />
              </FieldLabel>
              <div className="rounded-lg border hairline bg-surface-elevated px-4 py-2 text-center shrink-0">
                <div className="font-mono text-xl font-semibold leading-none">{jornadas}</div>
                <div className="font-mono text-[8px] uppercase tracking-[0.2em] text-muted-foreground mt-0.5">
                  jornadas
                </div>
              </div>
            </div>
          </Section>

          {/* Equipos */}
          <Section icon={Box} title={`Equipos · ${items.length}`}>
            {/* Trigger buscador */}
            <button
              type="button"
              onClick={() => setOpenSearchSheet(true)}
              className="flex w-full items-center gap-2.5 px-3 py-2.5 mb-2 rounded-md border hairline text-sm text-muted-foreground hover:bg-muted/30 transition"
            >
              <Search className="h-4 w-4 shrink-0" />
              <span>Buscar para añadir equipos…</span>
            </button>

            <ul className="divide-y hairline">
              {items.map((it) => {
                const stock = stockMap[String(it.equipo_id)];
                const max = stock ? Math.max(0, stock.cantidad - stock.reservado) : it.cantidad;
                const disponible = max - it.cantidad;
                const overstock = it.cantidad > max && !!stock;
                const subtotal = it.precio_jornada * it.cantidad * Math.max(1, jornadas);

                return (
                  <li key={it.equipo_id} className="py-2.5 space-y-1.5">
                    <div className="flex items-center gap-3">
                      <span className="inline-flex h-10 w-10 items-center justify-center rounded-md border hairline text-muted-foreground shrink-0">
                        <ShoppingCart className="h-4 w-4" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="text-sm text-ink truncate">
                          {it.nombre_publico || it.nombre}
                        </div>
                        <div className="font-mono text-[11px] text-muted-foreground flex items-center gap-1.5">
                          <span>{fmtArs(it.precio_jornada)} / jornada</span>
                          {stock && (
                            <span
                              className={cn(
                                "inline-flex items-center rounded px-1.5 py-0.5 text-[10px]",
                                disponible <= 0
                                  ? "bg-destructive/10 text-destructive"
                                  : "bg-muted text-muted-foreground",
                              )}
                            >
                              {disponible <= 0 ? `${disponible} restante` : `${disponible} libres`}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="font-mono text-sm font-semibold tabular-nums w-24 text-right shrink-0">
                        {fmtArs(subtotal)}
                      </div>
                      <button
                        type="button"
                        onClick={() => removeItem(it.equipo_id)}
                        aria-label="Quitar equipo"
                        className="inline-flex h-11 w-11 items-center justify-center rounded-md text-muted-foreground hover:text-destructive"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                    {/* Stepper + precio editable */}
                    <div className="flex items-center gap-2 pl-13">
                      <div className="flex items-center gap-1">
                        <Button
                          size="icon"
                          variant="outline"
                          className="h-9 w-9"
                          onClick={() =>
                            updateItem(it.equipo_id, { cantidad: Math.max(1, it.cantidad - 1) })
                          }
                        >
                          <Minus className="h-3 w-3" />
                        </Button>
                        <Input
                          type="number"
                          min={1}
                          value={it.cantidad}
                          onChange={(e) =>
                            updateItem(it.equipo_id, {
                              cantidad: parseInt(e.target.value) || 1,
                            })
                          }
                          className={cn(
                            "h-9 w-10 text-center text-sm p-0",
                            overstock && "border-destructive text-destructive",
                          )}
                        />
                        <Button
                          size="icon"
                          variant="outline"
                          className="h-9 w-9"
                          onClick={() => updateItem(it.equipo_id, { cantidad: it.cantidad + 1 })}
                        >
                          <Plus className="h-3 w-3" />
                        </Button>
                      </div>
                      <div className="flex items-center gap-1 ml-2">
                        <Input
                          type="number"
                          min={0}
                          value={it.precio_jornada}
                          onChange={(e) =>
                            updateItem(it.equipo_id, {
                              precio_jornada: parseInt(e.target.value) || 0,
                            })
                          }
                          className="h-9 w-24 text-sm"
                        />
                        <span className="text-xs text-muted-foreground whitespace-nowrap">
                          /día
                        </span>
                      </div>
                      {overstock && (
                        <div className="ml-auto text-[11px] text-destructive flex items-center gap-1">
                          <AlertTriangle className="h-3 w-3" /> Excede stock ({max})
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
              {items.length === 0 && (
                <li className="py-4 text-sm text-muted-foreground">
                  Sin equipos. Agregá al menos uno para confirmar.
                </li>
              )}
            </ul>

            <EquipoSearchSheet
              open={openSearchSheet}
              onOpenChange={setOpenSearchSheet}
              existing={items}
              stockMap={stockMap}
              onAdd={(eq: Equipo) => {
                const display = eq.nombre_publico || eq.nombre;
                const existing = items.find((i) => i.equipo_id === eq.id);
                if (existing) {
                  updateItem(eq.id, { cantidad: existing.cantidad + 1 });
                  toast.success(`+1 ${display}`);
                } else {
                  setItems((its) => [
                    ...(its ?? []),
                    {
                      equipo_id: eq.id,
                      cantidad: 1,
                      precio_jornada: eq.precio_jornada ?? 0,
                      nombre: eq.nombre,
                      marca: eq.marca,
                      nombre_publico: eq.nombre_publico ?? null,
                    },
                  ]);
                  toast.success(`Agregado: ${display}`);
                }
                setOpenSearchSheet(false);
              }}
            />
          </Section>

          {/* Notas */}
          <Section icon={FileText} title="Notas internas">
            <textarea
              value={datos.notas}
              placeholder="Notas para el equipo de Rambla…"
              onChange={(e) => setDatos((d) => d && { ...d, notas: e.target.value })}
              className="w-full min-h-[88px] rounded-md border hairline bg-surface-elevated px-3 py-2 text-sm resize-y focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Section>
        </div>

        {/* ── Rail ── (visible en lg en el lado derecho; en mobile fluye debajo) */}
        <aside className="px-4 md:px-5 py-5 space-y-4 bg-surface/40 lg:border-t-0 border-t hairline pb-28 lg:pb-5">
          {/* Estado */}
          <RailSection label="Estado del pedido">
            <EstadoDropdown
              p={p}
              onSet={(e) => estadoMut.mutate(e)}
              disabled={estadoMut.isPending}
            />
            <FlowStrip estado={p.estado} />
            {ns && (
              <Button
                variant={ns.blocked ? "outline" : "amber"}
                className="w-full"
                disabled={!!ns.blocked || estadoMut.isPending}
                title={ns.blocked ?? ""}
                onClick={() => estadoMut.mutate(ns.target)}
              >
                <ArrowRight className="h-4 w-4 mr-1" />
                {ns.blocked ? `Falta: ${ns.blocked}` : ns.label}
              </Button>
            )}
          </RailSection>

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
                v={totales.conIva ? fmtArs(totales.iva) : "— cons. final"}
              />
              <div className="border-t hairline my-1" />
              <BdRow l="Total" v={fmtArs(total)} strong />
            </div>
            <FieldLabel label="Descuento manual %" className="mt-3 max-w-[140px]">
              <Input
                type="number"
                min={0}
                max={100}
                value={datos.descuento_pct}
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
            </FieldLabel>
          </RailSection>

          {/* Cobranza */}
          <RailSection label="Cobranza">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] text-muted-foreground">cobranza</span>
              <span
                className={cn(
                  "font-mono text-[11px]",
                  pagadoMonto >= total && total > 0 ? "text-verde" : "text-destructive",
                )}
              >
                {pagadoMonto >= total && total > 0 ? "pagado" : `resta ${fmtArs(restante)}`}
              </span>
            </div>
            <div className="mt-1.5 h-1.5 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full bg-amber"
                style={{ width: `${total ? Math.min(100, (pagadoMonto / total) * 100) : 0}%` }}
              />
            </div>
            <div className="mt-1 font-mono text-[11px] text-muted-foreground">
              {fmtArs(pagadoMonto)} de {fmtArs(total)}
              {pagadoMonto === 0 ? " · sin seña" : ""}
            </div>
            {(p.pagos ?? []).map((pago) => (
              <PagoRow key={pago.id} pago={pago} pedidoId={p.id} />
            ))}
            <Button
              variant="outline"
              size="sm"
              className="w-full mt-2"
              disabled={p.estado === "cancelado"}
              onClick={() => setOpenPagoModal(true)}
            >
              <Coins className="h-4 w-4 mr-1" /> Registrar pago
            </Button>
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
                    className="inline-flex items-center gap-1 rounded-md border hairline px-2 py-1 font-mono text-[11px] text-muted-foreground hover:text-ink hover:border-ink"
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
          <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
            Total
          </div>
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
              onClick={() => estadoMut.mutate(ns.target)}
            >
              {ns.blocked ?? ns.label.split(" ")[0]}
            </Button>
          )}
        </div>
      </div>

      {/* Modales */}
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

// ── PagoRow con delete ────────────────────────────────────────────────────────

function PagoRow({
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

// ── Subcomponentes ───────────────────────────────────────────────────────────

function BackLink({ onClick }: { onClick: () => void }) {
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

function SaveIndicator({ status }: { status: string }) {
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

function Section({
  icon: Icon,
  title,
  aside,
  children,
}: {
  icon: typeof Box;
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

function FieldLabel({
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
      <span className="block font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground mb-1">
        {label}
      </span>
      {children}
    </label>
  );
}

function RailSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
        {label}
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function BdRow({ l, v, neg, strong }: { l: string; v: string; neg?: boolean; strong?: boolean }) {
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

function FlowStrip({ estado }: { estado: PedidoEstado }) {
  if (estado === "cancelado") {
    return (
      <div className="flex items-center">
        <span className="inline-flex items-center gap-1 rounded-md border border-destructive/40 bg-destructive/5 px-2 py-1 font-mono text-[10px] text-destructive">
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
              "font-mono text-[10px]",
              i < idx && "text-verde",
              i === idx && "text-ink font-semibold",
              i > idx && "text-muted-foreground/60",
            )}
          >
            {ESTADO_LABEL[e].slice(0, 5)}
          </span>
          {i < FLOW.length - 1 && <span className="text-muted-foreground/40 text-[10px]">›</span>}
        </span>
      ))}
    </div>
  );
}

function EstadoDropdown({
  p,
  onSet,
  disabled,
}: {
  p: Pedido;
  onSet: (e: PedidoEstado) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (ev: MouseEvent) => {
      if (ref.current && !ref.current.contains(ev.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  const valid = transiciones(p.estado);
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 rounded-md border hairline bg-surface-elevated px-3 py-2 text-sm hover:border-ink disabled:opacity-60"
      >
        <span className="text-ink">{ESTADO_LABEL[p.estado]}</span>
        <ChevronDown className="h-3.5 w-3.5 ml-auto text-muted-foreground" />
      </button>
      {open && (
        <div className="absolute z-20 mt-1 w-full rounded-md border hairline bg-surface-elevated shadow-lg py-1">
          {ALL_TARGETS.map((e) => {
            const isCur = e === p.estado;
            const allowed = isCur || valid.includes(e);
            const reason = allowed && !isCur ? blockReason(p, e) : null;
            const dis = !allowed || !!reason;
            return (
              <button
                key={e}
                type="button"
                disabled={dis}
                onClick={() => {
                  if (!dis && !isCur) {
                    onSet(e);
                    setOpen(false);
                  }
                }}
                className={cn(
                  "w-full flex items-center gap-2 px-3 py-1.5 text-sm text-left",
                  isCur && "bg-amber-soft",
                  dis ? "text-muted-foreground/60 cursor-not-allowed" : "hover:bg-surface",
                )}
              >
                <span>{ESTADO_LABEL[e]}</span>
                {isCur && <Check className="h-3.5 w-3.5 ml-auto text-verde" />}
                {reason && (
                  <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                    {reason}
                  </span>
                )}
                {!allowed && !isCur && <Lock className="h-3 w-3 ml-auto text-muted-foreground" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
