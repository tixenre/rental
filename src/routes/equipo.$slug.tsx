/**
 * Ficha pública de un equipo individual — /equipo/{id}.
 *
 * Reemplaza al modal anterior (EquipmentDetailDialog). Cada equipo tiene
 * URL única indexable por Google, meta tags propios y JSON-LD Product
 * schema para rich snippets en SERP.
 *
 * Carga inicial vía loader (pre-fetch) para que el HTML inicial tenga el
 * equipo cargado antes del render — mejor UX y SEO friendly.
 */

import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ArrowLeft, Plus, Sparkles, Share2, Check, ChevronDown, Maximize2 } from "lucide-react";

import { PublicLayout } from "@/components/rental/PublicLayout";
import { EmptyImage } from "@/components/rental/EmptyImage";
import { KitSection } from "@/components/rental/KitSection";
import { KeywordChips } from "@/components/rental/KeywordChips";
import { StepperPill } from "@/components/rental/equipment/shared/StepperPill";
import { SpecsGrid } from "@/components/rental/equipment/shared/SpecsGrid";
import { Lightbox } from "@/components/rental/Lightbox";
import { backendToEquipment } from "@/hooks/useEquipos";
import { useCart } from "@/lib/cart-store";
import { formatARS } from "@/lib/format";
import { useClienteSession, aplicaIva } from "@/lib/iva";
import { priceBreakdown } from "@/lib/pricing";
import { buildEquipoSlug } from "@/lib/equipo-slug";
import { buildCategoriaSlug } from "@/lib/categoria-slug";
import { type Equipment } from "@/data/equipment";

const SITE_URL = "https://ramblarental.com";

async function fetchEquipo(id: string): Promise<Equipment | null> {
  const res = await fetch(`/api/equipos/${id}`);
  if (!res.ok) return null;
  const raw = await res.json();
  return backendToEquipment(raw);
}

