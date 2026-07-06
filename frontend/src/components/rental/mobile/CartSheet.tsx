import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/design-system/ui/button";
import { formatARS } from "@/lib/format";
import { type Equipment } from "@/data/equipment";
import { cn } from "@/lib/utils";
import { createOrder } from "@/lib/orders";
import { CheckoutResumen, type FacturacionTarget } from "@/components/rental/CheckoutResumen";
import { whatsappLink, normalizePhone } from "@/lib/whatsapp";
import { BUSINESS_PHONE } from "@/lib/business";
import { useClienteSession } from "@/lib/iva";
import { toLocalISO } from "@/lib/rental-dates";
import { useCotizacion, descuentoLabel, lineaPorEquipo } from "@/lib/cotizacion";
import { EquipoFoto } from "@/components/rental/EquipoFoto";
import { CatIcon, SheetClose } from "./shared";

function fmtDate(d: Date | null): string {
  if (!d) return "—";
  const dias = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
  const meses = [
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
  ];
  return `${dias[d.getDay()]} ${d.getDate()} ${meses[d.getMonth()]}`;
}

/* ── CartItem ────────────────────────────────────────────────────── */
function CartItem({
  eq,
  qty,
  fechaDesde,
  jornadas,
  precioJornada,
  periodTotal,
}: {
  eq: Equipment;
  qty: number;
  fechaDesde: Date | null;
  jornadas: number;
  // Precio efectivo por jornada + total del período, YA resueltos por el backend
  // (FASE 3: el front muestra, no calcula; combo-aware).
  precioJornada: number;
  periodTotal: number;
}) {
  return (
    <div className="flex items-center gap-3 px-5 py-3.5 border-b border-hairline last:border-b-0">
      <div className="w-11 h-11 rounded-lg bg-surface border border-hairline flex items-center justify-center text-muted-foreground shrink-0 overflow-hidden">
        <EquipoFoto
          foto={eq}
          alt={eq.name}
          sizes="44px"
          blur={false}
          loading="lazy"
          className="w-full h-full object-contain p-1"
          fallback={<CatIcon cat={eq.category} size={18} />}
        />
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-mono text-2xs tracking-[0.18em] uppercase text-muted-foreground">
          {eq.brand}
        </div>
        <div className="font-sans text-sm font-bold text-ink leading-tight mt-0.5 truncate">
          {eq.name}
        </div>
        <div className="font-mono text-2xs text-muted-foreground mt-0.5">
          {fechaDesde
            ? `${qty} × ${formatARS(precioJornada)} / jorn.`
            : `${formatARS(precioJornada)} / jornada`}
        </div>
      </div>
      <div className="shrink-0 text-right">
        <div
          className="font-mono text-sm font-bold text-ink"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {formatARS(periodTotal)}
        </div>
        <div className="font-mono text-xs tracking-[0.1em] text-muted-foreground mt-0.5">
          {fechaDesde ? `${jornadas} jorn.` : "/ jorn."}
        </div>
      </div>
    </div>
  );
}

/* ── CartSheet ───────────────────────────────────────────────────── */
interface CartSheetProps {
  onClose: () => void;
  onOpenDateSheet: () => void;
  equipos: Equipment[];
  cartItems: Record<string, number>;
  sessionId: string;
  jornadas: number;
  fechaDesde: Date | null;
  fechaHasta: Date | null;
  horaDesde: string;
  horaHasta: string;
  /** Si el sheet se reabre volviendo de un desvío (Didit) con
   *  `?carritoPaso=resumen`, entra directo al paso de resumen. */
  resumeStep?: "resumen";
}

const WA_PHONE = BUSINESS_PHONE;

