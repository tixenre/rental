/**
 * PedidoPage — detalle de pedido.
 *
 * Desktop (≥ lg): 2 columnas — [Cliente+Recogida / Items / Totales] | [Sidebar sticky]
 * Mobile: columna única con las mismas secciones apiladas.
 */

import { useEffect, useState, useMemo, useRef } from "react";
import { Link, useRouter, useBlocker } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronDown,
  ChevronRight,
  Plus,
  Minus,
  Search,
  X,
  Trash2,
  AlertTriangle,
  Check,
  FileText,
  FileSignature,
  Truck,
  MoreHorizontal,
  Loader2,
  CloudOff,
  CloudCheck,
  Eye,
  Download,
  ShoppingCart,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { EstadoBadge } from "@/components/kit/EstadoBadge";
import { BottomSheet, ActionMenu } from "@/components/mobile";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
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
import { cn } from "@/lib/utils";

import {
  adminApi,
  ESTADO_LABEL,
  pedidoPdfUrl,
  type PedidoEstado,
  type Equipo,
  type Cliente,
  type PedidoHistorialItem,
} from "@/lib/admin/api";
import { clienteApi } from "@/lib/cliente/api";
import { WhatsAppButton } from "@/components/admin/WhatsAppButton";
import { apiGetDescuentosJornada } from "@/lib/api";
import { computeCartTotal } from "@/lib/cart-total";
import { type PerfilImpuestos } from "@/lib/iva";
import {
  usePedidoDraft,
  jornadasEntre,
  type DraftItem,
  type DraftDatos,
  type SaveStatus,
  type PedidoMode,
} from "./usePedidoDraft";

// ── Formatters ────────────────────────────────────────────────────────────

const fmtArs = (n: number | null | undefined) =>
  n ? `$${Math.round(Number(n)).toLocaleString("es-AR", { maximumFractionDigits: 0 })}` : "$0";

const fmtFecha = (s: string) => {
  if (!s) return "—";
  const [y, m, d] = s.slice(0, 10).split("-");
  return `${d}-${m}-${y}`;
};

