import { useEffect, useId, useRef, useState } from "react";
import { toast } from "sonner";
import { useNavigate } from "@tanstack/react-router";

import { useCart } from "@/lib/cart-store";
import { type Equipment } from "@/data/equipment";
import { useClienteSession } from "@/lib/iva";
import { createOrder } from "@/lib/orders";
import { toLocalISO } from "@/lib/rental-dates";
import { useCotizacion } from "@/lib/cotizacion";
import { useAntelacionMinimaHoras } from "@/hooks/useSettings";
import { useBusinessPhone } from "@/lib/business";
import { whatsappLink } from "@/lib/whatsapp";
import { CartDrawerView } from "./CartDrawerView";

type CheckoutStep = "carrito" | "resumen" | "exito";

/** Cuánto se muestra la pantalla de éxito antes de redirigir al portal —
 *  tiempo para que se lea "Pedido #X enviado" sin que se pise con el toast
 *  de siempre (que coincidía con la navegación al portal). */
const EXITO_REDIRECT_MS = 2500;

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * CartDrawer — container del drawer del carrito (checkout, desktop + bottom-sheet).
 *
 * Toda la lógica vive acá: store (useCart), cotización del backend, focus-trap +
 * scroll-lock, validación de fechas, pre-check de cuenta/verificación y creación
 * del pedido. El markup vive en el shell presentacional `CartDrawerView` (fuente
 * única del diseño, que también muestra la vitrina del DS con estado mock). El
 * core de reservas/cotización/órdenes no se toca — solo se cablea a la View.
 */
