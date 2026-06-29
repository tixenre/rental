// LEGACY parcial — era el editor v1 de Pedidos del back-office; el admin ahora usa /admin/pedidos/$id
// (el editor canónico, ex-v2). Sobrevive solo como editor del portal del cliente
// (/cliente/pedidos/$id/editar, mode="cliente"), HOY PAUSADO (#750). No agregar features nuevas acá;
// se elimina cuando la modificación del cliente se retome/rediseñe o se descarte (#750).
/**
 * PedidoPage — detalle de pedido.
 *
 * Desktop (≥ lg): 2 columnas — [Cliente+Recogida / Items / Totales] | [Sidebar sticky]
 * Mobile: columna única con las mismas secciones apiladas.
 */

import { useEffect, useState, useRef } from "react";
import { Link, useRouter, useBlocker } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronDown,
  ChevronRight,
  X,
  Trash2,
  Check,
  MoreHorizontal,
  Loader2,
  CloudOff,
  CloudCheck,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { Label } from "@/design-system/ui/label";
import { Textarea } from "@/design-system/ui/textarea";
import { EstadoBadge } from "@/design-system/kit/EstadoBadge";
import { Pill } from "@/design-system/kit/Pill";
import { ActionMenu } from "@/components/mobile";
import { TableSkeleton } from "@/components/admin/skeletons";
import { ErrorState } from "@/components/admin/ErrorState";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/design-system/ui/dropdown-menu";
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
import { cn } from "@/lib/utils";

import { adminApi, ESTADO_LABEL, type PedidoEstado } from "@/lib/admin/api";
import { clienteApi } from "@/lib/cliente/api";
import { WhatsAppButton } from "@/components/admin/WhatsAppButton";
import { useCotizacion } from "@/lib/cotizacion";
import { usePedidoDraft, jornadasEntre, type SaveStatus, type PedidoMode } from "./usePedidoDraft";
import { fmtArs, formatFechaDisplay } from "@/lib/format";
import { nombreCliente } from "@/lib/cliente-nombre";
import { ClienteAutocomplete } from "./ClienteAutocomplete";
import {
  ItemsCard,
  TotalesCard,
  PagosSidebar,
  DocumentosSidebar,
  HistorialModificaciones,
  SolicitudDiffDialog,
} from "./PedidoPageCards";

// ── Formatters ────────────────────────────────────────────────────────────

const fmtFecha = (s: string) => formatFechaDisplay(s);

// ── Avatar ────────────────────────────────────────────────────────────────

// Tier 3 (categórico): paleta de avatares — colores distinguibles entre sí
// para identidad visual, no semánticos. Off-brand a propósito. Ver
// docs/DESIGN_SYSTEM.md → Tiers de color.
/* eslint-disable no-restricted-syntax */
const AVATAR_COLORS = [
  "bg-blue-500",
  "bg-violet-500",
  "bg-emerald-500",
  "bg-amber-600",
  "bg-rose-500",
  "bg-cyan-600",
  "bg-orange-500",
  "bg-teal-600",
];
/* eslint-enable no-restricted-syntax */

function avatarBg(name: string) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = name.charCodeAt(i) + ((h << 5) - h);
  return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
}

function nameInitials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

function ClienteAvatar({ name }: { name: string }) {
  return (
    <div
      className={cn(
        "h-10 w-10 rounded-full flex items-center justify-center text-white text-sm font-medium shrink-0",
        avatarBg(name),
      )}
    >
      {nameInitials(name)}
    </div>
  );
}

// ── Sidebar collapsible section ────────────────────────────────────────────

function SidebarSection({
  title,
  badge,
  defaultOpen = true,
  children,
}: {
  title: string;
  badge?: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b hairline last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-ink hover:bg-muted/30 transition"
      >
        <span>
          {title}
          {badge != null && badge > 0 && (
            <span className="ml-1.5 inline-flex items-center justify-center rounded-full bg-muted text-muted-foreground text-2xs h-4 min-w-4 px-1">
              {badge}
            </span>
          )}
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-muted-foreground transition-transform",
            !open && "-rotate-90",
          )}
        />
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

// ── Save indicator ────────────────────────────────────────────────────────

