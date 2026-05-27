import { useEffect, useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import {
  Calendar as CalendarIcon,
  Check,
  Clock,
  Loader2,
  LogIn,
  MessageCircle,
  Minus,
  Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Checkbox } from "@/components/ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { formatARS } from "@/lib/format";
import { authedFetch } from "@/lib/authedFetch";
import { StudioPackKit } from "@/components/studio/StudioPackKit";
import { STUDIO, STUDIO_PHONE } from "@/data/studio";
import {
  apiGetEstudioDisponibilidad,
  apiCrearReservaEstudio,
  type EstudioPackEquipo,
} from "@/lib/api";

export type StudioBookingConfig = {
  pricePerHour: number;
  minHours: number;
  openHour: number;
  closeHour: number;
  packActivo: boolean;
  packNombre: string;
  packDescripcion: string;
  packPrecio: number;
};

function pad(n: number) {
  return n.toString().padStart(2, "0");
}

function buildTimeSlots(openHour: number, closeHour: number) {
  const slots: { value: string; label: string; hour: number; minute: 0 | 30 }[] = [];
  for (let h = openHour; h < closeHour; h++) {
    for (const m of [0, 30] as const) {
      slots.push({
        value: `${pad(h)}:${pad(m)}`,
        label: `${pad(h)}:${pad(m)}`,
        hour: h,
        minute: m,
      });
    }
  }
  return slots;
}

type Disponibilidad = "idle" | "checking" | "libre" | "ocupado" | "error";

/** Pill de estado de disponibilidad. Es la respuesta visual más importante
 * después de elegir fecha+hora — tiene que saltar. */
function DispoChip({ status, motivo }: { status: Disponibilidad; motivo: string | null }) {
  if (status === "idle") return null;
  const map: Record<Exclude<Disponibilidad, "idle">, { text: string; className: string }> = {
    checking: {
      text: "Verificando…",
      className: "bg-ink/5 text-muted-foreground border-ink/10",
    },
    libre: {
      text: "Disponible",
      className: "bg-emerald-500/10 text-emerald-700 border-emerald-500/20",
    },
    ocupado: {
      text: motivo ?? "Ocupado en esa franja",
      className: "bg-red-500/10 text-red-700 border-red-500/20",
    },
    error: {
      text: "No pudimos verificar — reintentá",
      className: "bg-amber/15 text-ink border-amber/30",
    },
  };
  const cfg = map[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
        cfg.className,
      )}
      aria-live="polite"
    >
      {status === "checking" && <Loader2 className="h-3 w-3 animate-spin" />}
      {status === "libre" && <Check className="h-3 w-3" />}
      {cfg.text}
    </span>
  );
}

function Section({
  step,
  title,
  children,
  className,
  action,
}: {
  step: number;
  title: string;
  children: React.ReactNode;
  className?: string;
  action?: React.ReactNode;
}) {
  return (
    <section className={cn("rounded-2xl border hairline bg-surface p-5 sm:p-6", className)}>
      <header className="flex items-baseline justify-between gap-3">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground tabular">
            {pad(step)}
          </span>
          <h3 className="font-display text-lg sm:text-xl">{title}</h3>
        </div>
        {action}
      </header>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <label className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
      {children}
    </label>
  );
}

