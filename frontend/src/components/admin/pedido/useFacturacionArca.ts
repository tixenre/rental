import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { facturacionApi, type PedidoEstado, type Factura } from "@/lib/admin/api";

export const ESTADOS_FACTURABLES: PedidoEstado[] = [
  "confirmado",
  "retirado",
  "entregado",
  "devuelto",
  "finalizado",
];

// Proporción ancho/alto de cada layout (ver arca_fe/render.py: "simplificada" = 4:5 fijo,
// "oficial"/"detallada" = A4). El preview del modal usa esto para dimensionar el panel de la
// factura SIN el sobrante gris que el propio HTML deja alrededor cuando el viewport no matchea
// la proporción exacta (el `.page`/`body` de arca_fe centra y escala manteniendo aspecto — si le
// damos el mismo aspecto de entrada, el sobrante desaparece solo, no hay que "recortar" nada).
export const LAYOUT_ASPECT: Record<string, number> = {
  simplificada: 1080 / 1350,
  oficial: 210 / 297,
  detallada: 210 / 297,
};

/**
 * Estado + mutaciones de la facturación ARCA de un pedido — extraído de
 * `FacturacionRailSection` (que vivía solo en el detalle de pedido) para que
 * el listado también pueda ofrecer "Facturar" en su barra de acciones rápidas
 * sin reimplementar la lógica (a pedido del dueño). Un consumidor "rico"
 * (`FacturacionRailSection`, en `PedidoPageHelpers.tsx`) usa todo el bag; uno
 * compacto (el listado) solo necesita `puedeFacturar` +
 * `setShowPreview`/`preview.mutate` + renderizar `<FacturaPreviewDialog>` una vez.
 *
 * En su propio archivo (no en `PedidoPageHelpers.tsx`) porque un hook no puede
 * compartir módulo con componentes sin romper el Fast Refresh de Vite
 * (`react-refresh/only-export-components`) — mismo patrón que
 * `usePedidoDraft.ts`/`useDisponibilidadDraft.ts` en esta misma carpeta.
 */
export function useFacturacionArca(
  pedidoId: number,
  estadoPedido: PedidoEstado,
  opts?: { enabled?: boolean },
) {
  // `enabled`: el listado llama a este hook desde el tope de PreviewPane (regla de
  // hooks — no puede esperar a que el pedido termine de cargar para recién ahí
  // llamarlo), así que a veces pedidoId/estadoPedido todavía no son reales. El
  // detalle de pedido lo monta recién con el pedido ya cargado — no necesita pasar
  // esto, el default `true` no le cambia nada.
  const enabled = opts?.enabled ?? true;
  const qc = useQueryClient();

  const q = useQuery({
    queryKey: ["admin", "facturas", pedidoId],
    queryFn: () => facturacionApi.listFacturasPedido(pedidoId),
    enabled,
  });

  // Layouts disponibles (nombre/descripción/advertencia) — estáticos en la práctica, cache larga.
  const layoutsQ = useQuery({
    queryKey: ["admin", "facturacion", "layouts"],
    queryFn: () => facturacionApi.getLayouts(),
    staleTime: Infinity,
    enabled,
  });
  const layouts = layoutsQ.data ?? [];
  const [layout, setLayout] = useState<string>("simplificada");
  const layoutInfo = layouts.find((l) => l.id === layout);

  const [showPreview, setShowPreview] = useState(false);

  const preview = useMutation({
    mutationFn: () => facturacionApi.previewFactura(pedidoId),
    onError: (e: Error) => toast.error(e.message),
  });

  // Factura completa (mismo layout real, CAE/QR placeholder) embebida en el propio modal — pedido
  // del dueño de ir directo a la vista real en vez de un resumen en texto + un link aparte. Mismo
  // patrón que ContratoPreviewModal (blob URL + <iframe src>, no srcDoc: un documento con fuentes
  // embebidas en base64 tarda mucho más en pintar vía srcDoc que navegado como blob real).
  const [facturaBlobUrl, setFacturaBlobUrl] = useState<string | null>(null);
  const [facturaHtmlError, setFacturaHtmlError] = useState<string | null>(null);
  const [facturaIframeReady, setFacturaIframeReady] = useState(false);

  useEffect(() => {
    if (!showPreview) return;
    let alive = true;
    let url: string | null = null;
    setFacturaIframeReady(false);
    setFacturaHtmlError(null);
    facturacionApi
      .previewFacturaHtml(pedidoId, layout)
      .then((html) => {
        if (!alive) return;
        url = URL.createObjectURL(new Blob([html], { type: "text/html" }));
        setFacturaBlobUrl(url);
      })
      .catch((err: unknown) => {
        if (alive) {
          setFacturaHtmlError(
            err instanceof Error ? err.message : "No pudimos generar el preview de la factura.",
          );
        }
      });
    return () => {
      alive = false;
      setFacturaBlobUrl(null);
      if (url) URL.revokeObjectURL(url);
    };
  }, [showPreview, pedidoId, layout]);

  const facturar = useMutation({
    mutationFn: () => facturacionApi.facturarPedido(pedidoId),
    onSuccess: () => {
      toast.success("Factura emitida");
      qc.invalidateQueries({ queryKey: ["admin", "facturas", pedidoId] });
      setShowPreview(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const notaCredito = useMutation({
    mutationFn: (facturaId: number) => facturacionApi.notaCreditoFactura(facturaId),
    onSuccess: () => {
      toast.success("Nota de crédito emitida");
      qc.invalidateQueries({ queryKey: ["admin", "facturas", pedidoId] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const enviarMail = useMutation({
    mutationFn: (facturaId: number) => facturacionApi.enviarMailFactura(facturaId, layout),
    onSuccess: (data) => toast.success(`Factura enviada a ${data.to}`),
    onError: (e: Error) => toast.error(e.message),
  });

  const facturas = q.data ?? [];
  const principal = facturas.find(
    (f: Factura) => f.nota_credito_de == null && f.estado !== "anulada",
  );
  const nc = facturas.find((f: Factura) => f.nota_credito_de != null);
  // Un intento previo en estado 'error' es reintentable — el backend inserta
  // un nuevo intento y vuelve a pedirle el CAE a ARCA (`get_factura_vigente`
  // solo considera 'pendiente'/'emitida', el índice único parcial excluye
  // 'error'). Sin este chequeo, un primer intento fallido dejaba el pedido
  // sin forma de facturar nunca más (bug real de prod).
  const puedeFacturar =
    ESTADOS_FACTURABLES.includes(estadoPedido) && (!principal || principal.estado === "error");
  const puedeAnular = principal?.estado === "emitida" && !nc;

  const cbteLetra = principal
    ? ({ 1: "A", 3: "A", 6: "B", 8: "B", 11: "C", 13: "C" }[principal.cbte_tipo] ?? "?")
    : null;

  return {
    q,
    layouts,
    layout,
    setLayout,
    layoutInfo,
    showPreview,
    setShowPreview,
    preview,
    facturaBlobUrl,
    facturaHtmlError,
    facturaIframeReady,
    setFacturaIframeReady,
    facturar,
    notaCredito,
    enviarMail,
    facturas,
    principal,
    nc,
    puedeFacturar,
    puedeAnular,
    cbteLetra,
  };
}

export type FacturacionArca = ReturnType<typeof useFacturacionArca>;
