import { AnimatePresence, motion } from "framer-motion";
import {
  X,
  Trash2,
  AlertCircle,
  Calendar as CalendarIcon,
  ShoppingBag,
  ChevronDown,
} from "lucide-react";
import { Button } from "@/design-system/ui/button";
import { StepperPill } from "./equipment/shared/StepperPill";
import { IncludesLine } from "./equipment/shared/IncludesLine";
import { KitSection } from "./KitSection";
import { EmptyState } from "./EmptyState";
import { useEffect, useId, useRef, useState } from "react";
import { toast } from "sonner";
import { useNavigate } from "@tanstack/react-router";
import { useCart } from "@/lib/cart-store";
import { type Equipment } from "@/data/equipment";
import { formatARS } from "@/lib/format";
import { useClienteSession } from "@/lib/iva";
import { EmptyImage } from "./EmptyImage";
import { createOrder, OrderVerificationError } from "@/lib/orders";
import { chequearEstadoCuenta, iniciarVerificacionIdentidad } from "@/lib/verificacion";
import { VerificacionRequeridaPanel } from "@/components/rental/VerificacionRequeridaPanel";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { RentalDateModal } from "./RentalDateModal";
import { GuardarComoListaButton } from "./GuardarComoListaButton";
import { CompartirComposicionButton } from "./CompartirComposicionButton";
import { toLocalISO } from "@/lib/rental-dates";
import { useCotizacion, descuentoLabel, lineaPorEquipo } from "@/lib/cotizacion";
import { cn } from "@/lib/utils";

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
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [needsLogin, setNeedsLogin] = useState(false);
  const [needsVerif, setNeedsVerif] = useState(false);
  const [iniciandoVerif, setIniciandoVerif] = useState(false);
  const [notas, setNotas] = useState("");
  const [showNotas, setShowNotas] = useState(false);
  const [dateModalOpen, setDateModalOpen] = useState(false);
  // Por-ítem: qué kits/combos tienen el desglose "qué incluye" abierto en el
  // carrito. La data (`it.includes`) ya viaja en el equipo — misma fuente que
  // el catálogo y los documentos (la puerta de contenido). No se fetchea nada.
  const [openKits, setOpenKits] = useState<Record<string, boolean>>({});

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
  // Sin fechas: estimado por jornada (el backend devuelve 1 jornada sin
  // descuento ni IVA — es solo referencia; el submit exige fechas válidas).
  const hayFechas = !!(startDate && endDate);

  const hayNoDisponible =
    !!startDate &&
    list.some(({ it, qty }) => {
      const cap = getDisponible?.(it) ?? it.cantidad ?? Infinity;
      return getDisponible?.(it) !== undefined && cap < qty;
    });

  const nombresSinDisp = hayNoDisponible
    ? list
        .filter(({ it, qty }) => {
          const cap = getDisponible?.(it) ?? it.cantidad ?? Infinity;
          return getDisponible?.(it) !== undefined && cap < qty;
        })
        .map(({ it }) => it.name)
    : [];

  const { data: clienteSession } = useClienteSession();

  // Auto-cerrar panel de login si el usuario logueó (sesión cambió). Declarado
  // acá, después de `clienteSession` — antes vivía arriba y rompía el typecheck
  // por usar la var antes de declararla.
  useEffect(() => {
    if (clienteSession && needsLogin) {
      setNeedsLogin(false);
    }
  }, [clienteSession, needsLogin]);

  // Total calculado por el BACKEND (fuente única, /api/cotizar). El front no
  // reimplementa la fórmula: manda ítems + fechas y muestra el desglose. #617.
  const totales = useCotizacion({
    items: list.map(({ it, qty }) => ({ equipoId: it._backendId ?? Number(it.id), cantidad: qty })),
    fechaDesde: hayFechas ? toLocalISO(startDate!, startTime) : null,
    fechaHasta: hayFechas ? toLocalISO(endDate!, endTime) : null,
  }).data;
  const {
    subtotal: subtotalTotal,
    descuentoPct,
    descuentoOrigen,
    descuentoMonto,
    totalNeto,
    conIva,
  } = totales;

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
      const nodes = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (n) => n.offsetParent !== null || n === document.activeElement,
      );
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
    setNeedsVerif(false);

    // #27 — Pre-check de cuenta antes de submitear (fuente única en
    // verificacion.ts). Sin sesión → panel login/registro; logueado pero sin
    // DNI validado → panel de verificación de identidad; en vez del 401/403 críptico.
    const estado = await chequearEstadoCuenta();
    if (estado === "no-logueado") {
      setNeedsLogin(true);
      setSubmitting(false);
      return;
    }
    if (estado === "error") {
      toast.error("No pudimos verificar tu cuenta, reintentá.");
      setSubmitting(false);
      return;
    }
    if (estado === "no-verificado") {
      setNeedsVerif(true);
      setSubmitting(false);
      return;
    }
    // "logueado-verificado" → sigue al createOrder

    try {
      const order = await createOrder({
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
      clear();
      setShowNotas(false);
      setNotas("");
      setDrawerOpen(false);
      toast.success(`Pedido #${order.numero_pedido} enviado`, {
        description: "Te llevamos a tu portal para seguir el estado y los próximos pasos.",
        duration: 6000,
      });
      navigate({ to: "/cliente/portal", search: { nuevo: Number(order.id) } });
    } catch (err: unknown) {
      // Backstop: si el backend rechaza por identidad (403), mostramos el panel
      // de verificación en vez del toast genérico.
      if (err instanceof OrderVerificationError) {
        setNeedsVerif(true);
        setSubmitting(false);
        return;
      }
      const msg = err instanceof Error ? err.message : "Error al enviar el pedido";
      setSubmitError(msg);
      toast.error(msg, { duration: 6000 });
    } finally {
      setSubmitting(false);
    }
  }

  function goToLogin() {
    // Vamos a login pero con parámetro para que al volver se reabra el drawer
    navigate({ to: "/cliente/login", search: { from: "carrito" } });
  }

  function goToRegister() {
    // Vamos a registro pero con parámetro para que al volver se reabra el drawer
    navigate({ to: "/cliente/registro", search: { from: "carrito" } });
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
                ? // Mobile: bottom sheet ~80% con esquinas redondeadas arriba
                  "fixed inset-x-0 bottom-0 z-50 flex h-[80dvh] w-full flex-col rounded-t-2xl bg-background shadow-2xl"
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
                <div className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
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
                className="grid h-11 w-11 shrink-0 place-items-center rounded-full hover:bg-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-amber"
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
                    <span>
                      {format(startDate, "EEE dd MMM", { locale: es })} {startTime}
                    </span>
                    <span className="text-muted-foreground">→</span>
                    <span>
                      {format(endDate, "EEE dd MMM", { locale: es })} {endTime}
                    </span>
                    <span className="font-mono text-2xs uppercase tracking-wider text-muted-foreground">
                      · {d} {d === 1 ? "jornada" : "jornadas"}
                    </span>
                  </span>
                ) : (
                  <span className="text-sm font-semibold">Elegir fechas</span>
                )}
              </button>
            </div>

            {/* Contenido */}
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
                      {[...list]
                        .sort((a, b) => {
                          const aCap = getDisponible?.(a.it) ?? a.it.cantidad ?? Infinity;
                          const bCap = getDisponible?.(b.it) ?? b.it.cantidad ?? Infinity;
                          const aND =
                            !!startDate && getDisponible?.(a.it) !== undefined && aCap < a.qty;
                          const bND =
                            !!startDate && getDisponible?.(b.it) !== undefined && bCap < b.qty;
                          return aND === bND ? 0 : aND ? -1 : 1;
                        })
                        .map(({ it, qty }) => {
                          const cap = getDisponible?.(it) ?? it.cantidad ?? Infinity;
                          const reachedMax = qty >= cap;
                          const noDisponible =
                            !!startDate && getDisponible?.(it) !== undefined && cap < qty;
                          // Detalle por línea desde el BACKEND (FASE 3: el front
                          // muestra, no calcula). `subtotalDia` cae a un placeholder
                          // transitorio (precio del catálogo × cant) solo mientras
                          // llega la primera cotización; se corrige al instante con la
                          // respuesta (y para combos el número bueno es el del backend).
                          const linea = lineaPorEquipo(totales, it._backendId ?? Number(it.id));
                          const subtotalDia = linea?.subtotalPorJornada ?? it.pricePerDay * qty;
                          const lineaBruta = linea?.bruto ?? subtotalDia * (d || 1);
                          const lineaNeta = linea?.neto ?? lineaBruta;
                          const lineaDto = lineaBruta - lineaNeta;
                          return (
                            <li
                              key={it.id}
                              className={`flex gap-3 rounded-lg border p-3 transition-colors ${
                                noDisponible
                                  ? "border-destructive/30 bg-destructive/5"
                                  : "hairline bg-surface"
                              }`}
                            >
                              <div className="h-16 w-20 shrink-0 overflow-hidden rounded">
                                {it.fotoUrl ? (
                                  <img
                                    loading="lazy"
                                    decoding="async"
                                    src={it.fotoUrl}
                                    alt={it.name}
                                    className="h-full w-full object-cover"
                                  />
                                ) : (
                                  <EmptyImage category={it.category} brand={it.brand} />
                                )}
                              </div>
                              <div className="min-w-0 flex-1">
                                <div className="font-mono text-2xs uppercase tracking-widest text-muted-foreground">
                                  {it.brand}
                                </div>
                                <div className="line-clamp-2 font-sans text-sm font-bold leading-tight">
                                  {it.name}
                                </div>
                                {it.includes && it.includes.length > 0 ? (
                                  <div className="mt-0.5">
                                    <button
                                      type="button"
                                      onClick={() =>
                                        setOpenKits((p) => ({ ...p, [it.id]: !p[it.id] }))
                                      }
                                      aria-expanded={!!openKits[it.id]}
                                      aria-label={
                                        openKits[it.id] ? "Ocultar qué incluye" : "Ver qué incluye"
                                      }
                                      className="group flex w-full items-center gap-1 text-left focus:outline-none focus-visible:underline"
                                    >
                                      <ChevronDown
                                        className={cn(
                                          "h-3 w-3 shrink-0 text-muted-foreground transition-transform group-hover:text-ink",
                                          openKits[it.id] && "rotate-180",
                                        )}
                                      />
                                      <IncludesLine
                                        includes={it.includes}
                                        label="Incluye:"
                                        className="text-2xs group-hover:text-ink"
                                      />
                                    </button>
                                    <AnimatePresence initial={false}>
                                      {openKits[it.id] && (
                                        <motion.div
                                          initial={{ height: 0, opacity: 0 }}
                                          animate={{ height: "auto", opacity: 1 }}
                                          exit={{ height: 0, opacity: 0 }}
                                          transition={{ duration: 0.2, ease: "easeOut" }}
                                          className="overflow-hidden"
                                        >
                                          <div className="mt-2">
                                            <KitSection item={it} />
                                          </div>
                                        </motion.div>
                                      )}
                                    </AnimatePresence>
                                  </div>
                                ) : null}
                                {noDisponible && (
                                  <div className="mt-1 flex items-center justify-between gap-2">
                                    <div className="flex items-center gap-1 text-2xs font-semibold text-destructive uppercase tracking-wide">
                                      <AlertCircle className="h-3 w-3 shrink-0" />
                                      Sin stock en estas fechas
                                    </div>
                                    <button
                                      onClick={() => remove(it.id)}
                                      className="flex items-center gap-1 text-2xs font-medium text-destructive/80 underline underline-offset-2 transition hover:text-destructive"
                                    >
                                      Quitar
                                    </button>
                                  </div>
                                )}
                                <div className="mt-2 flex items-center justify-between gap-2">
                                  <StepperPill
                                    qty={qty}
                                    onIncrement={() => {
                                      if (!reachedMax) add(it.id);
                                    }}
                                    onDecrement={() => remove(it.id)}
                                    maxReached={reachedMax}
                                    size="lg"
                                  />
                                  <div className="text-right">
                                    <div className="text-xs tabular text-ink">
                                      {formatARS(subtotalDia)}
                                      <span className="text-muted-foreground"> /día</span>
                                    </div>
                                    {d > 0 && (
                                      <div className="hidden sm:flex items-center justify-end gap-1 mt-0.5 text-xs tabular">
                                        {lineaDto > 0 && (
                                          <span className="line-through text-muted-foreground/60">
                                            {formatARS(lineaBruta)}
                                          </span>
                                        )}
                                        <span
                                          className={
                                            lineaDto > 0
                                              ? "text-verde-ink font-medium"
                                              : "text-muted-foreground"
                                          }
                                        >
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
                        <div className="font-mono text-2xs uppercase tracking-widest text-muted-foreground mb-1">
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
                      <div
                        role="alert"
                        className="mt-3 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2.5 text-sm text-destructive"
                      >
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
                  <span className="text-muted-foreground">
                    {hayFechas
                      ? `Subtotal · ${d} ${d === 1 ? "jornada" : "jornadas"}`
                      : "Subtotal · por jornada"}
                  </span>
                  <span className="tabular">{formatARS(subtotalTotal)}</span>
                </div>
                {descuentoPct > 0 && (
                  <div className="flex items-center justify-between text-sm text-verde-ink">
                    <span>
                      {descuentoLabel(descuentoOrigen, d, clienteSession?.nombre)} · {descuentoPct}%
                    </span>
                    <span className="tabular">−{formatARS(descuentoMonto)}</span>
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
                    {hayFechas ? "Total" : "Estimado · por jornada"}
                  </span>
                  <span className="font-display text-3xl tabular text-ink">
                    {formatARS(totalNeto)}
                    {conIva && (
                      <span className="ml-1 align-baseline font-sans text-base text-muted-foreground">
                        {" "}
                        + IVA
                      </span>
                    )}
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
                <Button
                  variant="amber"
                  size="lg"
                  className="w-full uppercase tracking-widest"
                  disabled={list.length === 0 || hayNoDisponible}
                  loading={submitting}
                  onClick={handleSubmit}
                >
                  {submitting ? (
                    "Enviando…"
                  ) : (
                    <span className="flex items-center gap-2">
                      Confirmar solicitud
                      {list.length > 0 && totalNeto > 0 && (
                        <span className="font-mono text-xs font-normal opacity-70 tracking-normal normal-case tabular-nums">
                          · {formatARS(totalNeto)}
                          {conIva ? " + IVA" : ""}
                        </span>
                      )}
                    </span>
                  )}
                </Button>

                {hayNoDisponible ? (
                  <p className="flex items-center justify-center gap-1.5 text-center text-xs text-destructive">
                    <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                    {nombresSinDisp.length === 1
                      ? `${nombresSinDisp[0]} no tiene stock en estas fechas`
                      : `${nombresSinDisp.join(" y ")} no tienen stock en estas fechas`}
                    {" — "}quitálos del carrito o cambiá las fechas.
                  </p>
                ) : !startDate || !endDate ? (
                  <p className="flex items-center justify-center gap-1.5 text-center text-xs text-amber">
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
                      <Button
                        variant="primary"
                        size="sm"
                        className="flex-1 uppercase tracking-wider"
                        onClick={goToLogin}
                      >
                        Iniciar sesión
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex-1 uppercase tracking-wider"
                        onClick={goToRegister}
                      >
                        Crear cuenta
                      </Button>
                    </div>
                  </div>
                )}

                {/* Verificación de identidad requerida (logueado sin DNI validado) */}
                {needsVerif && (
                  <VerificacionRequeridaPanel
                    iniciando={iniciandoVerif}
                    onVerificar={async () => {
                      setIniciandoVerif(true);
                      try {
                        await iniciarVerificacionIdentidad("/?openCarrito=1");
                      } catch {
                        /* el helper ya hizo toast */
                      } finally {
                        setIniciandoVerif(false);
                      }
                    }}
                  />
                )}

                {/* Guardar como lista — solo logueado (las listas son server-only). */}
                {clienteSession && list.length > 0 && (
                  <GuardarComoListaButton
                    items={list.map(({ it, qty }) => ({
                      equipo_id: it._backendId ?? Number(it.id),
                      cantidad: qty,
                    }))}
                  />
                )}

                {/* Compartir — público: anda logueado o anónimo (la puerta /api/public/compartir
                    no pide sesión), así un gaffer le pasa el carrito a un productor sin cuenta. */}
                {list.length > 0 && (
                  <CompartirComposicionButton
                    label="Compartir pedido"
                    items={list.map(({ it, qty }) => ({
                      equipo_id: it._backendId ?? Number(it.id),
                      cantidad: qty,
                    }))}
                  />
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
          </motion.aside>

          {/* Modal de fechas — montado fuera del drawer para que se vea encima */}
          <RentalDateModal open={dateModalOpen} onOpenChange={setDateModalOpen} />
        </>
      )}
    </AnimatePresence>
  );
}
