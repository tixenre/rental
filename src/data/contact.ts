/**
 * Datos de contacto y dirección de Rambla Rental.
 *
 * Single source of truth — usado por Footer, página FAQ, página Estudio,
 * meta tags, etc. Editar acá actualiza todo.
 *
 * Los TODO son datos que el dueño tiene que confirmar antes de publicar al
 * público.
 */

export const CONTACT = {
  /** Número internacional sin signos, formato wa.me. */
  whatsappNumber: "5492235852510",
  /** Display human-readable del teléfono. */
  phoneDisplay: "+54 9 223 585 2510",

  /** TODO: confirmar email real. */
  email: "hola@rambla.studio",

  /** TODO: confirmar dirección exacta. */
  address: {
    line1: "Mar del Plata",
    line2: "", // calle + número, barrio
    city: "Mar del Plata",
    province: "Buenos Aires",
    country: "Argentina",
    /** Link a Google Maps. TODO: completar con coordenadas reales. */
    mapsUrl: "https://maps.google.com/?q=Mar+del+Plata",
  },

  /** TODO: confirmar horarios reales de atención (retiro/devolución). */
  hours: [
    { days: "Lunes a Viernes", hours: "10:00 – 19:00" },
    { days: "Sábado", hours: "10:00 – 14:00" },
    { days: "Domingo", hours: "Cerrado" },
  ],

  social: {
    /** TODO: confirmar handle real de Instagram. */
    instagram: "ramblarental",
  },

  /** Métodos de pago aceptados — display only en el footer. */
  paymentMethods: ["Transferencia bancaria", "MercadoPago", "Efectivo"],
};

/** URL de WhatsApp con mensaje pre-cargado opcional. */
export function whatsappUrl(prefilledText?: string): string {
  const base = `https://wa.me/${CONTACT.whatsappNumber}`;
  if (!prefilledText) return base;
  return `${base}?text=${encodeURIComponent(prefilledText)}`;
}
