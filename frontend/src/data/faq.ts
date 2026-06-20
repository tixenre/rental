/**
 * Preguntas frecuentes del rental (página /preguntas-frecuentes).
 *
 * Separadas de las del Estudio (data/studio.ts) — el estudio tiene su FAQ
 * propia más enfocada en la operativa del espacio.
 *
 * TODO: revisar respuestas con el dueño antes de publicar al público.
 * Las marcadas con [BORRADOR] son redacción tentativa.
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
          "coordinar retiro y forma de pago.",
      },
      {
        q: "¿Cuánto tiempo antes tengo que reservar?",
        a:
          "[BORRADOR] Idealmente con 48-72 hs de anticipación para asegurar " +
          "disponibilidad, sobre todo en fines de semana largos. Para reservas " +
          "más urgentes escribinos por WhatsApp.",
      },
      {
        q: "¿Puedo modificar o cancelar una reserva?",
        a:
          "[BORRADOR] Sí, podés modificar fechas o equipos hasta 24 hs antes " +
          "del retiro sin costo. Cancelaciones con menos aviso pueden tener costo " +
          "de reserva.",
      },
      {
        q: "¿Puedo ver el equipo antes de retirarlo?",
        a:
          "Sí, podés pasar por el local en horario de atención. También se hace " +
          "una verificación juntos al momento del retiro.",
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
          "[BORRADOR] Para equipos de mayor valor pedimos un depósito en garantía " +
          "que se devuelve al regresar el equipo en buenas condiciones. Para clientes " +
          "habituales con cuenta puede no ser necesario.",
      },
      {
        q: "¿Hacen factura?",
        a:
          "[BORRADOR] Sí, emitimos factura A o B según necesidad. Avisanos al " +
          "momento de la reserva.",
      },
    ],
  },
  {
    title: "Retiro y devolución",
    items: [
      {
        q: "¿Hacen envíos / pueden ir a buscar el equipo?",
        a:
          "[BORRADOR] Por defecto el retiro y devolución son en nuestro local en " +
          "Mar del Plata. Para producciones grandes podemos coordinar logística " +
          "en la ciudad — consultanos.",
      },
      {
        q: "¿Qué necesito presentar al retirar?",
        a:
          "[BORRADOR] DNI vigente y comprobante de la seña. Para clientes nuevos " +
          "también pedimos un segundo documento o referencia.",
      },
      {
        q: "¿Qué pasa si devuelvo el equipo más tarde?",
        a:
          "[BORRADOR] Avisanos lo antes posible. Demoras de algunas horas suelen " +
          "no tener costo si no afectan otra reserva. Demoras mayores se cobran " +
          "como jornadas adicionales.",
      },
    ],
  },
  {
    title: "Seguros y daños",
    items: [
      {
        q: "¿Qué pasa si se rompe el equipo?",
        a:
          "[BORRADOR] Si el daño es por uso normal y razonable lo cubre Rambla. " +
          "Daños por negligencia, mal uso o accidente quedan a cargo del cliente. " +
          "Cobramos el costo de reparación o reposición según corresponda.",
      },
      {
        q: "¿Tienen seguro propio?",
        a:
          "[BORRADOR] Los equipos están cubiertos para uso interno. Para producciones " +
          "que requieran seguro técnico específico, consultanos antes — podemos " +
          "ayudarte a contratar uno por la fecha del rodaje.",
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
          "Trabajamos con horarios de atención que pueden variar según el día de la " +
          "semana. Cuando elegís las fechas, el sistema te muestra solo los horarios " +
          "disponibles de cada día — los días en que estamos cerrados no se pueden elegir.",
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
