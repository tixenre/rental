import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { authedFetch } from "@/lib/authedFetch";
import { PublicLayout } from "@/components/rental/PublicLayout";
import { StatCard } from "@/components/rental/StatCard";
import { EstadoBadge } from "@/components/rental/EstadoBadge";
import { ViewToggle } from "@/components/rental/ViewToggle";
import { EmptyState } from "@/components/rental/EmptyState";
import { ShoppingBag, Pencil, Plus, Minus, Search, X, MessageSquare, AlertCircle } from "lucide-react";

export const Route = createFileRoute("/cliente/portal")({
  head: () => ({ meta: [{ title: "Mi cuenta — Rambla Rental" }] }),
  component: ClientePortal,
});

type Perfil = {
  nombre: string; apellido: string; email: string;
  telefono: string; direccion: string;
};

type Item = {
  equipo_id: number;
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
type Solicitud = {
  id: number;
  mensaje: string | null;
  estado: "pendiente" | "aprobada" | "rechazada" | "cancelada";
  respuesta: string | null;
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
  solicitudes?: Solicitud[];
  documentos_disponibles: { remito: boolean; contrato: boolean; albaran: boolean };
};

type EquipoCatalogo = {
  id: number;
  nombre: string;
  marca: string | null;
  precio_jornada: number | null;
  foto_url: string | null;
  nombre_publico?: string | null;
};

const ACTIVE_STATES = new Set(["solicitado", "confirmado", "entregado", "presupuesto"]);
const HIST_STATES = new Set(["devuelto", "finalizado"]);
/** Estados en los que el cliente puede pedir una modificación. */
const MOD_ELIGIBLE = new Set(["presupuesto", "solicitado", "confirmado"]);

const TAB_OPTIONS = [
  { value: "todos" as const, label: "Todos" },
  { value: "activos" as const, label: "Activos" },
  { value: "historial" as const, label: "Historial" },
];

function fmt(n?: number) {
  if (n == null) return "—";
  return new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 }).format(n);
}
function fmtDate(s?: string) {
  if (!s) return "—";
  // slice(0,10) normaliza "YYYY-MM-DD HH:MM:SS" y "YYYY-MM-DDTHH:MM:SS" a "YYYY-MM-DD"
  return new Date(s.slice(0, 10) + "T12:00:00").toLocaleDateString("es-AR", { day: "numeric", month: "short", year: "numeric" });
}

