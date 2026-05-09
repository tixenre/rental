// Configuración del Estudio (producto estrella).
// TODO: completar precios reales y contenido.

export const STUDIO = {
  name: "El Estudio",
  tagline: "Foto y video en Mar del Plata",
  pricePerHour: 0, // TODO: precio real $/hora
  minHours: 3,
  openHour: 8, // 08:00
  closeHour: 22, // 22:00 (último inicio razonable)
  features: [
    { label: "Superficie", value: "— m²" },
    { label: "Ciclorama", value: "Sí" },
    { label: "Altura", value: "— m" },
    { label: "Equipo fijo", value: "Sí" },
  ],
  gallery: 6, // cantidad de placeholders
  faq: [
    { q: "¿Cuál es el mínimo de horas?", a: "—" },
    { q: "¿Cómo se abona?", a: "—" },
    { q: "¿Puedo llevar equipo extra?", a: "—" },
    { q: "¿Tienen estacionamiento?", a: "—" },
  ],
  addon: {
    name: "Pack Todo Incluido",
    description:
      "Todas las luces y griperías del estudio sin pensar en sumar ítem por ítem.",
    pricePerDay: 0, // TODO: monto fijo por día
    includes: [
      "Set de luces continuo y flash",
      "Modificadores (softbox, beauty dish, paraguas)",
      "C-stands, banderas y brazos mágicos",
      "Trípodes y cabezales",
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
