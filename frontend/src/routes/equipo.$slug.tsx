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
import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Plus,
  Sparkles,
  Share2,
  Check,
  ChevronDown,
  Maximize2,
  AlertTriangle,
} from "lucide-react";

import { PublicLayout } from "@/components/rental/shell/PublicLayout";
import { EmptyImage } from "@/components/rental/EmptyImage";
import { KitSection, BoxItemsSection } from "@/components/rental/KitSection";
import { KeywordChips } from "@/components/rental/KeywordChips";
import { StepperPill } from "@/components/rental/equipment/shared/StepperPill";
import { Pill } from "@/design-system/ui/Pill";
import { SpecsGrid } from "@/components/rental/equipment/shared/SpecsGrid";
import { PriceBlock } from "@/components/rental/equipment/shared/PriceBlock";
import { Lightbox } from "@/components/rental/Lightbox";
import { MediaGallery } from "@/components/common/MediaGallery";
import { YouTubeEmbed } from "@/components/common/YouTubeEmbed";
import { useEntityMedia } from "@/hooks/useEntityMedia";
import { extractYoutubeId } from "@/lib/media/youtube";
import { backendToEquipment } from "@/hooks/useEquipos";
import { useCart } from "@/lib/cart-store";
import { useClienteSession, aplicaIva } from "@/lib/iva";
import { buildEquipoSlug } from "@/lib/equipo-slug";
import { buildCategoriaSlug } from "@/lib/categoria-slug";
import { SITE_URL } from "@/lib/site";
import { shareEquipo } from "@/lib/share";
import { type Equipment } from "@/data/equipment";
import { EquipoFoto } from "@/components/rental/EquipoFoto";

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
            onClick={() => navigate({ to: "/rental" })}
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
  const showPeriodTotal = hasDateRange && jornadas > 1;
  const { data: clienteSession } = useClienteSession();
  const conIva = aplicaIva(clienteSession?.perfil_impuestos);
  // Ficha técnica: abierta por default si son pocas specs, colapsada si hay muchas.
  // La ficha técnica es el corazón de la página → visible por default.
  const [specsOpen, setSpecsOpen] = useState(true);
  const [descExpanded, setDescExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  // Foto seleccionada de la galería: manda en el preview grande (hero) Y en el
  // índice donde abre el lightbox. Las miniaturas la cambian; el swipe del
  // lightbox también la sincroniza (#125).
  const [selectedPhoto, setSelectedPhoto] = useState(0);

  // Galería del lightbox (#125): fotos del equipo (equipo_fotos, principal
  // primero) + fotos de los items del kit (si los hay). Si el equipo no tiene
  // galería multi-foto, cae a la foto principal. Se deduplica por url.
  const lightboxPhotos: Array<{ url: string; alt: string }> = (() => {
    const out: Array<{ url: string; alt: string }> = [];
    const seen = new Set<string>();
    const push = (url: string | null | undefined, alt: string) => {
      if (url && !seen.has(url)) {
        seen.add(url);
        out.push({ url, alt });
      }
    };
    if (item.fotos && item.fotos.length > 0) {
      for (const f of item.fotos) push(f.url, item.name);
    } else {
      push(item.fotoUrl, item.name);
    }
    for (const inc of item.includes ?? []) push(inc.fotoUrl, inc.name);
    return out;
  })();

  // URL que se muestra en el preview grande: la foto seleccionada de la galería,
  // con fallback a la principal. Clamp por si el índice quedó fuera de rango.
  const heroUrl =
    lightboxPhotos[selectedPhoto]?.url ?? lightboxPhotos[0]?.url ?? item.fotoUrl ?? null;

  // AVIF + blur-up solo cuando el hero muestra la foto principal (la única con
  // columnas denorm AVIF/LQIP en el payload). Para una foto secundaria de la galería
  // pasamos solo {fotoUrl} → EquipoFoto cae a <img> plano sin srcset ni blur, igual
  // que antes. (Las secundarias se resuelven en #1056 vía MediaGallery/backfill.)
  const isMainHero = heroUrl === item.fotoUrl;

  const DESC_LIMIT = 320;
  const desc = item.description ?? "";
  const isLongDesc = desc.length > DESC_LIMIT;
  const shownDesc = !isLongDesc || descExpanded ? desc : desc.slice(0, DESC_LIMIT).trimEnd() + "…";
  const cap = item.cantidad ?? Infinity;
  const sinStock = cap <= 0;
  const canAddMore = qty < cap;

  // Parcialmente disponible: solo para combos con componentes best-effort.
  // Cuando hay fechas seleccionadas y algún componente best-effort no tiene stock,
  // mostramos el badge "sin [nombre]" (C2 + A2 #635).
  const startDate = useCart((s) => s.startDate);
  const endDate = useCart((s) => s.endDate);
  const bestEffortComponents = useMemo(
    () =>
      item.tipo === "combo" ? (item.includes ?? []).filter((inc) => inc.esencial === false) : [],
    [item.tipo, item.includes],
  );
  const bestEffortIds = useMemo(
    () => bestEffortComponents.map((inc) => Number(inc.id)).filter(Boolean),
    [bestEffortComponents],
  );
  const disponibilidadQ = useQuery({
    queryKey: ["disponibilidad", startDate, endDate, bestEffortIds],
    queryFn: async () => {
      if (!startDate || !endDate || bestEffortIds.length === 0) return {};
      const res = await fetch(
        `/api/disponibilidad?fecha_desde=${startDate}&fecha_hasta=${endDate}`,
      );
      if (!res.ok) return {};
      return res.json() as Promise<Record<string, number>>;
    },
    enabled: !!startDate && !!endDate && bestEffortIds.length > 0,
  });
  const faltantes = useMemo(() => {
    if (!disponibilidadQ.data || bestEffortComponents.length === 0) return [];
    return bestEffortComponents.filter((inc) => {
      const avail = disponibilidadQ.data[String(inc.id)] ?? 0;
      return avail <= 0;
    });
  }, [disponibilidadQ.data, bestEffortComponents]);

  // Assets del nuevo sistema de media (F1). Cuando haya fotos subidas via R2
  // se muestra <MediaGallery> con srcset + LQIP. Mientras no haya, la galería
  // legacy (fotos de equipo_fotos) sigue funcionando sin cambios.
  const { data: mediaAssets = [] } = useEntityMedia("equipo", parseInt(item.id, 10));
  const hasMediaAssets = mediaAssets.length > 0;

  const handleShare = async () => {
    // URL canónica (dominio oficial + slug-id), no window.location.origin.
    // Lógica compartida con las cards del catálogo — ver @/lib/share.
    const result = await shareEquipo(item);
    if (result === "copied") {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    }
  };

  return (
    <article className="space-y-6">
      {/* Breadcrumb + back */}
      <nav className="flex items-center gap-3 text-xs">
        <button
          onClick={() => navigate({ to: "/rental" })}
          className="flex items-center gap-1.5 text-muted-foreground hover:text-ink transition"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Volver al catálogo
        </button>
        <span className="text-muted-foreground/40">/</span>
        <span className="text-muted-foreground">{item.category}</span>
      </nav>

      {/* Header con marca, nombre, badges */}
      <header className="space-y-2">
        <div className="flex items-center gap-2 font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground flex-wrap">
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
              to="/rental"
              search={{ cat: c.nombre }}
              className="rounded-full border hairline px-2 py-0.5 normal-case tracking-normal text-muted-foreground hover:border-foreground/40 hover:text-ink transition"
            >
              {c.nombre}
            </Link>
          ))}
          {item.isNew && (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-ink px-1.5 py-0.5 text-[var(--area-accent)]">
              <Sparkles className="h-2.5 w-2.5" /> nuevo
            </span>
          )}
          {item.destacado && (
            <Pill className="gap-0.5 border-transparent bg-[color-mix(in_oklch,var(--area-accent)_15%,transparent)] px-1.5 text-ink">
              ★ destacado
            </Pill>
          )}
          {faltantes.length > 0 && (
            <Pill tone="warning" className="gap-1">
              <AlertTriangle className="h-2.5 w-2.5" />
              parcialmente disponible
            </Pill>
          )}
        </div>
        <div className="flex items-start justify-between gap-3">
          <h1 className="font-display text-3xl md:text-4xl text-ink leading-tight">{item.name}</h1>
          <button
            onClick={handleShare}
            className="flex items-center justify-center gap-1.5 rounded-full border hairline px-3 py-1.5 text-xs hover:border-foreground/40 transition shrink-0 min-h-11 min-w-11 sm:min-w-0"
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
        <PriceBlock perDay={item.pricePerDay} jornadas={jornadas} conIva={conIva} size="md" />
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
          {/* Galería: nuevo sistema (MediaGallery con srcset + LQIP) cuando
              haya assets subidos via R2; galería legacy mientras no. */}
          {hasMediaAssets ? (
            <MediaGallery
              assets={mediaAssets}
              alt={item.name}
              mainClassName="aspect-[4/3] rounded-xl border hairline overflow-hidden bg-white"
            />
          ) : (
            <>
              {/* Foto hero (legacy) */}
              <button
                type="button"
                onClick={() => setLightboxOpen(true)}
                disabled={!heroUrl}
                className="relative aspect-[4/3] w-full overflow-hidden rounded-xl bg-white border hairline group cursor-zoom-in disabled:cursor-default"
                aria-label={heroUrl ? `Ver foto ampliada de ${item.name}` : item.name}
              >
                {heroUrl ? (
                  <>
                    <EquipoFoto
                      foto={isMainHero ? item : { fotoUrl: heroUrl }}
                      blur={isMainHero}
                      alt={item.name}
                      sizes="(max-width: 768px) 100vw, 600px"
                      loading="eager"
                      decoding="async"
                      fetchPriority="high"
                      className="h-full w-full object-contain p-4 transition group-hover:scale-[1.01]"
                      fallback={<EmptyImage category={item.category} brand={item.brand} />}
                    />
                    <span className="absolute bottom-2 right-2 inline-flex items-center gap-1 rounded-full bg-ink/70 text-white text-2xs font-medium px-2 py-1 opacity-0 group-hover:opacity-100 transition pointer-events-none">
                      <Maximize2 className="h-3 w-3" /> Ampliar
                    </span>
                  </>
                ) : (
                  <EmptyImage category={item.category} brand={item.brand} />
                )}
              </button>

              {/* Miniaturas legacy (multi-foto #125) */}
              {lightboxPhotos.length > 1 && (
                <div
                  className="flex gap-2 overflow-x-auto pb-1"
                  role="list"
                  aria-label={`Más fotos de ${item.name}`}
                >
                  {lightboxPhotos.map((p, i) => (
                    <button
                      key={p.url}
                      type="button"
                      role="listitem"
                      onClick={() => setSelectedPhoto(i)}
                      aria-pressed={i === selectedPhoto}
                      className={`relative h-16 w-16 shrink-0 overflow-hidden rounded-lg border bg-white cursor-pointer transition ${
                        i === selectedPhoto
                          ? "border-ink ring-1 ring-ink"
                          : "hairline hover:border-ink/30"
                      }`}
                      aria-label={`Mostrar foto ${i + 1} de ${lightboxPhotos.length}`}
                    >
                      <img
                        src={p.url}
                        alt=""
                        loading="lazy"
                        decoding="async"
                        className="h-full w-full object-contain p-1"
                      />
                    </button>
                  ))}
                </div>
              )}
            </>
          )}

          {/* Precio + agregar (desktop — en la col visual) */}
          <div className="hidden md:flex items-center justify-between gap-3 card px-4 py-3">
            <PriceBlock perDay={item.pricePerDay} jornadas={jornadas} conIva={conIva} size="lg" />
            <CartButtons
              qty={qty}
              sinStock={sinStock}
              canAddMore={canAddMore}
              onAdd={() => add(item.id)}
              onRemove={() => remove(item.id)}
            />
          </div>

          {/* "Incluye" (kit / componentes del combo) */}
          {item.includes && item.includes.length > 0 && <KitSection item={item} />}

          {/* Badge de faltantes best-effort para combos */}
          {faltantes.length > 0 && (
            <div className="rounded-lg border border-amber/30 bg-amber/5 px-3 py-2.5 space-y-1">
              <p className="text-xs font-medium text-amber flex items-center gap-1.5">
                <AlertTriangle className="h-3.5 w-3.5" />
                Combo parcialmente disponible para las fechas seleccionadas
              </p>
              <ul className="text-xs text-foreground/70 space-y-0.5 pl-5 list-disc">
                {faltantes.map((f) => (
                  <li key={f.id}>
                    {f.name}
                    {(f.qty ?? 1) > 1 && ` (×${f.qty})`} — sin stock
                  </li>
                ))}
              </ul>
              <p className="text-xs text-muted-foreground">
                Podés reservar igual. Confirmaremos la disponibilidad de estos items al momento del
                pedido.
              </p>
            </div>
          )}

          {/* Descripción */}
          {desc && (
            <section className="space-y-2">
              <h2 className="t-section">Descripción</h2>
              <p className="text-base leading-relaxed text-foreground/90 whitespace-pre-line">
                {shownDesc}
              </p>
              {isLongDesc && (
                <button
                  type="button"
                  onClick={() => setDescExpanded((v) => !v)}
                  className="font-mono text-2xs uppercase tracking-widest text-muted-foreground underline-offset-4 transition hover:text-ink hover:underline"
                >
                  {descExpanded ? "Ver menos" : "Ver más"}
                </button>
              )}
            </section>
          )}

          {extractYoutubeId(item.videoUrl) && (
            <YouTubeEmbed videoId={extractYoutubeId(item.videoUrl)!} />
          )}

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
                <h2 className="t-section">
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
                      <dt className="text-base text-muted-foreground shrink-0">{s.label}</dt>
                      <dd className="text-base font-mono tabular-nums text-ink text-right">
                        {s.value}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
            </section>
          )}

          {item.contenidoIncluido && item.contenidoIncluido.length > 0 && (
            <BoxItemsSection
              title="Contenido de la caja"
              items={item.contenidoIncluido.map((it) => ({
                name: it.nombre,
                qty: it.cantidad,
                fotoUrl: it.foto_url,
              }))}
            />
          )}
          {item.conectividad && item.conectividad.length > 0 && (
            <FichaPillSection title="Conectividad" items={item.conectividad} />
          )}
          {item.compatibleCon && item.compatibleCon.length > 0 && (
            <FichaPillSection title="Compatible con" items={item.compatibleCon} />
          )}
        </div>
      </div>

      {!hasMediaAssets && (
        <Lightbox
          open={lightboxOpen}
          onClose={() => setLightboxOpen(false)}
          photos={lightboxPhotos}
          index={selectedPhoto}
          onIndexChange={setSelectedPhoto}
        />
      )}
    </article>
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
        className="inline-flex items-center justify-center gap-1.5 min-h-11 rounded-md bg-ink px-4 py-2.5 text-sm font-medium uppercase tracking-wider text-[var(--area-accent)] transition hover:bg-foreground disabled:cursor-not-allowed disabled:opacity-40"
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
      <h2 className="t-section">{title}</h2>
      <div className="flex flex-wrap gap-1.5">
        {items.map((it, i) => (
          <span
            key={`${title}-${i}`}
            className="inline-flex items-center card px-2 py-1 text-xs text-ink/90"
          >
            {it}
          </span>
        ))}
      </div>
    </section>
  );
}