function SaveIndicator({ status }: { status: SaveStatus }) {
  if (status === "saving" || status === "dirty")
    return (
      <span className="hidden sm:flex text-xs text-muted-foreground items-center gap-1">
        <Loader2 className="h-3 w-3 animate-spin" /> Guardando…
      </span>
    );
  if (status === "saved")
    return (
      <span className="hidden sm:flex text-xs text-muted-foreground items-center gap-1">
        <CloudCheck className="h-3 w-3" /> Guardado
      </span>
    );
  if (status === "error")
    return (
      <span className="hidden sm:flex text-xs text-destructive items-center gap-1">
        <CloudOff className="h-3 w-3" /> Error al guardar
      </span>
    );
  return null;
}

// ── Main component ─────────────────────────────────────────────────────────

export type PedidoPageProps = {
  pedidoId: number;
  /** Modo de la vista. 'admin' (default) o 'cliente' (portal). */
  mode?: PedidoMode;
  /** Mensaje opcional para acompañar la solicitud (sólo cliente). */
  mensaje?: string;
  /** Callback al volver desde la vista cliente. */
  onClose?: () => void;
};

// El mock muestra "Solicitado" para el estado interno 'presupuesto'.
const estadoLabel = (e: PedidoEstado) => (e === "presupuesto" ? "Solicitado" : ESTADO_LABEL[e]);