export default function ClientePortal() {
  const navigate = useNavigate();
  const [perfil, setPerfil] = useState<Perfil | null>(null);
  const [pedidos, setPedidos] = useState<Pedido[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [tab, setTab] = useState<"todos" | "activos" | "historial">("todos");
  const [modPedido, setModPedido] = useState<Pedido | null>(null);

  async function reloadPedidos() {
    const r = await authedFetch("/api/cliente/pedidos");
    if (r.ok) setPedidos(await r.json());
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

  const filteredPedidos =
    tab === "activos" ? pedidos.filter((p) => ACTIVE_STATES.has(p.estado))
    : tab === "historial" ? pedidos.filter((p) => HIST_STATES.has(p.estado))
    : pedidos;

  return (
    <PublicLayout
      topBar={{ variant: "cliente", userName, onLogout: handleLogout }}
    >
      {/* Sub-header amarillo Rambla — saludo / título de página */}
      <div className="bg-amber border-b hairline">
        <div className="max-w-2xl mx-auto px-4 py-6 sm:py-8">
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-ink/60">
            Portal de clientes
          </div>
          <h1 className="font-display text-4xl sm:text-5xl font-black text-ink mt-1.5 leading-none tracking-tight">
            {perfil ? `Hola, ${perfil.nombre}` : "Mi cuenta"}
          </h1>
          <p className="mt-3 text-sm text-ink/70">
            Mirá tus pedidos, descargá documentos y consultá pagos.
          </p>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        {/* Stats row */}
        {pedidos.length > 0 && (
          <div className="grid grid-cols-3 gap-2.5">
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

        {/* Filter tabs */}
        {pedidos.length > 0 && (
          <div className="flex items-center justify-between">
            <ViewToggle options={TAB_OPTIONS} value={tab} onChange={setTab} />
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground tabular-nums">
              {filteredPedidos.length} {filteredPedidos.length === 1 ? "pedido" : "pedidos"}
            </span>
          </div>
        )}

        {pedidos.length === 0 ? (
          <EmptyState
            icon={<ShoppingBag className="h-6 w-6" />}
            title="Sin pedidos aún"
            sub="Todavía no tenés pedidos registrados."
          />
        ) : filteredPedidos.length === 0 ? (
          <EmptyState
            icon={<ShoppingBag className="h-6 w-6" />}
            title={tab === "activos" ? "Sin rentals activos" : "Sin historial aún"}
            sub={
              tab === "activos"
                ? "No tenés rentals activos en este momento."
                : "Todavía no tenés pedidos completados."
            }
          />
        ) : (
          <div className="space-y-3">
            {filteredPedidos.map((p) => (
              <PedidoCard
                key={p.id}
                pedido={p}
                expanded={expanded === p.id}
                onToggle={() => setExpanded(expanded === p.id ? null : p.id)}
                onModRequest={() => setModPedido(p)}
              />
            ))}
          </div>
        )}
      </div>

      {modPedido && (
        <ModRequestModal
          pedido={modPedido}
          onClose={() => setModPedido(null)}
          onSuccess={async () => {
            setModPedido(null);
            await reloadPedidos();
          }}
        />
      )}
    </PublicLayout>
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
  pedido,
  expanded,
  onToggle,
  onModRequest,
}: {
  pedido: Pedido;
  expanded: boolean;
  onToggle: () => void;
  onModRequest: () => void;
}) {
  const { documentos_disponibles: docs } = pedido;
  const numero = pedido.numero_pedido ?? pedido.id;
  const jornadas = jornadasEntre(pedido.fecha_desde, pedido.fecha_hasta);

  const subtotalItems = pedido.items.reduce((acc, it) => acc + it.subtotal, 0);
  const descuentoPct = pedido.descuento_pct ?? 0;
  const descuentoMonto = Math.round(subtotalItems * (descuentoPct / 100));
  const total = pedido.monto_total ?? (subtotalItems - descuentoMonto);
  const pagado = pedido.monto_pagado ?? 0;
  const balance = Math.max(0, total - pagado);

  const pendiente = pedido.solicitudes?.find((s) => s.estado === "pendiente");
  const puedeModificar = MOD_ELIGIBLE.has(pedido.estado) && !pendiente;

  return (
    <div className="rounded-xl border hairline bg-surface overflow-hidden">
      {/* Cabecera del pedido */}
      <button
        onClick={onToggle}
        className="w-full text-left px-4 py-3 flex items-center justify-between hover:bg-muted/30 transition"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="font-mono text-xs text-muted-foreground shrink-0">
            #{pedido.numero_pedido}
          </span>
          <EstadoBadge estado={pedido.estado} />
          <span className="text-xs text-muted-foreground truncate hidden sm:block">
            {fmtDate(pedido.fecha_desde)} – {fmtDate(pedido.fecha_hasta)}
          </span>
        </div>
        <div className="flex items-center gap-3 shrink-0 ml-2">
          {pedido.monto_total != null && (
            <span className="text-sm font-medium text-ink">{fmt(pedido.monto_total)}</span>
          )}
          <svg
            className={`h-4 w-4 text-muted-foreground transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Detalle expandido — vista read-only del pedido */}
      {expanded && (
        <div className="border-t hairline px-4 py-4 space-y-5">

          {/* Bloque: período de alquiler */}
          <section className="grid grid-cols-3 gap-2 text-xs">
            <div className="rounded-md border hairline bg-background px-3 py-2">
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Desde</div>
              <div className="text-ink mt-0.5">{fmtDate(pedido.fecha_desde)}</div>
            </div>
            <div className="rounded-md border hairline bg-background px-3 py-2">
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Hasta</div>
              <div className="text-ink mt-0.5">{fmtDate(pedido.fecha_hasta)}</div>
            </div>
            <div className="rounded-md border hairline bg-background px-3 py-2">
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Jornadas</div>
              <div className="text-ink mt-0.5 tabular-nums">{jornadas}</div>
            </div>
          </section>

          {/* Bloque: items detallados */}
          <section>
            <h3 className="text-[11px] uppercase tracking-wider text-muted-foreground mb-2">
              Equipos ({pedido.items.length})
            </h3>
            <ul className="space-y-2">
              {pedido.items.map((item, i) => {
                const display = item.nombre_publico || item.nombre;
                const cap = `${item.marca ?? ""}${item.modelo ? ` · ${item.modelo}` : ""}`.trim();
                return (
                  <li key={i} className="flex items-start gap-3 text-sm">
                    {item.foto_url ? (
                      <img
                        src={item.foto_url}
                        alt={display}
                        loading="lazy"
                        className="h-10 w-10 rounded object-cover shrink-0 bg-muted"
                      />
                    ) : (
                      <div className="h-10 w-10 rounded bg-muted shrink-0" />
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="text-ink truncate">{display}</div>
                      {cap && <div className="text-xs text-muted-foreground truncate">{cap}</div>}
                      <div className="text-[11px] text-muted-foreground tabular-nums mt-0.5">
                        {item.cantidad} × {fmt(item.precio_jornada)} × {jornadas} {jornadas === 1 ? "jornada" : "jornadas"}
                      </div>
                    </div>
                    <div className="text-sm text-ink tabular-nums shrink-0">{fmt(item.subtotal)}</div>
                  </li>
                );
              })}
            </ul>
          </section>

          {/* Bloque: desglose económico */}
          <section className="border-t hairline pt-3 space-y-1 text-xs">
            <div className="flex justify-between text-muted-foreground">
              <span>Subtotal equipos</span>
              <span className="tabular-nums">{fmt(subtotalItems)}</span>
            </div>
            {descuentoPct > 0 && (
              <div className="flex justify-between text-muted-foreground">
                <span>Descuento ({descuentoPct}%)</span>
                <span className="tabular-nums text-amber-700">−{fmt(descuentoMonto)}</span>
              </div>
            )}
            <div className="flex justify-between pt-1 border-t hairline">
              <span className="text-ink font-medium">Total</span>
              <span className="text-ink font-medium tabular-nums">{fmt(total)}</span>
            </div>
            {pagado > 0 && (
              <>
                <div className="flex justify-between text-green-700">
                  <span>Pagado</span>
                  <span className="tabular-nums">{fmt(pagado)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink">Balance pendiente</span>
                  <span className={`tabular-nums font-medium ${balance > 0 ? "text-ink" : "text-green-700"}`}>
                    {fmt(balance)}
                  </span>
                </div>
              </>
            )}
          </section>

          {/* Bloque: pagos detallados */}
          {pedido.pagos && pedido.pagos.length > 0 && (
            <section>
              <h3 className="text-[11px] uppercase tracking-wider text-muted-foreground mb-2">Pagos</h3>
              <ul className="space-y-1 text-xs">
                {pedido.pagos.map((pg, i) => (
                  <li key={i} className="flex items-center justify-between gap-2 text-muted-foreground">
                    <span className="truncate">
                      {fmtDate(pg.fecha)}{pg.concepto ? ` · ${pg.concepto}` : ""}
                    </span>
                    <span className="tabular-nums text-green-700 shrink-0">{fmt(pg.monto)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Bloque: notas */}
          {pedido.notas && (
            <section>
              <h3 className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1">Notas</h3>
              <p className="text-xs text-muted-foreground whitespace-pre-wrap">{pedido.notas}</p>
            </section>
          )}

          {/* Bloque: solicitud de modificación pendiente */}
          {pendiente && (
            <section className="rounded-md border border-amber/40 bg-amber-soft p-3 flex gap-2.5">
              <MessageSquare className="h-4 w-4 text-amber shrink-0 mt-0.5" />
              <div className="flex-1 text-xs leading-snug">
                <div className="font-mono text-[9px] font-bold uppercase tracking-widest text-muted-foreground mb-1">
                  Solicitud de modificación pendiente
                </div>
                {pendiente.mensaje && (
                  <div className="text-ink whitespace-pre-wrap">{pendiente.mensaje}</div>
                )}
                <div className="font-mono text-[10px] text-muted-foreground mt-1.5">
                  Esperando respuesta del equipo Rambla
                </div>
              </div>
            </section>
          )}

          {/* Acción: solicitar modificación */}
          {puedeModificar && (
            <section>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); onModRequest(); }}
                className="w-full inline-flex items-center justify-center gap-2 rounded-md border border-dashed border-hairline bg-background px-3 py-2.5 text-xs font-semibold text-muted-foreground hover:border-ink hover:text-ink hover:border-solid transition-colors"
              >
                <Pencil className="h-3.5 w-3.5" /> Solicitar modificación
              </button>
            </section>
          )}

          {/* Bloque: documentos (preview HTML + descarga PDF). Issue #106. */}
          {(docs.remito || docs.contrato || docs.albaran) && (
            <section className="border-t hairline pt-3">
              <h3 className="text-[11px] uppercase tracking-wider text-muted-foreground mb-2">
                Documentos
              </h3>
              <div className="flex flex-col gap-1.5">
                {docs.remito && (
                  <DocActions
                    pedidoId={pedido.id}
                    numero={numero}
                    tipo="remito"
                    label="Remito"
                  />
                )}
                {docs.contrato && (
                  <DocActions
                    pedidoId={pedido.id}
                    numero={numero}
                    tipo="contrato"
                    label="Contrato"
                  />
                )}
                {docs.albaran && (
                  <DocActions
                    pedidoId={pedido.id}
                    numero={numero}
                    tipo="albaran"
                    label="Albarán"
                  />
                )}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}

function PdfIcon() {
  return (
    <svg className="h-3.5 w-3.5 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
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
      <div className="flex items-stretch gap-1.5">
        <button
          type="button"
          onClick={() => setPreviewOpen(true)}
          className="flex-1 inline-flex items-center gap-1.5 rounded-md border hairline bg-background px-3 py-3 text-xs font-medium text-ink hover:bg-muted/50 transition justify-start"
        >
          <PdfIcon /> Ver {label}
        </button>
        <a
          href={`/api/cliente/pedidos/${pedidoId}/${tipo}.pdf`}
          download={`${tipo}-${numero}.pdf`}
          className="inline-flex items-center gap-1.5 rounded-md border hairline bg-background px-3 py-3 text-xs font-medium text-muted-foreground hover:bg-muted/50 hover:text-ink transition"
          title={`Descargar ${label} en PDF`}
        >
          ⬇ PDF
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

// ── ModRequestModal ──────────────────────────────────────────────────────────
//
// Permite al cliente proponer cambios estructurados a un pedido activo: editar
// cantidades, sumar/quitar equipos, mover fechas, agregar mensaje.

function ModRequestModal({
  pedido,
  onClose,
  onSuccess,
}: {
  pedido: Pedido;
  onClose: () => void;
  onSuccess: () => void;
}) {
  // Items propuestos: arranca con los actuales del pedido.
  const [items, setItems] = useState<Map<number, number>>(
    () => new Map(pedido.items.map((it) => [it.equipo_id, it.cantidad])),
  );
  const [fechaDesde, setFechaDesde] = useState(pedido.fecha_desde?.slice(0, 10) ?? "");
  const [fechaHasta, setFechaHasta] = useState(pedido.fecha_hasta?.slice(0, 10) ?? "");
  const [mensaje, setMensaje] = useState("");
  const [search, setSearch] = useState("");
  const [equipos, setEquipos] = useState<EquipoCatalogo[] | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Lazy load catálogo cuando el cliente abre la búsqueda.
  useEffect(() => {
    if (equipos !== null) return;
    if (search.trim().length < 2) return;
    let alive = true;
    fetch("/api/equipos?per_page=500")
      .then((r) => r.ok ? r.json() : { items: [] })
      .then((d) => { if (alive) setEquipos(d.items ?? []); })
      .catch(() => { if (alive) setEquipos([]); });
    return () => { alive = false; };
  }, [search, equipos]);

  // ESC + lock scroll
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  // Mapa equipo_id → snapshot (nombre/marca/precio) usando el pedido actual
  // + el catálogo cargado.
  const infoPorId = useMemo(() => {
    const m = new Map<number, { nombre: string; marca: string | null; precio: number; foto: string | null }>();
    for (const it of pedido.items) {
      m.set(it.equipo_id, {
        nombre: it.nombre_publico || it.nombre,
        marca: it.marca,
        precio: it.precio_jornada,
        foto: it.foto_url ?? null,
      });
    }
    for (const e of equipos ?? []) {
      if (!m.has(e.id)) {
        m.set(e.id, {
          nombre: e.nombre_publico || e.nombre,
          marca: e.marca,
          precio: e.precio_jornada ?? 0,
          foto: e.foto_url,
        });
      }
    }
    return m;
  }, [pedido.items, equipos]);

  const itemsList = Array.from(items.entries());
  const itemsFinales = itemsList.filter(([, c]) => c > 0);
  const jornadas = jornadasEntre(fechaDesde, fechaHasta);
  const totalEstimado = itemsFinales.reduce((acc, [eq, c]) => {
    const precio = infoPorId.get(eq)?.precio ?? 0;
    return acc + precio * c * jornadas;
  }, 0);

  function bumpQty(equipo_id: number, delta: number) {
    setItems((prev) => {
      const next = new Map(prev);
      const cur = next.get(equipo_id) ?? 0;
      next.set(equipo_id, Math.max(0, cur + delta));
      return next;
    });
  }

  function addEquipo(eq: EquipoCatalogo) {
    setItems((prev) => {
      const next = new Map(prev);
      next.set(eq.id, (next.get(eq.id) ?? 0) + 1);
      return next;
    });
    setSearch("");
  }

  const searchResults = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q || !equipos) return [];
    return equipos
      .filter((e) => {
        if (items.has(e.id) && (items.get(e.id) ?? 0) > 0) return false;
        const hay = `${e.nombre} ${e.marca ?? ""}`.toLowerCase();
        return hay.includes(q);
      })
      .slice(0, 6);
  }, [search, equipos, items]);

  // El cliente debe haber cambiado algo: fechas, items o tirar un mensaje.
  const fechasCambian = (fechaDesde || null) !== (pedido.fecha_desde?.slice(0, 10) ?? null)
    || (fechaHasta || null) !== (pedido.fecha_hasta?.slice(0, 10) ?? null);
  const itemsCambian = (() => {
    const baseMap = new Map(pedido.items.map((it) => [it.equipo_id, it.cantidad]));
    if (itemsFinales.length !== baseMap.size) return true;
    for (const [eq, c] of itemsFinales) {
      if (baseMap.get(eq) !== c) return true;
    }
    return false;
  })();
  const haySolicitud = fechasCambian || itemsCambian || mensaje.trim().length > 0;

  async function handleSubmit() {
    setError(null);
    if (itemsFinales.length === 0) {
      setError("Tu propuesta no tiene equipos. Agregá al menos uno.");
      return;
    }
    setSubmitting(true);
    try {
      const r = await authedFetch(`/api/cliente/pedidos/${pedido.id}/solicitar-modificacion`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mensaje: mensaje.trim() || null,
          fecha_desde: fechaDesde || null,
          fecha_hasta: fechaHasta || null,
          items: itemsFinales.map(([equipo_id, cantidad]) => ({ equipo_id, cantidad })),
        }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body?.detail || `Error ${r.status}`);
      }
      onSuccess();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-stretch sm:items-center justify-center sm:p-6"
      onClick={onClose}
    >
      <div
        className="bg-background w-full sm:max-w-xl sm:max-h-[90vh] h-full sm:h-auto flex flex-col sm:rounded-lg overflow-hidden shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between gap-2 border-b hairline px-4 py-3 shrink-0">
          <div>
            <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
              Pedido #{pedido.numero_pedido ?? pedido.id}
            </div>
            <h2 className="font-display text-lg text-ink">Solicitar modificación</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-9 w-9 place-items-center rounded-md hover:bg-muted transition"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {/* Fechas */}
          <section>
            <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground mb-1.5">
              Fechas
            </div>
            <div className="grid grid-cols-2 gap-2">
              <label className="flex flex-col gap-1">
                <span className="text-[10px] text-muted-foreground">Desde</span>
                <input
                  type="date"
                  value={fechaDesde}
                  onChange={(e) => setFechaDesde(e.target.value)}
                  className="rounded-md border hairline bg-background px-2 py-2 text-sm text-ink"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[10px] text-muted-foreground">Hasta</span>
                <input
                  type="date"
                  value={fechaHasta}
                  min={fechaDesde || undefined}
                  onChange={(e) => setFechaHasta(e.target.value)}
                  className="rounded-md border hairline bg-background px-2 py-2 text-sm text-ink"
                />
              </label>
            </div>
            <div className="font-mono text-[10px] text-muted-foreground mt-1">
              {jornadas} {jornadas === 1 ? "jornada" : "jornadas"}
            </div>
          </section>

          {/* Items */}
          <section>
            <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground mb-1.5">
              Equipos
            </div>
            <div className="rounded-md border hairline overflow-hidden">
              {itemsList.length === 0 && (
                <div className="px-3 py-4 text-xs text-muted-foreground text-center">
                  No quedan equipos. Agregá al menos uno.
                </div>
              )}
              {itemsList.map(([equipo_id, c]) => {
                const info = infoPorId.get(equipo_id);
                const zeroed = c === 0;
                return (
                  <div
                    key={equipo_id}
                    className={
                      "flex items-center gap-2.5 px-3 py-2 border-b hairline last:border-b-0 " +
                      (zeroed ? "bg-destructive/5" : "bg-background")
                    }
                  >
                    <div className="flex-1 min-w-0">
                      <div className={"text-sm font-medium " + (zeroed ? "text-muted-foreground line-through" : "text-ink")}>
                        {info?.nombre ?? "—"}
                      </div>
                      <div className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
                        {info?.marca ?? ""}
                      </div>
                    </div>
                    <div className="inline-flex items-center rounded-full border hairline bg-background overflow-hidden">
                      <button
                        type="button"
                        onClick={() => bumpQty(equipo_id, -1)}
                        disabled={c === 0}
                        className="h-7 w-7 grid place-items-center text-muted-foreground hover:bg-muted hover:text-ink disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        <Minus className="h-3 w-3" />
                      </button>
                      <span className="font-mono text-xs font-bold text-ink tabular-nums px-1.5 min-w-[28px] text-center">
                        {c}
                      </span>
                      <button
                        type="button"
                        onClick={() => bumpQty(equipo_id, +1)}
                        className="h-7 w-7 grid place-items-center text-muted-foreground hover:bg-muted hover:text-ink"
                      >
                        <Plus className="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                );
              })}
              <div className="flex items-center gap-2 px-3 py-2 bg-amber-soft/30 border-t hairline">
                <Search className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                <input
                  placeholder="Buscar equipo del catálogo…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="flex-1 bg-background rounded-md border hairline px-2 py-1.5 text-xs"
                />
              </div>
            </div>
            {searchResults.length > 0 && (
              <div className="mt-1.5 rounded-md border hairline bg-background max-h-44 overflow-y-auto">
                {searchResults.map((eq) => (
                  <button
                    key={eq.id}
                    type="button"
                    onClick={() => addEquipo(eq)}
                    className="w-full text-left flex items-center gap-2 px-3 py-2 border-b hairline last:border-b-0 hover:bg-surface transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-semibold text-ink truncate">
                        {eq.nombre_publico || eq.nombre}
                      </div>
                      <div className="font-mono text-[9px] text-muted-foreground truncate">
                        {eq.marca ?? "—"} · {fmt(eq.precio_jornada ?? 0)}/jornada
                      </div>
                    </div>
                    <span className="h-6 w-6 grid place-items-center rounded-full bg-ink text-amber shrink-0">
                      <Plus className="h-3 w-3" strokeWidth={2.5} />
                    </span>
                  </button>
                ))}
              </div>
            )}
          </section>

          {/* Mensaje */}
          <section>
            <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground mb-1.5">
              Mensaje (opcional)
            </div>
            <textarea
              value={mensaje}
              onChange={(e) => setMensaje(e.target.value)}
              placeholder="Contanos qué necesitás cambiar y por qué…"
              className="w-full min-h-[72px] rounded-md border hairline bg-background px-3 py-2 text-sm text-ink resize-vertical"
            />
          </section>

          {/* Resumen */}
          <section className="rounded-md bg-amber-soft/40 border border-amber/30 px-3 py-2.5 flex items-baseline justify-between">
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              Total estimado
            </span>
            <span className="font-display text-lg font-black text-ink tabular-nums">
              {fmt(totalEstimado)}
            </span>
          </section>

          {error && (
            <div className="flex items-center gap-1.5 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              {error}
            </div>
          )}
        </div>

        <footer className="border-t hairline px-4 py-3 flex gap-2 shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-md border hairline bg-background px-3 py-2.5 text-sm text-muted-foreground hover:text-ink hover:border-ink transition-colors"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting || !haySolicitud || itemsFinales.length === 0}
            className="flex-1 rounded-md bg-ink text-amber px-3 py-2.5 text-sm font-semibold hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {submitting ? "Enviando…" : "Enviar solicitud"}
          </button>
        </footer>
      </div>
    </div>
  );
}
