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

import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Plus,
  Minus,
  Sparkles,
  Share2,
  Check,
  ChevronDown,
} from "lucide-react";

import { PublicLayout } from "@/components/rental/PublicLayout";
import { EmptyImage } from "@/components/rental/EmptyImage";
import { IncludedList } from "@/components/rental/IncludedList";
import { KitSection } from "@/components/rental/KitSection";
import { KeywordChips } from "@/components/rental/KeywordChips";
import { backendToEquipment } from "@/hooks/useEquipos";
import { useCart } from "@/lib/cart-store";
import { formatARS } from "@/lib/format";
import { priceBreakdown } from "@/lib/pricing";
import { buildEquipoSlug } from "@/lib/equipo-slug";
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
    const image = equipo.fotoUrl || `${SITE_URL}/icon-512.png`;

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
      ],
    };
  },
  component: EquipoPage,
});

function EquipoPage() {
  const { slug } = Route.useParams();
  const navigate = useNavigate();
  const { data: equipo, isLoading, isError } = useQuery({
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
          <h1 className="font-display text-3xl text-ink mb-2">
            Equipo no encontrado
          </h1>
          <p className="text-sm text-muted-foreground">
            Tal vez fue retirado del catálogo o el link es viejo. Volvé al
            catálogo para ver lo disponible.
          </p>
        </div>
      </PublicLayout>
    );
  }

  return (
    <PublicLayout>
      <div className="max-w-4xl mx-auto w-full px-4 md:px-6 py-6 md:py-10">
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
  const [specsOpen, setSpecsOpen] = useState(false);
  const [descExpanded, setDescExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
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
          <span>{item.category}</span>
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
          <h1 className="font-display text-3xl md:text-4xl text-ink leading-tight">
            {item.name}
          </h1>
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

      {/* Foto */}
      <div className="relative aspect-[4/3] md:aspect-[16/9] overflow-hidden rounded-lg bg-white border hairline">
        {item.fotoUrl ? (
          <img
            src={item.fotoUrl}
            alt={item.name}
            className="h-full w-full object-contain p-6"
          />
        ) : (
          <EmptyImage category={item.category} brand={item.brand} />
        )}
      </div>

      {/* "Incluye" arriba de todo (foto → incluye → descripción → specs).
       *  Lo más útil para el cliente al decidir el alquiler: ver qué kit
       *  viene incluido con fotos y cantidades. Solo si hay items con
       *  data rica (kit components); el componente IncludedList se sigue
       *  renderando abajo para keywords + spec highlights. */}
      {item.includes && item.includes.length > 0 && (
        <KitSection item={item} />
      )}

      {/* Precio + agregar al carrito (sticky en mobile) */}
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

      {/* Keywords */}
      {item.keywords && item.keywords.length > 0 && (
        <KeywordChips keywords={item.keywords} />
      )}

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

      <QuickFactsRow item={item} />

      {/* Specs colapsable */}
      {item.specs && item.specs.length > 0 && (
        <section className="border-t border-b hairline">
          <button
            type="button"
            onClick={() => setSpecsOpen((v) => !v)}
            aria-expanded={specsOpen}
            className="flex w-full items-center justify-between gap-3 py-4 text-left transition hover:text-ink"
          >
            <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Especificaciones
              <span className="ml-2 text-ink/60">({item.specs.length})</span>
            </span>
            <ChevronDown
              className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${specsOpen ? "rotate-180" : ""}`}
            />
          </button>
          {specsOpen && (
            <div className="pb-4">
              <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
                {item.specs.map((s, i) => (
                  <div key={i} className="flex justify-between gap-3 border-b hairline py-2 text-sm">
                    <dt className="text-muted-foreground">{s.label}</dt>
                    <dd className="text-right font-medium text-ink tabular">{s.value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </section>
      )}

      {item.incluye && item.incluye.length > 0 && (
        <FichaPillSection title="Incluye en la caja" items={item.incluye} />
      )}
      {item.conectividad && item.conectividad.length > 0 && (
        <FichaPillSection title="Conectividad" items={item.conectividad} />
      )}
      {item.compatibleCon && item.compatibleCon.length > 0 && (
        <FichaPillSection title="Compatible con" items={item.compatibleCon} />
      )}

      {item.videoUrl && <YouTubeEmbed url={item.videoUrl} />}

      {/* IncludedList: keywords + specs highlights. El kit ya se rendereó
       *  arriba via KitSection si hay items. */}
      <IncludedList item={item} />


      {/* Precio + agregar al carrito (desktop) */}
      <div className="hidden md:flex items-end justify-between gap-3 border-t hairline pt-6">
        <PriceBlock price={price} item={item} showPeriodTotal={showPeriodTotal} large />
        <CartButtons
          qty={qty}
          sinStock={sinStock}
          canAddMore={canAddMore}
          onAdd={() => add(item.id)}
          onRemove={() => remove(item.id)}
        />
      </div>
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
  return (
    <div>
      <div className={`font-display ${large ? "text-3xl" : "text-xl"} tabular text-ink`}>
        {formatARS(item.pricePerDay)}
      </div>
      <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
        / jornada
      </div>
      {showPeriodTotal && (
        <div className="mt-1 flex items-baseline gap-1.5">
          <span className={`font-display ${large ? "text-lg" : "text-sm"} tabular text-amber`}>
            {formatARS(price.total)}
          </span>
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            · {price.jornadas} jornadas
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
  return (
    <div className="flex items-center gap-1 rounded-md border border-amber/40 bg-amber-soft p-1">
      <button
        onClick={onRemove}
        className="grid h-9 w-9 place-items-center rounded text-amber hover:bg-amber/20"
        aria-label="Quitar uno"
      >
        <Minus className="h-4 w-4" />
      </button>
      <span className="w-8 text-center text-base font-semibold tabular">{qty}</span>
      <button
        onClick={() => canAddMore && onAdd()}
        disabled={!canAddMore}
        className="grid h-9 w-9 place-items-center rounded text-amber hover:bg-amber/20 disabled:opacity-40"
        aria-label="Sumar uno"
      >
        <Plus className="h-4 w-4" />
      </button>
    </div>
  );
}

function QuickFactsRow({ item }: { item: Equipment }) {
  const facts: { label: string; value: string }[] = [];
  if (item.montura) facts.push({ label: "Montura", value: item.montura });
  if (item.formato) facts.push({ label: "Formato", value: item.formato });
  if (item.resolucion) facts.push({ label: "Resolución", value: item.resolucion });
  if (item.peso) facts.push({ label: "Peso", value: item.peso });
  if (item.dimensiones) facts.push({ label: "Dimensiones", value: item.dimensiones });
  if (item.alimentacion) facts.push({ label: "Alimentación", value: item.alimentacion });
  if (facts.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5">
      {facts.map((f) => (
        <span
          key={f.label}
          className="inline-flex items-center gap-1.5 rounded-full border hairline bg-muted/30 px-2.5 py-1 text-[11px]"
        >
          <span className="font-mono uppercase tracking-wider text-muted-foreground">
            {f.label}
          </span>
          <span className="font-medium text-ink">{f.value}</span>
        </span>
      ))}
    </div>
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
    } catch { /* invalid url */ }
    return null;
  })();
  if (!id) return null;
  return (
    <section className="space-y-2">
      <h2 className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
        Video demo
      </h2>
      <div className="relative w-full overflow-hidden rounded-md border hairline" style={{ aspectRatio: "16 / 9" }}>
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