export function PedidoPage({ pedidoId, mode = "admin", mensaje, onClose }: PedidoPageProps) {
  const router = useRouter();
  const qc = useQueryClient();
  const isCliente = mode === "cliente";

  const pedidoQ = useQuery({
    queryKey: isCliente ? ["cliente", "pedido", pedidoId] : ["admin", "pedido", pedidoId],
    queryFn: () => (isCliente ? clienteApi.getPedido(pedidoId) : adminApi.getPedido(pedidoId)),
  });

  const pedido = pedidoQ.data;

  // En modo cliente el submitMode depende del estado del pedido:
  //  - presupuesto: autosave (se aplica directo)
  //  - confirmado:  propose   (genera solicitud pendiente de aprobación)
  const clienteSubmitMode = pedido?.estado === "confirmado" ? "propose" : "autosave";

  const draft = usePedidoDraft(pedido, {
    mode,
    submitMode: isCliente ? clienteSubmitMode : "autosave",
    mensaje,
    onProposalSent: (tipo) => {
      if (tipo === "aprobacion") {
        toast.success("Tu solicitud fue enviada. Te avisamos cuando la revisemos.");
        // Limpiamos el draft contra el server actual (que sigue intacto) y
        // volvemos al portal: el cliente no debe quedarse en el editor con
        // estado `dirty` después de enviar.
        if (onClose) onClose();
        else router.navigate({ to: "/cliente/portal" });
      }
    },
  });

  const [askDelete, setAskDelete] = useState(false);
  const [openActionMenu, setOpenActionMenu] = useState(false);
  const [showDiffConfirm, setShowDiffConfirm] = useState(false);

  const deleteMut = useMutation({
    mutationFn: () => adminApi.deletePedido(pedidoId),
    onSuccess: () => {
      toast.success("Pedido eliminado");
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
      router.navigate({ to: "/admin/pedidos" });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Warning si el cliente intenta salir con cambios sin enviar en modo
  // propose (confirmado). En autosave no hace falta — ya está guardado.
  const dirtyInPropose =
    isCliente && pedido?.estado === "confirmado" && draft.saveStatus === "dirty";
  const dirtyRef = useRef(false);
  dirtyRef.current = dirtyInPropose;
  // One-shot bypass del blocker: lo setea `onProposalSent` para que la
  // navegación post-submit no dispare el confirm de "cambios sin enviar".
  const skipBlockerRef = useRef(false);
  useEffect(() => {
    function onBeforeUnload(e: BeforeUnloadEvent) {
      if (skipBlockerRef.current) return;
      if (dirtyRef.current) {
        e.preventDefault();
        e.returnValue = "";
      }
    }
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, []);
  useBlocker({
    shouldBlockFn: () => {
      if (skipBlockerRef.current) return false;
      if (!dirtyRef.current) return false;
      return !window.confirm("Tenés cambios sin enviar. ¿Querés salir y perderlos?");
    },
    enableBeforeUnload: false,
  });

  // Disponibilidad — usada por ItemsCard y por el gate del botón "Enviar".
  // En cliente se usa el endpoint con ownership; en admin el normal.
  // IMPORTANTE: estos hooks deben estar ANTES de cualquier early return
  // (líneas más abajo de pedidoQ.isLoading / pedidoQ.error) porque
  // React exige que los hooks se llamen en el mismo orden cada render
  // (Rules of Hooks → React error #310). Usamos `?.` y `enabled` para que
  // no corran cuando los datos todavía no llegaron.
  const adminDispoQ = useQuery({
    queryKey: [
      "admin",
      "disponibilidad",
      draft.datos?.fecha_desde,
      draft.datos?.fecha_hasta,
      pedido?.id,
    ],
    queryFn: () =>
      adminApi.getDisponibilidad(draft.datos!.fecha_desde, draft.datos!.fecha_hasta, pedido!.id),
    enabled: !isCliente && !!pedido && !!draft.datos?.fecha_desde && !!draft.datos?.fecha_hasta,
  });
  const clienteDispoQ = useQuery({
    queryKey: [
      "cliente",
      "disponibilidad",
      pedido?.id,
      draft.datos?.fecha_desde,
      draft.datos?.fecha_hasta,
    ],
    queryFn: () =>
      clienteApi.getDisponibilidad(pedido!.id, draft.datos!.fecha_desde, draft.datos!.fecha_hasta),
    enabled: isCliente && !!pedido && !!draft.datos?.fecha_desde && !!draft.datos?.fecha_hasta,
  });

  // Total calculado por el BACKEND (fuente única, /api/cotizar). Se recotiza
  // al editar el draft (ítems / fechas / descuento) y mantiene el valor previo
  // mientras recalcula. El admin cotiza para el cliente del pedido (cliente_id)
  // con su descuento editable. OJO: es un hook → va ANTES de los early-returns
  // de abajo (regla de hooks). #617.
  const cotizacionQ = useCotizacion({
    items: (draft.items ?? []).map((it) => ({ equipoId: it.equipo_id, cantidad: it.cantidad })),
    fechaDesde: draft.datos?.fecha_desde || null,
    fechaHasta: draft.datos?.fecha_hasta || null,
    clienteId: pedido?.cliente_id ?? null,
    descuentoPct: draft.datos?.descuento_pct ?? null,
  });

  if (pedidoQ.isLoading) {
    return <TableSkeleton rows={8} className="p-6" />;
  }

  if (pedidoQ.error || !pedido || !draft.datos || !draft.items) {
    return <ErrorState error={pedidoQ.error} onRetry={() => pedidoQ.refetch()} />;
  }

  const jornadas = jornadasEntre(draft.datos.fecha_desde, draft.datos.fecha_hasta);

  // Desglose canónico del BACKEND (cotizacionQ, hoisteado arriba). Total e IVA
  // coinciden con carrito, portal cliente y PDF — todos salen de
  // services/precios.calcular_total. #617 / #496.
  const totales = cotizacionQ.data;
  const bruto = totales.subtotal;
  const totalNeto = totales.totalNeto;
  const total = totales.total; // total con IVA si el cliente es RI, si no = neto
  const ivaMonto = totales.iva;
  const conIva = totales.conIva;
  const ivaPct = 21;
  const pagado = pedido.monto_pagado ?? 0;
  const saldo = total - pagado;
  const numero = pedido.numero_pedido ? `#${pedido.numero_pedido}` : `(borrador #${pedido.id})`;
  const clienteNombre = draft.datos.cliente_nombre || "Sin cliente";

  // `/api/disponibilidad` (admin y cliente) devuelve `{ equipo_id: libres }` —
  // un número neto ya descontados reservas + mantenimiento (fuente única
  // `reservas.calcular_disponibilidad`). Se adapta a `{cantidad, reservado}`
  // (reservado=0 porque ya viene neto) para el UI. Antes el branch admin usaba
  // la respuesta cruda como si fueran objetos → `stock.cantidad` undefined →
  // "NaN libres" (bug de la modularización de reservas).
  const stockMap: Record<string, { cantidad: number; reservado: number }> = Object.fromEntries(
    Object.entries((isCliente ? clienteDispoQ.data : adminDispoQ.data) ?? {}).map(([k, v]) => [
      k,
      { cantidad: Number(v) || 0, reservado: 0 },
    ]),
  );

  const hasOverstock = draft.items.some((it) => {
    const s = stockMap[String(it.equipo_id)];
    if (!s) return false;
    const max = Math.max(0, s.cantidad - s.reservado);
    return it.cantidad > max;
  });

  const submitBlocked =
    draft.submitBlockedReason ?? (hasOverstock ? "Algún equipo excede el stock disponible" : null);

  const nextAction = (() => {
    switch (pedido.estado) {
      case "borrador":
        return {
          label: "Confirmar presupuesto",
          estado: "presupuesto" as PedidoEstado,
          needsItems: true,
        };
      case "presupuesto":
        return {
          label: "Confirmar pedido",
          estado: "confirmado" as PedidoEstado,
          needsItems: true,
        };
      case "confirmado":
        return { label: "Marcar retirado", estado: "retirado" as PedidoEstado };
      case "retirado":
        return { label: "Marcar devuelto", estado: "devuelto" as PedidoEstado };
      case "devuelto":
        return { label: "Finalizar", estado: "finalizado" as PedidoEstado };
      default:
        return null;
    }
  })();

  const actionDisabled =
    draft.estadoMut.isPending || (nextAction?.needsItems === true && draft.items.length === 0);

  return (
    <div className="-mx-4 md:-mx-6 -my-6 bg-muted/40">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-20 bg-background border-b hairline px-4 md:px-6 py-3 flex items-center gap-3">
        <div className="flex items-center gap-1.5 min-w-0 flex-1">
          {isCliente ? (
            <button
              type="button"
              onClick={() => onClose?.() ?? router.navigate({ to: "/cliente/portal" })}
              className="text-muted-foreground hover:text-ink transition shrink-0"
              aria-label="Volver"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          ) : (
            <Link
              to="/admin/pedidos"
              className="text-muted-foreground hover:text-ink transition shrink-0"
            >
              <ChevronLeft className="h-4 w-4" />
            </Link>
          )}
          <span className="text-muted-foreground text-sm hidden sm:inline">
            {isCliente ? "Mis pedidos" : "Pedidos"}
          </span>
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground hidden sm:inline shrink-0" />
          <span className="font-semibold text-sm text-ink truncate">{numero}</span>
          {isCliente && clienteSubmitMode === "propose" && draft.saveStatus === "dirty" && (
            <span
              className="sm:hidden h-2 w-2 rounded-full bg-amber shrink-0"
              title="Tenés cambios sin enviar"
              aria-label="Cambios sin enviar"
            />
          )}
          <EstadoBadge
            estado={pedido.estado}
            label={estadoLabel(pedido.estado)}
            className="ml-1 shrink-0"
          />
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <SaveIndicator status={draft.saveStatus} />
          {!isCliente && (
            <WhatsAppButton
              pedido={{
                numero_pedido: pedido.numero_pedido,
                numero_remito: pedido.numero_remito,
                cliente_nombre: draft.datos.cliente_nombre,
                fecha_desde: draft.datos.fecha_desde,
                fecha_hasta: draft.datos.fecha_hasta,
                monto_total: total,
                monto_pagado: pagado,
                estado: pedido.estado,
              }}
              phone={draft.datos.cliente_telefono}
              variant="icon"
            />
          )}
          {!isCliente && nextAction && (
            <Button
              size="sm"
              onClick={() => draft.estadoMut.mutate(nextAction.estado)}
              disabled={actionDisabled}
              className="hidden sm:inline-flex"
            >
              <Check className="h-3.5 w-3.5 mr-1" /> {nextAction.label}
            </Button>
          )}
          {isCliente && clienteSubmitMode === "propose" && (
            <Button
              size="sm"
              onClick={() => setShowDiffConfirm(true)}
              disabled={draft.isSubmitting || draft.saveStatus !== "dirty" || !!submitBlocked}
              title={submitBlocked ?? undefined}
              className="hidden sm:inline-flex"
            >
              <Check className="h-3.5 w-3.5 mr-1" /> Enviar solicitud
            </Button>
          )}
          {!isCliente && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="icon" variant="ghost" className="hidden sm:inline-flex">
                  <MoreHorizontal className="h-5 w-5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  disabled={pedido.estado === "cancelado"}
                  onClick={() => draft.estadoMut.mutate("cancelado")}
                >
                  Cancelar pedido
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onClick={() => setAskDelete(true)}
                >
                  <Trash2 className="h-4 w-4 mr-2" /> Eliminar
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          {!isCliente && (
            <Button
              size="icon"
              variant="ghost"
              className="sm:hidden"
              onClick={() => setOpenActionMenu(true)}
            >
              <MoreHorizontal className="h-5 w-5" />
            </Button>
          )}
        </div>
      </header>

      {/* ── 2-column body: main (2/3) + sidebar (1/3) ─────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,2fr)_300px] gap-4 lg:gap-6 p-4 md:p-6 items-start">
        {/* ── Columna principal ── */}
        <div className="space-y-4">
          {/* Cliente + Recogida — una sola card, lado a lado */}
          <section className="rounded-lg border hairline bg-background overflow-hidden">
            <div className="grid grid-cols-1 sm:grid-cols-2">
              {/* Cliente */}
              <div className="p-4 space-y-3 border-b hairline sm:border-b-0 sm:border-r">
                <h2 className="font-medium text-sm">Cliente</h2>
                {clienteNombre !== "Sin cliente" && (
                  <div className="flex items-center gap-3 rounded-md border hairline bg-muted/20 px-3 py-2.5">
                    <ClienteAvatar name={clienteNombre} />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-ink truncate">{clienteNombre}</div>
                      {draft.datos.cliente_email && (
                        <div className="text-xs text-muted-foreground truncate">
                          {draft.datos.cliente_email}
                        </div>
                      )}
                    </div>
                    {!isCliente && draft.datos.cliente_id && (
                      <button
                        type="button"
                        onClick={() => draft.setDatos({ ...draft.datos!, cliente_id: null })}
                        className="rounded p-1 text-muted-foreground hover:text-ink transition"
                        aria-label="Desvincular ficha"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                )}
                {!isCliente && (
                  <>
                    <ClienteAutocomplete
                      onPick={(c) =>
                        draft.setDatos({
                          ...draft.datos!,
                          cliente_id: c.id,
                          cliente_nombre: nombreCliente(c),
                          cliente_email: c.email ?? "",
                          cliente_telefono: c.telefono ?? "",
                          // El descuento sigue al cliente: si el nuevo no tiene
                          // uno propio, se resetea a 0 (antes quedaba pegado el
                          // del cliente anterior).
                          descuento_pct: c.descuento ?? 0,
                        })
                      }
                    />
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <div>
                        <Label className="text-xs">Nombre</Label>
                        <Input
                          value={draft.datos.cliente_nombre}
                          onChange={(e) =>
                            draft.setDatos({ ...draft.datos!, cliente_nombre: e.target.value })
                          }
                          className="h-8 text-sm text-base sm:text-sm"
                        />
                      </div>
                      <div>
                        <Label className="text-xs">Email</Label>
                        <Input
                          value={draft.datos.cliente_email}
                          onChange={(e) =>
                            draft.setDatos({ ...draft.datos!, cliente_email: e.target.value })
                          }
                          className="h-8 text-sm text-base sm:text-sm"
                        />
                      </div>
                      <div className="sm:col-span-2">
                        <Label className="text-xs">Teléfono</Label>
                        <Input
                          value={draft.datos.cliente_telefono}
                          onChange={(e) =>
                            draft.setDatos({ ...draft.datos!, cliente_telefono: e.target.value })
                          }
                          className="h-8 text-sm text-base sm:text-sm"
                        />
                      </div>
                    </div>
                  </>
                )}
                {isCliente && (
                  <div className="text-xs text-muted-foreground">
                    Para actualizar tus datos, andá a{" "}
                    <Link to="/cliente/perfil" className="underline">
                      tu perfil
                    </Link>
                    .
                  </div>
                )}
              </div>

              {/* Recogida */}
              <div className="p-4 space-y-4">
                <h2 className="font-medium text-sm">Recogida</h2>
                <div>
                  <Label className="text-xs text-muted-foreground mb-1.5">Desde</Label>
                  <div className="rounded-md border border-[color-mix(in_oklch,var(--amber)_45%,transparent)] px-3 py-3">
                    <div className="text-lg font-semibold text-ink tabular-nums">
                      {draft.datos.fecha_desde ? fmtFecha(draft.datos.fecha_desde) : "—"}
                    </div>
                    <Input
                      type="date"
                      value={draft.datos.fecha_desde}
                      onChange={(e) => {
                        const v = e.target.value;
                        if (
                          draft.datos!.fecha_hasta &&
                          new Date(draft.datos!.fecha_hasta) < new Date(v)
                        ) {
                          draft.setDatos({ ...draft.datos!, fecha_desde: v, fecha_hasta: v });
                        } else {
                          draft.setDatos({ ...draft.datos!, fecha_desde: v });
                        }
                      }}
                      className="mt-2 h-11 sm:h-8 text-base sm:text-sm"
                    />
                  </div>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground mb-1.5">Hasta</Label>
                  <div className="rounded-md border border-[color-mix(in_oklch,var(--amber)_45%,transparent)] px-3 py-3">
                    <div className="text-lg font-semibold text-ink tabular-nums">
                      {draft.datos.fecha_hasta ? fmtFecha(draft.datos.fecha_hasta) : "—"}
                    </div>
                    <Input
                      type="date"
                      value={draft.datos.fecha_hasta}
                      min={draft.datos.fecha_desde || undefined}
                      onChange={(e) =>
                        draft.setDatos({ ...draft.datos!, fecha_hasta: e.target.value })
                      }
                      className="mt-2 h-11 sm:h-8 text-base sm:text-sm"
                    />
                  </div>
                </div>
                {jornadas > 0 && (
                  <div className="text-sm text-muted-foreground text-center">
                    {jornadas} jornada{jornadas !== 1 ? "s" : ""}
                  </div>
                )}
              </div>
            </div>
          </section>

          {/* Items */}
          <ItemsCard
            items={draft.items}
            setItems={draft.setItems}
            jornadas={jornadas}
            stockMap={stockMap}
            mode={mode}
          />

          {/* Totales */}
          <TotalesCard
            bruto={bruto}
            totalNeto={totalNeto}
            total={total}
            conIva={conIva}
            ivaPct={ivaPct}
            ivaMonto={ivaMonto}
            jornadas={jornadas}
            descuentoPct={draft.datos.descuento_pct}
            setDescuentoPct={(v) => draft.setDatos({ ...draft.datos!, descuento_pct: v })}
            pagado={pagado}
            saldo={saldo}
            mode={mode}
          />
        </div>

        {/* ── Sidebar: Pagos + Docs + Notas — todo el alto ──
            En modo cliente sólo trae "Resumen" — info redundante con
            TotalesCard. Lo ocultamos en mobile y se ve en desktop. */}
        <div
          className={cn(
            "rounded-lg border hairline bg-background overflow-hidden lg:sticky lg:top-16",
            isCliente && "hidden lg:block",
          )}
        >
          {!isCliente && (
            <SidebarSection title="Pagos" defaultOpen>
              <PagosSidebar
                pedidoId={pedido.id}
                total={total}
                pagado={pagado}
                saldo={saldo}
                pagos={pedido.pagos ?? []}
              />
            </SidebarSection>
          )}

          {!isCliente && (
            <SidebarSection title="Documentos" defaultOpen>
              <DocumentosSidebar pedidoId={pedido.id} clienteEmail={pedido.cliente_email ?? ""} />
            </SidebarSection>
          )}

          {!isCliente && (
            <SidebarSection title="Notas" defaultOpen={false}>
              <Textarea
                rows={4}
                value={draft.datos.notas}
                onChange={(e) => draft.setDatos({ ...draft.datos!, notas: e.target.value })}
                placeholder="Visibles solo en el back-office"
                className="text-sm resize-none text-base sm:text-sm"
              />
            </SidebarSection>
          )}

          {isCliente && (
            <SidebarSection title="Resumen" defaultOpen>
              <div className="text-sm text-muted-foreground space-y-2">
                <div className="flex justify-between">
                  <span>Pagado</span>
                  <span className="tabular-nums text-ink">{fmtArs(pagado)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Saldo</span>
                  <span className="tabular-nums text-ink">{fmtArs(saldo)}</span>
                </div>
                {clienteSubmitMode === "propose" && (
                  <p className="pt-3 text-xs">
                    Tu pedido está confirmado. Los cambios se enviarán como solicitud para que los
                    aprobemos.
                  </p>
                )}
                {clienteSubmitMode === "autosave" && (
                  <p className="pt-3 text-xs">Los cambios se guardan automáticamente.</p>
                )}
              </div>
            </SidebarSection>
          )}

          {!isCliente && (pedido.historial_modificaciones?.length ?? 0) > 0 && (
            <SidebarSection
              title="Historial cliente"
              badge={pedido.historial_modificaciones?.length}
              defaultOpen={false}
            >
              <HistorialModificaciones items={pedido.historial_modificaciones ?? []} />
            </SidebarSection>
          )}

          {!isCliente && pedido.fuente && pedido.fuente !== "historico" && (
            <SidebarSection title="Etiquetas" badge={1} defaultOpen>
              <Pill tone="neutral" className="gap-1.5 px-2.5 py-1 text-xs text-ink">
                {pedido.fuente.toUpperCase()}
              </Pill>
            </SidebarSection>
          )}
        </div>
      </div>

      {/* Mobile: acción primaria flotante */}
      {!isCliente && nextAction && (
        <div className="sm:hidden fixed bottom-0 left-0 right-0 bg-background border-t hairline px-4 py-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] z-20">
          <Button
            className="w-full"
            onClick={() => draft.estadoMut.mutate(nextAction.estado)}
            disabled={actionDisabled}
          >
            <Check className="h-4 w-4 mr-1" /> {nextAction.label}
          </Button>
        </div>
      )}

      {isCliente && clienteSubmitMode === "propose" && (
        <div className="sm:hidden fixed bottom-0 left-0 right-0 bg-background border-t hairline px-4 py-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] z-20">
          {submitBlocked && draft.saveStatus === "dirty" && (
            <div className="text-xs text-destructive mb-2 text-center">{submitBlocked}</div>
          )}
          <Button
            className="w-full"
            onClick={() => setShowDiffConfirm(true)}
            disabled={draft.isSubmitting || draft.saveStatus !== "dirty" || !!submitBlocked}
          >
            <Check className="h-4 w-4 mr-1" /> Enviar solicitud
          </Button>
        </div>
      )}

      {!isCliente && (
        <ActionMenu
          open={openActionMenu}
          onOpenChange={setOpenActionMenu}
          title={numero}
          actions={[
            ...(nextAction
              ? [
                  {
                    label: nextAction.label,
                    icon: <Check className="h-4 w-4" />,
                    onClick: () => draft.estadoMut.mutate(nextAction.estado),
                  },
                ]
              : []),
            ...(pedido.estado !== "cancelado"
              ? [
                  {
                    label: "Cancelar pedido",
                    icon: <X className="h-4 w-4" />,
                    onClick: () => draft.estadoMut.mutate("cancelado"),
                  },
                ]
              : []),
            {
              label: "Eliminar pedido",
              icon: <Trash2 className="h-4 w-4" />,
              variant: "destructive" as const,
              onClick: () => setAskDelete(true),
            },
          ]}
        />
      )}

      {isCliente && (
        <SolicitudDiffDialog
          open={showDiffConfirm}
          onOpenChange={setShowDiffConfirm}
          original={pedido}
          datos={draft.datos}
          items={draft.items}
          isSubmitting={draft.isSubmitting}
          onConfirm={async () => {
            await draft.submitProposal();
            setShowDiffConfirm(false);
          }}
        />
      )}

      <AlertDialog open={askDelete} onOpenChange={setAskDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar pedido {numero}</AlertDialogTitle>
            <AlertDialogDescription>
              Se borrarán también sus ítems y pagos. No se puede deshacer.
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
