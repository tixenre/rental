import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { authedFetch } from "@/lib/authedFetch";
import { clienteApi } from "@/lib/cliente/api";
import { PublicLayout } from "@/components/rental/PublicLayout";
import { StatCard } from "@/components/rental/StatCard";
import { EstadoBadge } from "@/components/rental/EstadoBadge";
import { ArrowRight, ChevronDown, ShoppingBag, Pencil, Clock, X as XIcon, CheckCircle2, XCircle, Info, FileText, FileSignature, Truck, MessageCircle } from "lucide-react";
import { toast } from "sonner";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { businessWhatsappLink } from "@/lib/business";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/cliente/portal")({
  head: () => ({ meta: [{ title: "Mis pedidos — Rambla Rental" }] }),
  component: ClientePortal,
});

type Perfil = {
  nombre: string; apellido: string; email: string;
  telefono: string; direccion: string;
};

type Item = {
  nombre: string;
  marca: string;
  modelo?: string | null;
  cantidad: number;
  precio_jornada: number;
  subtotal: number;
  foto_url?: string;
  nombre_publico?: string | null;
  nombre_publico_largo?: string | null;
};
type Pago = { monto: number; concepto?: string | null; fecha: string };
type SolicitudPortal = {
  id: number;
  estado: "pendiente" | "aprobada" | "rechazada" | "cancelada";
  respuesta?: string | null;
  resolved_by?: string | null;
  resolved_at?: string | null;
  created_at: string;
};
type Pedido = {
  id: number; numero_pedido: string; estado: string;
  fecha_desde?: string; fecha_hasta?: string;
  monto_total?: number; monto_pagado?: number;
  descuento_pct?: number | null;
  notas?: string | null;
  items: Item[];
  pagos?: Pago[];
  solicitudes?: SolicitudPortal[];
  documentos_disponibles: { remito: boolean; contrato: boolean; albaran: boolean };
};

const ACTIVE_STATES = new Set(["borrador", "presupuesto", "confirmado", "retirado"]);
const HIST_STATES = new Set(["devuelto", "finalizado", "cancelado"]);
const MODIFICABLE_STATES = new Set(["presupuesto", "confirmado"]);

// ── Documentos: aclaraciones + notificación one-shot ─────────────────────

type DocTipo = "remito" | "contrato" | "albaran";

const DOC_LABEL: Record<DocTipo, string> = {
  remito: "Remito",
  contrato: "Contrato",
  albaran: "Albarán",
};

const DOC_DESCRIPTION: Partial<Record<DocTipo, string>> = {
  contrato: "Es el documento de alquiler firmado entre vos y nosotros.",
  albaran:  "Te sirve para tener constancia ante tu aseguradora.",
};

// Sólo Contrato y Albarán disparan el popup one-shot. Remito se incluye en el
// listado de docs pero no es trigger (mismo evento que Contrato).
const DOC_NOTIFICABLE: DocTipo[] = ["contrato", "albaran"];

const docSeenKey = (pedidoId: number, tipo: DocTipo) =>
  `rambla.doc_seen.${pedidoId}.${tipo}`;

function wasDocSeen(pedidoId: number, tipo: DocTipo): boolean {
  try { return localStorage.getItem(docSeenKey(pedidoId, tipo)) === "1"; }
  catch { return false; }
}

function markDocSeen(pedidoId: number, tipo: DocTipo): void {
  try { localStorage.setItem(docSeenKey(pedidoId, tipo), "1"); }
  catch { /* ignore */ }
}

type Filtro = "todos" | "activos" | "historial";

const TAB_OPTIONS: { value: Filtro; label: string }[] = [
  { value: "todos", label: "Todos" },
  { value: "activos", label: "Activos" },
  { value: "historial", label: "Historial" },
];

function fmt(n?: number) {
  if (n == null) return "—";
  return new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 }).format(n);
}
function fmtDate(s?: string) {
  if (!s) return "—";
  // slice(0,10) normaliza "YYYY-MM-DD HH:MM:SS" y "YYYY-MM-DDTHH:MM:SS" a "YYYY-MM-DD"
  const d = new Date(s.slice(0, 10) + "T12:00:00");
  const dias = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
  const meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  return `${dias[d.getDay()]} ${d.getDate()} ${meses[d.getMonth()]}`;
}
function fmtTime(s?: string) {
  if (!s || s.length < 16) return null;
  // "YYYY-MM-DD HH:MM:SS" → "HH:MM"
  return s.slice(11, 16);
}

