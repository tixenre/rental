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
import {
  ArrowLeft,
  Plus,
  Minus,
  Sparkles,
  Share2,
  Check,
  ChevronDown,
  Maximize2,
  X as XIcon,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

import { PublicLayout } from "@/components/rental/PublicLayout";
import { EmptyImage } from "@/components/rental/EmptyImage";
import { IncludedList } from "@/components/rental/IncludedList";
import { KitSection } from "@/components/rental/KitSection";
import { KeywordChips } from "@/components/rental/KeywordChips";
import { backendToEquipment } from "@/hooks/useEquipos";
import { useCart } from "@/lib/cart-store";
import { formatARS } from "@/lib/format";
import { useClienteSession, aplicaIva, IVA_RATE } from "@/lib/iva";
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

      {/* Foto — hero image: fetchPriority alta para LCP, abre lightbox al tap */}
      <button
        type="button"
        onClick={() => setLightboxOpen(true)}
        disabled={!item.fotoUrl}
        className="relative aspect-[4/3] md:aspect-[16/9] overflow-hidden rounded-lg bg-white border hairline group cursor-zoom-in disabled:cursor-default"
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
              className="h-full w-full object-contain p-6 transition group-hover:scale-[1.01]"
            />
            <span className="absolute bottom-2 right-2 inline-flex items-center gap-1 rounded-full bg-ink/70 text-white text-[10px] font-medium px-2 py-1 opacity-0 group-hover:opacity-100 transition pointer-events-none">
              <Maximize2 className="h-3 w-3" /> Ampliar
            </span>
          </>
        ) : (
          <EmptyImage category={item.category} brand={item.brand} />
        )}
      </button>

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
                    <dd className="text-right font-medium text-ink tabular whitespace-pre-line">{s.value}</dd>
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
  const totalConIva = conIva ? Math.round(price.total * (1 + IVA_RATE)) : price.total;
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
            {formatARS(totalConIva)}
          </span>
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            · {price.jornadas} jornadas{conIva ? " · IVA incluído" : ""}
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

// ─────────────────────────────────────────────────────────────────────────
// Lightbox — visor de fotos con zoom táctil y nav entre componentes del kit
// ─────────────────────────────────────────────────────────────────────────

function Lightbox({
  open, onClose, photos, index, onIndexChange,
}: {
  open: boolean;
  onClose: () => void;
  photos: Array<{ url: string; alt: string }>;
  index: number;
  onIndexChange: (i: number) => void;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft" && index > 0) onIndexChange(index - 1);
      if (e.key === "ArrowRight" && index < photos.length - 1) onIndexChange(index + 1);
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, index, photos.length, onClose, onIndexChange]);

  if (!open || photos.length === 0) return null;
  const current = photos[Math.min(index, photos.length - 1)];

  return (
    <div
      className="fixed inset-0 z-[100] bg-black/95 flex flex-col"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <header className="flex items-center justify-between px-3 sm:px-4 py-3 shrink-0 text-white/90">
        <span className="font-mono text-xs tabular-nums">
          {photos.length > 1 ? `${index + 1} / ${photos.length}` : ""}
        </span>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onClose(); }}
          className="grid h-10 w-10 place-items-center rounded-full hover:bg-white/10 transition"
          aria-label="Cerrar"
        >
          <XIcon className="h-5 w-5" />
        </button>
      </header>

      {/* Imagen — pinch-zoom nativo en mobile (touch-action: pinch-zoom). */}
      <div
        className="flex-1 flex items-center justify-center overflow-auto px-2"
        onClick={(e) => e.stopPropagation()}
        style={{ touchAction: "pinch-zoom" }}
      >
        <img
          src={current.url}
          alt={current.alt}
          loading="eager"
          decoding="async"
          className="max-h-full max-w-full object-contain select-none"
          draggable={false}
        />
      </div>

      <div
        className="px-4 py-2 text-center text-white/80 text-xs sm:text-sm shrink-0"
        onClick={(e) => e.stopPropagation()}
      >
        {current.alt}
      </div>

      {photos.length > 1 && (
        <>
          {index > 0 && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onIndexChange(index - 1); }}
              className="hidden sm:grid absolute left-3 top-1/2 -translate-y-1/2 h-12 w-12 place-items-center rounded-full bg-white/10 text-white hover:bg-white/20 transition"
              aria-label="Foto anterior"
            >
              <ChevronLeft className="h-6 w-6" />
            </button>
          )}
          {index < photos.length - 1 && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onIndexChange(index + 1); }}
              className="hidden sm:grid absolute right-3 top-1/2 -translate-y-1/2 h-12 w-12 place-items-center rounded-full bg-white/10 text-white hover:bg-white/20 transition"
              aria-label="Foto siguiente"
            >
              <ChevronRight className="h-6 w-6" />
            </button>
          )}

          <div
            className="shrink-0 flex gap-1.5 overflow-x-auto px-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] pt-2"
            onClick={(e) => e.stopPropagation()}
          >
            {photos.map((p, i) => (
              <button
                key={`${p.url}-${i}`}
                type="button"
                onClick={() => onIndexChange(i)}
                className={`h-14 w-14 shrink-0 rounded-md overflow-hidden border-2 transition ${
                  i === index ? "border-amber" : "border-transparent opacity-60 hover:opacity-100"
                }`}
                aria-label={`Ver ${p.alt}`}
              >
                <img
                  src={p.url}
                  alt=""
                  loading="lazy"
                  decoding="async"
                  className="h-full w-full object-cover bg-white"
                />
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
