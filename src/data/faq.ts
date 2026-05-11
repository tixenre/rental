/**
 * Preguntas frecuentes del rental (página /preguntas-frecuentes).
 *
 * Separadas de las del Estudio (data/studio.ts) — el estudio tiene su FAQ
 * propia más enfocada en la operativa del espacio.
 *
 * TODO: revisar respuestas con el dueño antes de publicar al público.
 * Las marcadas con [BORRADOR] son redacción tentativa.
 */

export type FaqItem = { q: string; a: string };

export type FaqGroup = {
  title: string;
  items: FaqItem[];
};

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
];