// ── Avatar ────────────────────────────────────────────────────────────────

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
            <span className="ml-1.5 inline-flex items-center justify-center rounded-full bg-muted text-muted-foreground text-[10px] h-4 min-w-4 px-1">
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

  // Puntos de descuento por jornadas — los usa `computeCartTotal` para
  // recalcular el total cuando el admin edita en vivo (alineado bit a
  // bit con el backend services/precios).
  const descuentosJornadaQ = useQuery({
    queryKey: ["descuentos-jornada"],
    queryFn: apiGetDescuentosJornada,
    staleTime: 60_000,
  });

  if (pedidoQ.isLoading) {
    return (
      <div className="flex items-center justify-center h-[60vh] text-muted-foreground gap-2">
        <Loader2 className="h-4 w-4 animate-spin" /> Cargando pedido…
      </div>
    );
  }

  if (pedidoQ.error || !pedido || !draft.datos || !draft.items) {
    return (
      <div className="p-6 text-sm text-destructive">
        Error: {(pedidoQ.error as Error | undefined)?.message ?? "no se pudo cargar el pedido"}
      </div>
    );
  }

  const jornadas = jornadasEntre(draft.datos.fecha_desde, draft.datos.fecha_hasta);

  // Desglose canónico vía lib/cart-total (alineado bit a bit con el
  // backend services/precios.calcular_total). Cierra #496: total e IVA
  // coinciden con admin, portal cliente, carrito y PDF.
  //
  // Mientras el admin edita en vivo (draft con cambios pendientes),
  // recomputamos local. Cuando no hay cambios, el resultado coincide
  // con `pedido.total_con_iva` que envió el backend.
  const totales = computeCartTotal({
    lines: draft.items.map((it) => ({ pricePerDay: it.precio_jornada, qty: it.cantidad })),
    jornadas,
    descuentosPuntos: descuentosJornadaQ.data ?? [],
    perfilImpuestos: (pedido.cliente_perfil_impuestos ?? null) as PerfilImpuestos | null,
    descuentoClientePct: draft.datos.descuento_pct ?? 0,
  });
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

  const stockMap: Record<string, { cantidad: number; reservado: number }> = isCliente
    ? Object.fromEntries(
        Object.entries(clienteDispoQ.data ?? {}).map(([k, v]) => [
          k,
          { cantidad: Number(v) || 0, reservado: 0 },
        ]),
      )
    : (adminDispoQ.data ?? {});

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
                      datos={draft.datos}
                      onPick={(c) =>
                        draft.setDatos({
                          ...draft.datos!,
                          cliente_id: c.id,
                          cliente_nombre: `${c.apellido}, ${c.nombre}`,
                          cliente_email: c.email ?? "",
                          cliente_telefono: c.telefono ?? "",
                          descuento_pct: c.descuento ?? draft.datos!.descuento_pct,
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
              <DocumentosSidebar pedidoId={pedido.id} />
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
              <span className="inline-flex items-center gap-1.5 rounded bg-muted px-2.5 py-1 text-xs font-medium text-ink">
                {pedido.fuente.toUpperCase()}
              </span>
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

// ─────────────────────────────────────────────────────────────────────────
// Items card
// ─────────────────────────────────────────────────────────────────────────

function ItemsCard({
  items,
  setItems,
  jornadas,
  stockMap,
  mode = "admin",
}: {
  items: DraftItem[];
  setItems: (v: DraftItem[]) => void;
  jornadas: number;
  stockMap: Record<string, { cantidad: number; reservado: number }>;
  mode?: PedidoMode;
}) {
  const [openSearch, setOpenSearch] = useState(false);
  const isCliente = mode === "cliente";

  const updateItem = (equipoId: number, patch: Partial<DraftItem>) =>
    setItems(items.map((it) => (it.equipo_id === equipoId ? { ...it, ...patch } : it)));

  const removeItem = (equipoId: number) => {
    if (items.length === 1) {
      toast.error("El pedido debe tener al menos un equipo.");
      return;
    }
    setItems(items.filter((it) => it.equipo_id !== equipoId));
  };

  return (
    <section className="rounded-lg border hairline bg-background overflow-hidden">
      {/* Search trigger */}
      <button
        type="button"
        onClick={() => setOpenSearch(true)}
        className="flex w-full items-center gap-2.5 px-4 py-3 border-b hairline text-sm text-muted-foreground hover:bg-muted/30 transition"
      >
        <Search className="h-4 w-4 shrink-0" />
        <span>Buscar para añadir productos</span>
      </button>

      {/* Column headers */}
      {items.length > 0 && (
        <div className="grid grid-cols-[1fr_auto_auto_auto] gap-2 px-4 py-2 border-b hairline bg-muted/20 text-[10px] uppercase tracking-wide text-muted-foreground">
          <span>Producto</span>
          <span className="text-right w-20">Disponible</span>
          <span className="text-right w-16">Cantidad</span>
          <span className="text-right w-24">Cargo</span>
        </div>
      )}

      {items.length === 0 && (
        <div className="px-4 py-10 text-center text-sm text-muted-foreground">
          Sin equipos. Usá el buscador para agregar.
        </div>
      )}

      <ul className="divide-y hairline">
        {items.map((it, idx) => {
          const stock = stockMap[String(it.equipo_id)];
          const max = stock ? Math.max(0, stock.cantidad - stock.reservado) : it.cantidad;
          const disponible = max - it.cantidad;
          const overstock = it.cantidad > max;
          const subtotal = it.precio_jornada * it.cantidad * jornadas;

          return (
            <li key={`${it.equipo_id}-${idx}`} className="px-4 py-3 space-y-2.5">
              {/* Row 1: thumb + info + disponible + total + remove */}
              <div className="flex items-start gap-3">
                <div className="h-10 w-10 rounded-md bg-muted/50 border hairline shrink-0 flex items-center justify-center text-muted-foreground">
                  <ShoppingCart className="h-4 w-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-ink truncate">
                    {it.nombre_publico || it.nombre}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {it.marca ?? "—"}
                    {stock && (
                      <span
                        className={cn(
                          "ml-1.5 inline-flex items-center rounded px-1.5 py-0.5 text-[10px]",
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
                <div className="text-right shrink-0">
                  <div className="text-sm tabular-nums font-medium text-ink">
                    {fmtArs(subtotal)}
                  </div>
                  <div className="text-[11px] text-muted-foreground">{jornadas}j</div>
                </div>
                <button
                  type="button"
                  onClick={() => removeItem(it.equipo_id)}
                  className="rounded p-1 text-muted-foreground hover:text-destructive transition shrink-0"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Row 2: controls */}
              <div className="flex items-center gap-2 pl-13">
                <div className="flex items-center gap-1">
                  <Button
                    size="icon"
                    variant="outline"
                    className="h-9 w-9 sm:h-7 sm:w-7"
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
                      updateItem(it.equipo_id, { cantidad: parseInt(e.target.value) || 1 })
                    }
                    className={cn(
                      "h-9 w-10 text-center text-sm p-0 sm:h-7",
                      overstock && "border-destructive text-destructive",
                    )}
                  />
                  <Button
                    size="icon"
                    variant="outline"
                    className="h-9 w-9 sm:h-7 sm:w-7"
                    onClick={() => updateItem(it.equipo_id, { cantidad: it.cantidad + 1 })}
                  >
                    <Plus className="h-3 w-3" />
                  </Button>
                </div>
                <div className="flex items-center gap-1 ml-2">
                  {isCliente ? (
                    <div className="h-9 sm:h-7 px-2 inline-flex items-center text-sm text-muted-foreground tabular-nums">
                      {fmtArs(it.precio_jornada)}
                    </div>
                  ) : (
                    <Input
                      type="number"
                      min={0}
                      value={it.precio_jornada}
                      onChange={(e) =>
                        updateItem(it.equipo_id, { precio_jornada: parseInt(e.target.value) || 0 })
                      }
                      className="h-9 w-24 text-sm text-base sm:text-sm sm:h-7"
                    />
                  )}
                  <span className="text-xs text-muted-foreground whitespace-nowrap">/día</span>
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
      </ul>

      <EquipoSearchSheet
        open={openSearch}
        onOpenChange={setOpenSearch}
        existing={items}
        stockMap={stockMap}
        onAdd={(eq) => {
          const display = eq.nombre_publico || eq.nombre;
          const idx = items.findIndex((i) => i.equipo_id === eq.id);
          if (idx >= 0) {
            updateItem(eq.id, { cantidad: items[idx].cantidad + 1 });
            toast.success(`+1 ${display}`);
          } else {
            setItems([
              ...items,
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
          setOpenSearch(false);
        }}
      />
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Totales card
// ─────────────────────────────────────────────────────────────────────────

function TotalesCard({
  bruto,
  totalNeto,
  total,
  conIva,
  ivaPct,
  ivaMonto,
  jornadas,
  descuentoPct,
  setDescuentoPct,
  pagado,
  saldo,
  mode = "admin",
}: {
  bruto: number;
  totalNeto: number;
  total: number;
  conIva: boolean;
  ivaPct: number;
  ivaMonto: number;
  jornadas: number;
  descuentoPct: number;
  setDescuentoPct: (v: number) => void;
  pagado: number;
  saldo: number;
  mode?: PedidoMode;
}) {
  const isCliente = mode === "cliente";
  return (
    <section className="rounded-lg border hairline bg-background overflow-hidden">
      <div className="px-4 py-3 space-y-2.5 text-sm">
        <div className="flex justify-between text-muted-foreground">
          <span>Subtotal</span>
          <span className="tabular-nums">{fmtArs(bruto)}</span>
        </div>
        {isCliente ? (
          descuentoPct > 0 && (
            <div className="flex items-center justify-between gap-3 text-muted-foreground">
              <span>Descuento {descuentoPct}%</span>
              <span className="tabular-nums">−{fmtArs(bruto - totalNeto)}</span>
            </div>
          )
        ) : (
          <div className="flex items-center justify-between gap-3">
            <span className="text-muted-foreground">Descuento %</span>
            <Input
              type="number"
              min={0}
              max={100}
              step="0.5"
              value={descuentoPct}
              onChange={(e) => {
                // Clamp 0–100: el atributo max no impide tipear >100, y el
                // backend rechaza >100 con 422. Clampeamos en la UI.
                const v = parseFloat(e.target.value) || 0;
                setDescuentoPct(Math.min(100, Math.max(0, v)));
              }}
              className="h-7 w-20 text-right text-sm"
            />
          </div>
        )}
        {!isCliente && descuentoPct > 0 && (
          <div className="flex justify-between text-muted-foreground">
            <span>−{descuentoPct}%</span>
            <span className="tabular-nums">−{fmtArs(bruto - totalNeto)}</span>
          </div>
        )}
        {conIva && (
          <>
            <div className="flex justify-between text-muted-foreground">
              <span>Subtotal neto</span>
              <span className="tabular-nums">{fmtArs(totalNeto)}</span>
            </div>
            <div className="flex justify-between text-muted-foreground">
              <span>IVA {ivaPct}%</span>
              <span className="tabular-nums">+{fmtArs(ivaMonto)}</span>
            </div>
          </>
        )}
        <div className="flex justify-between border-t hairline pt-2.5 font-semibold text-ink">
          <span>Total{conIva ? " · IVA incluído" : ""}</span>
          <span className="tabular-nums">{fmtArs(total)}</span>
        </div>
        {jornadas > 0 && (
          <div className="text-xs text-muted-foreground text-right">
            {jornadas} jornada{jornadas !== 1 ? "s" : ""}
          </div>
        )}
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Pagos sidebar
// ─────────────────────────────────────────────────────────────────────────

function PagosSidebar({
  pedidoId,
  total,
  pagado,
  saldo,
  pagos,
}: {
  pedidoId: number;
  total: number;
  pagado: number;
  saldo: number;
  pagos: { id: number; monto: number; concepto: string | null; fecha: string }[];
}) {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [monto, setMonto] = useState("");
  const [concepto, setConcepto] = useState("");

  const addMut = useMutation({
    mutationFn: () => adminApi.addPago(pedidoId, parseInt(monto || "0", 10), concepto || undefined),
    onSuccess: () => {
      toast.success("Pago registrado");
      setMonto("");
      setConcepto("");
      setShowForm(false);
      qc.invalidateQueries({ queryKey: ["admin", "pedido", pedidoId] });
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const delMut = useMutation({
    mutationFn: (pagoId: number) => adminApi.deletePago(pedidoId, pagoId),
    onSuccess: () => {
      toast.success("Pago eliminado");
      qc.invalidateQueries({ queryKey: ["admin", "pedido", pedidoId] });
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const estadoPago = saldo <= 0 ? "pagado" : "pendiente";

  return (
    <div className="space-y-3">
      {/* Badge estado + importes */}
      <div
        className={cn(
          "inline-flex items-center rounded-full px-3 py-1 text-xs font-medium",
          estadoPago === "pagado" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700",
        )}
      >
        {estadoPago === "pagado" ? "Pagado" : "Pago pendiente"}
      </div>
      <div className="text-sm space-y-1">
        <div className="flex justify-between text-muted-foreground">
          <span>Pagado</span>
          <span className="tabular-nums">{fmtArs(pagado)}</span>
        </div>
        <div className="flex justify-between font-medium text-ink">
          <span>Debido</span>
          <span className="tabular-nums">{fmtArs(total)}</span>
        </div>
      </div>

      {/* Historial */}
      {pagos.length > 0 && (
        <div className="divide-y hairline rounded-md border hairline overflow-hidden">
          {pagos.map((pg) => (
            <div key={pg.id} className="flex items-center justify-between px-3 py-2 text-xs">
              <div>
                <div className="tabular-nums font-medium text-ink">{fmtArs(pg.monto)}</div>
                <div className="text-muted-foreground">
                  {pg.fecha}
                  {pg.concepto ? ` · ${pg.concepto}` : ""}
                </div>
              </div>
              <button
                type="button"
                onClick={() => delMut.mutate(pg.id)}
                className="rounded p-1 text-muted-foreground hover:text-destructive transition"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Nuevo pago */}
      {showForm ? (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label className="text-xs">Monto</Label>
              <Input
                type="number"
                value={monto}
                onChange={(e) => setMonto(e.target.value)}
                placeholder="0"
                className="h-8 text-sm text-base sm:text-sm"
              />
            </div>
            <div>
              <Label className="text-xs">Concepto</Label>
              <Input
                value={concepto}
                onChange={(e) => setConcepto(e.target.value)}
                placeholder="Seña, saldo…"
                className="h-8 text-sm text-base sm:text-sm"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              className="flex-1"
              onClick={() => {
                const n = parseInt(monto || "0", 10);
                if (!n || n <= 0) return toast.error("Monto inválido");
                addMut.mutate();
              }}
              disabled={addMut.isPending}
            >
              {addMut.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Check className="h-3.5 w-3.5" />
              )}{" "}
              Guardar
            </Button>
            <Button size="sm" variant="outline" onClick={() => setShowForm(false)}>
              Cancelar
            </Button>
          </div>
        </div>
      ) : (
        <Button variant="outline" size="sm" className="w-full" onClick={() => setShowForm(true)}>
          <Plus className="h-3.5 w-3.5 mr-1" /> Nuevo Pago
        </Button>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Documentos sidebar
// ─────────────────────────────────────────────────────────────────────────

function DocumentosSidebar({ pedidoId }: { pedidoId: number }) {
  const docs: { kind: "pdf" | "albaran" | "contrato"; label: string; icon: React.ReactNode }[] = [
    { kind: "contrato", label: "Contrato", icon: <FileSignature className="h-4 w-4" /> },
    { kind: "pdf", label: "Presupuesto", icon: <FileText className="h-4 w-4" /> },
    { kind: "albaran", label: "Albarán", icon: <Truck className="h-4 w-4" /> },
  ];

  return (
    <div className="space-y-1.5">
      {docs.map((d) => (
        <div key={d.kind} className="flex items-center gap-2 rounded-md border hairline px-3 py-2">
          <span className="text-muted-foreground shrink-0">{d.icon}</span>
          <span className="flex-1 text-sm text-ink">{d.label}</span>
          <div className="flex items-center gap-1 shrink-0">
            <a
              href={`${pedidoPdfUrl(pedidoId, d.kind)}?format=html`}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded p-1 text-muted-foreground hover:text-ink transition"
              title="Ver"
            >
              <Eye className="h-3.5 w-3.5" />
            </a>
            <a
              href={pedidoPdfUrl(pedidoId, d.kind)}
              className="rounded p-1 text-muted-foreground hover:text-ink transition"
              title="Descargar PDF"
            >
              <Download className="h-3.5 w-3.5" />
            </a>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Buscar equipo (BottomSheet)
// ─────────────────────────────────────────────────────────────────────────

function EquipoSearchSheet({
  open,
  onOpenChange,
  existing,
  stockMap,
  onAdd,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  existing: DraftItem[];
  stockMap: Record<string, { cantidad: number; reservado: number }>;
  onAdd: (eq: Equipo) => void;
}) {
  const [q, setQ] = useState("");
  const equiposQ = useQuery({
    queryKey: ["admin", "equipos", "all"],
    queryFn: () => adminApi.listEquipos({ per_page: 500 }),
  });
  const categoriasQ = useQuery({
    queryKey: ["categorias"],
    queryFn: () => adminApi.listCategorias(),
    staleTime: 60_000,
  });

  const lista = useMemo(() => {
    const all = equiposQ.data?.items ?? [];
    const ql = q.trim().toLowerCase();
    return all
      .filter((e) => e.estado !== "fuera_servicio")
      .filter(
        (e) =>
          !ql ||
          e.nombre.toLowerCase().includes(ql) ||
          (e.nombre_publico ?? "").toLowerCase().includes(ql) ||
          (e.marca ?? "").toLowerCase().includes(ql) ||
          (e.modelo ?? "").toLowerCase().includes(ql),
      );
  }, [equiposQ.data, q]);

  const grupos = useMemo(() => {
    const SIN = "Sin categoría";
    const map = new Map<string, Equipo[]>();
    for (const eq of lista) {
      const cat = eq.etiquetas?.[0] ?? SIN;
      const arr = map.get(cat) ?? [];
      arr.push(eq);
      map.set(cat, arr);
    }
    const weight: Record<string, number> = {};
    const tree = categoriasQ.data ?? [];
    for (const root of tree) {
      const rp = root.prioridad ?? 999;
      weight[root.nombre] = rp * 1000;
      for (const c of root.children ?? []) {
        weight[c.nombre] = rp * 1000 + ((c as { prioridad?: number }).prioridad ?? 100);
      }
      (root.subtags ?? []).forEach((s, i) => {
        if (weight[s.nombre] == null) weight[s.nombre] = rp * 1000 + (i + 1) * 10;
      });
    }
    return Array.from(map.entries()).sort(([a], [b]) => {
      if (a === SIN) return 1;
      if (b === SIN) return -1;
      return (weight[a] ?? 999_000) - (weight[b] ?? 999_000) || a.localeCompare(b, "es");
    });
  }, [lista, categoriasQ.data]);

  return (
    <BottomSheet open={open} onOpenChange={onOpenChange} title="Agregar equipo" showClose>
      <div className="px-4 pt-3 pb-3 border-b hairline">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar…"
            className="pl-9 text-base sm:text-sm"
          />
        </div>
      </div>
      <div className="px-4 pb-4">
        {grupos.length === 0 && (
          <div className="py-8 text-center text-sm text-muted-foreground">Sin equipos.</div>
        )}
        {grupos.map(([cat, equipos]) => (
          <section key={cat} className="mb-2">
            <div className="sticky top-0 z-10 bg-background/95 backdrop-blur py-2 flex items-center justify-between border-b hairline">
              <h4 className="font-display text-sm text-ink">{cat}</h4>
              <span className="text-[11px] text-muted-foreground">{equipos.length}</span>
            </div>
            <ul className="divide-y hairline">
              {equipos.map((eq) => {
                const stock = stockMap[String(eq.id)];
                const inCart = existing.find((i) => i.equipo_id === eq.id);
                const max = stock ? Math.max(0, stock.cantidad - stock.reservado) : eq.cantidad;
                const disponible = max - (inCart?.cantidad ?? 0);
                return (
                  <li key={eq.id} className="flex items-center justify-between gap-2 py-3">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm text-ink truncate">
                        {eq.nombre_publico || eq.nombre}
                      </div>
                      <div className="text-xs text-muted-foreground truncate">
                        {[eq.marca, eq.modelo].filter(Boolean).join(" / ")}
                        {" · "}
                        <span className={disponible <= 0 ? "text-destructive" : ""}>
                          {disponible} libres
                        </span>
                        {eq.precio_jornada ? ` · ${fmtArs(eq.precio_jornada)}/día` : ""}
                      </div>
                    </div>
                    <Button
                      size="icon"
                      className="h-10 w-10 shrink-0"
                      disabled={disponible <= 0}
                      onClick={() => onAdd(eq)}
                      aria-label="Agregar"
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
    </BottomSheet>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Cliente autocomplete
// ─────────────────────────────────────────────────────────────────────────

function ClienteAutocomplete({
  datos,
  onPick,
}: {
  datos: DraftDatos;
  onPick: (c: Cliente) => void;
}) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [debouncedQ, setDebouncedQ] = useState("");

  useMemo(() => {
    const t = setTimeout(() => setDebouncedQ(q.trim()), 250);
    return () => clearTimeout(t);
  }, [q]);

  const clientesQ = useQuery({
    queryKey: ["admin", "clientes", { q: debouncedQ }],
    queryFn: () => adminApi.listClientes({ q: debouncedQ || undefined, per_page: 20 }),
    enabled: open && debouncedQ.length > 0,
  });

  return (
    <div className="relative">
      <Search className="absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
      <Input
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="Buscar ficha existente…"
        className="pl-9 h-8 text-sm text-base sm:text-sm"
      />
      {open && q.trim().length > 0 && (
        <div className="absolute z-30 left-0 right-0 mt-1 rounded-md border hairline bg-background shadow-md max-h-52 overflow-auto">
          {clientesQ.isLoading && (
            <div className="p-3 text-xs text-muted-foreground">Buscando…</div>
          )}
          {clientesQ.data?.items.length === 0 && (
            <div className="p-3 text-xs text-muted-foreground">Sin resultados</div>
          )}
          {(clientesQ.data?.items ?? []).map((c) => (
            <button
              key={c.id}
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                onPick(c);
                setQ("");
                setOpen(false);
              }}
              className="w-full text-left px-3 py-2 hover:bg-accent/50 transition"
            >
              <div className="text-sm text-ink">
                {c.apellido ? `${c.apellido}, ${c.nombre}` : c.nombre}
              </div>
              <div className="text-xs text-muted-foreground">
                {[c.email, c.telefono].filter(Boolean).join(" · ") || "—"}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Historial de modificaciones del cliente (sidebar admin)
// ─────────────────────────────────────────────────────────────────────────

const HIST_ESTADO_VARIANT: Record<
  PedidoHistorialItem["estado"],
  "default" | "secondary" | "destructive" | "outline"
> = {
  pendiente: "secondary",
  aprobada: "default",
  rechazada: "destructive",
  cancelada: "outline",
};

const HIST_ESTADO_LABEL: Record<PedidoHistorialItem["estado"], string> = {
  pendiente: "Pendiente",
  aprobada: "Aprobada",
  rechazada: "Rechazada",
  cancelada: "Cancelada",
};

function HistorialModificaciones({ items }: { items: PedidoHistorialItem[] }) {
  return (
    <ol className="space-y-2.5">
      {items.map((h) => {
        const c = h.cambios_json;
        const a = h.cambios_aplicados;
        const itemDeltas = Array.isArray(c?.items) ? (c?.items ?? []) : [];
        const isDirecto = h.tipo === "directo";
        // Si lo aplicado difiere de lo propuesto, marcamos "Modificada por admin".
        const overrideAplicado = !!(
          a &&
          c &&
          ((a.fecha_desde ?? null) !== (c.fecha_desde ?? null) ||
            (a.fecha_hasta ?? null) !== (c.fecha_hasta ?? null) ||
            (a.items?.length ?? 0) !== (c.items?.length ?? 0) ||
            (a.items ?? []).some((ai) => {
              const ci = (c.items ?? []).find((x) => x.equipo_id === ai.equipo_id);
              return !ci || ci.cantidad !== ai.cantidad;
            }))
        );
        return (
          <li key={h.id} className="rounded border hairline bg-card px-2.5 py-2">
            <div className="flex items-center gap-1.5 flex-wrap">
              <Badge variant={HIST_ESTADO_VARIANT[h.estado]} className="text-[10px]">
                {HIST_ESTADO_LABEL[h.estado]}
              </Badge>
              {isDirecto && (
                <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                  Auto
                </span>
              )}
              {overrideAplicado && (
                <span className="text-[10px] text-amber-700">modificada al aprobar</span>
              )}
              <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">
                {fmtFecha(h.created_at)}
              </span>
            </div>
            {(c?.fecha_desde || c?.fecha_hasta) && (
              <div className="text-xs text-muted-foreground mt-1.5 tabular-nums">
                Fechas: {fmtFecha(c?.fecha_desde ?? "")} → {fmtFecha(c?.fecha_hasta ?? "")}
              </div>
            )}
            {itemDeltas.length > 0 && (
              <div className="text-xs text-muted-foreground mt-1">
                {itemDeltas.length} item{itemDeltas.length !== 1 ? "s" : ""} en la propuesta
              </div>
            )}
            {overrideAplicado && a && (
              <div className="text-xs text-amber-700 mt-1 tabular-nums">
                Aplicado: {fmtFecha(a.fecha_desde ?? "")} → {fmtFecha(a.fecha_hasta ?? "")}
                {a.items && ` · ${a.items.length} item${a.items.length !== 1 ? "s" : ""}`}
              </div>
            )}
            {h.mensaje && (
              <div className="text-xs text-ink mt-1.5 whitespace-pre-wrap line-clamp-3">
                {h.mensaje}
              </div>
            )}
            {h.respuesta && (
              <div className="text-xs text-muted-foreground mt-1.5 italic line-clamp-2">
                Respuesta: {h.respuesta}
              </div>
            )}
            {h.resolved_by && h.resolved_at && (
              <div className="text-[10px] text-muted-foreground mt-1">
                {h.resolved_by} · {fmtFecha(h.resolved_at)}
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Modal de confirmación con diff (cliente, modo propose)
// ─────────────────────────────────────────────────────────────────────────

function SolicitudDiffDialog({
  open,
  onOpenChange,
  original,
  datos,
  items,
  isSubmitting,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  original: {
    fecha_desde: string | null;
    fecha_hasta: string | null;
    items: {
      equipo_id: number;
      cantidad: number;
      nombre: string;
      nombre_publico?: string | null;
    }[];
  };
  datos: DraftDatos;
  items: DraftItem[];
  isSubmitting: boolean;
  onConfirm: () => void;
}) {
  const origDesde = (original.fecha_desde ?? "").slice(0, 10);
  const origHasta = (original.fecha_hasta ?? "").slice(0, 10);
  const fechasCambian = origDesde !== datos.fecha_desde || origHasta !== datos.fecha_hasta;

  const beforeQty = new Map<number, number>();
  for (const it of original.items) beforeQty.set(it.equipo_id, it.cantidad);
  const afterQty = new Map<number, number>();
  for (const it of items) afterQty.set(it.equipo_id, it.cantidad);
  const nombres = new Map<number, string>();
  for (const it of original.items) nombres.set(it.equipo_id, it.nombre_publico || it.nombre);
  for (const it of items) {
    if (!nombres.has(it.equipo_id)) nombres.set(it.equipo_id, it.nombre_publico || it.nombre);
  }
  const equipoIds = new Set<number>([...beforeQty.keys(), ...afterQty.keys()]);
  const itemsDiff = Array.from(equipoIds)
    .map((id) => ({
      id,
      antes: beforeQty.get(id) ?? 0,
      despues: afterQty.get(id) ?? 0,
      nombre: nombres.get(id) ?? `equipo #${id}`,
    }))
    .filter((d) => d.antes !== d.despues);

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-lg max-h-[85vh] flex flex-col">
        <AlertDialogHeader>
          <AlertDialogTitle>Confirmar solicitud de modificación</AlertDialogTitle>
          <AlertDialogDescription>
            Estos son los cambios que vas a pedirnos. Te avisamos por mail cuando los revisemos.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="space-y-3 max-h-[50vh] overflow-y-auto">
          {fechasCambian && (
            <div className="rounded-md border hairline px-3 py-2.5 text-sm">
              <div className="text-xs text-muted-foreground mb-1">Fechas</div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <div className="text-muted-foreground">Antes</div>
                  <div className="text-ink tabular-nums">
                    {fmtFecha(origDesde)} → {fmtFecha(origHasta)}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Nuevas</div>
                  <div className="text-ink font-medium tabular-nums">
                    {fmtFecha(datos.fecha_desde)} → {fmtFecha(datos.fecha_hasta)}
                  </div>
                </div>
              </div>
            </div>
          )}

          {itemsDiff.length > 0 && (
            <div className="rounded-md border hairline px-3 py-2.5 text-sm">
              <div className="text-xs text-muted-foreground mb-2">Equipos</div>
              <ul className="divide-y hairline -mx-3">
                {itemsDiff.map((d) => {
                  const delta = d.despues - d.antes;
                  const cls = delta > 0 ? "text-verde" : "text-destructive";
                  return (
                    <li key={d.id} className="px-3 py-1.5 flex items-center gap-2">
                      <span className="flex-1 text-ink truncate">{d.nombre}</span>
                      <span className="text-muted-foreground tabular-nums">{d.antes}</span>
                      <span className="text-muted-foreground">→</span>
                      <span className={`font-medium tabular-nums ${cls}`}>{d.despues}</span>
                      <span className={`text-xs tabular-nums w-10 text-right ${cls}`}>
                        {delta > 0 ? `+${delta}` : delta}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {!fechasCambian && itemsDiff.length === 0 && (
            <div className="text-sm text-muted-foreground">Sin cambios detectados.</div>
          )}
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel disabled={isSubmitting}>Volver</AlertDialogCancel>
          <AlertDialogAction
            onClick={(e) => {
              e.preventDefault();
              onConfirm();
            }}
            disabled={isSubmitting || (!fechasCambian && itemsDiff.length === 0)}
          >
            {isSubmitting ? "Enviando…" : "Enviar solicitud"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