export function CartSheet({
  onClose,
  onOpenDateSheet,
  equipos,
  cartItems,
  sessionId,
  jornadas,
  fechaDesde,
  fechaHasta,
  horaDesde,
  horaHasta,
  resumeStep,
}: CartSheetProps) {
  const navigate = useNavigate();
  const [solicitado, setSolicitado] = useState(false);
  const [step, setStep] = useState<"carrito" | "resumen">(
    resumeStep === "resumen" ? "resumen" : "carrito",
  );

  const entries = Object.entries(cartItems)
    .map(([id, qty]) => ({ eq: equipos.find((e) => e.id === id)!, qty }))
    .filter((x) => x.eq);

  // Total calculado por el BACKEND (fuente única, /api/cotizar) — mismo número
  // que el drawer desktop y el minibar. Sin fechas → estimado de una jornada
  // sin IVA ni descuento (lo decide el backend). #617.
  const hayFechas = !!fechaDesde;
  const { data: clienteSession } = useClienteSession();
  const totales = useCotizacion({
    items: entries.map(({ eq, qty }) => ({
      equipoId: eq._backendId ?? Number(eq.id),
      cantidad: qty,
    })),
    fechaDesde: hayFechas && fechaDesde ? toLocalISO(fechaDesde, horaDesde) : null,
    fechaHasta: hayFechas && fechaHasta ? toLocalISO(fechaHasta, horaHasta) : null,
  }).data;
  const { subtotal, descuentoPct, descuentoOrigen, descuentoMonto, totalNeto, conIva } = totales;

  // "Solicitar rental": solo lo que el portero de checkout NO puede chequear
  // (fechas, sesión de cliente) — identidad/T&C/firma los resuelve el paso de
  // resumen (`CheckoutResumen`) preguntándole al backend. Espeja CartDrawer.tsx.
  function handleIrAResumen() {
    if (entries.length === 0) return;
    if (!fechaDesde || !fechaHasta) {
      toast.error("Elegí las fechas del rental antes de solicitar.");
      return;
    }
    if (!clienteSession) {
      toast.error("Debés iniciar sesión para solicitar un rental.", {
        duration: 5000,
        action: {
          label: "Iniciar sesión",
          onClick: () => navigate({ to: "/cliente/login", search: { from: "carrito" } }),
        },
      });
      return;
    }
    setStep("resumen");
  }

  async function handleCrearPedido(sessionConfirmed: boolean, target: FacturacionTarget) {
    await createOrder({
      status: "solicitado",
      startDate: fechaDesde ?? undefined,
      endDate: fechaHasta ?? undefined,
      startTime: horaDesde,
      endTime: horaHasta,
      days: jornadas,
      sessionConfirmed,
      perfilFiscalId: target.perfilFiscalId,
      productoraId: target.productoraId,
      resolvedItems: entries.map(({ eq, qty }) => ({
        id: eq.id,
        name: eq.name,
        brand: eq.brand,
        category: eq.category,
        qty,
        pricePerDay: eq.pricePerDay,
        backendId: eq._backendId,
      })),
    });
    setSolicitado(true);
  }

  const waMessage = [
    "¡Hola! Acabo de solicitar un rental en Rambla:",
    ...entries.map(({ eq, qty }) => `• ${qty}× ${eq.brand} ${eq.name}`),
    fechaDesde ? `Fechas: ${fmtDate(fechaDesde)} → ${fmtDate(fechaHasta)} (${jornadas} jorn.)` : "",
    `Total estimado: ${formatARS(totalNeto)}${conIva ? " + IVA" : ""}`,
  ]
    .filter(Boolean)
    .join("\n");
  const waHref =
    whatsappLink({ phone: WA_PHONE, message: waMessage }) ??
    `https://wa.me/${normalizePhone(WA_PHONE)}`;

  return (
    <>
      <div
        className="fixed inset-0 z-[60] bg-scrim animate-in fade-in duration-200"
        onClick={onClose}
      />
      <div
        className="fixed inset-x-0 bottom-0 z-[61] bg-card flex flex-col animate-in slide-in-from-bottom duration-[260ms]"
        style={{
          height: "72%",
          maxHeight: "72%",
          borderRadius: "24px 24px 0 0",
          boxShadow: "0 -8px 40px rgba(0,0,0,0.18)",
        }}
      >
        <div className="w-9 h-1 rounded-full bg-hairline mx-auto mt-2.5 shrink-0" />
        <div className="flex items-center justify-between px-5 py-3 border-b border-hairline shrink-0">
          <span className="font-sans text-base font-bold text-ink">Tu rental</span>
          <SheetClose onClose={onClose} />
        </div>

        {/* Period summary */}
        {fechaDesde ? (
          <div
            className="flex items-center gap-0 px-5 py-3 shrink-0 border-b border-hairline"
            style={{ background: "var(--amber-soft)" }}
          >
            <div className="flex-1 flex items-center gap-2.5">
              <div>
                <div className="font-mono text-2xs tracking-[0.2em] uppercase text-muted-foreground mb-0.5">
                  Salida
                </div>
                <div className="font-sans text-sm font-bold leading-tight text-ink">
                  {fmtDate(fechaDesde)}
                </div>
                <div className="font-mono text-xs text-muted-foreground mt-0.5">{horaDesde}</div>
              </div>
              <ChevronRight size={14} className="text-muted-foreground/50 shrink-0" />
              <div>
                <div className="font-mono text-2xs tracking-[0.2em] uppercase text-muted-foreground mb-0.5">
                  Devolución
                </div>
                <div className="font-sans text-sm font-bold leading-tight text-ink">
                  {fmtDate(fechaHasta)}
                </div>
                <div className="font-mono text-xs text-muted-foreground mt-0.5">{horaHasta}</div>
              </div>
            </div>
            <div
              className="text-center shrink-0 pl-3 border-l"
              style={{ borderColor: "color-mix(in oklch, var(--amber) 40%, transparent)" }}
            >
              <div className="font-mono text-2xs tracking-[0.2em] uppercase text-muted-foreground mb-0.5">
                Jorn.
              </div>
              <div
                style={{
                  fontFamily: "var(--font-display)",
                  fontSize: 24,
                  fontWeight: 900,
                  color: "var(--ink)",
                  lineHeight: 1,
                }}
              >
                {jornadas}
              </div>
            </div>
          </div>
        ) : (
          <div
            className="flex items-center gap-3 px-5 py-3.5 shrink-0 border-b border-hairline"
            style={{
              background: "var(--amber-soft)",
              borderTopColor: "color-mix(in oklch, var(--amber) 35%, transparent)",
            }}
          >
            <div className="flex-1">
              <div className="font-sans text-sm font-bold text-ink leading-tight">
                Elegí las fechas para ver el precio total
              </div>
              <div className="font-mono text-xs tracking-[0.15em] uppercase text-muted-foreground mt-0.5">
                Precios mostrados por jornada
              </div>
            </div>
            <Button
              variant="primary"
              shape="pill"
              className="h-auto px-3.5 py-1.5 text-xs font-bold font-sans shrink-0 whitespace-nowrap"
              onClick={() => {
                onClose();
                onOpenDateSheet();
              }}
            >
              Asignar fechas
            </Button>
          </div>
        )}

        {/* Scrollable body / paso de resumen */}
        {step === "resumen" && !solicitado ? (
          <div className="flex-1 overflow-y-auto flex flex-col" style={{ scrollbarWidth: "none" }}>
            <CheckoutResumen
              sessionId={sessionId}
              startDate={fechaDesde ?? undefined}
              endDate={fechaHasta ?? undefined}
              startTime={horaDesde}
              endTime={horaHasta}
              d={jornadas}
              items={entries.map(({ eq, qty }) => ({
                id: eq.id,
                nombre: eq.name,
                marca: eq.brand,
                cantidad: qty,
              }))}
              subtotalTotal={subtotal}
              descuentoPct={descuentoPct}
              descuentoOrigen={descuentoOrigen}
              descuentoMonto={descuentoMonto}
              totalNeto={totalNeto}
              conIva={conIva}
              clienteNombre={clienteSession?.nombre}
              nombreLegal={clienteSession?.nombreLegal}
              emailComunicacion={clienteSession?.emailComunicacion}
              telefonoContacto={clienteSession?.telefonoContacto}
              direccionLegal={clienteSession?.direccionLegal}
              perfilImpuestos={clienteSession?.perfil_impuestos}
              onBack={() => setStep("carrito")}
              onCrearPedido={handleCrearPedido}
            />
          </div>
        ) : (
          <>
            <div
              className="flex-1 overflow-y-auto flex flex-col"
              style={{ scrollbarWidth: "none" }}
            >
              {/* Items */}
              {entries.map(({ eq, qty }) => {
                // Precio/total desde el backend (FASE 3); placeholder transitorio
                // (precio catálogo) solo hasta que llega la cotización.
                const linea = lineaPorEquipo(totales, eq._backendId ?? Number(eq.id));
                return (
                  <CartItem
                    key={eq.id}
                    eq={eq}
                    qty={qty}
                    fechaDesde={fechaDesde}
                    jornadas={jornadas}
                    precioJornada={linea?.precioJornada ?? eq.pricePerDay}
                    periodTotal={linea?.bruto ?? eq.pricePerDay * qty * totales.jornadas}
                  />
                );
              })}

              {/* Totals — auto margin pushes to bottom when few items */}
              <div className="border-t border-hairline mt-auto">
                <div className="flex flex-col gap-2 px-5 py-3.5">
                  <div className="flex justify-between items-baseline">
                    <span className="font-sans text-sm text-muted-foreground">
                      {hayFechas
                        ? `Subtotal · ${jornadas} ${jornadas === 1 ? "jornada" : "jornadas"}`
                        : "Subtotal · por jornada"}
                    </span>
                    <span className="font-mono text-sm font-semibold text-ink tabular-nums">
                      {formatARS(subtotal)}
                    </span>
                  </div>

                  {descuentoPct > 0 && (
                    <div className="flex items-center justify-between py-1">
                      <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                        {descuentoLabel(descuentoOrigen, jornadas, clienteSession?.nombre)}
                        <span
                          className={cn(
                            "inline-flex items-center px-1.5 py-px rounded-full font-mono text-xs font-bold",
                            descuentoOrigen === "cliente"
                              ? "bg-verde/10 text-verde-ink"
                              : "bg-azul/10 text-azul",
                          )}
                        >
                          −{descuentoPct}%
                        </span>
                      </div>
                      <span className="font-mono text-sm font-semibold text-verde-ink tabular-nums">
                        −{formatARS(descuentoMonto)}
                      </span>
                    </div>
                  )}

                  <div className="flex justify-between items-baseline opacity-45">
                    <span className="font-sans text-sm text-muted-foreground">
                      Depósito de seguridad
                    </span>
                    <span className="font-mono text-sm text-muted-foreground">A definir</span>
                  </div>

                  <div className="flex justify-between items-baseline pt-2 border-t border-hairline mt-1">
                    <span className="font-sans text-15 font-bold text-ink">
                      {hayFechas ? "Total" : "Estimado / jornada"}
                    </span>
                    <span
                      style={{
                        fontFamily: "var(--font-display)",
                        fontSize: 24,
                        fontWeight: 900,
                        color: "var(--ink)",
                        fontVariantNumeric: "tabular-nums",
                      }}
                    >
                      {formatARS(totalNeto)}
                      {conIva && (
                        <span className="font-sans text-sm font-normal text-muted-foreground">
                          {" "}
                          + IVA
                        </span>
                      )}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div
              className="px-5 pt-3 border-t border-hairline shrink-0"
              style={{ paddingBottom: 20 }}
            >
              {solicitado ? (
                <div className="flex flex-col gap-2.5">
                  <div
                    className="px-4 py-3 rounded-[var(--radius-lg)] border"
                    style={{
                      background: "var(--amber-soft)",
                      borderColor: "color-mix(in oklch, var(--amber) 40%, transparent)",
                    }}
                  >
                    <div className="font-sans text-sm font-bold text-ink mb-0.5">
                      ¡Listo! Rental solicitado.
                    </div>
                    <div className="font-sans text-xs text-muted-foreground leading-relaxed">
                      Lo revisamos manualmente y te confirmamos a la brevedad.
                    </div>
                  </div>
                  <a
                    href={waHref}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full py-3 rounded-full border-[1.5px] border-hairline bg-transparent text-ink font-sans text-sm font-semibold flex items-center justify-center gap-2 hover:border-ink hover:bg-muted transition-colors"
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z" />
                      <path
                        d="M12 0C5.373 0 0 5.373 0 12c0 2.122.558 4.112 1.528 5.836L.057 23.857a.5.5 0 00.609.61l6.098-1.458A11.945 11.945 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.818 9.818 0 01-5.006-1.368l-.36-.214-3.722.89.921-3.618-.234-.373A9.818 9.818 0 1112 21.818z"
                        fillRule="evenodd"
                        clipRule="evenodd"
                      />
                    </svg>
                    Consultanos por WhatsApp
                  </a>
                </div>
              ) : (
                <Button
                  variant="primary"
                  shape="pill"
                  className="w-full h-auto py-3.5 font-sans text-15 font-bold disabled:cursor-not-allowed"
                  onClick={handleIrAResumen}
                >
                  Solicitar rental
                </Button>
              )}
            </div>
          </>
        )}
      </div>
    </>
  );
}
