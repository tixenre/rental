import { useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";
import { fmtArs, formatFechaCorta } from "@/lib/format";
import { Button } from "@/design-system/ui/button";
import { SegmentedControl } from "@/design-system/ui/segmented-control";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/design-system/ui/tooltip";
import { Popover, PopoverContent, PopoverTrigger } from "@/design-system/ui/popover";
import { adminApi, type CalendarioPedido, type PedidoEstado } from "@/lib/admin/api";
import { EstadoBadge } from "@/design-system/ui/EstadoBadge";
import { estadoClase } from "@/design-system/ui/estado-color";

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

/** Estados que se muestran en la leyenda y sirven de filtro clickeable —
 * los mismos que el backend devuelve en `get_calendario`. */
const LEGEND_ESTADOS: PedidoEstado[] = [
  "presupuesto",
  "confirmado",
  "retirado",
  "devuelto",
  "finalizado",
];

const ymd = (d: Date) => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
};

type View = "mes" | "semana";

/** Un pedido dentro de UNA semana del grid: en qué columna (0-6, lun-dom)
 * arranca/termina EN ESA FILA, y si continúa más allá de sus bordes (la
 * misma reserva puede cruzar varias filas-semana). */
type Segmento = {
  pedido: CalendarioPedido;
  colStart: number;
  colEnd: number;
  continuaIzq: boolean;
  continuaDer: boolean;
};

/** Para una semana (7 días consecutivos), calcula qué pedidos la atraviesan y
 * en qué rango de columnas. Reusa `byDay` (no recalcula fechas a mano) para
 * que la inclusión de días sea IDÉNTICA a la que ya usa el resto del widget —
 * sin esto, un desajuste de horas en fecha_desde/hasta correría el segmento
 * un día de más o de menos respecto de los chips que antes se veían por día. */
function segmentosDeSemana(semana: Date[], byDay: Map<string, CalendarioPedido[]>): Segmento[] {
  const rango = new Map<number, { colStart: number; colEnd: number }>();
  const porId = new Map<number, CalendarioPedido>();
  semana.forEach((d, col) => {
    for (const p of byDay.get(ymd(d)) ?? []) {
      porId.set(p.id, p);
      const r = rango.get(p.id);
      if (r) r.colEnd = col;
      else rango.set(p.id, { colStart: col, colEnd: col });
    }
  });
  return [...rango.entries()].map(([id, { colStart, colEnd }]) => {
    const pedido = porId.get(id)!;
    return {
      pedido,
      colStart,
      colEnd,
      // Si el propio fecha_desde/hasta cae ANTES/DESPUÉS de esta semana, el
      // segmento está recortado (clamped) → borde plano, sigue en la fila vecina.
      continuaIzq: new Date(pedido.fecha_desde) < semana[0],
      continuaDer: new Date(pedido.fecha_hasta) > semana[6],
    };
  });
}

/** Empaquetado greedy en "carriles" (mismo algoritmo que un calendario tipo
 * Google/FullCalendar): ordena por inicio y asigna cada segmento al primer
 * carril libre para su rango de columnas. Lo que no entra en `maxCarriles`
 * queda en `overflow` (se resume como "+N más" por día). */
