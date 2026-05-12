/**
 * Dashboard de uso de equipos (#205). Modal desde la lista admin con:
 * - Stats globales (equipos, pedidos, revenue)
 * - Top 10 más alquilados
 * - Equipos sin movimiento (candidatos a vender/revisar)
 * - Revenue por categoría
 */

import { useQuery } from "@tanstack/react-query";
import { TrendingUp, AlertCircle, BarChart3, DollarSign } from "lucide-react";

import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

import { adminApi } from "@/lib/admin/api";

const fmtMoneda = (n: number | null | undefined) => {
  if (n == null) return "—";
  return new Intl.NumberFormat("es-AR", {
    style: "currency", currency: "ARS", maximumFractionDigits: 0,
  }).format(n);
};

const fmtFecha = (iso: string | null) => {
  if (!iso) return "—";
  try {
    const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? iso + "T00:00:00" : iso;
    return new Date(dateOnly).toLocaleDateString("es-AR", {
      day: "2-digit", month: "short", year: "numeric",
    });
  } catch { return iso; }
};

const diasDesde = (iso: string | null): number | null => {
  if (!iso) return null;
  try {
    const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? iso + "T00:00:00" : iso;
    const d = new Date(dateOnly);
    return Math.floor((Date.now() - d.getTime()) / (1000 * 60 * 60 * 24));
  } catch { return null; }
};

