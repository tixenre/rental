import { AnimatePresence, motion } from "framer-motion";
import {
  X,
  ShoppingBag,
  Calendar as CalendarIcon,
  ChevronDown,
  AlertCircle,
  Trash2,
  MessageCircle,
  CheckCircle2,
} from "lucide-react";
import { format } from "date-fns";
import { es } from "date-fns/locale";

import { Button } from "@/design-system/ui/button";
import { type Equipment } from "@/data/equipment";
import { formatARS } from "@/lib/format";
import { descuentoLabel, type DescuentoOrigen } from "@/lib/cotizacion";
import { cn } from "@/lib/utils";
import { StepperPill } from "./equipment/shared/StepperPill";
import { IncludesLine } from "./equipment/shared/IncludesLine";
import { KitSection } from "./KitSection";
import { EmptyState } from "@/design-system/composites/EmptyState";
import { EmptyImage } from "./EmptyImage";
import { GuardarComoListaButton } from "./GuardarComoListaButton";
import { CompartirComposicionButton } from "./CompartirComposicionButton";
import { RentalDateModal } from "./RentalDateModal";
import { CheckoutResumen } from "./CheckoutResumen";

/** Forma mínima de la sesión del cliente que usa el panel (nombre + presencia). */
type ClienteSessionLike = { nombre?: string | null } | null | undefined;

/**
 * CartDrawerView — el SHELL presentacional del drawer del carrito (checkout).
 *
 * Fuente única del diseño del panel: NO conoce useCart, el router, la cotización
 * ni la creación de pedidos. Recibe todo computado por props + callbacks. El
 * container (`CartDrawer`) tiene TODA la lógica (submit, verificación, navegación,
 * focus-trap, cotización) y se lo pasa; la vitrina del DS le pasa estado mock con
 * callbacks no-op → se prueba el panel sin tocar el checkout real.
 *
 * Es un move-verbatim del markup del drawer: misma estructura, mismas clases.
 */
