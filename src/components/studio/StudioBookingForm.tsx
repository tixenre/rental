import { useEffect, useMemo, useState } from "react";
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
  packPrecio: number;
};

function pad(n: number) {
  return n.toString().padStart(2, "0");
}

function buildTimeSlots(openHour: number, closeHour: number, minHours: number) {
  const slots: { value: string; label: string; hour: number; minute: 0 | 30 }[] = [];
  // Último inicio que todavía permite el mínimo de horas antes del cierre. Sin
  // este tope se ofrecían horarios (ej. 21:30 con cierre 22 y mín 2h) que el
  // backend rechazaba con 400 → el chip mostraba "error" en vez de algo útil.
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
      className: "bg-verde/10 text-verde border-verde/20",
    },
    ocupado: {
      text: motivo ?? "Ocupado en esa franja",
      className: "bg-destructive/10 text-destructive border-destructive/20",
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

/** Round-trip de login: dejamos en la URL la franja elegida (d/h/dur/pack)
 * antes de mandar al OAuth. Al volver, la restoramos y limpiamos la URL. */
const QUERY_KEYS = { d: "d", h: "h", dur: "dur", pack: "pack" } as const;

function readBookingFromQuery() {
  if (typeof window === "undefined") return null;
  const sp = new URLSearchParams(window.location.search);
  const d = sp.get(QUERY_KEYS.d);
  const h = sp.get(QUERY_KEYS.h);
  const dur = sp.get(QUERY_KEYS.dur);
  const pack = sp.get(QUERY_KEYS.pack);
  if (!d && !h && !dur && !pack) return null;
  // Validación liviana: si fecha está, tiene que parsear a Date razonable.
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
  // Solo reemplazamos si quedó algo distinto — evita un history entry innecesario.
  if (url.toString() !== window.location.href) {
    window.history.replaceState({}, "", url.toString());
  }
}

export function StudioBookingForm({ config }: { config?: StudioBookingConfig }) {
  const navigate = useNavigate();
  const pricePerHour = config?.pricePerHour ?? STUDIO.pricePerHour;
  const minHours = config?.minHours ?? STUDIO.minHours;
  const openHour = config?.openHour ?? STUDIO.openHour;
  const closeHour = config?.closeHour ?? STUDIO.closeHour;
  const packActivo = config?.packActivo ?? false;
  const packPrecio = config?.packPrecio ?? 0;

  // Estado inicial: si volvimos del OAuth con la franja en la URL, la restoramos
  // y limpiamos los query params (evita refrescar = re-disparar el flujo).
  const initial = useMemo(() => readBookingFromQuery(), []);
  const [date, setDate] = useState<Date | undefined>(initial?.date);
  const [startSlot, setStartSlot] = useState<string>(initial?.start ?? `${pad(openHour)}:00`);
  const [hours, setHours] = useState<number>(initial?.hours ?? minHours);
  const [withPack, setWithPack] = useState<boolean>(initial?.withPack ?? false);
  // Banner de "sesión iniciada" si volvimos del OAuth — se muestra una vez,
  // hasta que el usuario apriete Reservar o cierre el flag (auto-clear en 12s).
  const [returnedFromLogin, setReturnedFromLogin] = useState<boolean>(!!initial);

  useEffect(() => {
    if (initial) {
      clearBookingQuery();
      const t = setTimeout(() => setReturnedFromLogin(false), 12_000);
      return () => clearTimeout(t);
    }
  }, [initial]);

  // Pre-chequeo de sesión: silencioso. No bloquea ni renderiza paso. Lo usamos
  // para decidir, al apretar Reservar, si abrimos el modal de login o mandamos.
  const [auth, setAuth] = useState<"checking" | "in" | "out">("checking");

  useEffect(() => {
    let cancelado = false;
    authedFetch("/api/cliente/me")
      .then((r) => {
        if (cancelado) return;
        setAuth(r.ok ? "in" : "out");
      })
      .catch(() => {
        if (!cancelado) setAuth("out");
      });
    return () => {
      cancelado = true;
    };
  }, []);

  const [packEquipos, setPackEquipos] = useState<EstudioPackEquipo[]>([]);

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

  // Fallback sintético si la config no deja ningún inicio válido (ventana <
  // mínimo) — evita un crash en `slot.hour` aunque el estudio no sea reservable.
  // Memoizado para no cambiar de identidad en cada render (rompería los useMemo
  // que dependen de `slot`).
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

  // Si el inicio elegido dejó de ser válido (cambió la config del estudio), lo
  // reseteamos al primero disponible para que el <select> no quede desfasado.
  useEffect(() => {
    if (slots.length > 0 && !slots.some((s) => s.value === startSlot)) {
      setStartSlot(slots[0].value);
    }
  }, [slots, startSlot]);

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

  // El botón Reservar se habilita con fecha + disponibilidad libre. El login
  // ya no es un paso visible — si falta sesión, abrimos el modal al apretar.
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
        description: "Te llevamos a tu portal para seguir el estado y los próximos pasos.",
        duration: 6000,
      });
      setReturnedFromLogin(false);
      navigate({ to: "/cliente/portal", search: { nuevo: res.id } });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "No se pudo crear la reserva";
      // Sesión vencida entre el pre-chequeo y el submit → pedir login de nuevo.
      if (/401|sesión/i.test(msg)) {
        setAuth("out");
        setLoginModalOpen(true);
      }
      // Si chocó con otra reserva, refrescamos el estado a ocupado.
      if (/disponible|409/.test(msg)) setDisponibilidad("ocupado");
      setErrorMsg(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleContinuarConGoogle = () => {
    if (!fechaISO) return;
    // Codificamos la franja para volver acá tras el OAuth. El backend valida
    // que `next` sea un path interno (no open-redirect).
    const inner = new URLSearchParams({
      [QUERY_KEYS.d]: fechaISO,
      [QUERY_KEYS.h]: startSlot,
      [QUERY_KEYS.dur]: String(hours),
      [QUERY_KEYS.pack]: withPack ? "1" : "0",
    });
    const nextPath = `/estudio?${inner.toString()}`;
    const outer = new URLSearchParams({ next: nextPath });
    window.location.href = `/cliente/auth/google?${outer.toString()}`;
  };

  const handleWhatsapp = () => {
    if (!date) return;
    const start = `${pad(slot.hour)}:${pad(slot.minute)}`;
    const lines = [
      `Hola! Quiero consultar por el estudio.`,
      `📅 ${format(date, "EEEE d 'de' MMMM, yyyy", { locale: es })}`,
      `🕒 ${start} – ${endTime} (${hours} h)`,
      withPack ? `➕ Con equipos (luces, griperías y modificadores)` : null,
      total > 0 ? `💵 Total estimado: ${formatARS(total)}` : null,
    ].filter(Boolean);
    const text = encodeURIComponent(lines.join("\n"));
    window.open(`https://wa.me/${STUDIO_PHONE}?text=${text}`, "_blank");
  };

  // Post-submit: la pantalla de confirmación local se quitó — ahora redirigimos
  // al portal del cliente (decisión PR #564) con `?nuevo=<id>` para que destaque
  // el pedido recién creado en el listado de "Mis pedidos".
  const ctaLabel = auth === "out" ? "Iniciar sesión y reservar" : "Reservar";

  return (
    <div className="space-y-4">
      {returnedFromLogin && auth === "in" && (
        <div className="rounded-xl border border-verde/30 bg-verde/10 px-4 py-3 text-sm text-verde">
          <span className="font-medium">Sesión iniciada.</span> Revisá los datos y apretá Reservar
          para confirmar tu sesión en el estudio.
        </div>
      )}

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

        {/* Readout: hora de fin + hint según estado. */}
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

        {/* Selector de modalidad — solo el estudio vs estudio + equipos. Vive
            en el paso 01 porque es una decisión de producto primaria, no un
            add-on de confirmación. Cuando el admin apaga `pack_activo`,
            ocultamos el bloque entero (queda "solo el estudio" implícito). */}
        {packActivo && (
          <fieldset
            className="mt-5 grid gap-2.5 sm:grid-cols-2"
            role="radiogroup"
            aria-label="¿Qué reservás?"
          >
            <legend className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground mb-2 sm:col-span-2">
              ¿Qué reservás?
            </legend>

            {/* Card A — solo estudio */}
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
                onChange={() => setWithPack(false)}
                className="sr-only"
              />
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-semibold">Solo el estudio</span>
                <span className="font-mono text-xs tabular shrink-0 text-muted-foreground">
                  {pricePerHour > 0 ? `${formatARS(pricePerHour)}/h` : "Consultar"}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Reservás el estudio por las horas elegidas. Traés tu equipamiento.
              </p>
            </label>

            {/* Card B — estudio + equipos */}
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
                onChange={() => setWithPack(true)}
                className="sr-only"
              />
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-semibold">Estudio + equipos</span>
                <span className="font-mono text-xs tabular shrink-0">
                  {packPrecio > 0 ? `+${formatARS(packPrecio)} fijo` : "Consultar"}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Sumás <span className="text-ink font-medium">luces, griperías y modificadores</span>{" "}
                durante toda la reserva. Llegás con la cámara y filmás.
              </p>
              {withPack && packEquipos.length > 0 && <StudioPackKit equipos={packEquipos} />}
            </label>
          </fieldset>
        )}
      </Section>

      {/* ── 2. Confirmar (total + CTAs) ────────────────────────────────── */}
      <Section step={2} title="Confirmar y reservar">
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
                <span>Equipos (luces, griperías, modificadores)</span>
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
          <p className="mt-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {errorMsg}
          </p>
        )}

        <Button
          onClick={handleReservarClick}
          disabled={!canSubmit}
          className="mt-4 w-full bg-amber text-ink hover:bg-amber/90"
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

        {/* Helper específico según estado */}
        {!date && (
          <p className="mt-3 text-center text-xs text-muted-foreground">
            Elegí una fecha para continuar.
          </p>
        )}
        {date && disponibilidad === "ocupado" && (
          <p className="mt-3 text-center text-xs text-destructive">
            Probá otro horario o fecha — esa franja está ocupada.
          </p>
        )}
      </Section>

      {/* ── Modal de login (se abre al apretar Reservar sin sesión) ───── */}
      <Dialog open={loginModalOpen} onOpenChange={setLoginModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Iniciá sesión para reservar</DialogTitle>
            <DialogDescription>
              Usamos los datos de tu cuenta — no te pedimos formularios.
            </DialogDescription>
          </DialogHeader>

          {/* Recap de lo que está por reservar — para que confirme antes de irse */}
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
            Te llevamos a Google a iniciar sesión y volvés acá automáticamente para confirmar.
          </p>
        </DialogContent>
      </Dialog>
    </div>
  );
}
