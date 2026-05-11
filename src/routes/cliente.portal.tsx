import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { authedFetch } from "@/lib/authedFetch";

export const Route = createFileRoute("/cliente/portal")({
  head: () => ({ meta: [{ title: "Mi cuenta — Rambla Rental" }] }),
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

const ESTADO_LABEL: Record<string, string> = {
  borrador: "Borrador", presupuesto: "Presupuesto", solicitado: "Solicitado",
  confirmado: "Confirmado", entregado: "Entregado", devuelto: "Devuelto",
  finalizado: "Finalizado", cancelado: "Cancelado",
};
const ESTADO_COLOR: Record<string, string> = {
  borrador: "bg-muted text-muted-foreground",
  presupuesto: "bg-blue-50 text-blue-700 border-blue-200",
  solicitado: "bg-amber-50 text-amber-700 border-amber-200",
  confirmado: "bg-green-50 text-green-700 border-green-200",
  entregado: "bg-green-100 text-green-800 border-green-300",
  devuelto: "bg-slate-100 text-slate-600 border-slate-300",
  finalizado: "bg-slate-100 text-slate-600 border-slate-300",
  cancelado: "bg-red-50 text-red-600 border-red-200",
};

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
    return <div className="min-h-screen grid place-items-center text-sm text-muted-foreground">Cargando…</div>;
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header con branding Rambla */}
      <header className="border-b hairline bg-background sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 h-14 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2 group">
            <span className="wordmark text-2xl text-amber leading-none group-hover:brightness-110 transition">rambla</span>
            <span className="font-mono text-[9px] uppercase tracking-[0.3em] text-foreground/70 border-l hairline pl-2">
              Rental
            </span>
          </a>
          <div className="flex items-center gap-3">
            <a href="/" className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-ink transition">
              ← Catálogo
            </a>
            {perfil && (
              <a
                href="/cliente/perfil"
                className="text-xs text-muted-foreground hover:text-ink transition hidden sm:block"
                title="Editar mi perfil"
              >
                {perfil.nombre} {perfil.apellido}
              </a>
            )}
            <a
              href="/cliente/perfil"
              className="text-xs text-muted-foreground hover:text-ink transition sm:hidden"
            >
              Perfil
            </a>
            <button
              onClick={handleLogout}
              className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-ink transition"
            >
              Salir
            </button>
          </div>
        </div>
      </header>

      {/* Sub-header amarillo Rambla */}
      <div className="bg-amber border-b hairline">
        <div className="max-w-2xl mx-auto px-4 py-5">
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-ink/70">
            Portal de clientes
          </div>
          <h1 className="font-display text-3xl text-ink mt-1">
            {perfil ? `Hola, ${perfil.nombre}` : "Mi cuenta"}
          </h1>
        </div>
      </div>

      <main className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        <h2 className="font-display text-xl text-ink">Mis pedidos</h2>

        {pedidos.length === 0 ? (
          <div className="rounded-xl border hairline p-8 text-center text-sm text-muted-foreground">
            Todavía no tenés pedidos registrados.
          </div>
        ) : (
          <div className="space-y-3">
            {pedidos.map((p) => (
              <PedidoCard
                key={p.id}
                pedido={p}
                expanded={expanded === p.id}
                onToggle={() => setExpanded(expanded === p.id ? null : p.id)}
              />
            ))}
          </div>
        )}
      </main>
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
  const estadoClass = ESTADO_COLOR[pedido.estado] ?? "bg-muted text-muted-foreground";
  const numero = pedido.numero_pedido ?? pedido.id;
  const jornadas = jornadasEntre(pedido.fecha_desde, pedido.fecha_hasta);

  const subtotalItems = pedido.items.reduce((acc, it) => acc + it.subtotal, 0);
  const descuentoPct = pedido.descuento_pct ?? 0;
  const descuentoMonto = Math.round(subtotalItems * (descuentoPct / 100));
  const total = pedido.monto_total ?? (subtotalItems - descuentoMonto);
  const pagado = pedido.monto_pagado ?? 0;
  const balance = Math.max(0, total - pagado);

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
          <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${estadoClass}`}>
            {ESTADO_LABEL[pedido.estado] ?? pedido.estado}
          </span>
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
          className="flex-1 inline-flex items-center gap-1.5 rounded-md border hairline bg-background px-3 py-1.5 text-xs font-medium text-ink hover:bg-muted/50 transition justify-start"
        >
          <PdfIcon /> Ver {label}
        </button>
        <a
          href={`/api/cliente/pedidos/${pedidoId}/${tipo}.pdf`}
          download={`${tipo}-${numero}.pdf`}
          className="inline-flex items-center gap-1.5 rounded-md border hairline bg-background px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted/50 hover:text-ink transition"
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
              className="inline-flex items-center gap-1.5 rounded-md bg-ink text-amber px-3 py-1.5 text-xs font-medium hover:brightness-110 transition"
            >
              ⬇ Descargar PDF
            </a>
            <button
              type="button"
              onClick={onClose}
              className="grid h-9 w-9 place-items-center rounded-md hover:bg-muted transition"
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
