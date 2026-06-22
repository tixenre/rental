import { useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/design-system/ui/button";
import { adminApi, type CalendarioPedido } from "@/lib/admin/api";
import { EstadoBadge } from "@/design-system/kit/EstadoBadge";

const MESES = [
  "Enero",
  "Febrero",
  "Marzo",
  "Abril",
  "Mayo",
  "Junio",
  "Julio",
  "Agosto",
  "Septiembre",
  "Octubre",
  "Noviembre",
  "Diciembre",
];
const DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

const ymd = (d: Date) => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
};

type View = "mes" | "semana";

export type CalendarioWidgetProps = {
  /** "compact" baja la altura de cada celda y muestra menos pedidos por día. */
  variant?: "full" | "compact";
  /** Vista inicial. Default "mes". */
  initialView?: View;
  /** Si querés ocultar el switcher de vistas (forzar una). */
  hideViewSwitch?: boolean;
  /** Mostrar leyenda de estados abajo. Default true. */
  showLegend?: boolean;
};

export function CalendarioWidget({
  variant = "full",
  initialView = "mes",
  hideViewSwitch = false,
  showLegend = true,
}: CalendarioWidgetProps) {
  const today = new Date();
  const navigate = useNavigate();
  const [view, setView] = useState<View>(initialView);
  const [cursor, setCursor] = useState(
    new Date(today.getFullYear(), today.getMonth(), today.getDate()),
  );

  const { cells, rangeStart, rangeEnd, headerLabel } = useMemo(() => {
    if (view === "semana") {
      // Lunes = 0
      const dow = (cursor.getDay() + 6) % 7;
      const start = new Date(cursor);
      start.setDate(cursor.getDate() - dow);
      const days = Array.from({ length: 7 }, (_, i) => {
        const d = new Date(start);
        d.setDate(start.getDate() + i);
        return d;
      });
      const end = days[6];
      const sameMonth = start.getMonth() === end.getMonth();
      const label = sameMonth
        ? `${start.getDate()}–${end.getDate()} ${MESES[start.getMonth()]} ${start.getFullYear()}`
        : `${start.getDate()} ${MESES[start.getMonth()].slice(0, 3)} – ${end.getDate()} ${MESES[end.getMonth()].slice(0, 3)} ${end.getFullYear()}`;
      return { cells: days, rangeStart: ymd(start), rangeEnd: ymd(end), headerLabel: label };
    }
    // Mes
    const year = cursor.getFullYear();
    const month = cursor.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startOffset = (firstDay.getDay() + 6) % 7;
    const gridStart = new Date(year, month, 1 - startOffset);
    const totalCells = Math.ceil((startOffset + lastDay.getDate()) / 7) * 7;
    const days = Array.from({ length: totalCells }, (_, i) => {
      const d = new Date(gridStart);
      d.setDate(gridStart.getDate() + i);
      return d;
    });
    return {
      cells: days,
      rangeStart: ymd(days[0]),
      rangeEnd: ymd(days[days.length - 1]),
      headerLabel: `${MESES[month]} ${year}`,
    };
  }, [cursor, view]);

  const calQ = useQuery({
    queryKey: ["admin", "calendario", rangeStart, rangeEnd],
    queryFn: () => adminApi.getCalendario(rangeStart, rangeEnd),
    staleTime: 60_000,
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

  const cursorMonth = cursor.getMonth();
  const compact = variant === "compact";
  const maxPedidosPorDia = compact ? 2 : 3;
  const minCellHeight = compact ? "min-h-[78px]" : "min-h-[110px]";

  const goPrev = () => {
    const d = new Date(cursor);
    if (view === "semana") d.setDate(d.getDate() - 7);
    else d.setMonth(d.getMonth() - 1);
    setCursor(d);
  };
  const goNext = () => {
    const d = new Date(cursor);
    if (view === "semana") d.setDate(d.getDate() + 7);
    else d.setMonth(d.getMonth() + 1);
    setCursor(d);
  };
  const goToday = () => setCursor(new Date(today.getFullYear(), today.getMonth(), today.getDate()));

  return (
    <div className="space-y-3">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
        <div className="font-display text-lg md:text-xl text-ink">{headerLabel}</div>
        <div className="flex items-center gap-2">
          {!hideViewSwitch && (
            <div className="inline-flex rounded-full border hairline bg-background overflow-hidden text-xs">
              <button
                type="button"
                onClick={() => setView("mes")}
                className={`px-3 py-1 font-mono uppercase tracking-[0.15em] ${
                  view === "mes" ? "bg-ink text-background" : "text-muted-foreground hover:text-ink"
                }`}
              >
                Mes
              </button>
              <button
                type="button"
                onClick={() => setView("semana")}
                className={`px-3 py-1 font-mono uppercase tracking-[0.15em] ${
                  view === "semana"
                    ? "bg-ink text-background"
                    : "text-muted-foreground hover:text-ink"
                }`}
              >
                Semana
              </button>
            </div>
          )}
          <Button variant="outline" size="icon" onClick={goPrev} aria-label="Anterior">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button variant="outline" onClick={goToday}>
            Hoy
          </Button>
          <Button variant="outline" size="icon" onClick={goNext} aria-label="Siguiente">
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {calQ.error && (
        <div className="rounded-md border hairline border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          Error: {(calQ.error as Error).message}
        </div>
      )}

      <div className="rounded-lg border hairline overflow-hidden bg-background">
        <div className="grid grid-cols-7 border-b hairline">
          {DIAS.map((d) => (
            <div
              key={d}
              className="px-2 py-1.5 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground text-center"
            >
              {d}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7">
          {cells.map((d, i) => {
            const k = ymd(d);
            const inMonth = view === "semana" ? true : d.getMonth() === cursorMonth;
            const isToday = ymd(today) === k;
            const pedidos = byDay.get(k) ?? [];
            return (
              <div
                key={i}
                className={`${minCellHeight} border-r border-b hairline p-1.5 ${
                  inMonth ? "bg-background" : "bg-muted/30"
                }`}
              >
                <div
                  className={`text-xs font-mono mb-1 ${
                    isToday
                      ? "inline-flex items-center justify-center h-5 min-w-5 rounded-full bg-ink text-background px-1"
                      : inMonth
                        ? "text-ink"
                        : "text-muted-foreground/60"
                  }`}
                >
                  {d.getDate()}
                </div>
                <div className="space-y-1">
                  {pedidos.slice(0, maxPedidosPorDia).map((p) => (
                    <button
                      key={p.id}
                      onClick={() =>
                        navigate({ to: "/admin/pedidos/$id", params: { id: String(p.id) } })
                      }
                      className="block w-full text-left rounded-sm bg-accent/40 hover:bg-accent/70 px-1 py-0.5 text-[10px] leading-tight"
                      title={`#${p.numero_pedido ?? p.id} · ${p.cliente_nombre ?? ""} · ${p.equipos ?? ""}`}
                    >
                      <div className="truncate text-ink">
                        {p.cliente_nombre || `Pedido #${p.numero_pedido ?? p.id}`}
                      </div>
                    </button>
                  ))}
                  {pedidos.length > maxPedidosPorDia && (
                    <div className="text-[10px] text-muted-foreground pl-1">
                      +{pedidos.length - maxPedidosPorDia} más
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="text-xs text-muted-foreground">
          {calQ.isLoading ? "Cargando…" : `${calQ.data?.length ?? 0} pedidos en pantalla`}
        </div>
        {showLegend && (
          <div className="flex flex-wrap gap-1.5 text-xs">
            {(["presupuesto", "confirmado", "retirado", "devuelto", "finalizado"] as const).map(
              (e) => (
                <EstadoBadge key={e} estado={e} />
              ),
            )}
          </div>
        )}
      </div>
    </div>
  );
}
