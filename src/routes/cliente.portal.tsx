import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { authedFetch } from "@/lib/authedFetch";
import { PdfViewerModal } from "@/components/PdfViewerModal";

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
  cantidad: number;
  precio_jornada: number;
  subtotal: number;
  foto_url?: string;
  nombre_publico?: string | null;
  nombre_publico_largo?: string | null;
};
type Pedido = {
  id: number; numero_pedido: string; estado: string;
  fecha_desde?: string; fecha_hasta?: string;
  monto_total?: number; monto_pagado?: number;
  items: Item[];
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
  return new Date(s + "T12:00:00").toLocaleDateString("es-AR", { day: "numeric", month: "short", year: "numeric" });
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
      {/* Header */}
      <header className="border-b hairline bg-background sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 h-12 flex items-center justify-between">
          <span className="font-display text-sm text-ink">Rambla Rental</span>
          <div className="flex items-center gap-3">
            {perfil && (
              <span className="text-xs text-muted-foreground hidden sm:block">
                {perfil.nombre} {perfil.apellido}
              </span>
            )}
            <button
              onClick={handleLogout}
              className="text-xs text-muted-foreground hover:text-ink transition"
            >
              Salir
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        <h1 className="font-display text-xl text-ink">Mis pedidos</h1>

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

type PdfDoc = { url: string; filename: string; titulo: string };

function PedidoCard({ pedido, expanded, onToggle }: { pedido: Pedido; expanded: boolean; onToggle: () => void }) {
  const { documentos_disponibles: docs } = pedido;
  const estadoClass = ESTADO_COLOR[pedido.estado] ?? "bg-muted text-muted-foreground";
  const [pdfDoc, setPdfDoc] = useState<PdfDoc | null>(null);
  const numero = pedido.numero_pedido ?? pedido.id;

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

      {/* Detalle expandido */}
      {expanded && (
        <div className="border-t hairline px-4 py-4 space-y-4">
          {/* Fechas en móvil */}
          <p className="text-xs text-muted-foreground sm:hidden">
            {fmtDate(pedido.fecha_desde)} – {fmtDate(pedido.fecha_hasta)}
          </p>

          {/* Items */}
          <div className="space-y-2">
            {pedido.items.map((item, i) => {
              const display = item.nombre_publico || item.nombre;
              return (
                <div key={i} className="flex items-center gap-3 text-sm">
                  {item.foto_url && (
                    <img src={item.foto_url} alt={display}
                      className="h-8 w-8 rounded object-cover shrink-0 bg-muted" />
                  )}
                  <div className="min-w-0 flex-1">
                    <span className="text-ink truncate block">{display}</span>
                    <span className="text-xs text-muted-foreground">{item.marca} · ×{item.cantidad}</span>
                  </div>
                  <span className="text-xs text-muted-foreground shrink-0">{fmt(item.subtotal)}</span>
                </div>
              );
            })}
          </div>

          {/* Resumen financiero */}
          {pedido.monto_total != null && (
            <div className="border-t hairline pt-3 space-y-1 text-xs">
              <div className="flex justify-between text-muted-foreground">
                <span>Total</span>
                <span className="font-medium text-ink">{fmt(pedido.monto_total)}</span>
              </div>
              {pedido.monto_pagado != null && pedido.monto_pagado > 0 && (
                <div className="flex justify-between text-muted-foreground">
                  <span>Pagado</span>
                  <span className="text-green-700">{fmt(pedido.monto_pagado)}</span>
                </div>
              )}
            </div>
          )}

          {/* Documentos */}
          {(docs.remito || docs.contrato || docs.albaran) && (
            <div className="border-t hairline pt-3 flex flex-wrap gap-2">
              {docs.remito && (
                <button
                  onClick={() => setPdfDoc({
                    url: `/api/cliente/pedidos/${pedido.id}/remito.pdf`,
                    filename: `remito-${numero}.pdf`,
                    titulo: "Remito",
                  })}
                  className="inline-flex items-center gap-1.5 rounded-md border hairline bg-background px-3 py-1.5 text-xs font-medium text-ink hover:bg-muted/50 transition">
                  <PdfIcon /> Remito
                </button>
              )}
              {docs.contrato && (
                <button
                  onClick={() => setPdfDoc({
                    url: `/api/cliente/pedidos/${pedido.id}/contrato.pdf`,
                    filename: `contrato-${numero}.pdf`,
                    titulo: "Contrato",
                  })}
                  className="inline-flex items-center gap-1.5 rounded-md border hairline bg-background px-3 py-1.5 text-xs font-medium text-ink hover:bg-muted/50 transition">
                  <PdfIcon /> Contrato
                </button>
              )}
              {docs.albaran && (
                <button
                  onClick={() => setPdfDoc({
                    url: `/api/cliente/pedidos/${pedido.id}/albaran.pdf`,
                    filename: `albaran-${numero}.pdf`,
                    titulo: "Albarán",
                  })}
                  className="inline-flex items-center gap-1.5 rounded-md border hairline bg-background px-3 py-1.5 text-xs font-medium text-ink hover:bg-muted/50 transition">
                  <PdfIcon /> Albarán
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {pdfDoc && (
        <PdfViewerModal
          url={pdfDoc.url}
          filename={pdfDoc.filename}
          titulo={`${pdfDoc.titulo} · #${numero}`}
          onClose={() => setPdfDoc(null)}
        />
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