export const Route = createFileRoute("/equipo/$slug")({
  loader: async ({ params, context }) => {
    const ctx = context as {
      queryClient?: {
        fetchQuery: <T>(opts: { queryKey: unknown[]; queryFn: () => Promise<T> }) => Promise<T>;
      };
    };
    const qc = ctx.queryClient;
    if (qc) {
      return qc.fetchQuery({
        queryKey: ["equipo", params.slug],
        queryFn: () => fetchEquipo(params.slug),
      });
    }
    return fetchEquipo(params.slug);
  },
  head: ({ loaderData }) => {
    const equipo = loaderData as Equipment | null;
    if (!equipo) {
      return {
        meta: [
          { title: "Equipo no encontrado — Rambla Rental" },
          { name: "robots", content: "noindex" },
        ],
      };
    }
    const title = `${equipo.name} — Rambla Rental`;
    const desc =
      equipo.description ||
      `${equipo.brand} ${equipo.name} para alquilar por jornada en Rambla Rental, Mar del Plata.`;
    const truncatedDesc = desc.length > 160 ? desc.slice(0, 157) + "..." : desc;
    // URL canónica = slug-id. Aunque el visitor haya llegado con solo /equipo/47,
    // le decimos a Google que indexe /equipo/<slug>-47.
    const canonicalSlug = buildEquipoSlug(equipo);
    const url = `${SITE_URL}/equipo/${canonicalSlug}`;
    // Si fotoUrl es absoluta (Supabase Storage la devuelve así) la usamos
    // directo; si por alguna razón vino relativa, le ponemos el host.
    const rawImage = equipo.fotoUrl || `${SITE_URL}/icon-512.png`;
    const image = rawImage.startsWith("http") ? rawImage : `${SITE_URL}${rawImage}`;

    return {
      meta: [
        { title },
        { name: "description", content: truncatedDesc },
        // Open Graph
        { property: "og:type", content: "product" },
        { property: "og:url", content: url },
        { property: "og:title", content: title },
        { property: "og:description", content: truncatedDesc },
        { property: "og:image", content: image },
        // Dimensiones explícitas: WhatsApp e Instagram las usan para
        // generar el preview sin tener que descargar la imagen primero.
        { property: "og:image:width", content: "1200" },
        { property: "og:image:height", content: "630" },
        { property: "og:image:alt", content: `${equipo.brand} ${equipo.name}` },
        { property: "og:locale", content: "es_AR" },
        { property: "og:site_name", content: "Rambla Rental" },
        // Twitter Cards
        { name: "twitter:card", content: "summary_large_image" },
        { name: "twitter:title", content: title },
        { name: "twitter:description", content: truncatedDesc },
        { name: "twitter:image", content: image },
        // Producto específico
        { property: "product:brand", content: equipo.brand },
        {
          property: "product:price:amount",
          content: String(equipo.pricePerDay),
        },
        { property: "product:price:currency", content: "ARS" },
      ],
      links: [{ rel: "canonical", href: url }],
      scripts: [
        {
          type: "application/ld+json",
          children: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "Product",
            name: equipo.name,
            description: truncatedDesc,
            brand: { "@type": "Brand", name: equipo.brand },
            category: equipo.category,
            image: image,
            url: url,
            offers: {
              "@type": "Offer",
              priceCurrency: "ARS",
              price: equipo.pricePerDay,
              availability:
                (equipo.cantidad ?? 0) > 0
                  ? "https://schema.org/InStock"
                  : "https://schema.org/OutOfStock",
              priceSpecification: {
                "@type": "UnitPriceSpecification",
                price: equipo.pricePerDay,
                priceCurrency: "ARS",
                unitText: "jornada",
              },
            },
          }),
        },
        // BreadcrumbList: Inicio → Categoría → Equipo. Google muestra el
        // camino en SERP en vez de la URL fea — mejor CTR.
        {
          type: "application/ld+json",
          children: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            itemListElement: [
              {
                "@type": "ListItem",
                position: 1,
                name: "Inicio",
                item: `${SITE_URL}/`,
              },
              ...(equipo.category
                ? [
                    {
                      "@type": "ListItem",
                      position: 2,
                      name: equipo.category,
                      item: `${SITE_URL}/categoria/${buildCategoriaSlug(equipo.category)}`,
                    },
                  ]
                : []),
              {
                "@type": "ListItem",
                position: equipo.category ? 3 : 2,
                name: equipo.name,
              },
            ],
          }),
        },
      ],
    };
  },
  component: EquipoPage,
});

function EquipoPage() {
  const { slug } = Route.useParams();
  const navigate = useNavigate();
  const {
    data: equipo,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["equipo", slug],
    queryFn: () => fetchEquipo(slug),
    staleTime: 60_000,
  });

  // Redirect a la URL canónica con slug-id si el visitor llegó con solo el ID
  // (back-compat). Mejor para SEO — Google ve la canónica con keywords.
  useEffect(() => {
    if (!equipo) return;
    const canonical = buildEquipoSlug(equipo);
    if (slug !== canonical) {
      navigate({ to: "/equipo/$slug", params: { slug: canonical }, replace: true });
    }
  }, [equipo, slug, navigate]);

  if (isLoading) {
    return (
      <PublicLayout>
        <div className="max-w-4xl mx-auto w-full px-6 py-10 text-center text-muted-foreground">
          Cargando equipo…
        </div>
      </PublicLayout>
    );
  }

  if (isError || !equipo) {
    return (
      <PublicLayout>
        <div className="max-w-4xl mx-auto w-full px-6 py-10">
          <button
            onClick={() => navigate({ to: "/" })}
            className="text-sm text-muted-foreground hover:text-ink transition flex items-center gap-1.5 mb-6"
          >
            <ArrowLeft className="h-4 w-4" /> Volver al catálogo
          </button>
          <h1 className="font-display text-3xl text-ink mb-2">Equipo no encontrado</h1>
          <p className="text-sm text-muted-foreground">
            Tal vez fue retirado del catálogo o el link es viejo. Volvé al catálogo para ver lo
            disponible.
          </p>
        </div>
      </PublicLayout>
    );
  }

  return (
    <PublicLayout>
      <div className="max-w-7xl mx-auto w-full px-4 md:px-8 py-6 md:py-10">
        <EquipmentDetailBody item={equipo} />
      </div>
    </PublicLayout>
  );
}