function asignarCarriles(segmentos: Segmento[], maxCarriles: number) {
  const ordenados = [...segmentos].sort(
    (a, b) => a.colStart - b.colStart || b.colEnd - b.colStart - (a.colEnd - a.colStart),
  );
  const finDeCarril: number[] = [];
  const ubicados: (Segmento & { carril: number })[] = [];
  const overflow: Segmento[] = [];
  for (const seg of ordenados) {
    let carril = finDeCarril.findIndex((fin) => fin < seg.colStart);
    if (carril === -1) carril = finDeCarril.length;
    if (carril >= maxCarriles) {
      overflow.push(seg);
      continue;
    }
    finDeCarril[carril] = seg.colEnd;
    ubicados.push({ ...seg, carril });
  }
  return { ubicados, overflow };
}

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
  // Filtro por estado (clic en la leyenda). null = todos.
  const [filtroEstado, setFiltroEstado] = useState<PedidoEstado | null>(null);

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
    staleTime: 30_000,
  });

  // Pedidos que efectivamente se pintan: todos, o solo el estado filtrado.
  // byDay/segmentos/overflow/conteo derivan de acá → el filtro se respeta en
  // todo el widget con una sola fuente.
  const pedidosVisibles = useMemo(() => {
    const data = calQ.data ?? [];
    return filtroEstado ? data.filter((p) => p.estado === filtroEstado) : data;
  }, [calQ.data, filtroEstado]);

  const byDay = useMemo(() => {
    const map = new Map<string, CalendarioPedido[]>();
    for (const p of pedidosVisibles) {
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
  }, [pedidosVisibles]);

  const cursorMonth = cursor.getMonth();
  const compact = variant === "compact";
  // La vista Semana tiene una sola fila y todo el alto libre → muchos más
  // carriles antes de caer en overflow. La vista Mes se queda compacta (si no,
  // 5-6 filas de semana × 8 carriles = un scroll enorme).
  const maxCarriles = view === "semana" ? 8 : compact ? 2 : 3;
  const minCellHeight = compact ? "min-h-[78px]" : "min-h-[110px]";
  // Alto de fila fijo por carril — la altura de celda de arriba ya reserva
  // aire suficiente para maxCarriles filas de este alto + la fila del número.
  // La barra se centra en su carril (self-center) → el sobrante es el aire
  // entre barras apiladas.
  const altoCarril = compact ? 22 : 28;

  // Filas-semana de 7 días — la vista "semana" ya es una sola.
  const semanas = useMemo(() => {
    const out: Date[][] = [];
    for (let i = 0; i < cells.length; i += 7) out.push(cells.slice(i, i + 7));
    return out;
  }, [cells]);

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
            <SegmentedControl
              variant="pill"
              value={view}
              onChange={(v) => setView(v as "mes" | "semana")}
              options={[
                { value: "mes", label: "Mes" },
                { value: "semana", label: "Semana" },
              ]}
            />
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

      <TooltipProvider delayDuration={200}>
        <div className="rounded-lg border hairline overflow-hidden bg-background">
          <div className="grid grid-cols-7 border-b hairline">
            {DIAS.map((d) => (
              <div key={d} className="px-2 py-1.5 t-eyebrow text-center">
                {d}
              </div>
            ))}
          </div>
          {semanas.map((semana, wi) => {
            const segmentos = segmentosDeSemana(semana, byDay);
            const { ubicados } = asignarCarriles(segmentos, maxCarriles);
            // "+N más" por día = lo que ese día tiene en byDay menos lo que
            // efectivamente quedó cubierto por una barra ubicada — así el
            // conteo sigue siendo verdad aunque un pedido largo ocupe varios
            // carriles-semana distintos a lo largo del mes.
            const overflowPorDia = semana.map((d, i) => {
              const total = (byDay.get(ymd(d)) ?? []).length;
              const cubiertos = ubicados.filter((u) => u.colStart <= i && i <= u.colEnd).length;
              return Math.max(0, total - cubiertos);
            });
            return (
              <div
                key={wi}
                className="grid"
                style={{
                  gridTemplateColumns: "repeat(7, minmax(0, 1fr))",
                  gridTemplateRows: `auto repeat(${maxCarriles}, ${altoCarril}px) auto`,
                }}
              >
                {semana.map((d, i) => {
                  const k = ymd(d);
                  const inMonth = view === "semana" ? true : d.getMonth() === cursorMonth;
                  const isToday = ymd(today) === k;
                  return (
                    <div
                      key={k}
                      style={{ gridColumn: i + 1, gridRow: "1 / -1" }}
                      className={cn(
                        minCellHeight,
                        "border-r border-b hairline p-1.5",
                        inMonth ? "bg-background" : "bg-muted/30",
                      )}
                    >
                      <div
                        className={cn(
                          "text-xs font-mono",
                          isToday
                            ? "inline-flex items-center justify-center h-5 min-w-5 rounded-full bg-ink text-background px-1"
                            : inMonth
                              ? "text-ink"
                              : "text-muted-foreground/60",
                        )}
                      >
                        {d.getDate()}
                      </div>
                    </div>
                  );
                })}
                {ubicados.map(
                  ({ pedido: p, colStart, colEnd, carril, continuaIzq, continuaDer }) => (
                    <Tooltip key={p.id}>
                      <TooltipTrigger asChild>
                        <button
                          onClick={() =>
                            navigate({ to: "/admin/pedidos/$id", params: { id: String(p.id) } })
                          }
                          style={{
                            gridColumn: `${colStart + 1} / ${colEnd + 2}`,
                            gridRow: carril + 2,
                          }}
                          className={cn(
                            "block min-w-0 self-center truncate px-1.5 py-1 text-left text-2xs leading-tight transition hover:opacity-80 sm:text-xs",
                            estadoClase(p.estado),
                            // Aire para que la barra no toque las líneas del grid.
                            // Un extremo que continúa en otra fila-semana SÍ pega
                            // al borde (se lee como una sola barra que sigue).
                            continuaIzq ? "rounded-l-none" : "ml-1 rounded-l-md",
                            continuaDer ? "rounded-r-none" : "mr-1 rounded-r-md",
                          )}
                        >
                          {continuaIzq && "◂ "}#{p.numero_pedido ?? p.id} ·{" "}
                          {p.cliente_nombre || "Sin cliente"}
                          {continuaDer && " ▸"}
                        </button>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64 whitespace-normal">
                        <div className="font-semibold">
                          #{p.numero_pedido ?? p.id} · {p.cliente_nombre || "Sin cliente"}
                        </div>
                        <div className="mt-0.5 opacity-80">
                          {formatFechaCorta(p.fecha_desde)} → {formatFechaCorta(p.fecha_hasta)}
                        </div>
                        {p.equipos && <div className="mt-0.5 opacity-80">{p.equipos}</div>}
                        <div className="mt-0.5 opacity-80">{fmtArs(p.monto_total)}</div>
                      </TooltipContent>
                    </Tooltip>
                  ),
                )}
                {overflowPorDia.map((n, i) => {
                  if (n <= 0) return null;
                  const d = semana[i];
                  const delDia = byDay.get(ymd(d)) ?? [];
                  // El popover lista TODOS los pedidos del día (visibles +
                  // ocultos) — así los que caían en overflow dejan de ser
                  // inalcanzables y hay contexto completo del día.
                  return (
                    <Popover key={`ov-${i}`}>
                      <PopoverTrigger asChild>
                        <button
                          style={{ gridColumn: i + 1, gridRow: maxCarriles + 2 }}
                          className="ml-1 text-left text-2xs text-muted-foreground transition hover:text-ink sm:text-xs"
                        >
                          +{n} más
                        </button>
                      </PopoverTrigger>
                      <PopoverContent align="start" className="w-72 p-2">
                        <div className="mb-1.5 px-1 text-xs font-semibold text-ink">
                          {d.getDate()} {MESES[d.getMonth()].slice(0, 3)} · {delDia.length}{" "}
                          {delDia.length === 1 ? "pedido" : "pedidos"}
                        </div>
                        <div className="flex max-h-72 flex-col gap-0.5 overflow-auto">
                          {delDia.map((p) => (
                            <button
                              key={p.id}
                              onClick={() =>
                                navigate({ to: "/admin/pedidos/$id", params: { id: String(p.id) } })
                              }
                              className="flex items-center gap-2 rounded-sm px-1.5 py-1 text-left text-xs transition hover:bg-muted"
                            >
                              <span className="shrink-0 font-mono text-2xs text-muted-foreground">
                                #{p.numero_pedido ?? p.id}
                              </span>
                              <span className="flex-1 truncate">
                                {p.cliente_nombre || "Sin cliente"}
                              </span>
                              <EstadoBadge estado={p.estado} className="shrink-0" />
                            </button>
                          ))}
                        </div>
                      </PopoverContent>
                    </Popover>
                  );
                })}
              </div>
            );
          })}
        </div>
      </TooltipProvider>

      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="text-xs text-muted-foreground">
          {calQ.isLoading
            ? "Cargando…"
            : `${pedidosVisibles.length} ${pedidosVisibles.length === 1 ? "pedido" : "pedidos"} en pantalla`}
        </div>
        {showLegend && (
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            {LEGEND_ESTADOS.map((e) => {
              const activo = filtroEstado === e;
              return (
                <button
                  key={e}
                  type="button"
                  onClick={() => setFiltroEstado(activo ? null : e)}
                  aria-pressed={activo}
                  title={activo ? `Quitar filtro: ${e}` : `Filtrar por ${e}`}
                  className={cn(
                    "rounded-full transition",
                    filtroEstado !== null && !activo && "opacity-40 hover:opacity-100",
                    activo && "ring-2 ring-ink/30 ring-offset-1 ring-offset-background",
                  )}
                >
                  <EstadoBadge estado={e} />
                </button>
              );
            })}
            {filtroEstado && (
              <button
                type="button"
                onClick={() => setFiltroEstado(null)}
                className="text-muted-foreground underline underline-offset-2 hover:text-ink"
              >
                Ver todos
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
