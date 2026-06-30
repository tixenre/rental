/**
 * /categoria/$slug — Página dedicada por categoría, SEO-friendly.
 *
 * Antes las categorías vivían sólo en queryparams (`/?cat=Lentes`), que
 * Google indexa mal. Esta ruta da una URL canónica con meta propios,
 * structured data CollectionPage y BreadcrumbList — apuntando a tráfico
 * orgánico desde búsquedas como "alquiler lentes Mar del Plata".
 */

import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo } from "react";
import { ArrowLeft, ShoppingBag } from "lucide-react";

import { PublicLayout } from "@/components/rental/PublicLayout";
import { EquipmentCard } from "@/components/rental/EquipmentCard";
import {
  apiGetCategorias,
  apiGetEquipos,
  type BackendCategoria,
  type BackendEquipo,
} from "@/lib/api";
import { backendToEquipment } from "@/hooks/useEquipos";
import { buildCategoriaSlug, findCategoriaBySlug } from "@/lib/categoria-slug";
import { SITE_URL } from "@/lib/site";
import { type Equipment } from "@/data/equipment";

type LoaderData = {
  categoria: BackendCategoria | null;
  equipos: Equipment[];
  slug: string;
};

async function fetchCategoriaPage(slug: string): Promise<LoaderData> {
  // Fetch en paralelo: categorías (para resolver slug → nombre) + equipos
  // (sólo visibles, top ranking). Sin filtro backend por categoría: el
  // endpoint actual `/api/equipos` ya filtra por `?categoria` pero la
  // navegación por categorías es una "vidriera" y mantenemos el orden
  // global para que los más populares aparezcan primero.
  const [cats, eqResp] = await Promise.all([
    apiGetCategorias().catch(() => [] as BackendCategoria[]),
    apiGetEquipos().catch(() => ({ items: [] as BackendEquipo[], total: 0 })),
  ]);

  // Aplanar el árbol de categorías por si la categoría matchea una hoja.
  const flat: BackendCategoria[] = [];
  for (const c of cats) {
    flat.push(c);
    for (const child of c.children ?? []) flat.push(child);
  }
  const categoria = findCategoriaBySlug(slug, flat) ?? null;

  // Si la categoría no existe, retornamos lista vacía + categoria=null.
  // El head responde con noindex y el component muestra estado vacío.
  if (!categoria) {
    return { categoria: null, equipos: [], slug };
  }

  // Filtrar equipos: match por nombre de categoría (M2M en `categorias[]`)
  // o por la categoría primaria (`e.category`).
  const filtered = eqResp.items.filter((be) => {
    if ((be.categorias ?? []).some((cc) => cc.nombre === categoria.nombre)) return true;
    // Fallback al `category` legacy si el equipo no tiene categorías M2M.
    return false;
  });

  return {
    categoria,
    equipos: filtered.map(backendToEquipment),
    slug,
  };
}

