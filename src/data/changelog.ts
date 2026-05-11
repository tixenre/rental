export type ChangelogEntry = {
  number: number;
  date: string; // YYYY-MM-DD
  type: "feat" | "fix" | "chore" | "docs" | "style" | "refactor";
  title: string;
  body?: string;
  labels?: string[];
};

export const changelog: ChangelogEntry[] = [
  {
    number: 38,
    date: "2026-05-11",
    type: "fix",
    title: "Seguridad: acceso restringido a endpoints de admin",
    body: "22 endpoints del backend que no tenían autenticación ahora requieren rol admin. Cerraba una escalada de privilegios donde un cliente podía acceder a rutas de back-office.",
    labels: ["seguridad"],
  },
  {
    number: 35,
    date: "2026-05-10",
    type: "feat",
    title: "Sección Novedades en el panel de administración",
    body: "Nueva página en el back-office que muestra los cambios recientes del sistema.",
  },
  {
    number: 34,
    date: "2026-05-10",
    type: "fix",
    title: "Marcas, preview de documentos y perfil del cliente",
    body: "Fusión de marcas duplicadas, preview de PDFs en cotizaciones y nueva sección de Perfil en el portal del cliente.",
  },
  {
    number: 33,
    date: "2026-05-10",
    type: "fix",
    title: "Calidad de fotos, calendario, logos de marcas y branding",
    body: "Mejora en la calidad de búsqueda de fotos, integración de calendario en el dashboard, logos correctos por marca y mejoras de branding general.",
  },
  {
    number: 32,
    date: "2026-05-10",
    type: "fix",
    title: "Slugs de foto y ranking en carruseles",
    body: "Corrección en la detección de URLs hospedadas y mejora en el ordenamiento de carruseles por relevancia.",
  },
  {
    number: 31,
    date: "2026-05-10",
    type: "fix",
    title: "UX: grilla, estados y categorías expandibles",
    body: "Eliminación de gaps visuales en la grilla, colores de estado corregidos, categorías expandibles en la sidebar y link al catálogo arreglado.",
  },
  {
    number: 30,
    date: "2026-05-10",
    type: "fix",
    title: "Carrusel de marcas y fechas inválidas en pedidos",
    body: "Carrusel de marcas mostraba 0 equipos. Fechas inválidas (\"Invalid Date\") en la sección Mis Pedidos del portal cliente.",
  },
  {
    number: 29,
    date: "2026-05-10",
    type: "feat",
    title: "Reordenamiento de specs con drag & drop y mejoras de UX",
    body: "Sistema de specs con Kit DnD para reordenar por arrastre. Scroll restaurado al cerrar modal de producto, login funcional en portal cliente, link en Enriquecer con IA.",
  },
  {
    number: 26,
    date: "2026-05-10",
    type: "feat",
    title: "Sistema de specs robusto + imágenes PNG con fondo correcto",
    body: "Gestión completa de especificaciones técnicas. Imágenes PNG ya no muestran fondo negro. Cambios en categorías ahora se guardan correctamente.",
  },
  {
    number: 21,
    date: "2026-05-10",
    type: "feat",
    title: "Mejoras en la barra superior (TopBar)",
    body: "Logo centrado en mobile, pill con día de semana y jornadas en texto completo, barra de búsqueda alineada, toggle de vista bajo el logo.",
  },
  {
    number: 14,
    date: "2026-05-10",
    type: "feat",
    title: "Carrusel de marcas y precios editables",
    body: "Nuevo carrusel de marcas en el catálogo. Precios editables inline en el panel de administración. Flag para marcar precios manuales.",
  },
];
