// Configuración del Estudio (producto estrella).

export const STUDIO = {
  name: "El Estudio",
  tagline: "Foto y video en Mar del Plata",
  description:
    "Un espacio para producciones audiovisuales con todos los equipos de " +
    "Rambla Rental a mano. Ideal para rodajes grandes — flexible para los chicos.",
  pricePerHour: 8500,
  minHours: 3,
  openHour: 8, // 08:00
  closeHour: 22, // 22:00 (último inicio razonable)
  features: [
    { label: "Ciclorama", value: "6×6 m" },
    { label: "Climatización", value: "A/C" },
    { label: "Living", value: "Sofás + mesa" },
    { label: "Área de trabajo", value: "Mesa roja + sillas" },
    { label: "Entrada para autos", value: "Descarga directa" },
    { label: "Cocina", value: "Equipada" },
    { label: "Cortinas blackout", value: "Sí" },
    { label: "Baños + vestuario", value: "2 cabinas" },
  ],
  // Fotos reales del espacio (public/estudio/)
  photos: [
    {
      src: "/estudio/Rambla_Estudio_S7V9519-HDR.jpg",
      alt: "El Estudio — vista general",
      hero: true,
    },
    { src: "/estudio/Rambla_Estudio_S7V9483.jpg", alt: "Vista general del espacio" },
    { src: "/estudio/Rambla_Estudio_S7V9463.jpg", alt: "Ciclorama 6×6 m", ciclorama: true },
    { src: "/estudio/Rambla_Estudio_S7V9470.jpg", alt: "Living — sofás y cocina" },
    { src: "/estudio/Rambla_Estudio_S7V9475.jpg", alt: "Mesa de producción" },
    { src: "/estudio/Rambla_Estudio_S7V9489.jpg", alt: "Pendiente oval — living" },
    { src: "/estudio/Rambla_Estudio_S7V9497.jpg", alt: "Living frontal" },
    { src: "/estudio/Rambla_Estudio_S7V9499.jpg", alt: "Pared blackout + cortinas" },
    { src: "/estudio/Rambla_Estudio_S7V9516-HDR.jpg", alt: "Rincón dark con cortinas negras" },
    { src: "/estudio/Rambla_Estudio_S7V9490.jpg", alt: "Sofá desde arriba" },
    { src: "/estudio/Rambla_Estudio_S7V9491.jpg", alt: "Living con cocina amarilla" },
    { src: "/estudio/Rambla_Estudio_S7V9510-HDR-Edit.jpg", alt: "Ángulo general con mesa" },
    { src: "/estudio/Rambla_Estudio_S7V9472.jpg", alt: "Living segundo ángulo" },
    { src: "/estudio/Rambla_Estudio_S7V9523-Edit.jpg", alt: "Baños — puertas rojas" },
  ],
  gallery: 6, // fallback si no hay fotos reales
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
    pricePerDay: 15000,
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