export default function ClientePortal() {
  const navigate = useNavigate();
  const [perfil, setPerfil] = useState<Perfil | null>(null);
  const [pedidos, setPedidos] = useState<Pedido[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [tab, setTab] = useState<Filtro>("todos");
  const [ventanaHoras, setVentanaHoras] = useState<number>(24);
  const [docsNuevos, setDocsNuevos] = useState<
    Array<{ pedidoId: number; numero: string; tipo: DocTipo }>
  >([]);

  function reloadPedidos() {
    authedFetch("/api/cliente/pedidos").then(async (r) => {
      if (r.ok) setPedidos(await r.json());
    });
  }

  useEffect(() => {
    let alive = true;
    Promise.all([
      authedFetch("/api/cliente/me"),
      authedFetch("/api/cliente/pedidos"),
    ]).then(async ([rp, ro]) => {
      if (!alive) return;
      if (!rp.ok || !ro.ok) { navigate({ to: "/cliente/login" }); return; }
      setPerfil(await rp.json());
      setPedidos(await ro.json());
    }).catch(() => navigate({ to: "/cliente/login" }))
      .finally(() => alive && setLoading(false));

    clienteApi.modificacionConfig()
      .then((c) => { if (alive) setVentanaHoras(c.ventana_horas); })
      .catch(() => { /* default 24 */ });

    return () => { alive = false; };
  }, [navigate]);

  // Calculamos los documentos "nuevos" (disponibles + no vistos antes) cada
  // vez que cambia la lista. Disparan el popup one-shot.
  useEffect(() => {
    const nuevos: Array<{ pedidoId: number; numero: string; tipo: DocTipo }> = [];
    for (const p of pedidos) {
      const docs = p.documentos_disponibles;
      if (!docs) continue;
      for (const tipo of DOC_NOTIFICABLE) {
        if (docs[tipo] && !wasDocSeen(p.id, tipo)) {
          nuevos.push({ pedidoId: p.id, numero: String(p.numero_pedido ?? p.id), tipo });
        }
      }
    }
    setDocsNuevos(nuevos);
  }, [pedidos]);

  function dismissDocsPopup() {
    for (const d of docsNuevos) markDocSeen(d.pedidoId, d.tipo);
    setDocsNuevos([]);
  }

  function verPedido(pedidoId: number) {
    setExpanded(pedidoId);
    dismissDocsPopup();
    // Scroll a la card después de renderizar la expansión.
    setTimeout(() => {
      const el = document.getElementById(`pedido-${pedidoId}`);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 100);
  }

  async function handleLogout() {
    await authedFetch("/auth/logout", { method: "POST" }).catch(() => {});
    navigate({ to: "/cliente/login" });
  }

  if (loading) {
    return (
      <PublicLayout topBar={{ variant: "cliente" }}>
        <div className="max-w-[760px] mx-auto px-6 pt-8 pb-20">
          <div className="grid grid-cols-3 gap-2 sm:gap-2.5 mb-8">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-[88px] rounded-md border hairline bg-muted/30 animate-pulse" />
            ))}
          </div>
          <div className="flex flex-col gap-2.5">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-14 rounded-xl border border-[var(--hairline)] bg-muted/20 animate-pulse" />
            ))}
          </div>
        </div>
      </PublicLayout>
    );
  }

  const userName = perfil ? `${perfil.nombre} ${perfil.apellido}` : undefined;

  const activosPedidos = pedidos.filter((p) => ACTIVE_STATES.has(p.estado));
  const totalActivos = activosPedidos.reduce((sum, p) => sum + (p.monto_total ?? 0), 0);
  const pendientePago = activosPedidos.reduce(
    (sum, p) => sum + Math.max(0, (p.monto_total ?? 0) - (p.monto_pagado ?? 0)),
    0,
  );
  const historico = pedidos.filter((p) => HIST_STATES.has(p.estado)).length;

  const counts: Record<Filtro, number> = {
    todos: pedidos.length,
    activos: activosPedidos.length,
    historial: historico,
  };

  const filteredPedidos =
    tab === "activos" ? pedidos.filter((p) => ACTIVE_STATES.has(p.estado))
    : tab === "historial" ? pedidos.filter((p) => HIST_STATES.has(p.estado))
    : pedidos;

  return (
    <PublicLayout
      topBar={{ variant: "cliente", userName, onLogout: handleLogout }}
    >
      <div className="bg-amber border-b border-[color-mix(in_oklch,var(--ink)_12%,transparent)]">
        <div className="max-w-[760px] mx-auto px-6 pt-9 pb-10">
          <div className="font-mono text-[10px] uppercase tracking-[0.26em] text-ink/60">
            Portal de clientes
          </div>
          <h1 className="font-display text-[48px] font-black text-ink leading-none tracking-[-0.025em] mt-1.5">
            {perfil ? `Hola, ${perfil.nombre}` : "Mis pedidos"}
          </h1>
          <p className="font-sans text-sm text-ink/70 mt-3">
            Mirá tus pedidos, descargá documentos y consultá pagos.
          </p>
        </div>
      </div>

      <div className="max-w-[760px] mx-auto px-6 pt-8 pb-20">
        {pedidos.length > 0 && (
          <div className="grid grid-cols-3 gap-2 sm:gap-2.5 mb-8">
            <StatCard
              label="Activos"
              value={String(activosPedidos.length)}
              meta={`${fmt(totalActivos)} en rentals`}
            />
            <StatCard
              label="A pagar"
              value={pendientePago > 0 ? fmt(pendientePago) : "$ 0"}
              meta={pendientePago > 0 ? "saldo pendiente" : "todo al día"}
              valueClassName={pendientePago === 0 ? "text-verde" : undefined}
            />
            <StatCard
              label="Histórico"
              value={String(historico)}
              meta="pedidos completados"
            />
          </div>
        )}

        <h2 className="font-display text-[22px] font-black text-ink tracking-[-0.01em] mb-4">
          Mis pedidos
        </h2>

        {pedidos.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-4">
            {TAB_OPTIONS.map(({ value, label }) => {
              const active = tab === value;
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => setTab(value)}
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full border px-3.5 py-1.5 font-sans text-xs font-semibold transition",
                    active
                      ? "bg-ink text-amber border-ink"
                      : "border-[var(--hairline)] text-muted-foreground hover:text-ink hover:border-ink",
                  )}
                >
                  {label}
                  <span
                    className={cn(
                      "font-mono text-[9px] tabular-nums",
                      active ? "opacity-85" : "opacity-60",
                    )}
                  >
                    {counts[value]}
                  </span>
                </button>
              );
            })}
          </div>
        )}

        {pedidos.length === 0 ? (
          <PedidoEmpty
            title="Sin pedidos aún"
            sub="Todavía no tenés pedidos registrados."
            cta
          />
        ) : filteredPedidos.length === 0 ? (
          <PedidoEmpty
            title={tab === "activos" ? "Sin rentals activos" : "Sin pedidos por acá"}
            sub={
              tab === "activos"
                ? "No tenés rentals activos en este momento."
                : "No tenés pedidos en esta sección todavía."
            }
            cta
          />
        ) : (
          <div className="flex flex-col gap-2.5">
            {filteredPedidos.map((p) => (
              <PedidoCard
                key={p.id}
                pedido={p}
                expanded={expanded === p.id}
                onToggle={() => setExpanded(expanded === p.id ? null : p.id)}
                ventanaHoras={ventanaHoras}
                onChanged={reloadPedidos}
              />
            ))}
          </div>
        )}
      </div>

      <DocAvailablePopup
        nuevos={docsNuevos}
        onDismiss={dismissDocsPopup}
        onVerPedido={verPedido}
      />
    </PublicLayout>
  );
}

