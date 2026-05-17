import { AnimatePresence, motion } from "framer-motion";
import { X, Trash2, Plus, Minus, Loader2, AlertCircle, Calendar as CalendarIcon, ShoppingBag } from "lucide-react";
import { EmptyState } from "./EmptyState";
import { useEffect, useId, useRef, useState } from "react";
import { toast } from "sonner";
import { useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useCart } from "@/lib/cart-store";
import { type Equipment } from "@/data/equipment";
import { formatARS } from "@/lib/format";
import { EmptyImage } from "./EmptyImage";
import { createOrder } from "@/lib/orders";
import { authedFetch } from "@/lib/authedFetch";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { RentalDateModal } from "./RentalDateModal";
import { apiGetDescuentosJornada, interpolarDescuento } from "@/lib/api";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function CartDrawer({
  allEquipos,
  getDisponible,
}: {
  allEquipos: Equipment[];
  getDisponible?: (item: Equipment) => number | undefined;
}) {
  const {
    drawerOpen,
    drawerPlacement,
    setDrawerOpen,
    items,
    add,
    remove,
    setQty,
    clear,
    days,
    startDate,
    endDate,
    startTime,
    endTime,
  } = useCart();

  const isBottom = drawerPlacement === "bottom";

  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [needsLogin, setNeedsLogin] = useState(false);
  const [notas, setNotas] = useState("");
  const [showNotas, setShowNotas] = useState(false);
  const [dateModalOpen, setDateModalOpen] = useState(false);

  // Refs para focus trap + restauración de foco
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  const titleId = useId();

  // Resolver equipos desde el store usando la data real de la API
  const list = Object.entries(items)
    .map(([id, qty]) => {
      const it = allEquipos.find((e) => e.id === id);
      return it ? { it, qty } : null;
    })
    .filter(Boolean) as { it: Equipment; qty: number }[];

  const d = days();
  const subtotal = list.reduce((s, { it, qty }) => s + it.pricePerDay * qty, 0);
  const subtotalTotal = subtotal * d;

  const { data: descuentosPuntos = [] } = useQuery({
    queryKey: ["descuentos-jornada"],
    queryFn: apiGetDescuentosJornada,
    staleTime: 10 * 60 * 1000,
  });
  const descuentoPct = d > 0 ? interpolarDescuento(descuentosPuntos, d) : 0;
  const descuentoMonto = Math.round(subtotalTotal * descuentoPct / 100);
  const total = subtotalTotal - descuentoMonto;

  // Lock scroll del body + guardar foco al abrir, restaurar al cerrar
  useEffect(() => {
    if (!drawerOpen) return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    // Foco inicial al botón cerrar
    requestAnimationFrame(() => closeBtnRef.current?.focus());

    return () => {
      document.body.style.overflow = prevOverflow;
      previouslyFocused.current?.focus?.();
    };
  }, [drawerOpen]);

  // Esc + focus trap (Tab cycling)
  useEffect(() => {
    if (!drawerOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        setDrawerOpen(false);
        return;
      }
      if (e.key !== "Tab") return;
      const root = dialogRef.current;
      if (!root) return;
      const nodes = Array.from(
        root.querySelectorAll<HTMLElement>(FOCUSABLE),
      ).filter((n) => n.offsetParent !== null || n === document.activeElement);
      if (nodes.length === 0) {
        e.preventDefault();
        return;
      }
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey && (active === first || !root.contains(active))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [drawerOpen, setDrawerOpen]);

  async function handleSubmit() {
    if (list.length === 0) return;

    // #28 — Validación de fechas explícita con toast
    if (!startDate || !endDate) {
      toast.error("Seleccioná fechas de retiro y devolución antes de confirmar", {
        duration: 4000,
      });
      return;
    }

    // Fechas guardadas de sesiones anteriores pueden quedar en el pasado
    const hoy = new Date();
    hoy.setHours(0, 0, 0, 0);
    if (startDate < hoy) {
      toast.error("La fecha de retiro ya pasó — elegí nuevas fechas", {
        duration: 5000,
        action: { label: "Cambiar fechas", onClick: () => setDateModalOpen(true) },
      });
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    setNeedsLogin(false);

    // #27 — Pre-check de login antes de submitear. Si no hay sesión, mostramos
    // panel con login/registro en vez del 401 críptico.
    try {
      const me = await authedFetch("/api/cliente/me");
      if (!me.ok) {
        setNeedsLogin(true);
        setSubmitting(false);
        return;
      }
    } catch {
      setNeedsLogin(true);
      setSubmitting(false);
      return;
    }

    try {
      await createOrder({
        status: "solicitado",
        startDate,
        endDate,
        startTime,
        endTime,
        days: d,
        notes: notas.trim() || undefined,
        resolvedItems: list.map(({ it, qty }) => ({
          id: it.id,
          name: it.name,
          brand: it.brand,
          category: it.category,
          qty,
          pricePerDay: it.pricePerDay,
          backendId: it._backendId,
        })),
      });
      setSubmitted(true);
      clear();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al enviar el pedido";
      setSubmitError(msg);
      toast.error(msg, { duration: 6000 });
    } finally {
      setSubmitting(false);
    }
  }

  function goToLogin() {
    setDrawerOpen(false);
    navigate({ to: "/cliente/login" });
  }

  function goToRegister() {
    setDrawerOpen(false);
    navigate({ to: "/cliente/registro" });
  }

  function reset() {
    setSubmitted(false);
    setSubmitError(null);
    setShowNotas(false);
    setNotas("");
    setDrawerOpen(false);
  }

  return (
    <AnimatePresence>
      {drawerOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setDrawerOpen(false)}
            aria-hidden="true"
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
          />
          <motion.aside
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            initial={isBottom ? { y: "100%" } : { x: "100%" }}
            animate={isBottom ? { y: 0 } : { x: 0 }}
            exit={isBottom ? { y: "100%" } : { x: "100%" }}
            transition={{ type: "tween", duration: 0.3, ease: [0.32, 0.72, 0, 1] }}
            className={
              isBottom
                ? // Mobile: pantalla completa (con safe-area), sin rounded ni drag
                  "fixed inset-0 z-50 flex h-[100dvh] w-full flex-col bg-background shadow-2xl"
                : // Desktop: panel lateral
                  "fixed right-0 top-0 z-50 flex h-[100dvh] w-full max-w-md flex-col border-l hairline bg-background"
            }
            style={{
              paddingTop: isBottom ? "env(safe-area-inset-top)" : undefined,
            }}
          >
            {/* Header sticky */}
            <div className="flex items-center justify-between gap-3 border-b hairline px-5 py-4 sm:px-6">
              <div className="min-w-0">
                <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                  Tu pedido
                </div>
                <h2 id={titleId} className="font-display text-2xl leading-tight">
                  Cotización
                </h2>
              </div>
              <button
                ref={closeBtnRef}
                onClick={() => setDrawerOpen(false)}
                aria-label="Cerrar carrito"
                className="grid h-10 w-10 shrink-0 place-items-center rounded-full hover:bg-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-amber"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Fechas — píldora clickeable que abre el RentalDateModal */}
            <div className="border-b hairline px-5 py-4 sm:px-6">
              <button
                type="button"
                onClick={() => setDateModalOpen(true)}
                aria-label={startDate ? "Editar fechas y horarios" : "Elegir fechas"}
                className="w-full flex items-center justify-center gap-3 rounded-full border-2 border-amber/50 bg-amber/10 px-5 py-2.5 transition hover:border-amber hover:bg-amber/20 shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-amber"
              >
                <CalendarIcon className="h-4 w-4 shrink-0 text-amber" />
                {startDate && endDate ? (
                  <span className="flex flex-wrap items-center justify-center gap-x-2 gap-y-0.5 text-sm font-semibold tabular-nums">
                    <span>{format(startDate, "EEE dd MMM", { locale: es })} {startTime}</span>
                    <span className="text-muted-foreground">→</span>
                    <span>{format(endDate, "EEE dd MMM", { locale: es })} {endTime}</span>
                    <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      · {d} {d === 1 ? "jornada" : "jornadas"}
                    </span>
                  </span>
                ) : (
                  <span className="text-sm font-semibold">Elegir fechas</span>
                )}
              </button>
            </div>

            {/* Contenido */}
            {submitted ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
                <div className="text-4xl" aria-hidden="true">✓</div>
                <div className="font-display text-2xl">¡Pedido enviado!</div>
                <p className="text-sm text-muted-foreground">
                  Recibimos tu solicitud. Te contactaremos a la brevedad para confirmar disponibilidad y coordinar el retiro.
                </p>
                <button
                  onClick={reset}
                  className="mt-4 rounded-md border hairline px-6 py-2 text-sm hover:bg-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-amber"
                >
                  Cerrar
                </button>
              </div>
            ) : (
              <>
                {/* Lista de items — área scrolleable */}
                <div className="flex-1 overflow-y-auto overscroll-contain px-5 py-4 sm:px-6">
                  {list.length === 0 ? (
                    <EmptyState
                      icon={<ShoppingBag className="h-6 w-6" />}
                      title="Tu rental está vacío"
                      sub="Elegí equipos del catálogo y se sumarán acá."
                    >
                      <button
                        onClick={() => setDrawerOpen(false, "bottom")}
                        className="rounded-full bg-ink px-5 py-2 text-sm font-semibold text-amber transition hover:opacity-90"
                      >
                        Explorar catálogo
                      </button>
                    </EmptyState>
                  ) : (
                    <>
                      <ul className="space-y-2.5">
                        {list.map(({ it, qty }) => {
                          const cap = getDisponible?.(it) ?? it.cantidad ?? Infinity;
                          const reachedMax = qty >= cap;
                          const lineaBruta = it.pricePerDay * qty * (d || 1);
                          const lineaDto   = descuentoPct > 0 ? Math.round(lineaBruta * descuentoPct / 100) : 0;
                          const lineaNeta  = lineaBruta - lineaDto;
                          return (
                            <li
                              key={it.id}
                              className="flex gap-3 rounded-lg border hairline bg-surface p-3"
                            >
                              <div className="h-16 w-20 shrink-0 overflow-hidden rounded">
                                {it.fotoUrl ? (
                                  <img
                                    src={it.fotoUrl}
                                    alt=""
                                    className="h-full w-full object-cover"
                                  />
                                ) : (
                                  <EmptyImage category={it.category} brand={it.brand} />
                                )}
                              </div>
                              <div className="min-w-0 flex-1">
                                <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                                  {it.brand}
                                </div>
                                <div className="line-clamp-2 font-display text-sm leading-tight">
                                  {it.name}
                                </div>
                                <div className="mt-2 flex items-center justify-between gap-2">
                                  <div
                                    role="group"
                                    aria-label={`Cantidad de ${it.name}`}
                                    className="flex items-center gap-0.5 rounded-full border hairline"
                                  >
                                    <button
                                      onClick={() => remove(it.id)}
                                      aria-label="Quitar uno"
                                      className="grid h-10 w-10 place-items-center rounded-full hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-amber"
                                    >
                                      <Minus className="h-3.5 w-3.5" />
                                    </button>
                                    <span
                                      className="w-6 text-center text-sm tabular"
                                      aria-live="polite"
                                    >
                                      {qty}
                                    </span>
                                    <button
                                      onClick={() => {
                                        if (!reachedMax) add(it.id);
                                      }}
                                      disabled={reachedMax}
                                      aria-label="Sumar uno"
                                      className="grid h-10 w-10 place-items-center rounded-full hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-amber"
                                    >
                                      <Plus className="h-3.5 w-3.5" />
                                    </button>
                                  </div>
                                  <div className="text-right">
                                    <div className="text-xs tabular text-ink">
                                      {formatARS(it.pricePerDay * qty)}
                                      <span className="text-muted-foreground"> /día</span>
                                    </div>
                                    {d > 0 && (
                                      <div className="hidden sm:flex items-center justify-end gap-1 mt-0.5 text-[11px] tabular">
                                        {lineaDto > 0 && (
                                          <span className="line-through text-muted-foreground/60">{formatARS(lineaBruta)}</span>
                                        )}
                                        <span className={lineaDto > 0 ? "text-emerald-600 font-medium" : "text-muted-foreground"}>
                                          {formatARS(lineaNeta)}
                                        </span>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>
                              <button
                                onClick={() => setQty(it.id, 0)}
                                aria-label={`Quitar ${it.name} del carrito`}
                                className="grid h-8 w-8 shrink-0 place-items-center self-start rounded-full text-muted-foreground hover:bg-surface hover:text-destructive focus:outline-none focus-visible:ring-2 focus-visible:ring-destructive"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </li>
                          );
                        })}
                      </ul>

                      {/* Notas opcionales */}
                      {showNotas && (
                        <div className="mt-4 space-y-2 rounded-lg border hairline bg-surface p-4">
                          <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground mb-1">
                            Notas para nosotros (opcional)
                          </div>
                          <textarea
                            value={notas}
                            onChange={(e) => setNotas(e.target.value)}
                            rows={3}
                            maxLength={500}
                            placeholder="Ej: necesito dolly extra, retiro fuera de horario, etc."
                            className="w-full resize-none rounded-md border hairline bg-background px-3 py-2 text-sm focus:border-amber/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber"
                          />
                        </div>
                      )}
                      {submitError && (
                        <div role="alert" className="mt-3 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2.5 text-sm text-destructive">
                          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                          <span>{submitError}</span>
                        </div>
                      )}
                    </>
                  )}
                </div>

                {/* Footer sticky con totales */}
                <div
                  className="border-t hairline bg-background px-5 py-4 space-y-3 sm:px-6"
                  style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}
                >
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Subtotal · {d} {d === 1 ? "jornada" : "jornadas"}</span>
                    <span className="tabular">{formatARS(subtotalTotal)}</span>
                  </div>
                  {descuentoPct > 0 && (
                    <div className="flex items-center justify-between text-sm text-emerald-600">
                      <span>Descuento {descuentoPct}% ({d} {d === 1 ? "jornada" : "jornadas"})</span>
                      <span className="tabular">−{formatARS(descuentoMonto)}</span>
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                      Total
                    </span>
                    <span className="font-display text-3xl tabular text-ink">
                      {formatARS(total)}
                    </span>
                  </div>

                  {!showNotas && list.length > 0 && (
                    <button
                      onClick={() => setShowNotas(true)}
                      className="w-full text-xs text-muted-foreground hover:text-ink focus:outline-none focus-visible:underline"
                    >
                      Agregar una nota
                    </button>
                  )}
                  <button
                    type="button"
                    disabled={submitting || list.length === 0}
                    onClick={handleSubmit}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-amber py-3 text-sm font-medium uppercase tracking-widest text-ink transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
                  >
                    {submitting ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" /> Enviando…
                      </>
                    ) : (
                      "Confirmar solicitud"
                    )}
                  </button>

                  {(!startDate || !endDate) ? (
                    <p className="flex items-center justify-center gap-1.5 text-center text-xs text-amber-700">
                      <AlertCircle className="h-3.5 w-3.5" />
                      Elegí fechas para confirmar
                    </p>
                  ) : null}

                  {/* #27 — Panel "necesitás cuenta" cuando el pre-check falla */}
                  {needsLogin && (
                    <div className="rounded-md border border-amber/40 bg-amber-soft p-3 space-y-2">
                      <p className="text-sm text-ink font-medium">
                        Necesitás una cuenta para confirmar
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Iniciá sesión o creá una cuenta para mandarnos tu solicitud.
                      </p>
                      <div className="flex gap-2 pt-1">
                        <button
                          type="button"
                          onClick={goToLogin}
                          className="flex-1 rounded-md bg-ink px-3 py-2 text-xs font-medium uppercase tracking-wider text-amber transition hover:brightness-110"
                        >
                          Iniciar sesión
                        </button>
                        <button
                          type="button"
                          onClick={goToRegister}
                          className="flex-1 rounded-md border hairline px-3 py-2 text-xs font-medium uppercase tracking-wider text-ink transition hover:bg-background"
                        >
                          Crear cuenta
                        </button>
                      </div>
                    </div>
                  )}

                  {list.length > 0 && (
                    <button
                      onClick={clear}
                      className="w-full text-xs text-muted-foreground hover:text-destructive focus:outline-none focus-visible:underline"
                    >
                      Vaciar pedido
                    </button>
                  )}
                </div>
              </>
            )}
          </motion.aside>

          {/* Modal de fechas — montado fuera del drawer para que se vea encima */}
          <RentalDateModal open={dateModalOpen} onOpenChange={setDateModalOpen} />
        </>
      )}
    </AnimatePresence>
  );
}