export function DashboardUsoDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const dataQ = useQuery({
    queryKey: ["admin", "dashboard-uso"],
    queryFn: () => adminApi.dashboardUso(90),
    enabled: open,
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-full sm:max-w-4xl max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">
            Dashboard de uso
          </DialogTitle>
          <p className="text-sm text-muted-foreground">
            Top alquilados · Sin movimiento · Revenue por categoría
          </p>
        </DialogHeader>

        {dataQ.isLoading && (
          <p className="text-sm text-muted-foreground py-6">Cargando…</p>
        )}

        {dataQ.error && (
          <div className="rounded-md border hairline border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            Error: {(dataQ.error as Error).message}
          </div>
        )}

        {dataQ.data && (
          <div className="space-y-5">
            {/* Stats globales */}
            <section className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <Stat icon={<BarChart3 className="h-3.5 w-3.5" />} label="Equipos activos" value={dataQ.data.totales.total_equipos} />
              <Stat icon={<BarChart3 className="h-3.5 w-3.5" />} label="Visibles" value={dataQ.data.totales.total_visibles} />
              <Stat icon={<TrendingUp className="h-3.5 w-3.5" />} label="Pedidos" value={dataQ.data.totales.total_pedidos} />
              <Stat icon={<DollarSign className="h-3.5 w-3.5" />} label="Revenue" value={fmtMoneda(dataQ.data.totales.revenue_total)} />
            </section>

            {/* Top alquilados */}
            <section>
              <h2 className="text-sm font-medium mb-2 flex items-center gap-1.5">
                <TrendingUp className="h-4 w-4" /> Top 10 más alquilados
              </h2>

              {/* Mobile: cards */}
              <div className="md:hidden space-y-2">
                {dataQ.data.top_alquilados.length === 0 ? (
                  <div className="rounded-md border hairline px-3 py-4 text-center text-sm text-muted-foreground">
                    Sin historial.
                  </div>
                ) : (
                  dataQ.data.top_alquilados.map((e) => (
                    <div key={e.id} className="rounded-md border hairline p-3 flex items-center gap-3">
                      {e.foto_url
                        ? <img src={e.foto_url} alt="" className="h-10 w-10 rounded object-cover bg-muted/30 shrink-0" loading="lazy" />
                        : <div className="h-10 w-10 rounded bg-muted/30 shrink-0" />}
                      <div className="min-w-0 flex-1">
                        <div className="font-medium text-sm truncate">{e.nombre}</div>
                        <div className="text-[11px] text-muted-foreground truncate">
                          {[e.marca, e.modelo].filter(Boolean).join(" / ")}
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="font-medium tabular-nums text-sm">{e.cant_pedidos} <span className="text-[10px] text-muted-foreground font-normal">pedidos</span></div>
                        <div className="text-[11px] text-muted-foreground tabular-nums">{fmtMoneda(e.revenue_total)}</div>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Desktop: tabla */}
              <div className="hidden md:block rounded-md border hairline overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-10"></TableHead>
                      <TableHead>Equipo</TableHead>
                      <TableHead className="text-right">Pedidos</TableHead>
                      <TableHead className="text-right">Revenue</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {dataQ.data.top_alquilados.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={4} className="text-center text-muted-foreground py-4 text-sm">
                          Sin historial.
                        </TableCell>
                      </TableRow>
                    )}
                    {dataQ.data.top_alquilados.map((e) => (
                      <TableRow key={e.id}>
                        <TableCell>
                          {e.foto_url
                            ? <img src={e.foto_url} alt="" className="h-7 w-7 rounded object-cover bg-muted/30" />
                            : <div className="h-7 w-7 rounded bg-muted/30" />}
                        </TableCell>
                        <TableCell>
                          <div className="font-medium text-xs">{e.nombre}</div>
                          <div className="text-[11px] text-muted-foreground">
                            {[e.marca, e.modelo].filter(Boolean).join(" / ")}
                          </div>
                        </TableCell>
                        <TableCell className="text-right tabular-nums font-medium text-sm">{e.cant_pedidos}</TableCell>
                        <TableCell className="text-right tabular-nums text-xs">{fmtMoneda(e.revenue_total)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </section>

            {/* Sin uso */}
            <section>
              <h2 className="text-sm font-medium mb-2 flex items-center gap-1.5">
                <AlertCircle className="h-4 w-4 text-amber" />
                Sin movimiento hace +{dataQ.data.dias_sin_uso_threshold} días
                <span className="text-xs text-muted-foreground font-normal">· candidatos a revisar/vender</span>
              </h2>

              {/* Mobile: cards */}
              <div className="md:hidden space-y-2">
                {dataQ.data.sin_uso.length === 0 ? (
                  <div className="rounded-md border hairline px-3 py-4 text-center text-sm text-muted-foreground">
                    Todos los equipos tuvieron movimiento reciente.
                  </div>
                ) : (
                  dataQ.data.sin_uso.map((e) => {
                    const dias = diasDesde(e.ultimo_alquiler);
                    return (
                      <div key={e.id} className="rounded-md border hairline p-3 flex items-center gap-3">
                        {e.foto_url
                          ? <img src={e.foto_url} alt="" className="h-10 w-10 rounded object-cover bg-muted/30 shrink-0" loading="lazy" />
                          : <div className="h-10 w-10 rounded bg-muted/30 shrink-0" />}
                        <div className="min-w-0 flex-1">
                          <div className="font-medium text-sm truncate">{e.nombre}</div>
                          <div className="text-[11px] text-muted-foreground truncate">
                            {[e.marca, e.modelo].filter(Boolean).join(" / ")}
                          </div>
                          <div className="mt-1 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                            {e.ultimo_alquiler ? (
                              <>
                                <span>{fmtFecha(e.ultimo_alquiler)}</span>
                                <Badge variant="outline" className="text-[9px]">
                                  {dias != null ? `${dias}d` : ""}
                                </Badge>
                              </>
                            ) : (
                              <Badge variant="destructive" className="text-[10px]">Nunca alquilado</Badge>
                            )}
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          <div className="text-xs tabular-nums font-medium">
                            {e.valor_reposicion ? `USD ${e.valor_reposicion.toLocaleString("es-AR")}` : "—"}
                          </div>
                          <div className="text-[10px] text-muted-foreground tabular-nums">
                            {e.total_alquileres} total
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Desktop: tabla */}
              <div className="hidden md:block rounded-md border hairline overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-10"></TableHead>
                      <TableHead>Equipo</TableHead>
                      <TableHead className="text-right">Último alquiler</TableHead>
                      <TableHead className="text-right">Total</TableHead>
                      <TableHead className="text-right">Valor USD</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {dataQ.data.sin_uso.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={5} className="text-center text-muted-foreground py-4 text-sm">
                          Todos los equipos tuvieron movimiento reciente.
                        </TableCell>
                      </TableRow>
                    )}
                    {dataQ.data.sin_uso.map((e) => {
                      const dias = diasDesde(e.ultimo_alquiler);
                      return (
                        <TableRow key={e.id}>
                          <TableCell>
                            {e.foto_url
                              ? <img src={e.foto_url} alt="" className="h-7 w-7 rounded object-cover bg-muted/30" />
                              : <div className="h-7 w-7 rounded bg-muted/30" />}
                          </TableCell>
                          <TableCell>
                            <div className="font-medium text-xs">{e.nombre}</div>
                            <div className="text-[11px] text-muted-foreground">
                              {[e.marca, e.modelo].filter(Boolean).join(" / ")}
                            </div>
                          </TableCell>
                          <TableCell className="text-right text-xs">
                            {e.ultimo_alquiler ? (
                              <div>
                                <div>{fmtFecha(e.ultimo_alquiler)}</div>
                                <Badge variant="outline" className="text-[9px]">
                                  {dias != null ? `${dias}d` : ""}
                                </Badge>
                              </div>
                            ) : (
                              <Badge variant="destructive" className="text-[10px]">Nunca</Badge>
                            )}
                          </TableCell>
                          <TableCell className="text-right tabular-nums text-muted-foreground text-xs">
                            {e.total_alquileres}
                          </TableCell>
                          <TableCell className="text-right tabular-nums text-xs">
                            {e.valor_reposicion ? `USD ${e.valor_reposicion.toLocaleString("es-AR")}` : "—"}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </section>

            {/* Cuentas por cobrar */}
            <section>
              <h2 className="text-sm font-medium mb-2 flex items-center gap-1.5">
                <DollarSign className="h-4 w-4 text-amber" /> Por cobrar
                <span className="text-xs text-muted-foreground font-normal">
                  · pedidos confirmados con monto pendiente
                </span>
              </h2>
              <div className="rounded-md border hairline bg-amber-soft/30 p-3 mb-2">
                <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Total adeudado</div>
                <div className="text-2xl font-medium tabular-nums">
                  {fmtMoneda(dataQ.data.por_cobrar.total)}
                </div>
                <div className="text-xs text-muted-foreground">
                  {dataQ.data.por_cobrar.count} pedido{dataQ.data.por_cobrar.count === 1 ? "" : "s"} con saldo
                </div>
              </div>
              {dataQ.data.por_cobrar.items.length > 0 && (
                <>
                  {/* Mobile: cards */}
                  <div className="md:hidden space-y-2">
                    {dataQ.data.por_cobrar.items.map((p) => (
                      <div key={p.id} className="rounded-md border hairline p-3 space-y-1.5">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-1.5 min-w-0">
                            <span className="font-mono text-xs shrink-0">
                              {p.numero_pedido ?? `#${p.id}`}
                            </span>
                            <Badge variant="outline" className="text-[10px]">{p.estado}</Badge>
                          </div>
                          <div className="text-right shrink-0">
                            <div className="text-xs tabular-nums font-medium text-amber-700">
                              {fmtMoneda(p.pendiente)}
                            </div>
                            <div className="text-[10px] text-muted-foreground tabular-nums">
                              de {fmtMoneda(p.monto_total)}
                            </div>
                          </div>
                        </div>
                        <div className="text-xs truncate">{p.cliente}</div>
                        <div className="text-[11px] text-muted-foreground">
                          {fmtFecha(p.fecha_desde)} → {fmtFecha(p.fecha_hasta)}
                        </div>
                      </div>
                    ))}
                    {dataQ.data.por_cobrar.count > dataQ.data.por_cobrar.items.length && (
                      <p className="text-[11px] text-muted-foreground italic text-center pt-1">
                        Mostrando top {dataQ.data.por_cobrar.items.length} de {dataQ.data.por_cobrar.count}.
                      </p>
                    )}
                  </div>

                  {/* Desktop: tabla */}
                  <div className="hidden md:block rounded-md border hairline overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Pedido</TableHead>
                          <TableHead>Cliente</TableHead>
                          <TableHead>Fechas</TableHead>
                          <TableHead className="text-right">Total</TableHead>
                          <TableHead className="text-right">Pendiente</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {dataQ.data.por_cobrar.items.map((p) => (
                          <TableRow key={p.id}>
                            <TableCell>
                              <div className="flex items-center gap-1.5">
                                <span className="font-mono text-xs">
                                  {p.numero_pedido ?? `#${p.id}`}
                                </span>
                                <Badge variant="outline" className="text-[10px]">{p.estado}</Badge>
                              </div>
                            </TableCell>
                            <TableCell className="text-xs">{p.cliente}</TableCell>
                            <TableCell className="text-[11px] text-muted-foreground">
                              {fmtFecha(p.fecha_desde)} → {fmtFecha(p.fecha_hasta)}
                            </TableCell>
                            <TableCell className="text-right tabular-nums text-xs">
                              {fmtMoneda(p.monto_total)}
                            </TableCell>
                            <TableCell className="text-right tabular-nums text-xs font-medium text-amber-700">
                              {fmtMoneda(p.pendiente)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                    {dataQ.data.por_cobrar.count > dataQ.data.por_cobrar.items.length && (
                      <p className="text-[11px] text-muted-foreground italic px-2 py-1.5 bg-muted/20">
                        Mostrando top {dataQ.data.por_cobrar.items.length} de {dataQ.data.por_cobrar.count} — el resto suma al total de arriba.
                      </p>
                    )}
                  </div>
                </>
              )}
            </section>

            {/* Por categoría */}
            <section>
              <h2 className="text-sm font-medium mb-2 flex items-center gap-1.5">
                <DollarSign className="h-4 w-4" /> Revenue por categoría
              </h2>

              {/* Mobile: cards */}
              <div className="md:hidden rounded-md border hairline divide-y hairline">
                {dataQ.data.por_categoria.length === 0 ? (
                  <div className="px-3 py-4 text-center text-sm text-muted-foreground">
                    Sin datos.
                  </div>
                ) : (
                  dataQ.data.por_categoria.map((c) => (
                    <div key={c.id} className="flex items-center justify-between gap-2 px-3 py-2.5">
                      <div className="font-medium text-sm truncate">{c.nombre}</div>
                      <div className="text-right shrink-0">
                        <div className="text-sm tabular-nums">{fmtMoneda(c.revenue_total)}</div>
                        <div className="text-[10px] text-muted-foreground tabular-nums">
                          {c.cant_pedidos} pedidos
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Desktop: tabla */}
              <div className="hidden md:block rounded-md border hairline overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Categoría</TableHead>
                      <TableHead className="text-right">Pedidos</TableHead>
                      <TableHead className="text-right">Revenue</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {dataQ.data.por_categoria.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={3} className="text-center text-muted-foreground py-4 text-sm">
                          Sin datos.
                        </TableCell>
                      </TableRow>
                    )}
                    {dataQ.data.por_categoria.map((c) => (
                      <TableRow key={c.id}>
                        <TableCell className="font-medium text-sm">{c.nombre}</TableCell>
                        <TableCell className="text-right tabular-nums text-sm">{c.cant_pedidos}</TableCell>
                        <TableCell className="text-right tabular-nums text-sm">{fmtMoneda(c.revenue_total)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </section>
          </div>
        )}

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cerrar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Stat({
  icon, label, value,
}: { icon: React.ReactNode; label: string; value: string | number }) {
  return (
    <div className="rounded-md border hairline bg-muted/20 p-3">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground flex items-center gap-1">
        {icon} {label}
      </div>
      <div className="text-lg font-medium tabular-nums mt-0.5">{value}</div>
    </div>
  );
}