function PedidoEmpty({ title, sub, cta }: { title: string; sub: string; cta?: boolean }) {
  return (
    <div className="rounded-xl border border-dashed border-[var(--hairline)] px-6 py-[60px] text-center">
      <div className="mx-auto mb-3.5 grid h-14 w-14 place-items-center rounded-full bg-amber-soft text-amber">
        <ShoppingBag className="h-6 w-6" strokeWidth={1.5} />
      </div>
      <div className="font-display text-xl font-black text-ink mb-1.5">{title}</div>
      <div className="font-sans text-[13px] text-muted-foreground mb-[18px]">{sub}</div>
      {cta && (
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 rounded-full bg-ink px-5 py-2.5 font-sans text-[13px] font-bold text-amber transition hover:bg-amber hover:text-ink"
        >
          Explorar catálogo <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      )}
    </div>
  );
}

function jornadasEntre(desde?: string, hasta?: string): number {
  if (!desde || !hasta) return 1;
  const d1 = new Date(desde + "T12:00:00").getTime();
  const d2 = new Date(hasta + "T12:00:00").getTime();
  if (Number.isNaN(d1) || Number.isNaN(d2) || d2 < d1) return 1;
  return Math.max(1, Math.ceil((d2 - d1) / 86_400_000) + 1);
}

