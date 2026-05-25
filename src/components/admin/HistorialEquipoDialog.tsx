/**
 * Vista de historial de alquileres de un equipo. Modal con stats arriba
 * (total alquileres, días, revenue) + tabla con cada pedido en el que
 * apareció el equipo.
 *
 * Lee de GET /api/equipos/:id/historial (ya existía en el backend).
 */

import { useQuery } from "@tanstack/react-query";
import { Loader2, ExternalLink } from "lucide-react";
import { Link } from "@tanstack/react-router";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { adminApi, type Equipo } from "@/lib/admin/api";

const fmtFecha = (iso: string) => {
  try {
    // El backend devuelve fechas como TEXT "YYYY-MM-DD" (a veces con timestamp).
    // Si solo tenemos día (10 chars), parseamos como medianoche LOCAL para que
    // toLocaleDateString no shiftee al día anterior por timezone (es-AR es UTC-3).
    const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? iso + "T00:00:00" : iso;
    return new Date(dateOnly).toLocaleDateString("es-AR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
};

const fmtMoneda = (n: number) =>
  new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  }).format(n);

export function HistorialEquipoDialog({
  equipo,
  open,
  onOpenChange,
}: {
  equipo: Equipo | null;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const histQ = useQuery({
    queryKey: ["admin", "equipo-historial", equipo?.id],
    queryFn: () => adminApi.getEquipoHistorial(equipo!.id),
    enabled: !!equipo?.id && open,
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-full sm:max-w-3xl max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display text-xl">Historial de alquileres</DialogTitle>
          {equipo && (
            <p className="text-sm text-muted-foreground">
              {equipo.nombre}
              {equipo.marca && <span className="ml-1.5 text-xs">· {equipo.marca}</span>}
            </p>
          )}
        </DialogHeader>

        {histQ.isLoading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground py-6">
            <Loader2 className="h-4 w-4 animate-spin" /> Cargando historial…
          </div>
        )}

        {histQ.error && (
          <div className="rounded-md border hairline border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            Error: {(histQ.error as Error).message}
          </div>
        )}

        {histQ.data && (
          <>
            {/* Stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <Stat label="Alquileres" value={histQ.data.stats.total_alquileres} />
              <Stat label="Días totales" value={histQ.data.stats.total_dias} />
              <Stat label="Revenue" value={fmtMoneda(histQ.data.stats.total_revenue)} />
              <Stat
                label="Último alquiler"
                value={
                  histQ.data.stats.ultimo_alquiler
                    ? fmtFecha(histQ.data.stats.ultimo_alquiler)
                    : "—"
                }
              />
            </div>

            {/* Tabla */}
            {histQ.data.historial.length === 0 ? (
              <p className="text-sm text-muted-foreground italic py-6 text-center">
                Sin historial. Este equipo no apareció en ningún pedido.
              </p>
            ) : (
              <div className="rounded-md border hairline overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Pedido</TableHead>
                      <TableHead>Cliente</TableHead>
                      <TableHead>Fechas</TableHead>
                      <TableHead className="text-right">Cant.</TableHead>
                      <TableHead className="text-right">Días</TableHead>
                      <TableHead className="text-right">Precio/día</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {histQ.data.historial.map((h) => (
                      <TableRow key={h.id}>
                        <TableCell>
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-xs">{h.numero_pedido}</span>
                            <Badge variant="outline" className="text-[10px]">
                              {h.estado}
                            </Badge>
                          </div>
                        </TableCell>
                        <TableCell className="text-sm">{h.cliente}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {fmtFecha(h.fecha_desde)} → {fmtFecha(h.fecha_hasta)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{h.cantidad}</TableCell>
                        <TableCell className="text-right tabular-nums text-muted-foreground">
                          {h.dias}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {h.precio_item ? fmtMoneda(h.precio_item) : "—"}
                        </TableCell>
                        <TableCell>
                          <Link to="/admin/pedidos/$id" params={{ id: String(h.id) }}>
                            <Button size="icon" variant="ghost" title="Ver pedido">
                              <ExternalLink className="h-3.5 w-3.5" />
                            </Button>
                          </Link>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </>
        )}

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cerrar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border hairline bg-muted/20 p-2">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="text-base font-medium tabular-nums">{value}</div>
    </div>
  );
}