export function StudioBookingForm({ config }: { config?: StudioBookingConfig }) {
  const pricePerHour = config?.pricePerHour ?? STUDIO.pricePerHour;
  const minHours = config?.minHours ?? STUDIO.minHours;
  const openHour = config?.openHour ?? STUDIO.openHour;
  const closeHour = config?.closeHour ?? STUDIO.closeHour;
  const packActivo = config?.packActivo ?? false;
  const packNombre = config?.packNombre ?? STUDIO.addon.name;
  const packDescripcion = config?.packDescripcion ?? STUDIO.addon.description;
  const packPrecio = config?.packPrecio ?? 0;

  const [date, setDate] = useState<Date | undefined>(undefined);
  const [startSlot, setStartSlot] = useState<string>(`${pad(openHour)}:00`);
  const [hours, setHours] = useState<number>(minHours);

  // Login obligatorio: los datos del cliente salen de la sesión (no se piden acá).
  // Pre-chequeo con authedFetch (mismo patrón que CartDrawer / v2-B).
  const [auth, setAuth] = useState<"checking" | "in" | "out">("checking");
  const [clienteNombre, setClienteNombre] = useState<string>("");

  useEffect(() => {
    let cancelado = false;
    authedFetch("/api/cliente/me")
      .then(async (r) => {
        if (cancelado) return;
        if (r.ok) {
          const me = await r.json().catch(() => ({}));
          setClienteNombre(me?.nombre ?? "");
          setAuth("in");
        } else {
          setAuth("out");
        }
      })
      .catch(() => {
        if (!cancelado) setAuth("out");
      });
    return () => {
      cancelado = true;
    };
  }, []);

  const [withPack, setWithPack] = useState(false);
  const [packEquipos, setPackEquipos] = useState<EstudioPackEquipo[]>([]);

  const [disponibilidad, setDisponibilidad] = useState<Disponibilidad>("idle");
  const [motivo, setMotivo] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [confirmada, setConfirmada] = useState<{ numero: number | null } | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [calendarOpen, setCalendarOpen] = useState(false);

  const slots = useMemo(() => buildTimeSlots(openHour, closeHour), [openHour, closeHour]);
  const today = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  const slot = slots.find((s) => s.value === startSlot) ?? slots[0];

  // Máxima duración válida: hasta close (en horas), capeado en 12.
  // Cuando cambia el slot de inicio, recortamos si quedaría fuera de horario.
  const maxHours = useMemo(() => {
    const startDecimal = slot.hour + slot.minute / 60;
    const remaining = closeHour - startDecimal;
    return Math.max(minHours, Math.min(12, Math.floor(remaining)));
  }, [slot, closeHour, minHours]);

  useEffect(() => {
    if (hours > maxHours) setHours(maxHours);
  }, [hours, maxHours]);

  const subtotal = pricePerHour * hours;
  const packTotal = withPack ? packPrecio : 0;
  const total = subtotal + packTotal;

  const fechaISO = date ? format(date, "yyyy-MM-dd") : null;
  // date-fns con locale 'es' devuelve todo en minúsculas ("sáb 30 de may"); sólo
  // capitalizamos la primera letra y dejamos el resto como está (no usar la
  // clase tailwind `capitalize`, que title-casea cada palabra).
  const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
  const dateLabel = date ? cap(format(date, "EEE d 'de' MMM", { locale: es })) : "Elegir fecha";
  const dateLabelFull = date
    ? cap(format(date, "EEEE d 'de' MMMM, yyyy", { locale: es }))
    : "Elegir fecha";

  // Hora de fin computada en vivo — es el modelo mental real del usuario.
  const endTime = useMemo(() => {
    const totalMin = slot.hour * 60 + slot.minute + hours * 60;
    const h = Math.floor(totalMin / 60) % 24;
    const m = totalMin % 60;
    return `${pad(h)}:${pad(m)}`;
  }, [slot, hours]);

  // Chequeo de disponibilidad en vivo cuando hay fecha + hora + duración.
  useEffect(() => {
    setConfirmada(null);
    setErrorMsg(null);
    if (!fechaISO) {
      setDisponibilidad("idle");
      return;
    }
    let cancelado = false;
    setDisponibilidad("checking");
    setMotivo(null);
    apiGetEstudioDisponibilidad(fechaISO, startSlot, hours)
      .then((res) => {
        if (cancelado) return;
        setDisponibilidad(res.libre ? "libre" : "ocupado");
        setMotivo(res.motivo ?? null);
        setPackEquipos(res.pack ?? []);
      })
      .catch(() => {
        if (!cancelado) setDisponibilidad("error");
      });
    return () => {
      cancelado = true;
    };
  }, [fechaISO, startSlot, hours]);

  const canReserve = !!fechaISO && disponibilidad === "libre" && auth === "in" && !submitting;

  const handleReservar = async () => {
    if (!fechaISO) return;
    setSubmitting(true);
    setErrorMsg(null);
    try {
      const res = await apiCrearReservaEstudio({
        fecha: fechaISO,
        start: startSlot,
        horas: hours,
        con_pack: withPack,
      });
      setConfirmada({ numero: res.numero_pedido ?? null });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "No se pudo crear la reserva";
      // Sesión vencida entre el pre-chequeo y el submit → pedir login de nuevo.
      if (/401|sesión/i.test(msg)) setAuth("out");
      // Si chocó con otra reserva, refrescamos el estado a ocupado.
      if (/disponible|409/.test(msg)) setDisponibilidad("ocupado");
      setErrorMsg(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleWhatsapp = () => {
    if (!date) return;
    const start = `${pad(slot.hour)}:${pad(slot.minute)}`;
    const lines = [
      `Hola! Quiero consultar por el estudio.`,
      `📅 ${format(date, "EEEE d 'de' MMMM, yyyy", { locale: es })}`,
      `🕒 ${start} – ${endTime} (${hours} h)`,
      withPack ? `➕ ${packNombre}` : null,
      total > 0 ? `💵 Total estimado: ${formatARS(total)}` : null,
    ].filter(Boolean);
    const text = encodeURIComponent(lines.join("\n"));
    window.open(`https://wa.me/${STUDIO_PHONE}?text=${text}`, "_blank");
  };

  if (confirmada) {
    return (
      <div className="rounded-2xl border hairline bg-surface p-6 sm:p-8 text-center">
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-emerald-500/10 text-emerald-700">
          <Check className="h-6 w-6" />
        </div>
        <h3 className="mt-4 font-display text-2xl">¡Solicitud enviada!</h3>
        <p className="mt-2 text-sm text-muted-foreground max-w-sm mx-auto">
          Recibimos tu reserva del estudio
          {confirmada.numero ? (
            <>
              {" "}
              <span className="font-mono text-ink">#{confirmada.numero}</span>
            </>
          ) : null}{" "}
          para el <span className="font-medium text-ink">{dateLabelFull}</span> de {startSlot} a{" "}
          {endTime} ({hours} h). Te vamos a contactar para confirmarla.
        </p>
        <Button
          variant="outline"
          className="mt-6"
          onClick={() => {
            setConfirmada(null);
            setDate(undefined);
            setHours(minHours);
            setStartSlot(`${pad(openHour)}:00`);
            setWithPack(false);
          }}
        >
          Reservar otra fecha
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* ── 1. Cuándo ─────────────────────────────────────────────────── */}
      <Section
        step={1}
        title="¿Cuándo?"
        action={<DispoChip status={disponibilidad} motivo={motivo} />}
      >
        <div className="grid gap-3 sm:grid-cols-[1.4fr_1fr_1fr]">
          {/* Fecha */}
          <div>
            <FieldLabel>Fecha</FieldLabel>
            <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  className={cn(
                    "mt-1.5 h-11 w-full justify-start text-left font-normal",
                    !date && "text-muted-foreground",
                  )}
                >
                  <CalendarIcon className="mr-2 h-4 w-4 shrink-0" />
                  <span className="truncate">{dateLabel}</span>
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="single"
                  selected={date}
                  onSelect={(d) => {
                    setDate(d);
                    if (d) setCalendarOpen(false);
                  }}
                  disabled={{ before: today }}
                  initialFocus
                  locale={es}
                  className="p-3 pointer-events-auto"
                />
              </PopoverContent>
            </Popover>
          </div>

          {/* Hora inicio */}
          <div>
            <FieldLabel>Hora</FieldLabel>
            <select
              value={startSlot}
              onChange={(e) => setStartSlot(e.target.value)}
              className="mt-1.5 h-11 w-full rounded-md border hairline bg-background px-3 text-base sm:text-sm focus:border-amber/60 focus:outline-none"
            >
              {slots.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>

          {/* Duración */}
          <div>
            <FieldLabel>Duración</FieldLabel>
            <div className="mt-1.5 flex h-11 items-center gap-1 rounded-md border hairline bg-background px-1">
              <button
                type="button"
                onClick={() => setHours((h) => Math.max(minHours, h - 1))}
                className="grid h-9 w-9 place-items-center rounded text-muted-foreground hover:bg-ink/5 hover:text-ink disabled:opacity-40"
                disabled={hours <= minHours}
                aria-label="Restar hora"
              >
                <Minus className="h-4 w-4" />
              </button>
              <div className="flex-1 text-center text-base font-semibold tabular">
                {hours} <span className="text-sm font-normal text-muted-foreground">h</span>
              </div>
              <button
                type="button"
                onClick={() => setHours((h) => Math.min(maxHours, h + 1))}
                className="grid h-9 w-9 place-items-center rounded text-muted-foreground hover:bg-ink/5 hover:text-ink disabled:opacity-40"
                disabled={hours >= maxHours}
                aria-label="Sumar hora"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Readout: hora de fin + hint según estado. Es el modelo mental real
            del usuario ("estoy de tal hora a tal hora"). */}
        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
          {date ? (
            <span className="inline-flex items-center gap-1.5 text-ink">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">{dateLabelFull}</span>
              <span className="text-muted-foreground">·</span>
              <span className="font-medium tabular">
                {startSlot} a {endTime}
              </span>
              <span className="text-muted-foreground">({hours} h)</span>
            </span>
          ) : (
            <span className="text-muted-foreground">
              Elegí una fecha para verificar disponibilidad. Mínimo {minHours} h · abierto de{" "}
              {pad(openHour)}:00 a {pad(closeHour)}:00.
            </span>
          )}
        </div>
      </Section>

      {/* ── 2. Tu cuenta ──────────────────────────────────────────────── */}
      {/* Login obligatorio (v2-B): si está logueado, mostramos la cuenta y
          listo; si no, redirigimos a /cliente/login. No pedimos datos acá. */}
      <Section step={2} title="Tu cuenta">
        {auth === "checking" && (
          <div className="flex items-center gap-2 rounded-md border hairline bg-background px-3 py-2.5 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Verificando tu sesión…
          </div>
        )}
        {auth === "out" && (
          <div>
            <p className="text-sm text-ink">
              Iniciá sesión para reservar — usamos los datos de tu cuenta.
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Si todavía no tenés cuenta, creá una en 1 minuto.
            </p>
            <div className="mt-3 flex flex-col gap-2 sm:flex-row">
              <Button asChild className="bg-amber text-ink hover:bg-amber/90">
                <Link to="/cliente/login">
                  <LogIn className="mr-2 h-4 w-4" /> Iniciar sesión
                </Link>
              </Button>
              <Button asChild variant="outline">
                <Link to="/cliente/registro">Crear cuenta</Link>
              </Button>
            </div>
          </div>
        )}
        {auth === "in" && (
          <div className="flex items-center justify-between gap-3 rounded-md border hairline bg-background px-3 py-2.5 text-sm">
            <span className="text-muted-foreground">Reservás como</span>
            <span className="font-semibold text-ink truncate">{clienteNombre || "tu cuenta"}</span>
          </div>
        )}
      </Section>

      {/* ── 3. Confirmar (pack + total + CTAs) ────────────────────────── */}
      <Section step={3} title="Confirmar y reservar">
        {/* Pack toggle inline — el detalle de qué incluye vive en el aside
            de la página (no duplicar acá). */}
        {packActivo && (
          <label
            className={cn(
              "mb-4 flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition",
              withPack ? "border-amber bg-amber/10" : "hairline hover:border-ink/40",
            )}
          >
            <Checkbox
              checked={withPack}
              onCheckedChange={(v) => setWithPack(v === true)}
              className="mt-0.5"
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline justify-between gap-3">
                <div className="font-semibold">{packNombre}</div>
                <div className="font-mono text-sm tabular shrink-0">
                  {packPrecio > 0 ? `+${formatARS(packPrecio)}` : "Consultar"}
                </div>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{packDescripcion}</p>
              {withPack && <StudioPackKit equipos={packEquipos} />}
            </div>
          </label>
        )}

        {/* Total breakdown */}
        <div className="rounded-xl bg-foreground p-4 text-background">
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-sm text-background/75">
              <span>
                Estudio · {hours} h{pricePerHour > 0 && ` × ${formatARS(pricePerHour)}`}
              </span>
              <span className="tabular">{subtotal > 0 ? formatARS(subtotal) : "—"}</span>
            </div>
            {withPack && (
              <div className="flex items-center justify-between text-sm text-background/75">
                <span>{packNombre}</span>
                <span className="tabular">{packPrecio > 0 ? formatARS(packPrecio) : "—"}</span>
              </div>
            )}
          </div>
          <div className="mt-3 flex items-end justify-between border-t border-background/15 pt-3">
            <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-background/60">
              Total estimado
            </span>
            <span className="text-2xl font-semibold tabular">
              {total > 0 ? formatARS(total) : "A consultar"}
            </span>
          </div>
        </div>

        {errorMsg && (
          <p className="mt-3 rounded-md border border-red-400/40 bg-red-500/10 px-3 py-2 text-xs text-red-700">
            {errorMsg}
          </p>
        )}

        <Button
          onClick={handleReservar}
          disabled={!canReserve}
          className="mt-4 w-full bg-amber text-ink hover:bg-amber/90"
          size="lg"
        >
          {submitting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Reservando…
            </>
          ) : (
            "Reservar"
          )}
        </Button>

        <button
          type="button"
          onClick={handleWhatsapp}
          disabled={!date}
          className={cn(
            "mt-2 inline-flex w-full items-center justify-center gap-2 rounded-md py-2 text-sm transition",
            date
              ? "text-muted-foreground hover:text-ink"
              : "text-muted-foreground/50 cursor-not-allowed",
          )}
        >
          <MessageCircle className="h-4 w-4" />
          ¿Preferís coordinarlo por WhatsApp?
        </button>

        {/* Helper específico según estado */}
        {!date && (
          <p className="mt-3 text-center text-xs text-muted-foreground">
            Elegí una fecha para continuar.
          </p>
        )}
        {date && disponibilidad === "libre" && auth === "out" && (
          <p className="mt-3 text-center text-xs text-muted-foreground">
            Sólo falta iniciar sesión para reservar.
          </p>
        )}
        {date && disponibilidad === "ocupado" && (
          <p className="mt-3 text-center text-xs text-red-700">
            Probá otro horario o fecha — esa franja está ocupada.
          </p>
        )}
      </Section>
    </div>
  );
}
