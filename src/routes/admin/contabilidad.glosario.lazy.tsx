/**
 * contabilidad.glosario.lazy.tsx — Glosario de Finanzas (#809).
 *
 * Página de referencia, en lenguaje claro: qué significa cada término y qué hace
 * cada acción. Para releer y sacarse dudas. NO calcula nada — es documentación viva
 * dentro del back-office (el modelo real vive en backend/contabilidad/).
 */
import { createLazyFileRoute, Link } from "@tanstack/react-router";

import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/contabilidad/glosario")({
  component: GlosarioPage,
});

type Item = { t: string; d: React.ReactNode };

const TERMINOS: Item[] = [
  {
    t: "Caja",
    d: "Plata real del negocio y dónde está: Efectivo, Banco, Mercado Pago, Dólares, Fondo Rambla. Sube y baja con movimientos. Su saldo es plata que existe de verdad.",
  },
  {
    t: "Total disponible",
    d: "La suma de las cajas. Es la plata del negocio que hay ahora. NO incluye lo de los socios (esa plata la tienen ellos en mano, no es caja).",
  },
  {
    t: "Cuenta corriente de un socio",
    d: "No es una caja: es el saldo de quién le debe a quién entre el socio (Pablo/Tincho) y Rambla. Se lee siempre en palabras: «le debe a Rambla» o «Rambla le debe».",
  },
  {
    t: "Deudor",
    d: "El socio le debe plata a Rambla (tiene plata del negocio en mano). Se muestra en rojo.",
  },
  {
    t: "Acreedor",
    d: "Rambla le debe plata al socio (le falta cobrar su parte). Se muestra en verde. Un acreedor NO es un error.",
  },
  { t: "Saldado", d: "El socio está a mano con Rambla: no debe ni le deben." },
  {
    t: "Arranque",
    d: "Lo que un socio ya tenía/debía ANTES de arrancar el sistema (ej. plata que cobró de Rambla). Es el punto de partida de su cuenta corriente.",
  },
  {
    t: "Cobró",
    d: "La plata de alquileres que el socio agarró (los cobros a su nombre). Le sube la deuda: agarró plata que en parte es de los otros.",
  },
  {
    t: "Su parte",
    d: "La comisión que le corresponde al socio por lo que se alquiló (del reporte de Liquidación). Le baja la deuda: es lo que sí es suyo.",
  },
  {
    t: "Devengado vs percibido",
    d: "Devengado = lo que se ganó (Liquidación, sobre pedidos saldados). Percibido = la plata que entró de verdad (incluidas señas). Pueden no coincidir mes a mes — es a propósito.",
  },
  {
    t: "Liquidación",
    d: "El reporte de cuánto generó cada equipo/dueño y cuánto le toca a cada socio, por mes, con los pedidos detrás. Es el «devengado».",
  },
  {
    t: "Ganancia neta del mes",
    d: "Lo devengado del mes menos los gastos del mes. El resultado del negocio (distinto del saldo de caja).",
  },
  {
    t: "Clean start",
    d: "Finanzas arranca en junio 2026: los alquileres anteriores a esa fecha no cuentan, aunque se cobren después. El corte es por la fecha del alquiler, no del pago.",
  },
  {
    t: "Reconciliación",
    d: "El semáforo de control: avisa si una caja quedó negativa, si hay cobros sin socio asignado, o si algo no cuadra.",
  },
];

const ACCIONES: Item[] = [
  {
    t: "Registrar un cobro",
    d: "Se hace desde el pedido (Cobros de pedidos). Entra a la caja de quien cobró (Rambla → Fondo Rambla) o le sube la deuda al socio que cobró.",
  },
  {
    t: "Cargar un gasto",
    d: "Una salida de plata de una caja, con su categoría (Sueldos, Equipos, etc.) y opcionalmente un beneficiario (ej. «Jimena») y comprobante.",
  },
  {
    t: "Transferencia",
    d: "Mover plata de una caja a otra (misma moneda). No cambia el total disponible, solo dónde está.",
  },
  {
    t: "Registrar pago de un socio (rendir)",
    d: "El socio entrega plata: baja su deuda y entra a la caja que elijas. Desde la tarjeta del socio, opción «me pagó / rindió».",
  },
  {
    t: "Cargar a la cuenta de un socio",
    d: "Rambla puso plata por el socio (ej. le compró un equipo): sale de una caja y le SUBE la deuda al socio. Desde la tarjeta del socio, opción «le cargué».",
  },
  {
    t: "Anular un movimiento",
    d: "La plata no se borra: anular deja el movimiento tachado con motivo y tu nombre, y deja de contar para los saldos.",
  },
  {
    t: "Cerrar el mes",
    d: "Congela el mes: ya no se pueden cargar/editar movimientos con fecha de ese mes. Se puede reabrir.",
  },
];

function GlosarioPage() {
  useDocumentTitle("Glosario · Finanzas");

  return (
    <div className="px-4 md:px-6 py-6 space-y-8 max-w-3xl mx-auto">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Back-office · Finanzas
          </div>
          <h1 className="font-display text-3xl text-ink">Glosario</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Qué significa cada término y qué hace cada acción. Para releer y sacarse dudas.
          </p>
        </div>
        <Link
          to="/admin/contabilidad"
          className="shrink-0 h-9 rounded-md border hairline px-3 text-sm flex items-center hover:bg-muted/40"
        >
          ← Tablero
        </Link>
      </header>

      <Bloque titulo="Términos" items={TERMINOS} />
      <Bloque titulo="Acciones" items={ACCIONES} />
    </div>
  );
}

function Bloque({ titulo, items }: { titulo: string; items: Item[] }) {
  return (
    <section className="space-y-3">
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        {titulo}
      </div>
      <dl className="space-y-3">
        {items.map((it) => (
          <div key={it.t} className="rounded-lg border hairline p-4">
            <dt className="font-medium text-ink">{it.t}</dt>
            <dd className="text-sm text-muted-foreground mt-1 leading-relaxed">{it.d}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
