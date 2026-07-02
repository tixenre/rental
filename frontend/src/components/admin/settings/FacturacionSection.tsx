/**
 * FacturacionSection — resumen de facturación electrónica ARCA en Settings.
 *
 * Muestra el ambiente activo + lista de emisores con estado de certificado.
 * La gestión completa (crear, editar, subir certs) está en /admin/facturacion/emisores.
 */
import { Link } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { CheckCircle2, XCircle, ExternalLink, RefreshCw } from "lucide-react";

import { facturacionApi } from "@/lib/admin/api";

export function FacturacionSection() {
  const qc = useQueryClient();
  const estadoQ = useQuery({
    queryKey: ["facturacion-estado"],
    queryFn: facturacionApi.getEstado,
    staleTime: 60_000,
  });

  const refrescarCatalogos = useMutation({
    mutationFn: facturacionApi.refrescarCatalogos,
    onSuccess: (r) => {
      toast.success(
        `Catálogos actualizados — ${r.doc_tipo} tipos de doc, ${r.concepto} conceptos, ${r.condicion_iva_receptor} condiciones IVA`,
      );
      qc.invalidateQueries({ queryKey: ["facturacion-estado"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const emisoresQ = useQuery({
    queryKey: ["admin", "emisores-arca"],
    queryFn: facturacionApi.listEmisores,
    staleTime: 60_000,
  });

  return (
    <section className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Motor de facturación electrónica ARCA. Los certificados y la clave maestra van en variables
        de entorno Railway (nunca acá). Gestión completa de emisores en la{" "}
        <Link
          to="/admin/facturacion/emisores"
          className="underline hover:text-ink inline-flex items-center gap-1"
        >
          página de emisores <ExternalLink className="h-3 w-3" />
        </Link>
        .
      </p>

      {estadoQ.data && (
        <div className="flex items-center gap-2">
          <span className="t-eyebrow">Ambiente:</span>
          <span
            className={`text-xs font-mono font-medium ${
              estadoQ.data.ambiente === "produccion" ? "text-verde-ink" : "text-amber-700" // eslint-disable-line no-restricted-syntax -- paleta categórica Tier 3: verde-ink producción, amber-700 homologación
            }`}
          >
            {estadoQ.data.ambiente === "produccion" ? "Producción" : "Homologación (pruebas)"}
          </span>
        </div>
      )}

      {estadoQ.data && (
        <div className="flex items-center justify-between gap-2 rounded border hairline bg-background px-3 py-2">
          <div className="text-xs text-muted-foreground">
            <span className="t-eyebrow">Catálogos ARCA</span> (tipo de documento, concepto,
            condición IVA del receptor — las etiquetas del PDF salen de acá, no del código):{" "}
            {estadoQ.data.catalogos_actualizados_at ? (
              <>
                actualizados el{" "}
                {new Date(estadoQ.data.catalogos_actualizados_at).toLocaleString("es-AR")}
              </>
            ) : (
              <span className="text-destructive">nunca se actualizaron</span>
            )}
          </div>
          <button
            type="button"
            onClick={() => refrescarCatalogos.mutate()}
            disabled={refrescarCatalogos.isPending}
            className="shrink-0 flex items-center gap-1.5 h-8 px-2.5 rounded-md border hairline text-xs text-muted-foreground hover:text-ink disabled:opacity-40"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${refrescarCatalogos.isPending ? "animate-spin" : ""}`}
            />
            {refrescarCatalogos.isPending ? "Actualizando…" : "Actualizar catálogos ARCA"}
          </button>
        </div>
      )}

      {emisoresQ.data && emisoresQ.data.length > 0 && (
        <div className="space-y-2">
          {emisoresQ.data.map((em) => (
            <div
              key={em.id}
              className="flex items-center justify-between rounded border hairline bg-background px-3 py-2"
            >
              <div>
                <span className="text-sm font-medium text-ink">{em.nombre}</span>
                <span className="ml-2 text-xs text-muted-foreground">{em.condicion_iva}</span>
              </div>
              <div className="flex items-center gap-1 text-xs shrink-0">
                {em.cert_cargado ? (
                  <>
                    <CheckCircle2 className="h-4 w-4 text-verde-ink" />
                    <span className="text-verde-ink">Cert. cargado</span>
                  </>
                ) : (
                  <>
                    <XCircle className="h-4 w-4 text-destructive" />
                    <span className="text-destructive">Sin cert.</span>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {emisoresQ.data && emisoresQ.data.length === 0 && (
        <p className="text-xs text-muted-foreground">
          No hay emisores configurados.{" "}
          <Link to="/admin/facturacion/emisores" className="underline hover:text-ink">
            Agregar emisor
          </Link>
        </p>
      )}
    </section>
  );
}