function PedidoCard({
  pedido, expanded, onToggle, ventanaHoras, onChanged,
}: {
  pedido: Pedido;
  expanded: boolean;
  onToggle: () => void;
  ventanaHoras: number;
  onChanged: () => void;
}) {
  const navigate = useNavigate();
  const { documentos_disponibles: docs } = pedido;
  const numero = pedido.numero_pedido ?? pedido.id;
  const jornadas = jornadasEntre(pedido.fecha_desde, pedido.fecha_hasta);

  const [askCancel, setAskCancel] = useState(false);
  const pendiente = (pedido.solicitudes ?? []).find((s) => s.estado === "pendiente");
  // Última solicitud que el cliente debe ver: aprobada, rechazada, o
  // cancelada por el sistema (cuando el pedido cambia de estado). Las
  // canceladas por el propio cliente las ocultamos: él la canceló.
  const ultimaResuelta = !pendiente ? (pedido.solicitudes ?? [])
    .filter((s) => {
      if (s.estado === "aprobada" || s.estado === "rechazada") return true;
      if (s.estado === "cancelada" && s.resolved_by === "system") return true;
      return false;
    })
    .sort((a, b) => (b.resolved_at ?? b.created_at).localeCompare(a.resolved_at ?? a.created_at))[0]
    : undefined;

  const dentroVentana = (() => {
    if (!pedido.fecha_desde) return true; // pedido sin fechas: permitir editar
    const desde = new Date(pedido.fecha_desde.slice(0, 10) + "T00:00:00").getTime();
    if (Number.isNaN(desde)) return true; // fecha inválida: no bloqueamos
    const ms = ventanaHoras * 60 * 60 * 1000;
    return desde - Date.now() >= ms;
  })();

  const puedeModificar =
    MODIFICABLE_STATES.has(pedido.estado) && !pendiente && dentroVentana;

  async function cancelarSolicitud() {
    if (!pendiente) return;
    try {
      await clienteApi.cancelarSolicitud(pedido.id, pendiente.id);
      toast.success("Solicitud cancelada");
      onChanged();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  const subtotalItems = pedido.items.reduce((acc, it) => acc + it.subtotal, 0);
  const descuentoPct = pedido.descuento_pct ?? 0;
  const descuentoMonto = Math.round(subtotalItems * (descuentoPct / 100));
  const total = pedido.monto_total ?? (subtotalItems - descuentoMonto);
  const pagado = pedido.monto_pagado ?? 0;
  const balance = Math.max(0, total - pagado);

  const retiroTime = fmtTime(pedido.fecha_desde);
  const devolucionTime = fmtTime(pedido.fecha_hasta);

  return (
    <div
      id={`pedido-${pedido.id}`}
      className={cn(
        "rounded-xl border bg-surface overflow-hidden transition-[border-color,box-shadow] scroll-mt-4",
        expanded
          ? "border-amber shadow-[0_0_0_1px_var(--amber)]"
          : "border-[var(--hairline)] hover:border-ink/30",
      )}
    >
      <div className="flex items-stretch">
        <button
          type="button"
          onClick={onToggle}
          className="flex-1 min-w-0 flex items-center gap-3.5 px-4 sm:px-[18px] py-3.5 transition hover:bg-[color-mix(in_oklch,var(--ink)_2%,transparent)] text-left"
        >
          <span className="font-mono text-[11px] font-bold text-ink tracking-[0.05em]">
            #{pedido.numero_pedido}
          </span>
          <EstadoBadge estado={pedido.estado} />
          <span className="font-sans text-[13px] text-muted-foreground flex-1 min-w-0 truncate">
            {fmtDate(pedido.fecha_desde)}
            <span className="opacity-40 mx-1">→</span>
            {fmtDate(pedido.fecha_hasta)}
          </span>
          {pedido.monto_total != null && (
            <span className="font-display text-lg font-extrabold text-ink tabular-nums shrink-0">
              {fmt(pedido.monto_total)}
            </span>
          )}
          <ChevronDown
            className={cn(
              "h-4 w-4 shrink-0 transition-[transform,color] duration-200",
              expanded ? "rotate-180 text-ink" : "text-muted-foreground",
            )}
          />
        </button>
        {!expanded && puedeModificar && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              navigate({
                to: "/cliente/pedidos/$id/editar",
                params: { id: String(pedido.id) },
              });
            }}
            className="shrink-0 px-3 sm:px-4 border-l border-[var(--hairline)] text-ink hover:bg-amber-soft transition inline-flex items-center gap-1.5"
            aria-label="Modificar pedido"
          >
            <Pencil className="h-3.5 w-3.5" />
            <span className="font-sans text-xs font-semibold hidden sm:inline">Modificar</span>
          </button>
        )}
      </div>

      {expanded && (
        <div className="border-t border-dashed border-[var(--hairline)] px-4 sm:px-[18px] pt-[18px] pb-[22px] flex flex-col gap-5 animate-[expand-in_.22s_ease-out]">

          {pendiente && (
            <section className="rounded-md border border-amber bg-amber-soft px-3.5 py-3 flex items-start gap-2.5">
              <Clock className="h-4 w-4 text-amber mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="font-sans text-[13px] font-semibold text-ink">
                  Solicitud de modificación pendiente
                </div>
                <div className="font-sans text-xs text-ink/70 mt-0.5">
                  Estamos revisando los cambios que pediste. Te avisamos por mail cuando los resolvamos.
                </div>
              </div>
              <button
                type="button"
                onClick={() => setAskCancel(true)}
                className="rounded-full px-4 py-2 font-sans text-sm font-semibold text-ink border border-ink/20 hover:border-ink transition shrink-0 inline-flex items-center gap-1.5 min-h-[40px]"
              >
                <XIcon className="h-3.5 w-3.5" /> Cancelar
              </button>
            </section>
          )}

          {ultimaResuelta && (() => {
            const isAprobada  = ultimaResuelta.estado === "aprobada";
            const isRechazada = ultimaResuelta.estado === "rechazada";
            const isSystemCancel = ultimaResuelta.estado === "cancelada"; // ya filtramos por resolved_by='system'
            const titulo =
              isAprobada  ? "Tu última solicitud fue aprobada"
              : isRechazada ? "Tu última solicitud fue rechazada"
              : "Tu solicitud quedó sin efecto";
            return (
              <section
                className={cn(
                  "rounded-md border px-3.5 py-3 flex items-start gap-2.5",
                  isAprobada  ? "border-emerald-300 bg-emerald-50"
                  : isRechazada ? "border-rose-300 bg-rose-50"
                  : "border-violet-300 bg-violet-50",
                )}
              >
                {isAprobada  ? <CheckCircle2 className="h-4 w-4 text-emerald-600 mt-0.5 shrink-0" />
                : isRechazada ? <XCircle className="h-4 w-4 text-rose-600 mt-0.5 shrink-0" />
                : <Info className="h-4 w-4 text-violet-600 mt-0.5 shrink-0" />}
                <div className="flex-1 min-w-0">
                  <div className="font-sans text-[13px] font-semibold text-ink">
                    {titulo}
                  </div>
                  {ultimaResuelta.respuesta && (
                    <div className="font-sans text-xs text-ink/80 mt-0.5 whitespace-pre-wrap">
                      {isSystemCancel ? ultimaResuelta.respuesta : ultimaResuelta.respuesta}
                    </div>
                  )}
                </div>
              </section>
            );
          })()}

          {puedeModificar && (
            <section>
              <button
                type="button"
                onClick={() => navigate({
                  to: "/cliente/pedidos/$id/editar",
                  params: { id: String(pedido.id) },
                })}
                className="inline-flex items-center gap-1.5 rounded-full bg-ink px-4 py-2 font-sans text-[13px] font-bold text-amber hover:bg-amber hover:text-ink transition"
              >
                <Pencil className="h-3.5 w-3.5" /> Modificar pedido
              </button>
              {pedido.estado === "confirmado" && (
                <p className="mt-2 font-sans text-xs text-muted-foreground">
                  Los cambios necesitarán nuestra aprobación.
                </p>
              )}
            </section>
          )}

          {!puedeModificar && MODIFICABLE_STATES.has(pedido.estado) && !pendiente && !dentroVentana && (
            <section className="rounded-md border border-dashed border-[var(--hairline)] px-3.5 py-2.5 font-sans text-xs text-muted-foreground">
              No es posible modificar este pedido a menos de {ventanaHoras} h del retiro. Contactanos directamente.
            </section>
          )}

          <section className="grid grid-cols-3 gap-2">
            <div className="rounded-md border border-[var(--hairline)] bg-card px-3 py-2.5">
              <div className="font-mono text-[8px] uppercase tracking-[0.22em] text-muted-foreground">Retiro</div>
              <div className="font-sans text-sm font-semibold text-ink mt-0.5">{fmtDate(pedido.fecha_desde)}</div>
              {retiroTime && <div className="font-mono text-[10px] text-muted-foreground">{retiroTime}</div>}
            </div>
            <div className="rounded-md border border-[var(--hairline)] bg-card px-3 py-2.5">
              <div className="font-mono text-[8px] uppercase tracking-[0.22em] text-muted-foreground">Devolución</div>
              <div className="font-sans text-sm font-semibold text-ink mt-0.5">{fmtDate(pedido.fecha_hasta)}</div>
              {devolucionTime && <div className="font-mono text-[10px] text-muted-foreground">{devolucionTime}</div>}
            </div>
            <div className="rounded-md border border-[var(--hairline)] bg-card px-3 py-2.5">
              <div className="font-mono text-[8px] uppercase tracking-[0.22em] text-muted-foreground">Jornadas</div>
              <div className="font-display text-2xl font-black text-ink tabular-nums leading-none mt-1">{jornadas}</div>
            </div>
          </section>

          <section>
            <h3 className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted-foreground mb-2">
              Equipos ({pedido.items.length})
            </h3>
            <ul>
              {pedido.items.map((item, i) => {
                const display = item.nombre_publico || item.nombre;
                return (
                  <li
                    key={i}
                    className="flex items-center gap-2.5 py-2 border-b border-[var(--hairline)] last:border-b-0"
                  >
                    {item.foto_url ? (
                      <img
                        src={item.foto_url}
                        alt={display}
                        loading="lazy"
                        className="h-10 w-10 rounded-sm border border-[var(--hairline)] bg-white object-cover shrink-0"
                      />
                    ) : (
                      <div className="h-10 w-10 rounded-sm border border-[var(--hairline)] bg-white grid place-items-center shrink-0">
                        <ShoppingBag className="h-4 w-4 text-muted-foreground" strokeWidth={1.5} />
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      {item.marca && (
                        <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground leading-none">
                          {item.marca}
                        </div>
                      )}
                      <div className="font-sans text-[13px] font-semibold text-ink leading-tight mt-0.5 truncate">
                        {display}
                      </div>
                      <div className="font-mono text-[10px] text-muted-foreground tabular-nums mt-0.5">
                        {item.cantidad} × {fmt(item.precio_jornada)}/j · {jornadas}j
                      </div>
                    </div>
                    <div className="font-mono text-[13px] font-bold text-ink tabular-nums shrink-0">
                      {fmt(item.subtotal)}
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>

          <section className="flex flex-col gap-1.5 pt-2.5 border-t border-[var(--hairline)]">
            <div className="flex justify-between items-baseline font-sans text-[13px]">
              <span className="text-muted-foreground">Subtotal equipos</span>
              <span className="font-mono font-semibold text-ink tabular-nums">{fmt(subtotalItems)}</span>
            </div>
            {descuentoPct > 0 && (
              <div className="flex justify-between items-baseline font-sans text-[13px]">
                <span className="text-muted-foreground">Descuento ({descuentoPct}%)</span>
                <span className="font-mono font-semibold tabular-nums text-verde">
                  −{fmt(descuentoMonto)}
                </span>
              </div>
            )}
            <div className="flex justify-between items-baseline pt-1.5 mt-1 border-t border-[var(--hairline)]">
              <span className="font-sans text-[15px] font-bold text-ink">Total</span>
              <span className="font-display text-[22px] font-black text-ink tabular-nums">{fmt(total)}</span>
            </div>
            {pagado > 0 && (
              <>
                <div className="flex justify-between items-baseline font-sans text-[13px]">
                  <span className="text-muted-foreground">Pagado</span>
                  <span className="font-mono font-semibold tabular-nums text-verde">{fmt(pagado)}</span>
                </div>
                <div className="flex justify-between items-baseline font-sans text-[13px]">
                  <span className="text-muted-foreground">{balance > 0 ? "Balance pendiente" : "Saldo"}</span>
                  <span className={cn("font-mono font-bold tabular-nums", balance > 0 ? "text-ink" : "text-verde")}>
                    {fmt(balance)}
                  </span>
                </div>
              </>
            )}
          </section>

          {pedido.pagos && pedido.pagos.length > 0 && (
            <section>
              <h3 className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted-foreground mb-2">Pagos</h3>
              <ul className="flex flex-col gap-1">
                {pedido.pagos.map((pg, i) => (
                  <li key={i} className="flex items-center justify-between gap-2 font-sans text-xs text-muted-foreground">
                    <span className="truncate">
                      {fmtDate(pg.fecha)}{pg.concepto ? ` · ${pg.concepto}` : ""}
                    </span>
                    <span className="font-mono tabular-nums text-verde shrink-0">{fmt(pg.monto)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {(docs.remito || docs.contrato || docs.albaran) && (
            <section>
              <h3 className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted-foreground mb-2">
                Documentos
              </h3>
              <div className="grid gap-2 [grid-template-columns:repeat(auto-fill,minmax(180px,1fr))]">
                {docs.remito && (
                  <DocActions pedidoId={pedido.id} numero={numero} tipo="remito" label="Remito" />
                )}
                {docs.contrato && (
                  <DocActions
                    pedidoId={pedido.id} numero={numero} tipo="contrato" label="Contrato"
                    description={DOC_DESCRIPTION.contrato}
                  />
                )}
                {docs.albaran && (
                  <DocActions
                    pedidoId={pedido.id} numero={numero} tipo="albaran" label="Albarán"
                    description={DOC_DESCRIPTION.albaran}
                  />
                )}
              </div>
            </section>
          )}

          {pedido.notas && (
            <section>
              <h3 className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted-foreground mb-2">Notas</h3>
              <div className="rounded-md border border-[color-mix(in_oklch,var(--amber)_40%,transparent)] bg-amber-soft px-3.5 py-3 font-sans text-xs text-ink leading-[1.5] whitespace-pre-wrap">
                {pedido.notas}
              </div>
            </section>
          )}

          {(() => {
            const waHref = businessWhatsappLink(
              `Hola, consulta sobre el pedido #${numero}`
            );
            if (!waHref) return null;
            return (
              <section>
                <a
                  href={waHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-full bg-[#25D366] text-white px-4 py-2.5 font-sans text-sm font-semibold hover:brightness-95 transition min-h-[44px]"
                >
                  <MessageCircle className="h-4 w-4" strokeWidth={2.2} />
                  Consulta por WhatsApp
                </a>
              </section>
            );
          })()}
        </div>
      )}

      <AlertDialog open={askCancel} onOpenChange={setAskCancel}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancelar solicitud de modificación</AlertDialogTitle>
            <AlertDialogDescription>
              Vamos a descartar los cambios que pediste. El pedido va a quedar como estaba.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Volver</AlertDialogCancel>
            <AlertDialogAction onClick={() => { setAskCancel(false); cancelarSolicitud(); }}>
              Cancelar solicitud
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

const DOC_ICONS: Record<"remito" | "contrato" | "albaran", string> = {
  remito:
    "M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8",
  contrato:
    "M9 11l3 3 8-8 M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11",
  albaran:
    "M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z",
};

function DocPath({ tipo }: { tipo: keyof typeof DOC_ICONS }) {
  const paths = DOC_ICONS[tipo].split(" M");
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      {paths.map((p, i) => <path key={i} d={i === 0 ? p : `M${p}`} />)}
    </svg>
  );
}

/**
 * Acciones por documento: Ver (preview HTML en modal) + Descargar (PDF).
 * Issue #106.
 */
function DocActions({
  pedidoId,
  numero,
  tipo,
  label,
  description,
}: {
  pedidoId: number;
  numero: string;
  tipo: "remito" | "contrato" | "albaran";
  label: string;
  description?: string;
}) {
  const [previewOpen, setPreviewOpen] = useState(false);
  // Badge "Nuevo" si todavía no se vio. Sólo para contrato/albaran (los
  // notificables). El estado vive en localStorage; lo trackeamos con un
  // ref local para que el badge desaparezca instantáneamente al tocar.
  const [seen, setSeen] = useState<boolean>(() =>
    tipo === "remito" ? true : wasDocSeen(pedidoId, tipo)
  );
  const showNewBadge = !seen;

  function markSeen() {
    if (tipo === "remito") return;
    markDocSeen(pedidoId, tipo);
    setSeen(true);
  }

  return (
    <>
      <div className="flex items-stretch gap-1">
        <button
          type="button"
          onClick={() => { markSeen(); setPreviewOpen(true); }}
          className="flex-1 relative flex items-center gap-2.5 rounded-md border border-[var(--hairline)] bg-card px-3 py-2.5 text-left transition hover:border-ink hover:bg-muted"
        >
          {showNewBadge && (
            <span className="absolute -top-1.5 -right-1.5 rounded-full bg-rose-500 text-white text-[9px] font-bold tracking-wide px-1.5 py-0.5 leading-none shadow">
              Nuevo
            </span>
          )}
          <div className="grid h-8 w-8 place-items-center rounded-sm bg-amber-soft text-amber shrink-0">
            <DocPath tipo={tipo} />
          </div>
          <div className="min-w-0">
            <div className="font-sans text-xs font-semibold text-ink leading-tight">{label}</div>
            {description ? (
              <div className="font-sans text-[11px] text-muted-foreground leading-tight mt-0.5 line-clamp-2">
                {description}
              </div>
            ) : (
              <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted-foreground mt-0.5">
                Ver · PDF
              </div>
            )}
          </div>
        </button>
        <a
          href={`/api/cliente/pedidos/${pedidoId}/${tipo}.pdf`}
          download={`${tipo}-${numero}.pdf`}
          onClick={markSeen}
          className="grid place-items-center w-10 rounded-md border border-[var(--hairline)] bg-card text-muted-foreground transition hover:border-ink hover:text-ink"
          title={`Descargar ${label} en PDF`}
          aria-label={`Descargar ${label} en PDF`}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
        </a>
      </div>

      {previewOpen && (
        <DocPreviewModal
          title={label}
          url={`/api/cliente/pedidos/${pedidoId}/${tipo}?format=html`}
          downloadUrl={`/api/cliente/pedidos/${pedidoId}/${tipo}.pdf`}
          downloadFilename={`${tipo}-${numero}.pdf`}
          onClose={() => setPreviewOpen(false)}
        />
      )}
    </>
  );
}

/**
 * Modal con iframe que muestra el HTML del documento. Botón de descargar
 * PDF en el header. ESC o click afuera cierra.
 */
function DocPreviewModal({
  title,
  url,
  downloadUrl,
  downloadFilename,
  onClose,
}: {
  title: string;
  url: string;
  downloadUrl: string;
  downloadFilename: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-stretch sm:items-center justify-center sm:p-6"
      onClick={onClose}
    >
      <div
        className="bg-background w-full sm:max-w-4xl sm:max-h-[90vh] h-full sm:h-auto flex flex-col sm:rounded-lg overflow-hidden shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between gap-2 border-b hairline px-3 sm:px-4 py-3 shrink-0">
          <h2 className="font-display text-base text-ink truncate min-w-0">{title}</h2>
          <div className="flex items-center gap-1 sm:gap-2 shrink-0">
            <a
              href={downloadUrl}
              download={downloadFilename}
              className="inline-flex items-center gap-1.5 rounded-md bg-ink text-amber px-2.5 sm:px-3 py-2 text-xs font-medium hover:brightness-110 transition"
              aria-label="Descargar PDF"
            >
              <span aria-hidden>⬇</span>
              <span className="hidden sm:inline">Descargar PDF</span>
            </a>
            <button
              type="button"
              onClick={onClose}
              className="grid h-10 w-10 place-items-center rounded-md hover:bg-muted transition"
              aria-label="Cerrar"
            >
              ✕
            </button>
          </div>
        </header>
        <iframe
          src={url}
          title={title}
          className="flex-1 w-full bg-white border-0"
        />
      </div>
    </div>
  );
}

/**
 * Popup one-shot que notifica al cliente cuando un documento nuevo
 * (Contrato/Albarán) está disponible. Cada (pedido, doc) se persiste en
 * localStorage al cerrar para no volver a aparecer.
 */
function DocAvailablePopup({
  nuevos, onDismiss, onVerPedido,
}: {
  nuevos: Array<{ pedidoId: number; numero: string; tipo: DocTipo }>;
  onDismiss: () => void;
  onVerPedido: (pedidoId: number) => void;
}) {
  const open = nuevos.length > 0;
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onDismiss(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Tenés documentos nuevos disponibles</DialogTitle>
          <DialogDescription>
            Estos documentos quedaron habilitados en tu portal. Podés verlos cuando quieras.
          </DialogDescription>
        </DialogHeader>
        <ul className="space-y-2.5 my-2">
          {nuevos.map((d) => {
            const Icon =
              d.tipo === "contrato" ? FileSignature
              : d.tipo === "albaran" ? Truck
              : FileText;
            return (
              <li
                key={`${d.pedidoId}-${d.tipo}`}
                className="flex items-start gap-3 rounded-md border hairline px-3 py-2.5"
              >
                <div className="grid h-9 w-9 place-items-center rounded-sm bg-amber-soft text-amber shrink-0">
                  <Icon className="h-4 w-4" strokeWidth={1.7} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-sans text-sm font-semibold text-ink">
                    {DOC_LABEL[d.tipo]}
                    <span className="text-muted-foreground font-mono text-xs ml-1.5">#{d.numero}</span>
                  </div>
                  {DOC_DESCRIPTION[d.tipo] && (
                    <div className="font-sans text-xs text-muted-foreground mt-0.5">
                      {DOC_DESCRIPTION[d.tipo]}
                    </div>
                  )}
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="shrink-0"
                  onClick={() => onVerPedido(d.pedidoId)}
                >
                  Ver pedido
                </Button>
              </li>
            );
          })}
        </ul>
        <DialogFooter>
          <Button onClick={onDismiss}>Entendido</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
