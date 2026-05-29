import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import {
  Calendar as CalendarIcon,
  Check,
  Clock,
  Loader2,
  MessageCircle,
  Minus,
  Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { GoogleIcon } from "@/components/ui/GoogleIcon";
import { Calendar } from "@/components/ui/calendar";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { formatARS } from "@/lib/format";
import { authedFetch } from "@/lib/authedFetch";
import { STUDIO, STUDIO_PHONE } from "@/data/studio";
import { apiGetEstudioDisponibilidad, apiCrearReservaEstudio } from "@/lib/api";

export type StudioBookingConfig = {
  pricePerHour: number;
  minHours: number;
  openHour: number;
  closeHour: number;
  packActivo: boolean;
  packPrecio: number;
};

function pad(n: number) {
  return n.toString().padStart(2, "0");
}

function buildTimeSlots(openHour: number, closeHour: number, minHours: number) {
  const slots: { value: string; label: string; hour: number; minute: 0 | 30 }[] = [];
  const lastStartMin = closeHour * 60 - minHours * 60;
  for (let h = openHour; h < closeHour; h++) {
    for (const m of [0, 30] as const) {
      if (h * 60 + m > lastStartMin) continue;
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

function Section({
  step,
  title,
  children,
  className,
}: {
  step: number;
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("rounded-2xl border hairline bg-surface p-5 sm:p-6", className)}>
      <header className="flex items-baseline gap-2 mb-4">
        <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground tabular">
          {pad(step)}
        </span>
        <h3 className="font-display text-lg sm:text-xl">{title}</h3>
      </header>
      {children}
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

const QUERY_KEYS = { d: "d", h: "h", dur: "dur", pack: "pack" } as const;

function readBookingFromQuery() {
  if (typeof window === "undefined") return null;
  const sp = new URLSearchParams(window.location.search);
  const d = sp.get(QUERY_KEYS.d);
  const h = sp.get(QUERY_KEYS.h);
  const dur = sp.get(QUERY_KEYS.dur);
  const pack = sp.get(QUERY_KEYS.pack);
  if (!d && !h && !dur && !pack) return null;
  let parsedDate: Date | undefined;
  if (d) {
    const [y, mo, da] = d.split("-").map((n) => parseInt(n, 10));
    if (y && mo && da) {
      const dt = new Date(y, mo - 1, da);
      if (!isNaN(dt.getTime())) parsedDate = dt;
    }
  }
  return {
    date: parsedDate,
    start: h && /^\d{2}:\d{2}$/.test(h) ? h : null,
    hours: dur && /^\d+$/.test(dur) ? parseInt(dur, 10) : null,
    withPack: pack === "1",
  };
}

function clearBookingQuery() {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  Object.values(QUERY_KEYS).forEach((k) => url.searchParams.delete(k));
  if (url.toString() !== window.location.href) window.history.replaceState({}, "", url.toString());
}

export function StudioBookingForm({
  config,
  withPack,
  onPackChange,
}: {
  config?: StudioBookingConfig;
  /** Estado controlado por el padre — permite que el aside sea reactivo */
  withPack: boolean;
  onPackChange: (v: boolean) => void;
}) {
  const navigate = useNavigate();
  const pricePerHour = config?.pricePerHour ?? STUDIO.pricePerHour;
  const minHours = config?.minHours ?? STUDIO.minHours;
  const openHour = config?.openHour ?? STUDIO.openHour;
  const closeHour = config?.closeHour ?? STUDIO.closeHour;
  const packActivo = config?.packActivo ?? false;
  const packPrecio = config?.packPrecio ?? 0;

  const initial = useMemo(() => readBookingFromQuery(), []);
  const [date, setDate] = useState<Date | undefined>(initial?.date);
  const [startSlot, setStartSlot] = useState<string>(initial?.start ?? `${pad(openHour)}:00`);
  const [hours, setHours] = useState<number>(initial?.hours ?? minHours);
  const [returnedFromLogin, setReturnedFromLogin] = useState<boolean>(!!initial);

  useEffect(() => {
    if (initial) {
      clearBookingQuery();
      if (initial.withPack) onPackChange(true);
      const t = setTimeout(() => setReturnedFromLogin(false), 12_000);
      return () => clearTimeout(t);
    }
  }, [initial, onPackChange]);

  const [auth, setAuth] = useState<"checking" | "in" | "out">("checking");
  useEffect(() => {
    let cancelado = false;
    authedFetch("/api/cliente/me")
      .then((r) => {
        if (!cancelado) setAuth(r.ok ? "in" : "out");
      })
      .catch(() => {
        if (!cancelado) setAuth("out");
      });
    return () => {
      cancelado = true;
    };
  }, []);

  const [disponibilidad, setDisponibilidad] = useState<Disponibilidad>("idle");
  const [motivo, setMotivo] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [loginModalOpen, setLoginModalOpen] = useState(false);

  const slots = useMemo(
    () => buildTimeSlots(openHour, closeHour, minHours),
    [openHour, closeHour, minHours],
  );
  const today = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  const slot = useMemo(
    () =>
      slots.find((s) => s.value === startSlot) ??
      slots[0] ?? {
        value: `${pad(openHour)}:00`,
        label: `${pad(openHour)}:00`,
        hour: openHour,
        minute: 0 as const,
      },
    [slots, startSlot, openHour],
  );

  const maxHours = useMemo(() => {
    const startDecimal = slot.hour + slot.minute / 60;
    return Math.max(minHours, Math.min(12, Math.floor(closeHour - startDecimal)));
  }, [slot, closeHour, minHours]);

  useEffect(() => {
    if (hours > maxHours) setHours(maxHours);
  }, [hours, maxHours]);
  useEffect(() => {
    if (slots.length > 0 && !slots.some((s) => s.value === startSlot)) setStartSlot(slots[0].value);
  }, [slots, startSlot]);

  const subtotal = pricePerHour * hours;
  const packTotal = withPack ? packPrecio : 0;
  const total = subtotal + packTotal;

  const fechaISO = date ? format(date, "yyyy-MM-dd") : null;
  const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
  const dateLabel = date ? cap(format(date, "EEE d 'de' MMM", { locale: es })) : "Elegir fecha";
  const dateLabelFull = date
    ? cap(format(date, "EEEE d 'de' MMMM, yyyy", { locale: es }))
    : "Elegir fecha";

  const endTime = useMemo(() => {
    const totalMin = slot.hour * 60 + slot.minute + hours * 60;
    return `${pad(Math.floor(totalMin / 60) % 24)}:${pad(totalMin % 60)}`;
  }, [slot, hours]);

  useEffect(() => {
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
      })
      .catch(() => {
        if (!cancelado) setDisponibilidad("error");
      });
    return () => {
      cancelado = true;
    };
  }, [fechaISO, startSlot, hours]);

  const canSubmit = !!fechaISO && disponibilidad === "libre" && !submitting;

  const handleReservarClick = () => {
    if (!canSubmit) return;
    if (auth !== "in") {
      setLoginModalOpen(true);
      return;
    }
    void handleReservar();
  };

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
      toast.success(`Reserva #${res.numero_pedido ?? res.id} enviada`, {
        description: "Te llevamos a tu portal para seguir el estado.",
        duration: 6000,
      });
      setReturnedFromLogin(false);
      navigate({ to: "/cliente/portal", search: { nuevo: res.id } });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "No se pudo crear la reserva";
      if (/401|sesión/i.test(msg)) {
        setAuth("out");
        setLoginModalOpen(true);
      }
      if (/disponible|409/.test(msg)) setDisponibilidad("ocupado");
      setErrorMsg(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleContinuarConGoogle = () => {
    if (!fechaISO) return;
    const inner = new URLSearchParams({
      [QUERY_KEYS.d]: fechaISO,
      [QUERY_KEYS.h]: startSlot,
      [QUERY_KEYS.dur]: String(hours),
      [QUERY_KEYS.pack]: withPack ? "1" : "0",
    });
    window.location.href = `/cliente/auth/google?${new URLSearchParams({ next: `/estudio?${inner.toString()}` }).toString()}`;
  };

  const handleWhatsapp = () => {
    if (!date) return;
    const lines = [
      `Hola! Quiero consultar por el estudio.`,
      `📅 ${format(date, "EEEE d 'de' MMMM, yyyy", { locale: es })}`,
      `🕒 ${startSlot} – ${endTime} (${hours} h)`,
      withPack ? `➕ Con equipos (luces, griperías y modificadores)` : null,
      total > 0 ? `💵 Total estimado: ${formatARS(total)}` : null,
    ].filter(Boolean);
    window.open(
      `https://wa.me/${STUDIO_PHONE}?text=${encodeURIComponent(lines.join("\n"))}`,
      "_blank",
    );
  };

  const ctaLabel = auth === "out" ? "Iniciar sesión y reservar" : "Reservar";

  return (
    <div className="space-y-4">
      {returnedFromLogin && auth === "in" && (
        <div className="rounded-xl border border-verde/30 bg-verde/10 px-4 py-3 text-sm text-verde">
          <span className="font-medium">Sesión iniciada.</span> Revisá los datos y apretá Reservar
          para confirmar.
        </div>
      )}

      {/* ── 1. ¿Cuándo? ─────────────────────────────────────────────── */}
      <Section step={1} title="¿Cuándo?">
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
            <FieldLabel>Duración · mín {minHours}h</FieldLabel>
            <div className="mt-1.5 flex h-11 items-center gap-1 rounded-md border hairline bg-background px-1">
              <button
                type="button"
                onClick={() => setHours((h) => Math.max(minHours, h - 1))}
                disabled={hours <= minHours}
                aria-label="Restar hora"
                className="grid h-9 w-9 place-items-center rounded text-muted-foreground hover:bg-ink/5 hover:text-ink disabled:opacity-40"
              >
                <Minus className="h-4 w-4" />
              </button>
              <div className="flex-1 text-center text-base font-semibold tabular">
                {hours} <span className="text-sm font-normal text-muted-foreground">h</span>
              </div>
              <button
                type="button"
                onClick={() => setHours((h) => Math.min(maxHours, h + 1))}
                disabled={hours >= maxHours}
                aria-label="Sumar hora"
                className="grid h-9 w-9 place-items-center rounded text-muted-foreground hover:bg-ink/5 hover:text-ink disabled:opacity-40"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {/* ¿Qué reservás? — sin expansión de equipos inline */}
        {packActivo && (
          <fieldset
            className="mt-5 grid gap-2.5 sm:grid-cols-2"
            role="radiogroup"
            aria-label="¿Qué reservás?"
          >
            <legend className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground mb-2 sm:col-span-2">
              ¿Qué reservás?
            </legend>

            {/* Card A — Solo el estudio */}
            <label
              className={cn(
                "flex cursor-pointer flex-col gap-1 rounded-xl border p-4 transition",
                !withPack ? "border-amber bg-amber/10" : "hairline hover:border-ink/40",
              )}
            >
              <input
                type="radio"
                name="studio-modalidad"
                checked={!withPack}
                onChange={() => onPackChange(false)}
                className="sr-only"
              />
              <span className="font-semibold">Solo el estudio</span>
              <p className="text-xs text-muted-foreground">
                Reservás el estudio por las horas elegidas. Traés tu equipamiento.
              </p>
            </label>

            {/* Card B — Estudio + equipos (sin StudioPackKit inline) */}
            <label
              className={cn(
                "flex cursor-pointer flex-col gap-1 rounded-xl border p-4 transition",
                withPack ? "border-amber bg-amber/10" : "hairline hover:border-ink/40",
              )}
            >
              <input
                type="radio"
                name="studio-modalidad"
                checked={withPack}
                onChange={() => onPackChange(true)}
                className="sr-only"
              />
              <span className="font-semibold">Estudio + equipos</span>
              <p className="text-xs text-muted-foreground">
                Sumás <span className="text-ink font-medium">luces, griperías y modificadores</span>{" "}
                durante toda la reserva. Llegás con la cámara y filmás.
              </p>
            </label>
          </fieldset>
        )}
      </Section>

      {/* ── 2. Confirmar y reservar ──────────────────────────────────── */}
      <Section step={2} title="Confirmar y reservar">
        {/* Confirm card: líneas → banda verde → total */}
        <div className="rounded-[14px] border border-hairline overflow-hidden mb-4">
          {/* Líneas de desglose */}
          <div className="p-4 flex flex-col gap-1.5">
            <div className="flex justify-between items-baseline text-sm text-muted-foreground">
              <span>
                Estudio · {hours} h{pricePerHour > 0 && ` × ${formatARS(pricePerHour)}`}
              </span>
              <span className="font-mono tabular text-ink">
                {subtotal > 0 ? formatARS(subtotal) : "—"}
              </span>
            </div>
            {withPack && (
              <div className="flex justify-between items-baseline text-sm text-muted-foreground">
                <span>Pack de equipos</span>
                <span className="font-mono tabular text-ink">
                  {packPrecio > 0 ? formatARS(packPrecio) : "—"}
                </span>
              </div>
            )}
          </div>

          {/* Banda verde — solo cuando hay fecha y está libre */}
          {fechaISO && disponibilidad === "libre" && (
            <div className="flex items-center gap-2.5 px-4 py-2.5 bg-verde/5 border-y border-verde/10">
              <span className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium bg-verde/10 text-verde border-verde/20">
                <Check className="h-3 w-3" /> Disponible
              </span>
              <span className="text-xs text-muted-foreground tabular">
                {dateLabel} · {startSlot} a {endTime}
              </span>
            </div>
          )}

          {/* Ocupado */}
          {fechaISO && disponibilidad === "ocupado" && (
            <div className="flex items-center gap-2 px-4 py-2.5 bg-destructive/5 border-y border-destructive/10">
              <span className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium bg-destructive/10 text-destructive border-destructive/20">
                {motivo ?? "Ocupado en esa franja"}
              </span>
            </div>
          )}

          {/* Verificando */}
          {disponibilidad === "checking" && (
            <div className="flex items-center gap-2 px-4 py-2.5 bg-ink/3 border-y border-hairline">
              <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                <Clock className="h-3 w-3 animate-pulse" /> Verificando disponibilidad…
              </span>
            </div>
          )}

          {/* Total */}
          <div className="px-4 py-3.5">
            <div className="flex justify-between items-baseline text-[15px] font-bold text-ink">
              <span>Total</span>
              <span className="font-mono tabular">{total > 0 ? formatARS(total) : "—"}</span>
            </div>
          </div>
        </div>

        {errorMsg && (
          <p className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {errorMsg}
          </p>
        )}

        <Button
          onClick={handleReservarClick}
          disabled={!canSubmit}
          className="w-full bg-ink text-amber hover:bg-[color-mix(in_oklch,var(--ink)_82%,var(--amber))]"
          size="lg"
        >
          {submitting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Reservando…
            </>
          ) : (
            ctaLabel
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

        {!date && (
          <p className="mt-3 text-center text-xs text-muted-foreground">
            Elegí una fecha para continuar.
          </p>
        )}
        {date && disponibilidad === "error" && (
          <p className="mt-3 text-center text-xs text-destructive">
            No pudimos verificar disponibilidad — reintentá.
          </p>
        )}

        <p className="mt-3 text-center text-xs text-muted-foreground flex items-center justify-center gap-1.5">
          <Check className="h-3 w-3" /> Cancelación gratis hasta 48hs antes
        </p>
      </Section>

      {/* Modal de login — sin cambios visuales */}
      <Dialog open={loginModalOpen} onOpenChange={setLoginModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Iniciá sesión para reservar</DialogTitle>
            <DialogDescription>
              Usamos los datos de tu cuenta — no te pedimos formularios.
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-xl border hairline bg-surface px-4 py-3 text-sm">
            <div className="font-medium text-ink">{dateLabelFull}</div>
            <div className="mt-1 text-muted-foreground">
              <span className="font-medium text-ink tabular">
                {startSlot} a {endTime}
              </span>{" "}
              · {hours} h
            </div>
            {withPack && (
              <div className="mt-1 text-muted-foreground">
                + <span className="text-ink">Con equipos</span> (luces, griperías y modificadores)
              </div>
            )}
            <div className="mt-2 flex items-baseline justify-between border-t hairline pt-2">
              <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                Total estimado
              </span>
              <span className="font-semibold tabular">
                {total > 0 ? formatARS(total) : "A consultar"}
              </span>
            </div>
          </div>
          <Button
            onClick={handleContinuarConGoogle}
            className="w-full bg-amber text-ink hover:bg-amber/90"
            size="lg"
          >
            <GoogleIcon size={16} /> <span className="ml-2">Continuar con Google</span>
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            Te llevamos a Google y volvés acá automáticamente para confirmar.
          </p>
        </DialogContent>
      </Dialog>
    </div>
  );
}
