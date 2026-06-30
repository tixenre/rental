/**
 * Plantillas de mensajes WhatsApp para click-to-chat con clientes.
 *
 * Interpolación simple — un texto fijo + datos del pedido. Más adelante
 * (cuando se ataque #62 email transaccional + sistema de plantillas):
 * mover a tabla `app_settings` para que el admin edite desde
 * `/admin/settings` sin tocar código.
 */

import { formatARS } from "@/lib/format";

const fmtFecha = (s: string | null | undefined): string => {
  if (!s) return "—";
  try {
    return new Date(s + "T12:00:00").toLocaleDateString("es-AR", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  } catch {
    return s;
  }
};

const fmtMonto = (n: number | null | undefined): string => formatARS(n ?? 0);

export type PedidoMinimal = {
  numero_pedido?: number | null;
  numero_remito?: string | null;
  cliente_nombre?: string | null;
  fecha_desde?: string | null;
  fecha_hasta?: string | null;
  monto_total?: number | null;
  monto_pagado?: number | null;
  estado?: string | null;
};

const numeroDoc = (p: PedidoMinimal): string => {
  if (p.numero_pedido) return `#${p.numero_pedido}`;
  if (p.numero_remito) return `#${p.numero_remito}`;
  return "";
};

const primerNombre = (s: string | null | undefined): string => {
  if (!s) return "";
  // "Apellido, Nombre" → "Nombre"
  if (s.includes(",")) {
    const parts = s.split(",");
    if (parts.length >= 2) return parts[1].trim().split(" ")[0];
  }
  return s.trim().split(" ")[0];
};

export type TemplateKey =
  | "saludo"
  | "presupuesto"
  | "confirmacion"
  | "recordatorio_retiro"
  | "recordatorio_devolucion"
  | "pago"
  | "consulta_libre";

export type TemplateOption = {
  key: TemplateKey;
  label: string;
  message: string;
};

/**
 * Genera la lista de plantillas aplicables a un pedido. Las plantillas
 * irrelevantes según el estado (e.g. confirmación cuando ya fue retirado)
 * podrían filtrarse — por ahora devolvemos todas y el admin elige.
 */
export function templatesForPedido(p: PedidoMinimal): TemplateOption[] {
  const nombre = primerNombre(p.cliente_nombre);
  const num = numeroDoc(p);
  const desde = fmtFecha(p.fecha_desde);
  const hasta = fmtFecha(p.fecha_hasta);
  const total = fmtMonto(p.monto_total);
  const pagado = p.monto_pagado ?? 0;
  const saldo = (p.monto_total ?? 0) - pagado;

  return [
    {
      key: "saludo",
      label: "Saludo simple",
      message: `Hola${nombre ? " " + nombre : ""}! Te escribo desde Rambla Rental.`,
    },
    {
      key: "presupuesto",
      label: "Cotización lista",
      message:
        `Hola${nombre ? " " + nombre : ""}! Te paso tu cotización ${num}:\n` +
        `Fechas: ${desde} → ${hasta}\n` +
        `Total: ${total}\n\n` +
        `Cualquier consulta avisame.`,
    },
    {
      key: "confirmacion",
      label: "Pedido confirmado",
      message:
        `Hola${nombre ? " " + nombre : ""}! Tu pedido ${num} está confirmado.\n` +
        `Lo retirás el ${desde}.\n` +
        `Cualquier cosa avisame.`,
    },
    {
      key: "recordatorio_retiro",
      label: "Recordatorio retiro",
      message:
        `Hola${nombre ? " " + nombre : ""}! Recordatorio: tu pedido ${num} se retira el ${desde}.\n` +
        `Te espero en el local.`,
    },
    {
      key: "recordatorio_devolucion",
      label: "Recordatorio devolución",
      message: `Hola${nombre ? " " + nombre : ""}! Recordatorio: la devolución de tu pedido ${num} es el ${hasta}.`,
    },
    {
      key: "pago",
      label: "Recordatorio de pago",
      message:
        `Hola${nombre ? " " + nombre : ""}! Te recuerdo que queda un saldo pendiente de ${fmtMonto(saldo)} en tu pedido ${num}.\n` +
        `Cualquier consulta avisame.`,
    },
    {
      key: "consulta_libre",
      label: "Mensaje en blanco",
      message: "",
    },
  ];
}