export function CartDrawerView({
  drawerOpen,
  isBottom,
  dialogRef,
  closeBtnRef,
  titleId,
  onClose,
  onExplore,
  step,
  pedidoEnviado,
  sessionId,
  onVolverAlCarrito,
  onCrearPedido,
  // fechas
  startDate,
  endDate,
  startTime,
  endTime,
  d,
  hayFechas,
  onOpenDateModal,
  dateModalOpen,
  onDateModalChange,
  // ítems
  list,
  getDisponible,
  openKits,
  onToggleKit,
  onAdd,
  onRemove,
  onSetQty,
  // plata
  subtotalTotal,
  descuentoPct,
  descuentoOrigen,
  descuentoMonto,
  totalNeto,
  conIva,
  // notas / errores / submit
  notas,
  showNotas,
  onNotasChange,
  onShowNotas,
  onSubmit,
  hayNoDisponible,
  nombresSinDisp,
  dentroDeLeadTime,
  leadTimeHoras,
  urgenciaWhatsappUrl,
  // auth
  needsLogin,
  onLogin,
  onRegister,
  // sesión / acciones
  clienteSession,
  onClear,
}: {
  drawerOpen: boolean;
  isBottom: boolean;
  dialogRef: React.RefObject<HTMLDivElement | null>;
  closeBtnRef: React.RefObject<HTMLButtonElement | null>;
  titleId: string;
  onClose: () => void;
  onExplore: () => void;
  /** "carrito" = lista de ítems (default); "resumen" = paso de revisión/confirmación
   *  (`CheckoutResumen`, backend-driven vía el portero de checkout); "exito" =
   *  pantalla post-creación, unos segundos antes de redirigir al portal. */
  step: "carrito" | "resumen" | "exito";
  /** Presente solo en el paso "exito" — número de pedido para el mensaje. */
  pedidoEnviado: { id: number; numeroPedido: string } | null;
  sessionId: string;
  onVolverAlCarrito: () => void;
  onCrearPedido: (sessionConfirmed: boolean) => Promise<void>;
  startDate?: Date;
  endDate?: Date;
  startTime: string;
  endTime: string;
  d: number;
  hayFechas: boolean;
  onOpenDateModal: () => void;
  dateModalOpen: boolean;
  onDateModalChange: (o: boolean) => void;
  list: { it: Equipment; qty: number }[];
  getDisponible?: (item: Equipment) => number | undefined;
  openKits: Record<string, boolean>;
  onToggleKit: (id: string) => void;
  onAdd: (id: string) => void;
  onRemove: (id: string) => void;
  onSetQty: (id: string, qty: number) => void;
  subtotalTotal: number;
  descuentoPct: number;
  descuentoOrigen: DescuentoOrigen;
  descuentoMonto: number;
  totalNeto: number;
  conIva: boolean;
  notas: string;
  showNotas: boolean;
  onNotasChange: (v: string) => void;
  onShowNotas: () => void;
  onSubmit: () => void;
  hayNoDisponible: boolean;
  nombresSinDisp: string[];
  dentroDeLeadTime: boolean;
  leadTimeHoras: number;
  urgenciaWhatsappUrl: string | null;
  needsLogin: boolean;
  onLogin: () => void;
  onRegister: () => void;
  clienteSession: ClienteSessionLike;
  onClear: () => void;
}) {
  return (
    <AnimatePresence>
      {drawerOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
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
                ? "fixed inset-x-0 bottom-0 z-50 flex h-[80dvh] w-full flex-col rounded-t-2xl bg-background shadow-2xl"
                : "fixed right-0 top-0 z-50 flex h-[100dvh] w-full max-w-md flex-col border-l hairline bg-background"
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
                onClick={onClose}
                aria-label="Cerrar carrito"
                className="grid h-11 w-11 shrink-0 place-items-center rounded-full hover:bg-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-amber"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Fechas — píldora clickeable que abre el RentalDateModal (solo en el
                paso carrito; en el resumen las fechas ya están fijadas para revisar) */}
            {step === "carrito" && (
              <div className="border-b hairline px-5 py-4 sm:px-6">
                <button
                  type="button"
                  onClick={onOpenDateModal}
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
            )}

            {/* Contenido */}
            {step === "exito" && pedidoEnviado ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-10 text-center">
                <div className="grid h-16 w-16 place-items-center rounded-full bg-verde/15">
                  <CheckCircle2 className="h-9 w-9 text-verde-ink" />
                </div>
                <h3 className="font-display text-2xl text-ink">
                  Pedido #{pedidoEnviado.numeroPedido} enviado
                </h3>
                <p className="max-w-xs text-sm text-muted-foreground">
                  Te llevamos a tu portal para seguir el estado y los próximos pasos…
                </p>
              </div>
            ) : step === "resumen" ? (
              <CheckoutResumen
                sessionId={sessionId}
                startDate={startDate}
                endDate={endDate}
                startTime={startTime}
                endTime={endTime}
                d={d}
                itemCount={list.reduce((acc, { qty }) => acc + qty, 0)}
                subtotalTotal={subtotalTotal}
                descuentoPct={descuentoPct}
                descuentoOrigen={descuentoOrigen}
                descuentoMonto={descuentoMonto}
                totalNeto={totalNeto}
                conIva={conIva}
                clienteNombre={clienteSession?.nombre}
                onBack={onVolverAlCarrito}
                onCrearPedido={onCrearPedido}
              />
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
                      <Button
                        variant="primary"
                        shape="pill"
                        onClick={onExplore}
                        className="px-5 font-semibold"
                      >
                        Explorar catálogo
                      </Button>
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
                            const lineaBruta = it.pricePerDay * qty * (d || 1);
                            const lineaDto =
                              descuentoPct > 0 ? Math.round((lineaBruta * descuentoPct) / 100) : 0;
                            const lineaNeta = lineaBruta - lineaDto;
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
                                        onClick={() => onToggleKit(it.id)}
                                        aria-expanded={!!openKits[it.id]}
                                        aria-label={
                                          openKits[it.id]
                                            ? "Ocultar qué incluye"
                                            : "Ver qué incluye"
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
                                        onClick={() => onRemove(it.id)}
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
                                        if (!reachedMax) onAdd(it.id);
                                      }}
                                      onDecrement={() => onRemove(it.id)}
                                      maxReached={reachedMax}
                                      size="lg"
                                    />
                                    <div className="text-right">
                                      <div className="text-xs tabular text-ink">
                                        {formatARS(it.pricePerDay * qty)}
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
                                  onClick={() => onSetQty(it.id, 0)}
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
                            onChange={(e) => onNotasChange(e.target.value)}
                            rows={3}
                            maxLength={500}
                            placeholder="Ej: necesito dolly extra, retiro fuera de horario, etc."
                            className="w-full resize-none rounded-md border hairline bg-background px-3 py-2 text-sm focus:border-amber/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber"
                          />
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
                        {descuentoLabel(descuentoOrigen, d, clienteSession?.nombre)} ·{" "}
                        {descuentoPct}%
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
                      onClick={onShowNotas}
                      className="w-full text-xs text-muted-foreground hover:text-ink focus:outline-none focus-visible:underline"
                    >
                      Agregar una nota
                    </button>
                  )}
                  <Button
                    variant="amber"
                    size="lg"
                    className="w-full uppercase tracking-widest"
                    disabled={list.length === 0 || hayNoDisponible || dentroDeLeadTime}
                    onClick={onSubmit}
                  >
                    <span className="flex items-center gap-2">
                      Confirmar solicitud
                      {list.length > 0 && totalNeto > 0 && (
                        <span className="font-mono text-xs font-normal opacity-70 tracking-normal normal-case tabular-nums">
                          · {formatARS(totalNeto)}
                          {conIva ? " + IVA" : ""}
                        </span>
                      )}
                    </span>
                  </Button>

                  {/* Lead-time (#1126): el retiro cae dentro de la ventana de antelación
                    mínima → no se puede confirmar online; ofrecemos WhatsApp para
                    coordinar la urgencia. El backend es el que enforza (portero +
                    backstop); esto avisa antes de tocar el botón. */}
                  {dentroDeLeadTime && (
                    <div
                      role="alert"
                      className="space-y-2 rounded-lg border border-amber/40 bg-amber-soft p-3 text-center"
                    >
                      <p className="flex items-center justify-center gap-1.5 text-xs font-semibold text-ink">
                        <AlertCircle className="h-3.5 w-3.5 shrink-0 text-amber" />
                        Tu retiro es en menos de {leadTimeHoras} h
                      </p>
                      <p className="text-xs leading-snug text-muted-foreground">
                        Por la antelación no podemos confirmar el pedido online. Si es urgente
                        escribinos: aunque figure stock en la web no lo garantizamos — cada pedido
                        se revisa y se acepta a mano.
                      </p>
                      {urgenciaWhatsappUrl && (
                        <a
                          href={urgenciaWhatsappUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex min-h-11 items-center gap-1.5 rounded-full border border-ink/15 bg-background px-4 py-2.5 text-xs font-semibold text-ink hover:bg-surface"
                        >
                          <MessageCircle className="h-4 w-4" />
                          Escribinos por WhatsApp
                        </a>
                      )}
                    </div>
                  )}

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
                          onClick={onLogin}
                        >
                          Iniciar sesión
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="flex-1 uppercase tracking-wider"
                          onClick={onRegister}
                        >
                          Crear cuenta
                        </Button>
                      </div>
                    </div>
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
                      onClick={onClear}
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
          <RentalDateModal open={dateModalOpen} onOpenChange={onDateModalChange} />
        </>
      )}
    </AnimatePresence>
  );
}
