/**
 * FacturacionSection — configuración de facturación electrónica ARCA (#1139).
 *
 * Muestra el estado de los dos emisores (Pablo/Santini): CUIT, PtoVta y si el
 * certificado está cargado en el entorno. Los secretos (cert/clave) van en
 * Railway → Variables, nunca en esta UI. El CUIT y PtoVta se editan acá.
 */
import { useQueryClient, useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { CheckCircle2, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { facturacionApi } from "@/lib/admin/api";
import { adminApi } from "@/lib/admin/api";
import { useState, useEffect } from "react";

type Emisor = "pablo" | "santini";

const LABELS: Record<Emisor, { nombre: string; tipo: string; cbte: string }> = {
  pablo: { nombre: "Pablo", tipo: "Responsable Inscripto", cbte: "Factura A" },
  santini: { nombre: "Santini", tipo: "Monotributo", cbte: "Factura C" },
};

function EmisorCard({ emisor }: { emisor: Emisor }) {
  const qc = useQueryClient();
  const estadoQ = useQuery({
    queryKey: ["facturacion-estado"],
    queryFn: facturacionApi.getEstado,
    staleTime: 60_000,
  });

  const info = estadoQ.data?.emisores[emisor];
  const { nombre, tipo, cbte } = LABELS[emisor];

  const [cuit, setCuit] = useState("");
  const [ptovta, setPtovta] = useState("");
  const [init, setInit] = useState(false);

  useEffect(() => {
    if (!init && info) {
      setCuit(info.cuit ?? "");
      setPtovta(info.ptovta ?? "");
      setInit(true);
    }
  }, [init, info]);

  const dirty =
    (cuit.trim() !== (info?.cuit ?? "")) || (ptovta.trim() !== (info?.ptovta ?? ""));

  const saveMut = useMutation({
    mutationFn: async () => {
      await adminApi.updateSetting(`afip_${emisor}_cuit`, cuit.trim());
      await adminApi.updateSetting(`afip_${emisor}_ptovta`, ptovta.trim());
    },
    onSuccess: () => {
      toast.success(`Datos de ${nombre} guardados`);
      qc.invalidateQueries({ queryKey: ["facturacion-estado"] });
      setInit(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="rounded border hairline bg-background p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-medium text-sm text-ink">{nombre}</div>
          <div className="text-[11px] text-muted-foreground">
            {tipo} · emite <strong>{cbte}</strong>
          </div>
        </div>
        {info && (
          <div className="flex items-center gap-1 text-xs shrink-0">
            {info.cert_cargado ? (
              <>
                <CheckCircle2 className="h-4 w-4 text-green-600" />
                <span className="text-green-700">Cert. cargado</span>
              </>
            ) : (
              <>
                <XCircle className="h-4 w-4 text-red-500" />
                <span className="text-red-600">Sin cert.</span>
              </>
            )}
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-3 border-t hairline pt-3">
        <div className="space-y-1">
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">CUIT</div>
          <Input
            placeholder="20123456789"
            className="w-40 font-mono text-sm"
            value={cuit}
            onChange={(e) => setCuit(e.target.value)}
          />
        </div>
        <div className="space-y-1">
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
            Punto de Venta
          </div>
          <Input
            placeholder="1"
            className="w-24 font-mono text-sm"
            value={ptovta}
            onChange={(e) => setPtovta(e.target.value)}
          />
        </div>
        <div className="flex items-end">
          <Button
            size="sm"
            onClick={() => saveMut.mutate()}
            disabled={!dirty || saveMut.isPending}
          >
            {saveMut.isPending ? "Guardando…" : "Guardar"}
          </Button>
        </div>
      </div>

      {!info?.cert_cargado && (
        <p className="text-[11px] text-muted-foreground">
          El certificado y la clave van en las variables de entorno Railway:{" "}
          <code className="text-[10px]">AFIP_{emisor.toUpperCase()}_CERT</code> y{" "}
          <code className="text-[10px]">AFIP_{emisor.toUpperCase()}_KEY</code> (en PEM).
        </p>
      )}
    </div>
  );
}

export function FacturacionSection() {
  const estadoQ = useQuery({
    queryKey: ["facturacion-estado"],
    queryFn: facturacionApi.getEstado,
    staleTime: 60_000,
  });

  return (
    <section className="space-y-3">
      <div>
        <p className="text-xs text-muted-foreground">
          Motor de facturación electrónica ARCA. Dos emisores: <strong>Pablo</strong> (RI →
          Factura A para clientes RI) y <strong>Santini</strong> (Monotributo → Factura C para el
          resto). El certificado y la clave privada van en las variables de entorno de Railway
          (nunca acá). El CUIT y el Punto de Venta se configuran abajo.
        </p>
        {estadoQ.data && (
          <div className="mt-1 flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Ambiente:
            </span>
            <span
              className={`text-xs font-mono font-medium ${
                estadoQ.data.ambiente === "produccion" ? "text-green-700" : "text-amber-600"
              }`}
            >
              {estadoQ.data.ambiente === "produccion" ? "Producción" : "Homologación (pruebas)"}
            </span>
          </div>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <EmisorCard emisor="pablo" />
        <EmisorCard emisor="santini" />
      </div>
    </section>
  );
}
