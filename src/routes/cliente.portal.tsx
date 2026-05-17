import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { authedFetch } from "@/lib/authedFetch";
import { PublicLayout } from "@/components/rental/PublicLayout";
import { StatCard } from "@/components/rental/StatCard";
import { EstadoBadge } from "@/components/rental/EstadoBadge";
import { ArrowRight, ChevronDown, ShoppingBag } from "lucide-react";
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
type Pedido = {
  id: number; numero_pedido: string; estado: string;
  fecha_desde?: string; fecha_hasta?: string;
  monto_total?: number; monto_pagado?: number;
  descuento_pct?: number | null;
  notas?: string | null;
  items: Item[];
  pagos?: Pago[];
  documentos_disponibles: { remito: boolean; contrato: boolean; albaran: boolean };
};

const ACTIVE_STATES = new Set(["solicitado", "confirmado", "entregado"]);
const HIST_STATES = new Set(["devuelto", "finalizado", "cancelado"]);

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
    return () => { alive = false; };
  }, [navigate]);

  async function handleLogout() {
    await authedFetch("/auth/logout", { method: "POST" }).catch(() => {});
    navigate({ to: "/cliente/login" });
  }

  if (loading) {
    return (
      <PublicLayout topBar={{ variant: "cliente" }}>
        <div className="grid place-items-center py-24 text-sm text-muted-foreground">
          Cargando…
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
          <div className="grid grid-cols-3 gap-2.5 mb-8">
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
              />
            ))}
          </div>
        )}
      </div>
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

function PedidoCard({ pedido, expanded, onToggle }: { pedido: Pedido; expanded: boolean; onToggle: () => void }) {
  const { documentos_disponibles: docs } = pedido;
  const numero = pedido.numero_pedido ?? pedido.id;
  const jornadas = jornadasEntre(pedido.fecha_desde, pedido.fecha_hasta);

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
      className={cn(
        "rounded-xl border bg-surface overflow-hidden transition-[border-color,box-shadow]",
        expanded
          ? "border-amber shadow-[0_0_0_1px_var(--amber)]"
          : "border-[var(--hairline)] hover:border-ink/30",
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center gap-3.5 px-4 sm:px-[18px] py-3.5 transition hover:bg-[color-mix(in_oklch,var(--ink)_2%,transparent)]"
      >
        <span className="font-mono text-[11px] font-bold text-ink tracking-[0.05em]">
          #{pedido.numero_pedido}
        </span>
        <EstadoBadge estado={pedido.estado} />
        <span className="font-sans text-[13px] text-muted-foreground flex-1 min-w-0 truncate text-left">
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

      {expanded && (
        <div className="border-t border-dashed border-[var(--hairline)] px-4 sm:px-[18px] pt-[18px] pb-[22px] flex flex-col gap-5 animate-[expand-in_.22s_ease-out]">

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
                  <DocActions pedidoId={pedido.id} numero={numero} tipo="contrato" label="Contrato" />
                )}
                {docs.albaran && (
                  <DocActions pedidoId={pedido.id} numero={numero} tipo="albaran" label="Albarán" />
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
        </div>
      )}
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
}: {
  pedidoId: number;
  numero: string;
  tipo: "remito" | "contrato" | "albaran";
  label: string;
}) {
  const [previewOpen, setPreviewOpen] = useState(false);

  return (
    <>
      <div className="flex items-stretch gap-1">
        <button
          type="button"
          onClick={() => setPreviewOpen(true)}
          className="flex-1 flex items-center gap-2.5 rounded-md border border-[var(--hairline)] bg-card px-3 py-2.5 text-left transition hover:border-ink hover:bg-muted"
        >
          <div className="grid h-8 w-8 place-items-center rounded-sm bg-amber-soft text-amber shrink-0">
            <DocPath tipo={tipo} />
          </div>
          <div className="min-w-0">
            <div className="font-sans text-xs font-semibold text-ink leading-tight">{label}</div>
            <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted-foreground mt-0.5">
              Ver · PDF
            </div>
          </div>
        </button>
        <a
          href={`/api/cliente/pedidos/${pedidoId}/${tipo}.pdf`}
          download={`${tipo}-${numero}.pdf`}
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
        <header className="flex items-center justify-between gap-2 border-b hairline px-4 py-3 shrink-0">
          <h2 className="font-display text-base text-ink">{title}</h2>
          <div className="flex items-center gap-2">
            <a
              href={downloadUrl}
              download={downloadFilename}
              className="inline-flex items-center gap-1.5 rounded-md bg-ink text-amber px-3 py-2 text-xs font-medium hover:brightness-110 transition"
            >
              ⬇ Descargar PDF
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
