import { createLazyFileRoute, useNavigate, useParams, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
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
  Trash2,
  ArrowRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EstadoBadge } from "@/components/kit/EstadoBadge";
import { StepperPill } from "@/components/rental/equipment/shared/StepperPill";
import { WhatsAppButton } from "@/components/admin/WhatsAppButton";
import {
  adminApi,
  ESTADO_LABEL,
  pedidoPdfUrl,
  type Pedido,
  type PedidoEstado,
} from "@/lib/admin/api";
import { usePedidoDraft } from "@/components/admin/pedido/usePedidoDraft";
import { useDocumentTitle } from "@/lib/use-document-title";
import { formatARS, formatFechaCorta } from "@/lib/format";

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
  const jornadas = p.cantidad_jornadas ?? 1;
  const pagadoMonto = p.monto_pagado ?? 0;
  const total = p.total_con_iva ?? p.monto_total ?? 0;
  const restante = Math.max(0, total - pagadoMonto);

  const setQty = (equipoId: number, delta: number) =>
    setItems((its) =>
      (its ?? []).map((it) =>
        it.equipo_id === equipoId ? { ...it, cantidad: Math.max(1, it.cantidad + delta) } : it,
      ),
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

          {/* Fechas (read-only en Sub-fase 1 — editar fechas re-valida stock, viene después) */}
          <Section
            icon={Calendar}
            title="Fechas del alquiler"
            aside={
              p.fecha_desde ? (
                <span className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wide text-verde">
                  <Check className="h-3 w-3" /> stock OK
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wide text-destructive">
                  <AlertTriangle className="h-3 w-3" /> sin fechas
                </span>
              )
            }
          >
            <div className="flex items-end gap-3 flex-wrap">
              <FieldLabel label="Retiro">
                <div className="h-9 px-3 flex items-center rounded-md border hairline bg-surface-elevated text-sm tabular-nums">
                  {p.fecha_desde ? formatFechaCorta(p.fecha_desde) : "definir"}
                </div>
              </FieldLabel>
              <FieldLabel label="Devolución">
                <div className="h-9 px-3 flex items-center rounded-md border hairline bg-surface-elevated text-sm tabular-nums">
                  {p.fecha_hasta ? formatFechaCorta(p.fecha_hasta) : "definir"}
                </div>
              </FieldLabel>
              <div className="rounded-lg border hairline bg-surface-elevated px-4 py-2 text-center shrink-0">
                <div className="font-mono text-xl font-semibold leading-none">{jornadas}</div>
                <div className="font-mono text-[8px] uppercase tracking-[0.2em] text-muted-foreground mt-0.5">
                  jornadas
                </div>
              </div>
            </div>
            <p className="mt-2 font-mono text-[11px] text-muted-foreground">
              Editar fechas (con re-validación de stock) se hace por ahora desde la{" "}
              <Link to="/admin/pedidos/$id" params={{ id: String(p.id) }} className="underline">
                vista clásica
              </Link>
              .
            </p>
          </Section>

          {/* Equipos */}
          <Section icon={Box} title={`Equipos · ${items.length}`}>
            <ul className="divide-y hairline">
              {items.map((it) => (
                <li key={it.equipo_id} className="flex items-center gap-3 py-2.5">
                  <span className="inline-flex h-10 w-10 items-center justify-center rounded-md border hairline text-muted-foreground shrink-0">
                    <Box className="h-4 w-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-ink truncate">
                      {it.nombre_publico || it.nombre}
                    </div>
                    <div className="font-mono text-[11px] text-muted-foreground">
                      {fmtArs(it.precio_jornada)} / jornada
                    </div>
                  </div>
                  <StepperPill
                    qty={it.cantidad}
                    onIncrement={() => setQty(it.equipo_id, 1)}
                    onDecrement={() => setQty(it.equipo_id, -1)}
                  />
                  <div className="font-mono text-sm font-semibold tabular-nums w-24 text-right">
                    {fmtArs(it.precio_jornada * it.cantidad * jornadas)}
                  </div>
                  <button
                    type="button"
                    onClick={() => removeItem(it.equipo_id)}
                    aria-label="Quitar equipo"
                    className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              ))}
              {items.length === 0 && (
                <li className="py-4 text-sm text-muted-foreground">
                  Sin equipos. Agregá al menos uno para confirmar.
                </li>
              )}
            </ul>
            <p className="mt-1 font-mono text-[11px] text-muted-foreground">
              Agregar equipos (buscador) llega en la próxima sub-fase.
            </p>
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

        {/* ── Rail ── */}
        <aside className="px-4 md:px-5 py-5 space-y-4 bg-surface/40 hidden lg:block">
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

          {/* Desglose */}
          <RailSection label="Desglose · lo calcula el backend">
            <div className="space-y-1 text-sm">
              <BdRow
                l={`Bruto · ${jornadas} jornada${jornadas !== 1 ? "s" : ""}`}
                v={fmtArs(p.bruto)}
              />
              {(p.descuento_pct ?? 0) > 0 && (
                <BdRow
                  l={`Descuento ${p.descuento_pct}%`}
                  v={`– ${fmtArs(p.descuento_monto)}`}
                  neg
                />
              )}
              <BdRow l="Neto" v={fmtArs(p.monto_neto)} />
              <BdRow
                l={`IVA ${p.con_iva ? "21%" : ""}`}
                v={p.con_iva ? fmtArs(p.iva_monto) : "— cons. final"}
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
              <div key={pago.id} className="flex items-center justify-between text-xs mt-1">
                <span className="text-muted-foreground">
                  {pago.concepto || "Pago"} · {formatFechaCorta(pago.fecha)}
                </span>
                <span className="font-mono">{fmtArs(pago.monto)}</span>
              </div>
            ))}
            <Button
              variant="outline"
              size="sm"
              className="w-full mt-2"
              disabled={p.estado === "cancelado"}
              onClick={() => navigate({ to: "/admin/pedidos/$id", params: { id: String(p.id) } })}
            >
              <Coins className="h-4 w-4 mr-1" /> Registrar pago
            </Button>
          </RailSection>

          {/* Documentos */}
          <RailSection label="Documentos">
            <div className="flex flex-wrap gap-1.5">
              {(
                [
                  ["Remito", "albaran"],
                  ["Contrato", "contrato"],
                  ["Packing", "packing-list"],
                  ["Presupuesto", "pdf"],
                ] as const
              ).map(([label, kind]) => (
                <a
                  key={kind}
                  href={pedidoPdfUrl(p.id, kind)}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 rounded-md border hairline px-2 py-1 font-mono text-[11px] text-muted-foreground hover:text-ink hover:border-ink"
                >
                  <FileText className="h-3 w-3" />
                  {label}
                </a>
              ))}
            </div>
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