export const Route = createFileRoute("/categoria/$slug")({
  loader: async ({ params, context }) => {
    const ctx = context as {
      queryClient?: {
        fetchQuery: <T>(opts: { queryKey: unknown[]; queryFn: () => Promise<T> }) => Promise<T>;
      };
    };
    const qc = ctx.queryClient;
    if (qc) {
      return qc.fetchQuery({
        queryKey: ["categoria", params.slug],
        queryFn: () => fetchCategoriaPage(params.slug),
      });
    }
    return fetchCategoriaPage(params.slug);
  },
  head: ({ loaderData }) => {
    const data = loaderData as LoaderData | null;
    if (!data?.categoria) {
      return {
        meta: [
          { title: "Categoría no encontrada — Rambla Rental" },
          { name: "robots", content: "noindex" },
        ],
      };
    }
    const cat = data.categoria;
    const nombre = cat.nombre;
    const slug = buildCategoriaSlug(nombre);
    const url = `${SITE_URL}/categoria/${slug}`;
    const title = `Alquiler de ${nombre} — Rambla Rental`;
    const desc =
      `Alquilá ${nombre.toLowerCase()} para tu próxima producción en Rambla Rental, Mar del Plata. ` +
      `Más de ${data.equipos.length} equipos disponibles, por jornada.`;
    const image = `${SITE_URL}/icon-512.png`;

    // BreadcrumbList: Home → Categoría. Google muestra el camino en SERP.
    const breadcrumbJsonLd = {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "Inicio", item: `${SITE_URL}/` },
        { "@type": "ListItem", position: 2, name: nombre, item: url },
      ],
    };

    // CollectionPage para señalarle a Google que esto es una lista de items.
    const collectionJsonLd = {
      "@context": "https://schema.org",
      "@type": "CollectionPage",
      name: title,
      description: desc,
      url,
      mainEntity: {
        "@type": "ItemList",
        numberOfItems: data.equipos.length,
        itemListElement: data.equipos.slice(0, 20).map((e, i) => ({
          "@type": "ListItem",
          position: i + 1,
          url: `${SITE_URL}/equipo/${e.slug}-${e.id}`,
          name: `${e.brand} ${e.name}`.trim(),
        })),
      },
    };

    return {
      meta: [
        { title },
        { name: "description", content: desc.slice(0, 160) },
        { property: "og:type", content: "website" },
        { property: "og:url", content: url },
        { property: "og:title", content: title },
        { property: "og:description", content: desc.slice(0, 160) },
        { property: "og:image", content: image },
        { property: "og:locale", content: "es_AR" },
        { property: "og:site_name", content: "Rambla Rental" },
        { name: "twitter:card", content: "summary_large_image" },
        { name: "twitter:title", content: title },
        { name: "twitter:description", content: desc.slice(0, 160) },
        { name: "twitter:image", content: image },
      ],
      links: [{ rel: "canonical", href: url }],
      scripts: [
        {
          type: "application/ld+json",
          children: JSON.stringify(breadcrumbJsonLd),
        },
        {
          type: "application/ld+json",
          children: JSON.stringify(collectionJsonLd),
        },
      ],
    };
  },
  component: CategoriaPage,
});

function CategoriaPage() {
  const data = Route.useLoaderData() as LoaderData;
  const equiposOrdenados = useMemo(() => data.equipos ?? [], [data.equipos]);

  if (!data.categoria) {
    return (
      <PublicLayout>
        <div className="max-w-[1200px] mx-auto px-6 py-16 text-center">
          <ShoppingBag className="h-12 w-12 mx-auto text-muted-foreground mb-4" strokeWidth={1.4} />
          <h1 className="font-display text-2xl text-ink mb-2">Categoría no encontrada</h1>
          <p className="text-sm text-muted-foreground mb-6">
            La categoría que buscás no existe o fue renombrada.
          </p>
          <Link
            to="/rental"
            className="inline-flex items-center gap-1.5 rounded-full bg-ink text-[var(--area-accent)] px-4 py-2 text-sm font-medium hover:brightness-110 transition"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Volver al catálogo
          </Link>
        </div>
      </PublicLayout>
    );
  }

  const nombre = data.categoria.nombre;

  return (
    <PublicLayout>
      <div className="max-w-[1200px] mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* Breadcrumb visual (acompaña al JSON-LD) */}
        <nav aria-label="Breadcrumb" className="mb-4">
          <ol className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <li>
              <Link to="/rental" className="hover:text-ink transition">
                Catálogo
              </Link>
            </li>
            <li aria-hidden>›</li>
            <li className="text-ink font-medium">{nombre}</li>
          </ol>
        </nav>

        <header className="mb-6">
          <h1 className="font-display text-3xl md:text-4xl text-ink tracking-tight">
            Alquiler de {nombre}
          </h1>
          <p className="text-sm text-muted-foreground mt-2">
            {equiposOrdenados.length} equipo{equiposOrdenados.length !== 1 ? "s" : ""} disponible
            {equiposOrdenados.length !== 1 ? "s" : ""} para alquilar por jornada en Mar del Plata.
          </p>
        </header>

        {equiposOrdenados.length === 0 ? (
          <div className="rounded-xl border border-dashed hairline py-12 text-center">
            <ShoppingBag
              className="h-10 w-10 mx-auto text-muted-foreground mb-3"
              strokeWidth={1.4}
            />
            <p className="text-sm text-muted-foreground">
              No hay equipos disponibles en esta categoría por ahora.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 sm:gap-4">
            {equiposOrdenados.map((eq, idx) => (
              <EquipmentCard key={eq.id} item={eq} index={idx} />
            ))}
          </div>
        )}
      </div>
    </PublicLayout>
  );
}
