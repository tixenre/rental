import { AnimatePresence, motion } from "framer-motion";
import { X, Trash2, Plus, Minus, Loader2 } from "lucide-react";
import { useState } from "react";
import { useCart } from "@/lib/cart-store";
import { type Equipment } from "@/data/equipment";
import { formatARS } from "@/lib/format";
import { EmptyImage } from "./EmptyImage";
import { apiPostPedido } from "@/lib/api";
import { format } from "date-fns";
import { es } from "date-fns/locale";

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

  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Form de contacto (mínimo para crear el pedido)
  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [telefono, setTelefono] = useState("");
  const [showForm, setShowForm] = useState(false);

  // Resolver equipos desde el store usando la data real de la API
  const list = Object.entries(items)
    .map(([id, qty]) => {
      const it = allEquipos.find((e) => e.id === id);
      return it ? { it, qty } : null;
    })
    .filter(Boolean) as { it: Equipment; qty: number }[];

  const d = days();
  const subtotal = list.reduce((s, { it, qty }) => s + it.pricePerDay * qty, 0);
  const total = subtotal * d;

  const formatFecha = (date: Date, time: string) =>
    `${format(date, "yyyy-MM-dd")}T${time}:00`;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!startDate || !endDate) return;
    if (list.length === 0) return;

    setSubmitting(true);
    setSubmitError(null);
    try {
      await apiPostPedido({
        cliente_nombre: nombre,
        cliente_email: email,
        cliente_telefono: telefono || undefined,
        fecha_desde: formatFecha(startDate, startTime),
        fecha_hasta: formatFecha(endDate, endTime),
        items: list.map(({ it, qty }) => ({
          equipo_id: it._backendId!,
          cantidad: qty,
          precio_jornada: it.pricePerDay,
        })),
      });
      setSubmitted(true);
      clear();
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : "Error al enviar el pedido");
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setSubmitted(false);
    setSubmitError(null);
    setShowForm(false);
    setNombre("");
    setEmail("");
    setTelefono("");
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
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
          />
          <motion.aside
            initial={isBottom ? { y: "100%" } : { x: "100%" }}
            animate={isBottom ? { y: 0 } : { x: 0 }}
            exit={isBottom ? { y: "100%" } : { x: "100%" }}
            transition={{ type: "tween", duration: 0.3, ease: [0.32, 0.72, 0, 1] }}
            drag={isBottom ? "y" : false}
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.4 }}
            onDragEnd={(_, info) => {
              if (isBottom && (info.offset.y > 120 || info.velocity.y > 600)) {
                setDrawerOpen(false);
              }
            }}
            className={
              isBottom
                ? "fixed inset-x-0 bottom-0 z-50 flex max-h-[85vh] w-full flex-col rounded-t-2xl border-t hairline bg-background shadow-2xl touch-pan-y"
                : "fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l hairline bg-background"
            }
          >
            {isBottom && (
              <div className="mx-auto mt-2 h-1 w-10 shrink-0 cursor-grab rounded-full bg-foreground/20 active:cursor-grabbing" />
            )}

            {/* Header */}
            <div className="flex items-center justify-between border-b hairline px-6 py-4">
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                  Tu pedido
                </div>
                <h2 className="font-display text-2xl">Cotización</h2>
              </div>
              <button
                onClick={() => setDrawerOpen(false)}
                className="grid h-8 w-8 place-items-center rounded-md hover:bg-surface"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Fechas */}
            <div className="border-b hairline px-6 py-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    Desde
                  </div>
                  <div className="tabular">
                    {startDate ? format(startDate, "dd MMM yyyy", { locale: es }) : "—"}
                    <span className="text-muted-foreground"> · {startTime}</span>
                  </div>
                </div>
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    Hasta
                  </div>
                  <div className="tabular">
                    {endDate ? format(endDate, "dd MMM yyyy", { locale: es }) : "—"}
                    <span className="text-muted-foreground"> · {endTime}</span>
                  </div>
                </div>
              </div>
              <div className="mt-3 font-mono text-[11px] uppercase tracking-widest text-ink">
                {d} {d === 1 ? "jornada" : "jornadas"}
              </div>
            </div>

            {/* Contenido */}
            {submitted ? (
              /* Confirmación */
              <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
                <div className="text-4xl">✓</div>
                <div className="font-display text-2xl">¡Pedido enviado!</div>
                <p className="text-sm text-muted-foreground">
                  Recibimos tu solicitud. Te contactaremos a la brevedad para confirmar disponibilidad y coordinar el retiro.
                </p>
                <button
                  onClick={reset}
                  className="mt-4 rounded-md border hairline px-6 py-2 text-sm hover:bg-surface"
                >
                  Cerrar
                </button>
              </div>
            ) : (
              <>
                {/* Lista de items */}
                <div className="flex-1 overflow-y-auto px-6 py-4">
                  {list.length === 0 ? (
                    <div className="flex h-full flex-col items-center justify-center text-center">
                      <div className="font-display text-xl text-muted-foreground">
                        Tu pedido está vacío
                      </div>
                      <p className="mt-2 max-w-xs text-sm text-muted-foreground">
                        Elegí equipos del catálogo y se sumarán acá.
                      </p>
                    </div>
                  ) : (
                    <>
                      <ul className="space-y-3">
                        {list.map(({ it, qty }) => (
                          <li
                            key={it.id}
                            className="flex gap-3 rounded-lg border hairline bg-surface p-3"
                          >
                            <div className="h-16 w-20 shrink-0 overflow-hidden rounded">
                              {it.fotoUrl ? (
                                <img
                                  src={it.fotoUrl}
                                  alt={it.name}
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
                              <div className="truncate font-display text-sm leading-tight">
                                {it.name}
                              </div>
                              <div className="mt-1 flex items-center justify-between">
                                <div className="flex items-center gap-1 rounded border hairline">
                                  <button
                                    onClick={() => remove(it.id)}
                                    className="grid h-6 w-6 place-items-center hover:text-ink"
                                  >
                                    <Minus className="h-3 w-3" />
                                  </button>
                                  <span className="w-5 text-center text-xs tabular">
                                    {qty}
                                  </span>
                                  <button
                                    onClick={() => {
                                      const disponible = getDisponible?.(it);
                                      if (disponible === undefined || qty < disponible) {
                                        add(it.id);
                                      }
                                    }}
                                    disabled={
                                      getDisponible !== undefined &&
                                      getDisponible(it) !== undefined &&
                                      qty >= getDisponible(it)!
                                    }
                                    className="grid h-6 w-6 place-items-center hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed"
                                  >
                                    <Plus className="h-3 w-3" />
                                  </button>
                                </div>
                                <div className="text-xs tabular text-ink">
                                  {formatARS(it.pricePerDay * qty)}
                                  <span className="text-muted-foreground"> /día</span>
                                </div>
                              </div>
                            </div>
                            <button
                              onClick={() => setQty(it.id, 0)}
                              className="text-muted-foreground hover:text-destructive"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </li>
                        ))}
                      </ul>

                      {/* Formulario de contacto */}
                      {showForm && (
                        <form
                          onSubmit={handleSubmit}
                          className="mt-4 space-y-3 rounded-lg border hairline bg-surface p-4"
                        >
                          <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground mb-3">
                            Tus datos de contacto
                          </div>
                          <input
                            required
                            placeholder="Nombre completo"
                            value={nombre}
                            onChange={(e) => setNombre(e.target.value)}
                            className="w-full rounded-md border hairline bg-background px-3 py-2 text-sm focus:border-amber/40 focus:outline-none"
                          />
                          <input
                            required
                            type="email"
                            placeholder="Email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full rounded-md border hairline bg-background px-3 py-2 text-sm focus:border-amber/40 focus:outline-none"
                          />
                          <input
                            placeholder="Teléfono (opcional)"
                            value={telefono}
                            onChange={(e) => setTelefono(e.target.value)}
                            className="w-full rounded-md border hairline bg-background px-3 py-2 text-sm focus:border-amber/40 focus:outline-none"
                          />
                          {submitError && (
                            <p className="text-xs text-destructive">{submitError}</p>
                          )}
                          <button
                            type="submit"
                            disabled={submitting}
                            className="w-full rounded-md bg-amber py-2.5 text-sm font-medium uppercase tracking-widest text-ink transition hover:brightness-110 disabled:opacity-60 inline-flex items-center justify-center gap-2"
                          >
                            {submitting ? (
                              <>
                                <Loader2 className="h-4 w-4 animate-spin" /> Enviando…
                              </>
                            ) : (
                              "Confirmar solicitud"
                            )}
                          </button>
                        </form>
                      )}
                    </>
                  )}
                </div>

                {/* Footer con totales */}
                <div className="border-t hairline px-6 py-5 space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Subtotal por jornada</span>
                    <span className="tabular">{formatARS(subtotal)}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>× {d} {d === 1 ? "jornada" : "jornadas"}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                      Total estimado
                    </span>
                    <span className="font-display text-3xl tabular text-ink">
                      {formatARS(total)}
                    </span>
                  </div>

                  {!showForm ? (
                    <button
                      disabled={list.length === 0 || !startDate || !endDate}
                      onClick={() => setShowForm(true)}
                      className="w-full rounded-md bg-amber py-3 text-sm font-medium uppercase tracking-widest text-ink transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      Solicitar cotización
                    </button>
                  ) : null}

                  {(!startDate || !endDate) ? (
                    <p className="text-center text-xs text-muted-foreground">
                      Elegí fechas para solicitar la cotización
                    </p>
                  ) : null}

                  {list.length > 0 && (
                    <button
                      onClick={clear}
                      className="w-full text-xs text-muted-foreground hover:text-destructive"
                    >
                      Vaciar pedido
                    </button>
                  )}
                </div>
              </>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
