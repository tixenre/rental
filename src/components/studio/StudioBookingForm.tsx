import { useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { Calendar as CalendarIcon, Minus, Plus, MessageCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { formatARS } from "@/lib/format";
import { STUDIO, STUDIO_PHONE } from "@/data/studio";
import { apiGetEstudioDisponibilidad, apiCrearReservaEstudio } from "@/lib/api";

export type StudioBookingConfig = {
  pricePerHour: number;
  minHours: number;
  openHour: number;
  closeHour: number;
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

export function StudioBookingForm({ config }: { config?: StudioBookingConfig }) {
  const pricePerHour = config?.pricePerHour ?? STUDIO.pricePerHour;
  const minHours = config?.minHours ?? STUDIO.minHours;
  const openHour = config?.openHour ?? STUDIO.openHour;
  const closeHour = config?.closeHour ?? STUDIO.closeHour;

  const [date, setDate] = useState<Date | undefined>(undefined);
  const [startSlot, setStartSlot] = useState<string>(`${pad(openHour)}:00`);
  const [hours, setHours] = useState<number>(minHours);

  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [telefono, setTelefono] = useState("");

  const [disponibilidad, setDisponibilidad] = useState<Disponibilidad>("idle");
  const [submitting, setSubmitting] = useState(false);
  const [confirmada, setConfirmada] = useState<{ numero: number | null } | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const slots = useMemo(() => buildTimeSlots(openHour, closeHour), [openHour, closeHour]);
  const today = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  const subtotal = pricePerHour * hours;
  const total = subtotal;
  const slot = slots.find((s) => s.value === startSlot) ?? slots[0];

  const fechaISO = date ? format(date, "yyyy-MM-dd") : null;

  const dateLabel = date ? format(date, "EEEE d 'de' MMMM, yyyy", { locale: es }) : "Elegir fecha";

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
    apiGetEstudioDisponibilidad(fechaISO, startSlot, hours)
      .then((res) => {
        if (cancelado) return;
        setDisponibilidad(res.libre ? "libre" : "ocupado");
      })
      .catch(() => {
        if (!cancelado) setDisponibilidad("error");
      });
    return () => {
      cancelado = true;
    };
  }, [fechaISO, startSlot, hours]);

  const emailValido = !email || /.+@.+\..+/.test(email);
  const canReserve =
    !!fechaISO &&
    disponibilidad === "libre" &&
    nombre.trim().length > 0 &&
    emailValido &&
    !submitting;

  const handleReservar = async () => {
    if (!fechaISO) return;
    setSubmitting(true);
    setErrorMsg(null);
    try {
      const res = await apiCrearReservaEstudio({
        fecha: fechaISO,
        start: startSlot,
        horas: hours,
        cliente_nombre: nombre.trim(),
        cliente_email: email.trim() || undefined,
        cliente_telefono: telefono.trim() || undefined,
      });
      setConfirmada({ numero: res.numero_pedido ?? null });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "No se pudo crear la reserva";
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
    const endTotalMin = slot.hour * 60 + slot.minute + hours * 60;
    const endH = Math.floor(endTotalMin / 60) % 24;
    const endM = endTotalMin % 60;
    const end = `${pad(endH)}:${pad(endM)}`;

    const lines = [
      `Hola! Quiero consultar por el estudio.`,
      `📅 ${format(date, "EEEE d 'de' MMMM, yyyy", { locale: es })}`,
      `🕒 ${start} – ${end} (${hours} h)`,
      total > 0 ? `💵 Total estimado: ${formatARS(total)}` : null,
    ].filter(Boolean);

    const text = encodeURIComponent(lines.join("\n"));
    window.open(`https://wa.me/${STUDIO_PHONE}?text=${text}`, "_blank");
  };

  if (confirmada) {
    return (
      <div className="rounded-2xl border hairline bg-surface p-6 text-center">
        <h3 className="font-display text-2xl">¡Solicitud enviada!</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          Recibimos tu reserva del estudio
          {confirmada.numero ? ` (#${confirmada.numero})` : ""} para el{" "}
          <span className="font-medium text-ink">{dateLabel}</span> de {startSlot} por {hours} h. Te
          vamos a contactar para confirmarla.
        </p>
        <Button
          variant="outline"
          className="mt-5"
          onClick={() => {
            setConfirmada(null);
            setDate(undefined);
            setNombre("");
            setEmail("");
            setTelefono("");
          }}
        >
          Reservar otra fecha
        </Button>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border hairline bg-surface p-5 sm:p-6">
      <div className="grid gap-5 lg:grid-cols-[1fr_auto_1fr] lg:gap-8">
        {/* Inputs */}
        <div className="space-y-4">
          {/* Fecha */}
          <div>
            <label className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Fecha
            </label>
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  className={cn(
                    "mt-1.5 w-full justify-start text-left font-normal",
                    !date && "text-muted-foreground",
                  )}
                >
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  <span className="capitalize">{dateLabel}</span>
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="single"
                  selected={date}
                  onSelect={setDate}
                  disabled={{ before: today }}
                  initialFocus
                  locale={es}
                  className={cn("p-3 pointer-events-auto")}
                />
              </PopoverContent>
            </Popover>
          </div>

          {/* Hora inicio */}
          <div>
            <label className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Hora de inicio
            </label>
            <select
              value={startSlot}
              onChange={(e) => setStartSlot(e.target.value)}
              className="mt-1.5 h-10 w-full rounded-md border hairline bg-background px-3 text-base sm:text-sm focus:border-amber/60 focus:outline-none"
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
            <label className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Duración (mín. {minHours} h)
            </label>
            <div className="mt-1.5 flex items-center gap-3 rounded-md border hairline bg-background px-2 py-1.5">
              <button
                type="button"
                onClick={() => setHours((h) => Math.max(minHours, h - 1))}
                className="flex h-10 w-10 items-center justify-center rounded-md border hairline text-muted-foreground hover:border-ink hover:text-ink disabled:opacity-40"
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
                onClick={() => setHours((h) => Math.min(12, h + 1))}
                className="flex h-10 w-10 items-center justify-center rounded-md border hairline text-muted-foreground hover:border-ink hover:text-ink"
                aria-label="Sumar hora"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Estado de disponibilidad */}
          {date && (
            <div className="text-xs" aria-live="polite">
              {disponibilidad === "checking" && (
                <span className="flex items-center gap-1.5 text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Verificando disponibilidad…
                </span>
              )}
              {disponibilidad === "libre" && (
                <span className="font-medium text-emerald-600">✓ Disponible en esa franja</span>
              )}
              {disponibilidad === "ocupado" && (
                <span className="font-medium text-red-600">
                  Ocupado en esa franja — probá otro horario o fecha.
                </span>
              )}
              {disponibilidad === "error" && (
                <span className="text-muted-foreground">
                  No pudimos verificar la disponibilidad. Probá de nuevo.
                </span>
              )}
            </div>
          )}
        </div>

        {/* Divider */}
        <div className="hidden lg:block w-px bg-border" />

        {/* Datos del cliente + resumen */}
        <div className="space-y-4">
          <div className="space-y-3">
            <div>
              <label className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                Nombre
              </label>
              <input
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                placeholder="Tu nombre"
                className="mt-1.5 h-10 w-full rounded-md border hairline bg-background px-3 text-base sm:text-sm focus:border-amber/60 focus:outline-none"
              />
            </div>
            <div>
              <label className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="tu@email.com"
                className={cn(
                  "mt-1.5 h-10 w-full rounded-md border bg-background px-3 text-base sm:text-sm focus:outline-none",
                  emailValido ? "hairline focus:border-amber/60" : "border-red-400",
                )}
              />
            </div>
            <div>
              <label className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                Teléfono
              </label>
              <input
                value={telefono}
                onChange={(e) => setTelefono(e.target.value)}
                placeholder="Tu teléfono"
                className="mt-1.5 h-10 w-full rounded-md border hairline bg-background px-3 text-base sm:text-sm focus:border-amber/60 focus:outline-none"
              />
            </div>
          </div>

          <div className="rounded-xl bg-foreground p-4 text-background">
            <div className="flex items-center justify-between text-xs text-background/70">
              <span>Estudio · {hours} h</span>
              <span className="tabular">{subtotal > 0 ? formatARS(subtotal) : "—"}</span>
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

          {errorMsg && <p className="text-center text-xs text-red-600">{errorMsg}</p>}

          <Button
            onClick={handleReservar}
            disabled={!canReserve}
            className="w-full bg-amber text-ink hover:bg-amber/90"
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

          <Button onClick={handleWhatsapp} disabled={!date} variant="outline" className="w-full">
            <MessageCircle className="mr-2 h-4 w-4" />
            Consultar por WhatsApp
          </Button>

          {!date && (
            <p className="text-center text-xs text-muted-foreground">
              Elegí una fecha para continuar.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
