import { useMemo, useState } from "react";
import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

import { adminApi, ESTADO_LABEL, type CalendarioPedido } from "@/lib/admin/api";
import { pedidoEstadoVariant } from "@/lib/admin/pedido-estado";

export const Route = createLazyFileRoute("/admin/calendario")({
  component: CalendarioPage,
});

const MESES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];
const DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

const ymd = (d: Date) => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
};

function CalendarioPage() {
  const today = new Date();
  const navigate = useNavigate();
  const [cursor, setCursor] = useState(new Date(today.getFullYear(), today.getMonth(), 1));

  const year = cursor.getFullYear();
  const month = cursor.getMonth();

  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  // Lunes = 0
  const startOffset = (firstDay.getDay() + 6) % 7;
  const gridStart = new Date(year, month, 1 - startOffset);
  const totalCells = Math.ceil((startOffset + lastDay.getDate()) / 7) * 7;
  const cells = Array.from({ length: totalCells }, (_, i) => {
    const d = new Date(gridStart);
    d.setDate(gridStart.getDate() + i);
    return d;
  });

  const desde = ymd(cells[0]);
  const hasta = ymd(cells[cells.length - 1]);

  const calQ = useQuery({
    queryKey: ["admin", "calendario", desde, hasta],
    queryFn: () => adminApi.getCalendario(desde, hasta),
  });

  const byDay = useMemo(() => {
    const map = new Map<string, CalendarioPedido[]>();
    for (const p of calQ.data ?? []) {
      const start = new Date(p.fecha_desde);
      const end = new Date(p.fecha_hasta);
      const cur = new Date(start);
      while (cur <= end) {
        const k = ymd(cur);
        if (!map.has(k)) map.set(k, []);
        map.get(k)!.push(p);
        cur.setDate(cur.getDate() + 1);
      }
    }
    return map;
  }, [calQ.data]);

  const goPrev = () => setCursor(new Date(year, month - 1, 1));
  const goNext = () => setCursor(new Date(year, month + 1, 1));
  const goToday = () => setCursor(new Date(today.getFullYear(), today.getMonth(), 1));

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-7xl mx-auto">
      <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Back-office
          </div>
          <h1 className="font-display text-3xl text-ink">
            {MESES[month]} {year}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {calQ.isLoading ? "Cargando…" : `${calQ.data?.length ?? 0} pedidos en pantalla`}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="icon" onClick={goPrev}><ChevronLeft className="h-4 w-4" /></Button>
          <Button variant="outline" onClick={goToday}>Hoy</Button>
          <Button variant="outline" size="icon" onClick={goNext}><ChevronRight className="h-4 w-4" /></Button>
        </div>
      </header>

      {calQ.error && (
        <div className="rounded-md border hairline border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          Error: {(calQ.error as Error).message}
        </div>
      )}

      <div className="rounded-lg border hairline overflow-hidden bg-background">
        <div className="grid grid-cols-7 border-b hairline">
          {DIAS.map((d) => (
            <div key={d} className="px-2 py-1.5 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground text-center">
              {d}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7">
          {cells.map((d, i) => {
            const k = ymd(d);
            const inMonth = d.getMonth() === month;
            const isToday = ymd(today) === k;
            const pedidos = byDay.get(k) ?? [];
            return (
              <div
                key={i}
                className={`min-h-[110px] border-r border-b hairline p-1.5 ${
                  inMonth ? "bg-background" : "bg-muted/30"
                }`}
              >
                <div className={`text-xs font-mono mb-1 ${
                  isToday ? "inline-flex items-center justify-center h-5 min-w-5 rounded-full bg-ink text-background px-1" :
                  inMonth ? "text-ink" : "text-muted-foreground/60"
                }`}>
                  {d.getDate()}
                </div>
                <div className="space-y-1">
                  {pedidos.slice(0, 3).map((p) => (
                    <button
                      key={p.id}
                      onClick={() => navigate({ to: "/admin/pedidos/$id", params: { id: String(p.id) } })}
                      className="block w-full text-left rounded-sm bg-accent/40 hover:bg-accent/70 px-1 py-0.5 text-[10px] leading-tight"
                      title={`#${p.numero_pedido ?? p.id} · ${p.cliente_nombre ?? ""} · ${p.equipos ?? ""}`}
                    >
                      <div className="truncate text-ink">
                        {p.cliente_nombre || `Pedido #${p.numero_pedido ?? p.id}`}
                      </div>
                    </button>
                  ))}
                  {pedidos.length > 3 && (
                    <div className="text-[10px] text-muted-foreground pl-1">
                      +{pedidos.length - 3} más
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Leyenda de estados */}
      <div className="flex flex-wrap gap-2 text-xs">
        {(["presupuesto", "confirmado", "retirado", "devuelto", "finalizado"] as const).map((e) => (
          <Badge key={e} variant={pedidoEstadoVariant(e)}>{ESTADO_LABEL[e]}</Badge>
        ))}
      </div>

    </div>
  );
}