// ── Body del detalle — extraído para poder eventualmente reusar en otros contextos ──

function EquipmentDetailBody({ item }: { item: Equipment }) {
  const navigate = useNavigate();
  const qty = useCart((s) => s.items[item.id] ?? 0);
  const add = useCart((s) => s.add);
  const remove = useCart((s) => s.remove);
  const jornadas = useCart((s) => s.days());
  const hasDateRange = useCart((s) => !!s.startDate && !!s.endDate);
  const price = priceBreakdown(item.pricePerDay, jornadas, 1);
  const showPeriodTotal = hasDateRange && jornadas > 1;
  // Ficha técnica: abierta por default si son pocas specs, colapsada si hay muchas.
  // La ficha técnica es el corazón de la página → visible por default.
  const [specsOpen, setSpecsOpen] = useState(true);
  const [descExpanded, setDescExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState(0);

  // Galería del lightbox: foto principal + fotos de los items del kit (si
  // los hay). Permite al cliente explorar el equipo en detalle. Se filtran
  // los items sin foto.
  const lightboxPhotos: Array<{ url: string; alt: string }> = (() => {
    const out: Array<{ url: string; alt: string }> = [];
    if (item.fotoUrl) out.push({ url: item.fotoUrl, alt: item.name });
    for (const inc of item.includes ?? []) {
      if (inc.fotoUrl) out.push({ url: inc.fotoUrl, alt: inc.name });
    }
    return out;
  })();

  const DESC_LIMIT = 320;
  const desc = item.description ?? "";
  const isLongDesc = desc.length > DESC_LIMIT;
  const shownDesc = !isLongDesc || descExpanded ? desc : desc.slice(0, DESC_LIMIT).trimEnd() + "…";
  const cap = item.cantidad ?? Infinity;
  const sinStock = cap <= 0;
  const canAddMore = qty < cap;

  const handleShare = async () => {
    if (typeof window === "undefined") return;
    const url = `${window.location.origin}/equipo/${item.id}`;
    try {
      if (navigator.share) {
        await navigator.share({ title: item.name, url });
      } else {
        await navigator.clipboard.writeText(url);
        setCopied(true);
        setTimeout(() => setCopied(false), 1800);
      }
    } catch {
      /* cancelled */
    }
  };

  return (
    <article className="space-y-6">
      {/* Breadcrumb + back */}
      <nav className="flex items-center gap-3 text-xs">
        <button
          onClick={() => navigate({ to: "/" })}
          className="flex items-center gap-1.5 text-muted-foreground hover:text-ink transition"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Volver al catálogo
        </button>
        <span className="text-muted-foreground/40">/</span>
        <span className="text-muted-foreground">{item.category}</span>
      </nav>

      {/* Header con marca, nombre, badges */}
      <header className="space-y-2">
        <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground flex-wrap">
          <span>{item.brand}</span>
          <span>·</span>
          {/* Categorías como chips: clickeables, deep-link al catálogo
           *  filtrado. Si el equipo tiene refs M2M (root + sub-cats),
           *  mostramos todas; si no, caemos al `category` (root inferido). */}
          {(item.categorias && item.categorias.length > 0
            ? item.categorias
            : [{ id: -1, nombre: item.category, parent_id: null }]
          ).map((c) => (
            <Link
              key={`${c.id}-${c.nombre}`}
              to="/"
              search={{ cat: c.nombre }}
              className="rounded-full border hairline px-2 py-0.5 normal-case tracking-normal text-muted-foreground hover:border-foreground/40 hover:text-ink transition"
            >
              {c.nombre}
            </Link>
          ))}
          {item.isNew && (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-ink px-1.5 py-0.5 text-amber">
              <Sparkles className="h-2.5 w-2.5" /> nuevo
            </span>
          )}
          {item.destacado && (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-amber/15 text-ink px-1.5 py-0.5">
              ★ destacado
            </span>
          )}
        </div>
        <div className="flex items-start justify-between gap-3">
          <h1 className="font-display text-3xl md:text-4xl text-ink leading-tight">{item.name}</h1>
          <button
            onClick={handleShare}
            className="flex items-center gap-1.5 rounded-full border hairline px-3 py-1.5 text-xs hover:border-foreground/40 transition shrink-0"
            aria-label="Compartir"
          >
            {copied ? <Check className="h-3.5 w-3.5" /> : <Share2 className="h-3.5 w-3.5" />}
            <span className="hidden sm:inline">{copied ? "Copiado" : "Compartir"}</span>
          </button>
        </div>
      </header>

      {/* Precio + agregar (sticky en mobile bottom bar). En desktop el precio
       *  vive en la columna derecha sticky. */}
      <div className="md:hidden sticky bottom-0 -mx-4 z-10 bg-background border-t hairline px-4 py-3 flex items-center justify-between gap-3">
        <PriceBlock price={price} item={item} showPeriodTotal={showPeriodTotal} />
        <CartButtons
          qty={qty}
          sinStock={sinStock}
          canAddMore={canAddMore}
          onAdd={() => add(item.id)}
          onRemove={() => remove(item.id)}
        />
      </div>

      {/* Layout desktop: 2 columnas iguales — visual izquierda, técnica derecha.
       *  Mobile: columna única, técnica primero (el cliente quiere saber specs). */}
      <div className="space-y-6 md:space-y-0 md:grid md:grid-cols-2 md:gap-10 md:items-start">
        {/* ── Columna izquierda: foto + kit + descripción ── */}
        <div className="space-y-6">
          {/* Foto hero */}
          <button
            type="button"
            onClick={() => setLightboxOpen(true)}
            disabled={!item.fotoUrl}
            className="relative aspect-[4/3] w-full overflow-hidden rounded-xl bg-white border hairline group cursor-zoom-in disabled:cursor-default"
            aria-label={item.fotoUrl ? `Ver foto ampliada de ${item.name}` : item.name}
          >
            {item.fotoUrl ? (
              <>
                <img
                  src={item.fotoUrl}
                  alt={item.name}
                  loading="eager"
                  decoding="async"
                  fetchPriority="high"
                  className="h-full w-full object-contain p-4 transition group-hover:scale-[1.01]"
                />
                <span className="absolute bottom-2 right-2 inline-flex items-center gap-1 rounded-full bg-ink/70 text-white text-[10px] font-medium px-2 py-1 opacity-0 group-hover:opacity-100 transition pointer-events-none">
                  <Maximize2 className="h-3 w-3" /> Ampliar
                </span>
              </>
            ) : (
              <EmptyImage category={item.category} brand={item.brand} />
            )}
          </button>

          {/* Precio + agregar (desktop — en la col visual) */}
          <div className="hidden md:flex items-center justify-between gap-3 rounded-xl border hairline bg-surface px-4 py-3">
            <PriceBlock price={price} item={item} showPeriodTotal={showPeriodTotal} large />
            <CartButtons
              qty={qty}
              sinStock={sinStock}
              canAddMore={canAddMore}
              onAdd={() => add(item.id)}
              onRemove={() => remove(item.id)}
            />
          </div>

          {/* "Incluye" (kit) */}
          {item.includes && item.includes.length > 0 && <KitSection item={item} />}

          {/* Descripción */}
          {desc && (
            <section className="space-y-2">
              <h2 className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                Descripción
              </h2>
              <p className="text-base leading-relaxed text-foreground/90 whitespace-pre-line">
                {shownDesc}
              </p>
              {isLongDesc && (
                <button
                  type="button"
                  onClick={() => setDescExpanded((v) => !v)}
                  className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-4 transition hover:text-ink hover:underline"
                >
                  {descExpanded ? "Ver menos" : "Ver más"}
                </button>
              )}
            </section>
          )}

          {item.videoUrl && <YouTubeEmbed url={item.videoUrl} />}

          {/* Keywords — al final, son SEO más que UX */}
          {item.keywords && item.keywords.length > 0 && (
            <KeywordChips keywords={item.keywords} className="opacity-60" />
          )}
        </div>

        {/* ── Columna derecha: especificaciones técnicas ── */}
        <div className="space-y-6 md:sticky md:top-20 md:max-h-[calc(100dvh-6rem)] md:overflow-y-auto md:pr-1">
          {/* Specs clave */}
          <SpecsGrid item={item} />

          {/* Ficha técnica — abierta por default */}
          {item.specs && item.specs.length > 0 && (
            <section className="space-y-1">
              <button
                type="button"
                onClick={() => setSpecsOpen((v) => !v)}
                aria-expanded={specsOpen}
                className="flex w-full items-center justify-between gap-3 py-1 text-left transition hover:text-ink"
              >
                <h2 className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                  Ficha técnica
                  <span className="ml-2 text-ink/40">({item.specs.length})</span>
                </h2>
                <ChevronDown
                  className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${specsOpen ? "rotate-180" : ""}`}
                />
              </button>
              {specsOpen && (
                <dl className="border-t hairline pt-2">
                  {item.specs.map((s, i) => (
                    <div key={i} className="flex justify-between gap-4 border-b hairline py-2">
                      <dt className="text-sm text-muted-foreground shrink-0">{s.label}</dt>
                      <dd className="text-sm font-mono tabular-nums text-ink text-right">
                        {s.value}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
            </section>
          )}

          {item.contenidoIncluido && item.contenidoIncluido.length > 0 && (
            <ContenidoIncluidoSection items={item.contenidoIncluido} />
          )}
          {item.conectividad && item.conectividad.length > 0 && (
            <FichaPillSection title="Conectividad" items={item.conectividad} />
          )}
          {item.compatibleCon && item.compatibleCon.length > 0 && (
            <FichaPillSection title="Compatible con" items={item.compatibleCon} />
          )}
        </div>
      </div>

      <Lightbox
        open={lightboxOpen}
        onClose={() => setLightboxOpen(false)}
        photos={lightboxPhotos}
        index={lightboxIndex}
        onIndexChange={setLightboxIndex}
      />
    </article>
  );
}

function PriceBlock({
  price,
  item,
  showPeriodTotal,
  large = false,
}: {
  price: ReturnType<typeof priceBreakdown>;
  item: Equipment;
  showPeriodTotal: boolean;
  large?: boolean;
}) {
  const { data: clienteSession } = useClienteSession();
  const conIva = aplicaIva(clienteSession?.perfil_impuestos);
  return (
    <div>
      <div className={`font-display ${large ? "text-3xl" : "text-xl"} tabular text-ink`}>
        {formatARS(item.pricePerDay)}
      </div>
      <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
        / jornada{conIva ? " +IVA" : ""}
      </div>
      {showPeriodTotal && (
        <div className="mt-1 flex items-baseline gap-1.5">
          <span className={`font-display ${large ? "text-lg" : "text-sm"} tabular text-amber`}>
            {formatARS(price.total)}
          </span>
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            · {price.jornadas} jornadas{conIva ? " + IVA" : ""}
          </span>
        </div>
      )}
    </div>
  );
}

function CartButtons({
  qty,
  sinStock,
  canAddMore,
  onAdd,
  onRemove,
}: {
  qty: number;
  sinStock: boolean;
  canAddMore: boolean;
  onAdd: () => void;
  onRemove: () => void;
}) {
  if (qty === 0) {
    return (
      <button
        onClick={() => !sinStock && onAdd()}
        disabled={sinStock}
        className="inline-flex items-center gap-1.5 rounded-md bg-ink px-4 py-2.5 text-sm font-medium uppercase tracking-wider text-amber transition hover:bg-foreground disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Plus className="h-4 w-4" /> {sinStock ? "Sin stock" : "Agregar"}
      </button>
    );
  }
  // Stepper canónico de la librería (equipment/shared) — el único de la web.
  // No recrear una variante ad-hoc (MEMORIA 2026-05-29).
  return (
    <StepperPill
      qty={qty}
      size="lg"
      onIncrement={() => onAdd()}
      onDecrement={() => onRemove()}
      maxReached={!canAddMore}
    />
  );
}

function FichaPillSection({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="space-y-2">
      <h2 className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
        {title}
      </h2>
      <div className="flex flex-wrap gap-1.5">
        {items.map((it, i) => (
          <span
            key={`${title}-${i}`}
            className="inline-flex items-center rounded-md border hairline bg-background px-2 py-1 text-[12px] text-ink/90"
          >
            {it}
          </span>
        ))}
      </div>
    </section>
  );
}

function ContenidoIncluidoSection({
  items,
}: {
  items: NonNullable<import("@/data/equipment").Equipment["contenidoIncluido"]>;
}) {
  return (
    <section className="space-y-2">
      <h2 className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
        Contenido de la caja
        <span className="ml-2 text-ink/40">({items.length})</span>
      </h2>
      <ul className="grid gap-1.5 sm:grid-cols-2">
        {items.map((it, i) => {
          const qty = it.cantidad ?? 1;
          return (
            <li
              key={i}
              className="flex items-center gap-2.5 rounded-md border hairline bg-background/60 p-2"
            >
              <span
                className={`shrink-0 grid h-9 min-w-9 place-items-center rounded-md px-1.5 font-mono text-xs tabular ${
                  qty > 1 ? "bg-ink text-amber font-bold" : "bg-muted text-ink/70 sm:hidden"
                }`}
                aria-label={`Cantidad: ${qty}`}
              >
                ×{qty}
              </span>
              <div className="relative aspect-square w-12 sm:w-10 shrink-0 overflow-hidden rounded bg-muted/40">
                {it.foto_url ? (
                  <img
                    src={it.foto_url}
                    alt={it.nombre}
                    className="h-full w-full object-cover"
                    loading="lazy"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.opacity = "0";
                    }}
                  />
                ) : (
                  <div className="grid h-full w-full place-items-center">
                    <span className="text-[18px] text-muted-foreground/40">□</span>
                  </div>
                )}
              </div>
              <div className="min-w-0 flex-1 text-sm leading-snug text-ink">{it.nombre}</div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function YouTubeEmbed({ url }: { url: string }) {
  const id = (() => {
    try {
      const u = new URL(url);
      if (u.hostname === "youtu.be") return u.pathname.slice(1);
      if (u.hostname.includes("youtube.com")) {
        const v = u.searchParams.get("v");
        if (v) return v;
        const m = u.pathname.match(/\/(?:embed|shorts)\/([\w-]+)/);
        if (m) return m[1];
      }
    } catch {
      /* invalid url */
    }
    return null;
  })();
  if (!id) return null;
  return (
    <section className="space-y-2">
      <h2 className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
        Video demo
      </h2>
      <div
        className="relative w-full overflow-hidden rounded-md border hairline"
        style={{ aspectRatio: "16 / 9" }}
      >
        <iframe
          src={`https://www.youtube.com/embed/${id}`}
          title="Video demo"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
          loading="lazy"
          className="absolute inset-0 h-full w-full"
        />
      </div>
    </section>
  );
}
