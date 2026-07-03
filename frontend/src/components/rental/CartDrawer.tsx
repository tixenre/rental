import { useEffect, useId, useRef, useState } from "react";
import { toast } from "sonner";
import { useNavigate } from "@tanstack/react-router";

import { useCart } from "@/lib/cart-store";
import { type Equipment } from "@/data/equipment";
import { useClienteSession } from "@/lib/iva";
import { createOrder, OrderVerificationError } from "@/lib/orders";
import { chequearEstadoVerificacion, iniciarVerificacionIdentidad } from "@/lib/verificacion";
import type { VerificacionPanelEstado } from "@/components/rental/VerificacionRequeridaPanel";
import { stepUpWithPasskey, passkeyErrorMessage } from "@/lib/passkey";
import { aceptarTyc, validarCheckout } from "@/lib/checkout";
import { toLocalISO } from "@/lib/rental-dates";
import { useCotizacion } from "@/lib/cotizacion";
import { useAntelacionMinimaHoras } from "@/hooks/useSettings";
import { useBusinessPhone } from "@/lib/business";
import { whatsappLink } from "@/lib/whatsapp";
import { CartDrawerView } from "./CartDrawerView";

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
  const [verifEstado, setVerifEstado] = useState<VerificacionPanelEstado | null>(null);
  const [verifMotivo, setVerifMotivo] = useState<string | null>(null);
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
    setVerifEstado(null);
    setVerifMotivo(null);

    // #27 — Pre-check de cuenta antes de submitear (fuente única en
    // verificacion.ts). Sin sesión → panel login/registro; logueado pero sin
    // DNI validado → panel de verificación de identidad (distingue no-verificado
    // / en-revision / rechazado); en vez del 401/403 críptico.
    const { estado, motivo } = await chequearEstadoVerificacion();
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
    if (estado === "no-verificado" || estado === "en-revision" || estado === "rechazado") {
      setVerifEstado(estado);
      setVerifMotivo(motivo ?? null);
      setSubmitting(false);
      return;
    }
    // "logueado-verificado" → sigue al createOrder

    try {
      // 1. Registrar aceptación de T&C (idempotente)
      await aceptarTyc();

      // 2. Passkey step-up: Face ID / huella = firma del pedido + aceptación de T&C
      await stepUpWithPasskey();

      // 3. Portero: verificar que todo esté en orden antes de crear
      const { listo, faltan } = await validarCheckout(useCart.getState().sessionId);
      if (!listo) {
        const msg = faltan.map((f) => f.mensaje).join(" • ");
        setSubmitError(msg);
        toast.error("Revisá los datos antes de continuar", { description: msg, duration: 8000 });
        setSubmitting(false);
        return;
      }

      // 4. Crear el pedido
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
        setVerifEstado("no-verificado");
        setSubmitting(false);
        return;
      }
      const msg = passkeyErrorMessage(err);
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

  async function onVerificar() {
    setIniciandoVerif(true);
    try {
      await iniciarVerificacionIdentidad("/?openCarrito=1");
    } catch {
      /* el helper ya hizo toast */
    } finally {
      setIniciandoVerif(false);
    }
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
      submitError={submitError}
      submitting={submitting}
      onSubmit={handleSubmit}
      hayNoDisponible={hayNoDisponible}
      nombresSinDisp={nombresSinDisp}
      dentroDeLeadTime={dentroDeLeadTime}
      leadTimeHoras={leadTimeHoras}
      urgenciaWhatsappUrl={urgenciaWhatsappUrl}
      needsLogin={needsLogin}
      onLogin={goToLogin}
      onRegister={goToRegister}
      verifEstado={verifEstado}
      verifMotivo={verifMotivo}
      iniciandoVerif={iniciandoVerif}
      onVerificar={onVerificar}
      clienteSession={clienteSession}
      onClear={clear}
    />
  );
}