export function CartDrawer({
  allEquipos,
  getDisponible,
  resumeStep,
}: {
  allEquipos: Equipment[];
  getDisponible?: (item: Equipment) => number | undefined;
  /** Si el carrito se reabre volviendo de un desvío (Didit) con
   *  `?carritoPaso=resumen`, entra directo al paso de resumen en vez de la
   *  lista de ítems — ver `RESUME_STEP_PARAM` en CheckoutResumen.tsx. */
  resumeStep?: "resumen";
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
    sessionId,
  } = useCart();

  const isBottom = drawerPlacement === "bottom";

  const navigate = useNavigate();
  const [step, setStep] = useState<CheckoutStep>("carrito");
  const [pedidoEnviado, setPedidoEnviado] = useState<{ id: number; numeroPedido: string } | null>(
    null,
  );
  const [needsLogin, setNeedsLogin] = useState(false);
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

  // Retorno de un desvío (Didit) con ?carritoPaso=resumen: reabrir directo en
  // el paso de resumen en vez de la lista de ítems (rental.tsx limpia el query
  // param al toque; este efecto solo actúa mientras `resumeStep` sigue vivo en
  // esa misma tanda de renders).
  useEffect(() => {
    if (drawerOpen && resumeStep === "resumen") {
      setStep("resumen");
    }
  }, [drawerOpen, resumeStep]);

  // Pantalla de éxito (paso "exito"): se muestra unos segundos y RECIÉN
  // después redirige al portal — antes el toast de éxito se pisaba con la
  // navegación (pasaban casi al mismo tiempo).
  useEffect(() => {
    if (!pedidoEnviado) return;
    const id = pedidoEnviado.id;
    const t = setTimeout(() => {
      clear();
      setShowNotas(false);
      setNotas("");
      setDrawerOpen(false);
      setStep("carrito");
      setPedidoEnviado(null);
      navigate({ to: "/cliente/portal", search: { nuevo: id } });
    }, EXITO_REDIRECT_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- clear/navigate/setDrawerOpen son estables; solo debe re-armar el timer cuando cambia pedidoEnviado
  }, [pedidoEnviado]);

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

  // Lead-time (#1126): el backend es la fuente de verdad (lo enforza el portero +
  // el backstop de creación). Acá solo leemos el setting para avisar ANTES de tocar
  // el botón: si el retiro cae dentro de la ventana mínima, mostramos un disclaimer
  // con CTA de WhatsApp y deshabilitamos "Confirmar". El umbral lo decide el back.
  const leadTimeHoras = useAntelacionMinimaHoras();
  const businessPhone = useBusinessPhone();
  const dentroDeLeadTime =
    leadTimeHoras > 0 &&
    !!startDate &&
    new Date(toLocalISO(startDate, startTime)).getTime() < Date.now() + leadTimeHoras * 3_600_000;
  const urgenciaWhatsappUrl = whatsappLink({
    phone: businessPhone,
    message:
      "¡Hola! Necesito un alquiler con urgencia (dentro del plazo mínimo de antelación). ¿Me pueden ayudar?",
  });

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

  // "Confirmar solicitud" (paso carrito): solo lo que el portero NO puede
  // chequear (fechas, sesión de cliente) — el resto (identidad/T&C/firma/etc.)
  // lo resuelve el paso de resumen preguntándole al backend (`CheckoutResumen`).
  function handleIrAResumen() {
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

    // El check de login no vive en el portero (lo dueña el guard del route) —
    // se sigue filtrando acá con la sesión ya cacheada por useClienteSession.
    if (!clienteSession) {
      setNeedsLogin(true);
      return;
    }
    setNeedsLogin(false);
    setStep("resumen");
  }

  async function handleCrearPedido(sessionConfirmed: boolean) {
    const order = await createOrder({
      status: "solicitado",
      startDate,
      endDate,
      startTime,
      endTime,
      days: d,
      notes: notas.trim() || undefined,
      sessionConfirmed,
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
    // La pantalla de éxito (paso "exito") se encarga de limpiar/cerrar/redirigir
    // después de EXITO_REDIRECT_MS (ver el efecto de arriba).
    setStep("exito");
    setPedidoEnviado({ id: Number(order.id), numeroPedido: order.numero_pedido });
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
    <CartDrawerView
      drawerOpen={drawerOpen}
      isBottom={isBottom}
      dialogRef={dialogRef}
      closeBtnRef={closeBtnRef}
      titleId={titleId}
      onClose={() => setDrawerOpen(false)}
      onExplore={() => setDrawerOpen(false, "bottom")}
      step={step}
      pedidoEnviado={pedidoEnviado}
      startDate={startDate}
      endDate={endDate}
      startTime={startTime}
      endTime={endTime}
      d={d}
      hayFechas={hayFechas}
      onOpenDateModal={() => setDateModalOpen(true)}
      dateModalOpen={dateModalOpen}
      onDateModalChange={setDateModalOpen}
      list={list}
      getDisponible={getDisponible}
      openKits={openKits}
      onToggleKit={(id) => setOpenKits((p) => ({ ...p, [id]: !p[id] }))}
      onAdd={add}
      onRemove={remove}
      onSetQty={setQty}
      subtotalTotal={subtotalTotal}
      descuentoPct={descuentoPct}
      descuentoOrigen={descuentoOrigen}
      descuentoMonto={descuentoMonto}
      totalNeto={totalNeto}
      conIva={conIva}
      notas={notas}
      showNotas={showNotas}
      onNotasChange={setNotas}
      onShowNotas={() => setShowNotas(true)}
      onSubmit={handleIrAResumen}
      hayNoDisponible={hayNoDisponible}
      nombresSinDisp={nombresSinDisp}
      dentroDeLeadTime={dentroDeLeadTime}
      leadTimeHoras={leadTimeHoras}
      urgenciaWhatsappUrl={urgenciaWhatsappUrl}
      needsLogin={needsLogin}
      onLogin={goToLogin}
      onRegister={goToRegister}
      clienteSession={clienteSession}
      onClear={clear}
      sessionId={sessionId}
      onVolverAlCarrito={() => setStep("carrito")}
      onCrearPedido={handleCrearPedido}
    />
  );
}
