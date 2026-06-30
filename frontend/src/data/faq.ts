/**
 * Preguntas frecuentes del rental (página /preguntas-frecuentes).
 *
 * Separadas de las del Estudio (data/studio.ts) — el estudio tiene su FAQ
 * propia más enfocada en la operativa del espacio.
 *
 * Esto es el DEFAULT (fallback). La fuente editable vive en el setting
 * `faq_json` (app_settings), que el admin edita desde /admin/settings →
 * sección "Preguntas frecuentes". Ver `useFaqGroups()` más abajo.
 */

import { useQuery } from "@tanstack/react-query";

export type FaqItem = { q: string; a: string };

export type FaqGroup = {
  title: string;
  items: FaqItem[];
};

/** Parsea el JSON del setting `faq_json`. null si vacío/ inválido. */
export function parseFaq(raw?: string | null): FaqGroup[] | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.length > 0 ? (parsed as FaqGroup[]) : null;
  } catch {
    return null;
  }
}

/**
 * FAQ pública: lee el setting editable `faq_json`; si no está configurado
 * (o falla), cae a `FAQ_GROUPS` hardcodeado. El admin las edita desde Settings.
 */
export function useFaqGroups(): FaqGroup[] {
  const q = useQuery({
    queryKey: ["settings", "faq_json"],
    queryFn: async () => {
      const res = await fetch("/api/settings/faq_json");
      if (!res.ok) return null;
      const data = await res.json();
      return parseFaq(data?.value as string | undefined);
    },
    staleTime: 5 * 60 * 1000,
  });
  return q.data ?? FAQ_GROUPS;
}

export const FAQ_GROUPS: FaqGroup[] = [
  {
    title: "Reservas",
    items: [
      {
        q: "¿Cómo reservo un equipo?",
        a:
          "Buscá el equipo en el catálogo, agregalo al carrito y elegí las fechas. " +
          "Después confirmás la cotización y te respondemos por WhatsApp para " +
          "coordinar el retiro y la forma de pago.",
      },
      {
        q: "¿Cuánto tiempo antes tengo que reservar?",
        a:
          "Idealmente con 48 a 72 hs de anticipación para asegurar disponibilidad. " +
          "Para consultas o reservas urgentes, escribinos por WhatsApp y lo vemos.",
      },
      {
        q: "¿Puedo modificar o cancelar una reserva?",
        a:
          "Sí. Si necesitás cambiar las fechas, los equipos o cancelar, escribinos " +
          "por WhatsApp lo antes posible y lo resolvemos juntos. Cuanto más aviso " +
          "nos des, más fácil es reacomodar todo.",
      },
      {
        q: "¿Puedo ver el equipo antes de retirarlo?",
        a:
          "Sí. Coordinando antes con nosotros podés pasar por el local a verlo. " +
          "Además, al momento del retiro revisamos juntos el equipo para que salgas " +
          "sabiendo que está todo en orden.",
      },
    ],
  },
  {
    title: "Pago",
    items: [
      {
        q: "¿Cómo se paga?",
        a:
          "Aceptamos transferencia bancaria, MercadoPago y efectivo. " +
          "Para confirmar la reserva pedimos una seña; el resto se paga al " +
          "retirar el equipo.",
      },
      {
        q: "¿Necesito dejar un depósito?",
        a:
          "En algunos casos, según el equipo, podemos pedir un depósito en garantía " +
          "que se devuelve al regresar el equipo en buenas condiciones. Si aplica a " +
          "tu reserva, te lo avisamos al confirmarla.",
      },
      {
        q: "¿Hacen factura?",
        a:
          "Sí. Avisanos al momento de la reserva que necesitás factura y qué tipo, " +
          "y la coordinamos.",
      },
    ],
  },
  {
    title: "Retiro y devolución",
    items: [
      {
        q: "¿Hacen envíos o pueden ir a buscar el equipo?",
        a:
          "Por defecto, el retiro y la devolución son en nuestro local de Mar del " +
          "Plata. Para producciones grandes podemos coordinar logística dentro de la " +
          "ciudad — consultanos y lo vemos según el caso.",
      },
      {
        q: "¿Qué necesito presentar al retirar?",
        a:
          "Un documento de identidad vigente y el comprobante de la seña. Si es tu " +
          "primera vez con nosotros, puede que te pidamos algún dato adicional; " +
          "cualquier requisito puntual te lo aclaramos al confirmar la reserva.",
      },
      {
        q: "¿Qué pasa si devuelvo el equipo más tarde?",
        a:
          "Avisanos lo antes posible. Una demora de algunas horas no suele tener " +
          "costo si no afecta a otra reserva, pero como dejamos un margen de " +
          "preparación entre alquileres, devolver tarde puede complicar la entrega " +
          "siguiente. Las demoras que pasan a otra jornada se cobran como jornadas " +
          "adicionales.",
      },
    ],
  },
  {
    title: "Seguros y daños",
    items: [
      {
        q: "¿Qué pasa si se rompe el equipo?",
        a:
          "Si el daño es por uso normal y razonable, lo cubre Rambla. Los daños por " +
          "negligencia, mal uso o accidente quedan a cargo del cliente: se cobra el " +
          "costo de reparación o reposición según corresponda. Ante cualquier " +
          "inconveniente con un equipo, avisanos enseguida.",
      },
      {
        q: "¿Necesito un seguro para alquilar?",
        a:
          "Para un alquiler común no hace falta. Si tu producción requiere un seguro " +
          "técnico específico, escribinos antes y lo vemos según el caso.",
      },
    ],
  },
  {
    title: "Cómo funciona el alquiler",
    items: [
      {
        q: "¿Cómo se cuentan las jornadas?",
        a:
          "Una jornada es un período de 24 horas desde el retiro. Por ejemplo, si " +
          "retirás el lunes a las 9:00 y devolvés el martes a las 9:00, es 1 jornada. " +
          "Si devolvés más tarde que la hora de retiro, se cuenta una jornada más. " +
          "El total de jornadas que ves al elegir las fechas es exactamente lo que se cobra.",
      },
      {
        q: "¿En qué horarios puedo retirar y devolver?",
        a:
          "Cuando elegís las fechas, el sistema te muestra los horarios de cada día " +
          "según nuestra configuración (los días cerrados no se pueden elegir). Son " +
          "horarios de referencia: que figuren disponibles no significa que estemos " +
          "en el local en ese momento. Coordiná siempre el retiro y la devolución con " +
          "nosotros por WhatsApp antes de venir.",
      },
      {
        q: "¿Cómo sé si un equipo está disponible en mis fechas?",
        a:
          "Al elegir las fechas, el catálogo te muestra cuántas unidades de cada equipo " +
          "quedan disponibles. Si un día ya está reservado, aparece bloqueado en el " +
          "calendario y no vas a poder elegir ese período para ese equipo.",
      },
      {
        q: "¿Por qué a veces un equipo no está disponible justo después de otra reserva?",
        a:
          "Entre un alquiler y el siguiente dejamos un margen de preparación y revisión " +
          "del equipo. Por eso puede que un equipo no esté disponible inmediatamente " +
          "después de que vuelve de otra reserva.",
      },
    ],
  },
];
