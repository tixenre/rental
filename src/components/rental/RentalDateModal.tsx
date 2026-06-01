import { es } from "date-fns/locale";
import { addDays, format, startOfDay } from "date-fns";
import {
  X,
  Calendar as CalendarIcon,
  Clock,
  Eraser,
  Minus,
  Plus,
  AlertTriangle,
} from "lucide-react";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Calendar } from "@/components/ui/calendar";
import { useCart } from "@/lib/cart-store";
import { deriveEndDate, diaAbierto, franjaParaFecha, timeToMinutes, ymd } from "@/lib/rental-dates";
import { useHorarios } from "@/lib/horarios";
import { apiGetDiasBloqueados } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";
import { TimeStepSelect } from "./TimeStepSelect";
import { useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";

type Props = {
  open: boolean;
  onOpenChange: (o: boolean) => void;
};

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 639px)");
    const update = () => setIsMobile(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return isMobile;
}

export function RentalDateModal({ open, onOpenChange }: Props) {
  const {
    items,
    startDate,
    endDate,
    startTime,
    endTime,
    setDates,
    setStartTime,
    setEndTime,
    days,
  } = useCart();
  const jornadas = days();
  const isMobile = useIsMobile();
  const horarios = useHorarios();
  // Estable durante el ciclo de vida del modal — evita recomputar memos por render.
  const today = useMemo(() => startOfDay(new Date()), []);

  // ── Días bloqueados (sin stock) ──────────────────────────────────────
  const itemsParam = useMemo(
    () =>
      Object.entries(items)
        .filter(([id, qty]) => /^\d+$/.test(id) && qty > 0)
        .map(([id, qty]) => `${id}:${qty}`)
        .join(","),
    [items],
  );
  const ventanaDesde = ymd(today);
  const ventanaHasta = ymd(addDays(today, 120));
  const diasBloqueadosQ = useQuery({
    queryKey: ["dias-bloqueados", itemsParam, ventanaDesde, ventanaHasta],
    queryFn: () => apiGetDiasBloqueados(itemsParam, ventanaDesde, ventanaHasta),
    enabled: open && itemsParam !== "",
    staleTime: 60_000,
  });
  const diasBloqueados = useMemo(
    () => new Set(diasBloqueadosQ.data?.dias_bloqueados ?? []),
    [diasBloqueadosQ.data],
  );

  // Ventana de consulta = 121 días (today … today+120). Si prácticamente todos
  // están bloqueados, hay al menos un item del carrito sin stock para ningún
  // período (ej.: un kit cuyo componente tiene stock < cantidad requerida).
  const sinStockTotal =
    diasBloqueadosQ.isSuccess && itemsParam !== "" && diasBloqueados.size >= 100;

  // ── Validaciones del rango ────────────────────────────────────────────
  const rangoCruzaBloqueado = useMemo(() => {
    if (!startDate || !endDate || diasBloqueados.size === 0) return false;
    for (let d = startOfDay(startDate); d <= startOfDay(endDate); d = addDays(d, 1)) {
      if (diasBloqueados.has(ymd(d))) return true;
    }
    return false;
  }, [startDate, endDate, diasBloqueados]);

  const franjaRetiro = franjaParaFecha(horarios, startDate);
  const franjaDevolucion = franjaParaFecha(horarios, endDate);
  const devolucionCerrada = !!endDate && !diaAbierto(horarios, endDate);

  // Devolver más tarde que el retiro suma una jornada
  const sumaJornadaPorHora =
    !!startDate && !!endDate && timeToMinutes(endTime) > timeToMinutes(startTime);

  // Solo bloquea "Aplicar" si el día de devolución está cerrado (error real).
  // El stock insuficiente es una advertencia — el usuario elige fechas y ve
  // en el carrito qué ítems no están disponibles para ese período.
  const blocked = devolucionCerrada;

  // ── Clamp hora a franja cuando el día cambia ──────────────────────────
  useEffect(() => {
    if (franjaRetiro && startTime < franjaRetiro.desde) setStartTime(franjaRetiro.desde);
    else if (franjaRetiro && startTime > franjaRetiro.hasta) setStartTime(franjaRetiro.hasta);
  }, [franjaRetiro, startTime, setStartTime]);
  useEffect(() => {
    if (franjaDevolucion && endTime < franjaDevolucion.desde) setEndTime(franjaDevolucion.desde);
    else if (franjaDevolucion && endTime > franjaDevolucion.hasta)
      setEndTime(franjaDevolucion.hasta);
  }, [franjaDevolucion, endTime, setEndTime]);

  const setJornadas = (target: number, base?: Date) => {
    const start = base ?? startDate;
    if (!start) return;
    setDates(start, deriveEndDate(start, target, startTime, endTime));
  };

  const handleStartSelect = (d: Date | undefined) => {
    if (!d) {
      setDates(undefined, undefined);
      return;
    }
    setJornadas(startDate && endDate ? jornadas : 1, d);
  };

  const incJornada = () => setJornadas(jornadas + 1);
  const decJornada = () => {
    if (jornadas <= 1) return;
    setJornadas(jornadas - 1);
  };
  const apply = () => onOpenChange(false);
  const clear = () => setDates(undefined, undefined);
  const hasStart = !!startDate;
  const hasRange = hasStart && !!endDate;

  // ── Calendar modifiers ────────────────────────────────────────────────
  // nostock: días sin stock para el carrito actual (fondo rojo + punto)
  // closed:  días cerrados según horarios (fondo rojo, tachado)
  // rango:   período seleccionado (fondo amber soft)
  const nostockDates = useMemo(
    () => [...diasBloqueados].map((s) => new Date(s + "T12:00:00")),
    [diasBloqueados],
  );

  const closedDates = useMemo(() => {
    if (!horarios) return [];
    const out: Date[] = [];
    for (let i = 0; i < 120; i++) {
      const d = addDays(today, i);
      if (!diaAbierto(horarios, d)) out.push(d);
    }
    return out;
  }, [horarios, today]);

  const calModifiers = {
    ...(hasRange ? { rango: { from: startDate!, to: endDate! } } : {}),
    ...(nostockDates.length > 0 ? { nostock: nostockDates } : {}),
    ...(closedDates.length > 0 ? { closed: closedDates } : {}),
  };

  const calModifiersClassNames = {
    rango: "bg-amber-soft/70 text-ink",
    nostock: "rdp-nostock", // → src/styles.css (@layer utilities)
    closed: "rdp-closed", // → src/styles.css (@layer utilities)
  };

  // ── Footer label contextual ───────────────────────────────────────────
  // Orden de prioridad: error > sin fechas > ok
  const footerLabel = !hasStart
    ? "sin fechas"
    : devolucionCerrada
      ? "día cerrado"
      : `${jornadas} ${jornadas === 1 ? "jornada" : "jornadas"}`;

  const footerLabelMuted = !hasStart || blocked;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        hideClose
        className="max-w-3xl p-0 gap-0 overflow-hidden bg-background flex flex-col h-[100dvh] sm:h-auto sm:max-h-[90dvh] sm:rounded-2xl rounded-none border-0 sm:border shadow-2xl"
      >
        <VisuallyHidden>
          <DialogTitle>Tu Rental — Seleccionar fechas</DialogTitle>
          <DialogDescription>
            Elegí la fecha de retiro y la cantidad de jornadas del alquiler.
          </DialogDescription>
        </VisuallyHidden>

        {/* ── Header ──────────────────────────────────────────────── */}
        <div
          className="flex items-center justify-between px-5 sm:px-6 py-4 border-b hairline shrink-0 bg-surface/30"
          style={{ paddingTop: "max(1rem, env(safe-area-inset-top))" }}
        >
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Fechas del alquiler
            </div>
            <h2 className="font-display text-xl sm:text-2xl text-ink leading-tight">
              Elegí tus fechas
            </h2>
          </div>
          <button
            onClick={() => onOpenChange(false)}
            className="grid h-9 w-9 place-items-center rounded-full hover:bg-muted transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* ── Retiro + Jornadas + Devolución ──────────────────────── */}
        <div className="px-5 sm:px-6 pt-5 pb-4 shrink-0 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* ── Retiro ─────────────────────────────────────────── */}
            <div
              className={cn(
                "rounded-xl px-3.5 py-3 border bg-surface/40",
                hasStart
                  ? "border-ink/15" // fecha elegida: borde sutil
                  : "border-dashed hairline", // vacío: borde dashed
              )}
            >
              <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground mb-1.5">
                Retiro
              </div>
              <div className="flex items-center justify-between gap-3">
                {hasStart ? (
                  <>
                    <span className="tabular-nums text-base font-display leading-none text-ink">
                      {format(startDate!, "dd MMM yyyy", { locale: es })}
                    </span>
                    <TimeStepSelect
                      value={startTime}
                      onChange={setStartTime}
                      min={franjaRetiro?.desde}
                      max={franjaRetiro?.hasta}
                      aria-label="Hora de retiro"
                      className="text-sm font-mono tabular-nums text-ink/80 hover:text-ink rounded-md px-2 py-1 bg-background border hairline"
                    />
                  </>
                ) : (
                  /* Estado vacío — placeholder amigable, no "--/--/----" */
                  <span className="text-sm font-sans text-muted-foreground/60 leading-none">
                    elegí en el calendario
                  </span>
                )}
              </div>
            </div>

            {/* ── Jornadas stepper ───────────────────────────────── */}
            <div className="rounded-xl border border-ink/15 bg-amber-soft/40 px-3.5 py-3">
              <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground mb-1.5">
                Jornadas
              </div>
              <div className="flex items-center justify-between gap-2">
                <button
                  onClick={decJornada}
                  disabled={!hasStart || jornadas <= 1}
                  aria-label="Quitar una jornada"
                  className="grid h-8 w-8 place-items-center rounded-full border hairline bg-background text-ink transition hover:border-ink disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <Minus className="h-4 w-4" />
                </button>
                <div className="flex items-baseline gap-1.5 leading-none">
                  <span
                    data-testid="jornadas-count"
                    className="font-display text-2xl font-black text-ink tabular-nums"
                  >
                    {hasStart ? jornadas : "—"}
                  </span>
                  <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
                    {jornadas === 1 ? "jornada" : "jornadas"}
                  </span>
                </div>
                <button
                  onClick={incJornada}
                  disabled={!hasStart}
                  aria-label="Agregar una jornada"
                  className="grid h-8 w-8 place-items-center rounded-full border hairline bg-background text-ink transition hover:border-ink hover:bg-amber disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <Plus className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>

          {/* ── Devolución calculada (solo si hay rango) ───────────── */}
          {hasRange && (
            <div
              className={cn(
                "rounded-xl border px-3.5 py-3 flex items-center justify-between gap-3",
                // Jerarquía de estados visuales (de mayor a menor prioridad):
                // 1. devolucionCerrada → destructive (bloquea)
                // 2. sumaJornadaPorHora → naranja (advierte)
                // 3. normal → amber (ok)
                devolucionCerrada
                  ? "border-destructive/40 bg-destructive/10"
                  : sumaJornadaPorHora
                    ? "border-naranja/45 bg-naranja/12"
                    : "border-amber/40 bg-amber-soft/60",
              )}
            >
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground mb-1">
                  Devolución
                </div>
                <div className="flex items-center gap-1.5 leading-none">
                  <span
                    className={cn(
                      "tabular-nums text-base font-display leading-none",
                      devolucionCerrada ? "text-destructive" : "text-ink",
                    )}
                  >
                    {format(endDate!, "dd MMM yyyy", { locale: es })}
                  </span>
                  {/* Badge "+1 J" — solo cuando suma jornada por hora */}
                  {sumaJornadaPorHora && !devolucionCerrada && (
                    <span className="rounded-full bg-naranja/20 px-1.5 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-wider text-naranja">
                      +1 J
                    </span>
                  )}
                </div>
              </div>
              {/* Hora de devolución — "—" si el día está cerrado */}
              {devolucionCerrada ? (
                <span className="font-mono text-sm text-muted-foreground/50">—</span>
              ) : (
                <TimeStepSelect
                  value={endTime}
                  onChange={setEndTime}
                  min={franjaDevolucion?.desde}
                  max={franjaDevolucion?.hasta}
                  aria-label="Hora de devolución"
                  className="text-sm font-mono tabular-nums text-ink/80 hover:text-ink rounded-md px-2 py-1 bg-background border hairline"
                />
              )}
            </div>
          )}

          {/* ── Feedback (jerarquía: error > warn > hint) ──────────── */}
          {devolucionCerrada ? (
            /* ERROR: día cerrado → bloquea Aplicar */
            <p className="flex items-start gap-1.5 text-[11px] text-destructive">
              <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              La devolución cae el{" "}
              <strong>{format(endDate!, "EEEE dd MMM", { locale: es })}</strong>, que está cerrado.
              Ajustá las jornadas o la fecha de retiro.
            </p>
          ) : rangoCruzaBloqueado ? (
            /* WARN: sin stock en el rango — no bloquea Aplicar, advierte para revisar el carrito */
            <p className="flex items-start gap-1.5 rounded-md bg-amber-soft/70 border border-amber/40 px-2.5 py-1.5 text-[11px] text-ink">
              <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0 text-amber" />
              <span>
                Algunos equipos del carrito no tienen stock en estas fechas —{" "}
                <strong>revisá el carrito</strong> antes de solicitar.
              </span>
            </p>
          ) : sumaJornadaPorHora ? (
            /* WARN: jornada extra por hora → Aplicar habilitado (avisa, no bloquea) */
            <p className="flex items-center gap-1.5 rounded-md bg-amber-soft/70 border border-amber/40 px-2.5 py-1.5 text-[11px] text-ink">
              <Clock className="h-3.5 w-3.5 shrink-0 text-amber" />
              <span>
                Devolvés a las <strong>{endTime}</strong>, más tarde que tu retiro ({startTime}) →{" "}
                <strong>suma 1 jornada</strong>. Devolvé a las {startTime} o antes para mantener{" "}
                {jornadas - 1} {jornadas - 1 === 1 ? "jornada" : "jornadas"}.
              </span>
            </p>
          ) : (
            /* HINT: info contextual — cambia según si hay fecha o no */
            <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <Clock className="h-3 w-3" />
              {hasStart
                ? "Horarios cada 30 min — sujeto a confirmación. Devolver más tarde que la hora de retiro suma una jornada."
                : "Tocá un día en el calendario para fijar el retiro. La devolución se calcula sola."}
            </p>
          )}
        </div>

        {/* ── Sin stock total (kit con componentes insuficientes) ─────── */}
        {sinStockTotal && (
          <div className="mx-5 sm:mx-6 mb-4 flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/8 px-3.5 py-3 text-[11px] text-destructive">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              Hay equipos en tu carrito sin disponibilidad para ninguna fecha del próximo período.
              Revisá las cantidades o sacá el equipo que no podés reservar.
            </span>
          </div>
        )}

        {/* ── Calendario ────────────────────────────────────────────── */}
        <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain flex justify-center px-2 sm:px-4 pb-2 border-t hairline">
          <Calendar
            mode="single"
            selected={startDate}
            onSelect={handleStartSelect}
            numberOfMonths={isMobile ? 1 : 2}
            locale={es}
            disabled={(date: Date) => date < today || !diaAbierto(horarios, date)}
            modifiers={calModifiers}
            modifiersClassNames={calModifiersClassNames}
            showOutsideDays={false}
            className="p-2 sm:p-4 pointer-events-auto"
          />
        </div>

        {/* ── Footer ────────────────────────────────────────────────── */}
        <div
          className="border-t hairline bg-surface/50 px-5 sm:px-6 pt-3 pb-3 shrink-0 flex items-center justify-between gap-3"
          style={{ paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))" }}
        >
          <button
            onClick={clear}
            disabled={!hasStart}
            className="flex items-center gap-1.5 text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground hover:text-ink transition px-2 py-2 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Eraser className="h-3.5 w-3.5" />
            Limpiar
          </button>

          {/* Label contextual — refleja el estado del modal */}
          <div
            className={cn(
              "flex items-center gap-1.5 font-mono text-xs uppercase tracking-[0.18em]",
              footerLabelMuted ? "text-muted-foreground" : "text-ink",
            )}
          >
            <CalendarIcon className="h-3.5 w-3.5" />
            {footerLabel}
          </div>

          <button
            onClick={apply}
            disabled={!hasStart || blocked}
            className="rounded-full bg-amber px-6 py-2.5 sm:py-2 text-sm font-semibold text-ink hover:brightness-110 transition shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ink disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Aplicar
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
