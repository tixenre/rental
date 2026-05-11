// Configuración del Estudio (producto estrella).
// TODO: completar precios reales — el resto del copy ya es producción-ready.

export const STUDIO = {
  name: "El Estudio",
  tagline: "Foto y video en Mar del Plata",
  description:
    "Un espacio pensado para producciones audiovisuales. Iluminación natural, " +
    "ciclorama infinito, climatización y todo el equipo de Rambla a mano. " +
    "Ideal para producto, retrato, video corporativo, redes sociales y " +
    "shoots editoriales.",
  pricePerHour: 0, // TODO: precio real $/hora
  minHours: 3,
  openHour: 8, // 08:00
  closeHour: 22, // 22:00 (último inicio razonable)
  features: [
    { label: "Superficie", value: "— m²" },
    { label: "Ciclorama", value: "Infinito" },
    { label: "Altura", value: "— m" },
    { label: "Climatización", value: "Sí" },
  ],
  gallery: 6, // cantidad de placeholders hasta que haya fotos reales
  faq: [
    {
      q: "¿Cuál es el mínimo de reserva?",
      a: "El mínimo es de 3 horas. Para producciones más cortas, escribinos por WhatsApp y vemos.",
    },
    {
      q: "¿Cómo se abona?",
      a: "Aceptamos transferencia bancaria, MercadoPago y efectivo. Se reserva con un 50% del total al confirmar la fecha.",
    },
    {
      q: "¿Puedo llevar equipo extra?",
      a: "Sí, podés traer cualquier equipo propio. Si necesitás algo puntual también podés alquilarlo en Rambla y armar todo en un único pedido.",
    },
    {
      q: "¿Tienen estacionamiento?",
      a: "Estacionamiento sobre la calle (zona azul gratuita los fines de semana). Para descarga rápida de equipos hay acceso directo.",
    },
    {
      q: "¿Incluye asistente / iluminador?",
      a: "Por defecto el estudio se reserva sin staff. Si necesitás un asistente o iluminador, lo coordinamos aparte — escribinos antes.",
    },
    {
      q: "¿Puedo cancelar o reagendar?",
      a: "Hasta 48 hs antes del shoot podés reagendar sin costo. Cancelaciones con menos aviso pierden la seña.",
    },
  ],
  addon: {
    name: "Pack Todo Incluido",
    description:
      "Todas las luces y griperías del estudio sin pensar en sumar ítem por ítem. " +
      "Llegás con la cámara y filmás.",
    pricePerDay: 0, // TODO: monto fijo por día
    includes: [
      "Set de luces continuas (LED COB) + flash de estudio",
      "Modificadores: softbox, beauty dish, paraguas, snoot",
      "C-stands, banderas, brazos mágicos y clamps",
      "Trípodes, cabezales y monitor de referencia",
      "Fondos de papel (blanco, negro, gris)",
      "Sistema de fondo motorizado",
    ],
  },
};

export const STUDIO_PHONE = "5492235852510";

export type StudioBooking = {
  date: Date;
  startHour: number; // 0-23
  startMinute: 0 | 30;
  durationHours: number;
  withAddon: boolean;
};

export function studioTotal(b: {
  durationHours: number;
  withAddon: boolean;
}): number {
  const base = STUDIO.pricePerHour * b.durationHours;
  const addon = b.withAddon ? STUDIO.addon.pricePerDay : 0;
  return base + addon;
}
