import { useState, useCallback, useMemo, useRef, useEffect } from "react";
import {
  Camera,
  Sun,
  Mic,
  Layers,
  Monitor,
  Zap,
  Battery,
  Package,
  SlidersHorizontal,
  Search,
  User,
  Plus,
  ChevronUp,
  ChevronRight,
  X,
  Calendar,
  Loader2,
  Check,
  ChevronDown,
} from "lucide-react";
import { BottomSheet } from "@/components/mobile/BottomSheet";
import { useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { useEquipos, useMarcas, useCategorias } from "@/hooks/useEquipos";
import { useCart } from "@/lib/cart-store";
import { useShallow } from "zustand/react/shallow";
import { formatARS } from "@/lib/format";
import { type Equipment } from "@/data/equipment";
import { cn } from "@/lib/utils";
import { StepperPill } from "@/components/rental/equipment/shared/StepperPill";
import { PriceBlock } from "@/components/rental/equipment/shared/PriceBlock";
import { FavButton } from "@/components/rental/equipment/shared/FavButton";
import { createOrder } from "@/lib/orders";
import { authedFetch } from "@/lib/authedFetch";
import { HERO_TAGLINES_DEFAULT, parseHeroTaglines } from "@/lib/hero-taglines";
import { useHeroPhotos } from "@/lib/studio/hero-photos";
import { whatsappLink, normalizePhone } from "@/lib/whatsapp";
import { BUSINESS_PHONE } from "@/lib/business";
import { useClienteSession, aplicaIva } from "@/lib/iva";
import { toLocalISO } from "@/lib/rental-dates";
import { useCotizacion, descuentoLabel } from "@/lib/cotizacion";
import { RentalDateModal } from "@/components/rental/RentalDateModal";

function fmtDate(d: Date | null): string {
  if (!d) return "—";
  const dias = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
  const meses = [
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
  ];
  return `${dias[d.getDay()]} ${d.getDate()} ${meses[d.getMonth()]}`;
}

const POPULAR_CHIPS = ["Sony FX3", "Aputure 600d", "RØDE", "Pack boda", "Pack entrevista"];

/* ── Category icon ───────────────────────────────────────────────── */
type IconComp = React.ComponentType<{ size?: number; className?: string; strokeWidth?: number }>;

const CAT_ICONS: Record<string, IconComp> = {
  Cámaras: Camera,
  Lentes: Sun, // Aperture not in lucide-react standard; Sun as fallback
  Luces: Sun,
  Iluminación: Sun,
  Tungsteno: Sun,
  Sonido: Mic,
  Audio: Mic,
  Trípode: Layers,
  Soportes: Layers,
  Stands: Layers,
  Monitores: Monitor,
  Flash: Zap,
  Baterías: Battery,
  Filtros: SlidersHorizontal,
  Comunicación: Monitor,
  Modificadores: Sun,
  "Brazo Mágico": Layers,
  Grips: Layers,
};

function CatIcon({ cat, size = 20 }: { cat: string; size?: number }) {
  const Icon = CAT_ICONS[cat] ?? Package;
  return <Icon size={size} strokeWidth={1.5} />;
}

/* ── Shared styles ───────────────────────────────────────────────── */
const SEARCH_BG = "color-mix(in oklch, var(--background) 94%, transparent)";
const TABS_BG = "color-mix(in oklch, var(--background) 90%, transparent)";
const CARTBAR_BG = "color-mix(in oklch, var(--background) 96%, transparent)";

/* ── Rambla Seal SVG ─────────────────────────────────────────────── */
// Inline SVG en lugar de /rambla-icon-seal.png para poder invertir los
// colores via CSS cuando el topbar entra en snap (>65% scroll-amber).
// Path[0] = badge exterior, Path[1] = letra R interior.
// Estado default: badge amber, R bone.
// Estado snap (.topbar-snap): badge bone, R amber.
function RamblaSeal() {
  return (
    <svg
      className="topbar-seal shrink-0 block"
      width={34}
      height={34}
      viewBox="0 0 2000 2000"
      aria-label="Rambla"
    >
      <path
        className="seal-badge"
        d="M1930.45,949.73c-.44-.28-.88-.55-1.32-.82l-5.91-3.61c-3.19-2.29-6.58-4.35-10.13-6.19l-121.29-74.1c-49.62-30.31-68.53-93.07-43.93-145.76l63.92-136.86c37.05-79.33-25.29-169.12-112.57-162.14l-150.57,12.05c-57.96,4.64-110.15-35.02-121.21-92.1l-28.73-148.29c-16.65-85.96-119.87-121.96-186.37-65.01l-114.72,98.25c-44.16,37.82-109.7,36.42-152.2-3.26l-110.4-103.08c-64-59.75-168.66-28.21-188.99,56.95l-35.07,146.92c-13.5,56.56-67.34,93.94-125.05,86.82l-149.9-18.5c-86.89-10.72-153.03,76.31-119.42,157.16l57.99,139.48c22.32,53.69.73,115.58-50.14,143.74l-140.79,77.93c-.61.33-1.21.68-1.8,1.02-31.8,18.36-44.19,49.65-41.44,79.73-2.42,22.36,6.21,45.75,29.16,60.2.44.28.88.55,1.32.82l5.91,3.61c3.19,2.29,6.58,4.35,10.13,6.19l121.29,74.1c49.62,30.31,68.54,93.08,43.93,145.76l-63.92,136.86c-37.05,79.33,25.29,169.12,112.57,162.14l150.57-12.05c57.96-4.64,110.15,35.02,121.21,92.1l28.73,148.29c16.65,85.96,119.87,121.96,186.37,65.01l114.72-98.25c44.17-37.82,109.7-36.42,152.2,3.26l110.4,103.08c64,59.75,168.66,28.21,188.99-56.95l35.07-146.92c13.5-56.56,67.34-93.94,125.05-86.82l149.9,18.5c86.89,10.72,153.03-76.31,119.42-157.16l-57.99-139.48c-22.32-53.69-.73-115.58,50.14-143.74l140.79-77.93c.61-.33,1.21-.67,1.8-1.02,31.8-18.36,44.19-49.65,41.44-79.72,2.42-22.36-6.21-45.75-29.16-60.2Z"
      />
      <path
        className="seal-r"
        fillRule="evenodd"
        d="M915.75,1195.19c4.65.25,9.34.57,14.09.7,180.57,4.81,361.28-126.11,403.64-292.43,42.36-166.32-69.69-323.8-250.26-328.61-60.73-1.62-124.87,22.33-177.52,54.92-12.49,7.73-28.44-1.73-27.15-16.37.03-.31.05-.61.08-.92.9-10.19-7.03-18.98-17.27-18.98h-187.42c-3.01,0-5.51,2.32-5.73,5.33-3.46,46.93-27.1,395.19,9.77,700.72,7.24,59.98,58.55,104.88,118.96,104.88h123.28c3.55,0,6.27-3.07,5.69-6.57-1.81-10.9-5.72-34.52-10.67-64.49-.88-5.33,5.3-8.96,9.37-5.4,43.04,37.71,196.54,152,393.92,65.79,2.12-.93,3.54-3.07,3.54-5.39v-254.14c0-9.38-10.05-15.37-18.26-10.83-57.94,32.1-242.52,124.87-389.33,93.98-18.62-3.92-17.49-23.19,1.25-22.2ZM876.68,978.38c26.29-62.04,108.33-118.54,183.26-126.2,74.92-7.66,114.35,36.41,88.07,98.45-26.29,62.04-108.33,118.54-183.26,126.2-74.92,7.66-114.35-36.41-88.07-98.45Z"
      />
    </svg>
  );
}

/* ── HeroBanner ──────────────────────────────────────────────────── */
// Hero amber del catálogo móvil. Foto rotante + eyebrow + headline + CTA "Elegir fechas".
// El heroRef ancla el amber-on-scroll del topbar. Las fotos salen de R2 (admin)
// vía useHeroPhotos — misma fuente que el hero desktop y la página /estudio.
function HeroBanner({
  heroRef,
  equipCount,
  onDateOpen,
}: {
  heroRef: React.RefObject<HTMLDivElement | null>;
  equipCount: number;
  onDateOpen: () => void;
}) {
  const navigate = useNavigate();
  const photos = useHeroPhotos();
  const [photoIdx, setPhotoIdx] = useState(0);

  useEffect(() => {
    setPhotoIdx(0);
    if (photos.length <= 1) return;
    const id = setInterval(() => setPhotoIdx((i) => (i + 1) % photos.length), 4500);
    return () => clearInterval(id);
  }, [photos.length]);

  const { data: taglinesData } = useQuery({
    queryKey: ["settings", "hero_taglines"],
    queryFn: async () => {
      try {
        const res = await fetch("/api/settings/hero_taglines");
        if (!res.ok) return HERO_TAGLINES_DEFAULT;
        const d = await res.json();
        return parseHeroTaglines(d.value as string);
      } catch {
        return HERO_TAGLINES_DEFAULT;
      }
    },
    staleTime: 5 * 60 * 1000,
  });
  const taglines = taglinesData ?? HERO_TAGLINES_DEFAULT;

  const taglineIdx = useMemo(() => Math.floor(Math.random() * 4), []);
  const tagline = taglines[taglineIdx % taglines.length];

  return (
    <div ref={heroRef} className="bg-ink">
      {/* Foto rotante 3:2 full-bleed. Crossfade con divs de background-image
          (NO <img>): background-size:cover es a prueba de balas en todos los
          browsers — no es elemento reemplazado, no tiene fallback a tamaño
          intrínseco, nunca deja marco/letterbox blanco. El aspectRatio 3/2
          matchea la proporción nativa de las fotos del estudio → se ven enteras
          sin recorte, a todo el ancho, pegadas al topbar arriba y a la sección
          amber abajo. bg-ink tapa cualquier gap subpíxel. */}
      <div
        className="relative overflow-hidden bg-ink"
        style={{
          width: "100%",
          aspectRatio: "3 / 2",
        }}
        role="img"
        aria-label="El Estudio — Rambla Rental"
      >
        {photos.map((src, i) => (
          <div
            key={src}
            aria-hidden
            style={{
              position: "absolute",
              inset: 0,
              backgroundImage: `url(${src})`,
              backgroundSize: "cover",
              backgroundPosition: "center",
              opacity: i === photoIdx ? 1 : 0,
              transition: "opacity 900ms",
            }}
          />
        ))}
        {/* Gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-ink/30" />
        <button
          type="button"
          onClick={() => navigate({ to: "/estudio" })}
          className="absolute left-4 bottom-4 inline-flex items-center gap-1.5 bg-ink text-amber font-bold text-[13px] tracking-[-0.01em] px-4 py-2.5 rounded-full"
          style={{ zIndex: 1 }}
        >
          Conocé el estudio
          <ChevronRight size={13} strokeWidth={2.5} />
        </button>
        {/* Navigation dots */}
        <div className="absolute right-4 bottom-5 flex gap-[5px]" style={{ zIndex: 1 }}>
          {photos.map((_, i) => (
            <i
              key={i}
              className="block h-[5px] rounded-full transition-[width,background] duration-[250ms]"
              style={{
                width: i === photoIdx ? 14 : 5,
                background: i === photoIdx ? "var(--amber)" : "rgba(255,255,255,0.45)",
              }}
            />
          ))}
        </div>
      </div>

      {/* Copy section — amber. */}
      <div className="bg-amber" style={{ padding: "24px 20px 32px" }}>
        <div className="font-mono text-[9px] uppercase tracking-[0.24em] text-ink/55 mb-3">
          Catálogo · {equipCount} equipos · Mar del Plata
        </div>

        <div className="font-display text-[42px] font-black text-ink leading-[1] tracking-[-0.02em] mb-4">
          {tagline[0]}
          <br />
          {tagline[1]}
        </div>

        <p className="font-sans text-[14px] leading-[1.55] text-ink/72 mb-8">
          Cámaras, ópticas, luces, audio y soportes para producciones audiovisuales en Mar del
          Plata.
        </p>

        {/* CTA principal */}
        <button
          type="button"
          onClick={onDateOpen}
          className="w-full flex items-center justify-center gap-2 py-4 rounded-full bg-ink text-amber font-sans text-[15px] font-bold transition active:scale-[0.97]"
        >
          <Calendar size={16} />
          Elegir fechas
        </button>
      </div>
    </div>
  );
}

/* ── SheetClose button ───────────────────────────────────────────── */
function SheetClose({ onClose }: { onClose: () => void }) {
  return (
    <button
      onClick={onClose}
      className="w-[30px] h-[30px] rounded-full bg-muted grid place-items-center text-muted-foreground hover:bg-ink/10 hover:text-ink transition-colors"
    >
      <X size={14} strokeWidth={2.5} />
    </button>
  );
}

/* ── CartItem (subcomponent with per-item imgFailed state) ───────── */
function CartItem({
  eq,
  qty,
  fechaDesde,
  jornadas,
  jornadasEfectivas,
}: {
  eq: Equipment;
  qty: number;
  fechaDesde: Date | null;
  jornadas: number;
  jornadasEfectivas: number;
}) {
  const [imgFailed, setImgFailed] = useState(false);
  return (
    <div className="flex items-center gap-3 px-5 py-3.5 border-b border-hairline last:border-b-0">
      <div className="w-11 h-11 rounded-lg bg-surface border border-hairline flex items-center justify-center text-muted-foreground shrink-0 overflow-hidden">
        {eq.fotoUrl && !imgFailed ? (
          <img
            src={eq.fotoUrl}
            alt={eq.name}
            className="w-full h-full object-contain p-1"
            loading="lazy"
            onError={() => setImgFailed(true)}
          />
        ) : (
          <CatIcon cat={eq.category} size={18} />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-mono text-[8px] tracking-[0.18em] uppercase text-muted-foreground">
          {eq.brand}
        </div>
        <div className="font-sans text-sm font-bold text-ink leading-tight mt-0.5 truncate">
          {eq.name}
        </div>
        <div className="font-mono text-[10px] text-muted-foreground mt-0.5">
          {fechaDesde
            ? `${qty} × ${formatARS(eq.pricePerDay)} / jorn.`
            : `${formatARS(eq.pricePerDay)} / jornada`}
        </div>
      </div>
      <div className="shrink-0 text-right">
        <div
          className="font-mono text-sm font-bold text-ink"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {formatARS(eq.pricePerDay * qty * jornadasEfectivas)}
        </div>
        <div className="font-mono text-[9px] tracking-[0.1em] text-muted-foreground mt-0.5">
          {fechaDesde ? `${jornadas} jorn.` : "/ jorn."}
        </div>
      </div>
    </div>
  );
}

/* ── CartSheet ───────────────────────────────────────────────────── */
interface CartSheetProps {
  onClose: () => void;
  onOpenDateSheet: () => void;
  equipos: Equipment[];
  cartItems: Record<string, number>;
  jornadas: number;
  fechaDesde: Date | null;
  fechaHasta: Date | null;
  horaDesde: string;
  horaHasta: string;
}

const WA_PHONE = BUSINESS_PHONE;

function CartSheet({
  onClose,
  onOpenDateSheet,
  equipos,
  cartItems,
  jornadas,
  fechaDesde,
  fechaHasta,
  horaDesde,
  horaHasta,
}: CartSheetProps) {
  const navigate = useNavigate();
  const [solicitado, setSolicitado] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const entries = Object.entries(cartItems)
    .map(([id, qty]) => ({ eq: equipos.find((e) => e.id === id)!, qty }))
    .filter((x) => x.eq);

  // Total calculado por el BACKEND (fuente única, /api/cotizar) — mismo número
  // que el drawer desktop y el minibar. Sin fechas → estimado de una jornada
  // sin IVA ni descuento (lo decide el backend). #617.
  const hayFechas = !!fechaDesde;
  const { data: clienteSession } = useClienteSession();
  const totales = useCotizacion({
    items: entries.map(({ eq, qty }) => ({
      equipoId: eq._backendId ?? Number(eq.id),
      cantidad: qty,
    })),
    fechaDesde: hayFechas && fechaDesde ? toLocalISO(fechaDesde, horaDesde) : null,
    fechaHasta: hayFechas && fechaHasta ? toLocalISO(fechaHasta, horaHasta) : null,
  }).data;
  const { subtotal, descuentoPct, descuentoOrigen, descuentoMonto, totalNeto, conIva } = totales;

  async function handleSubmit() {
    if (entries.length === 0) return;
    if (!fechaDesde || !fechaHasta) {
      toast.error("Elegí las fechas del rental antes de solicitar.");
      return;
    }
    setSubmitting(true);
    try {
      const me = await authedFetch("/api/cliente/me");
      if (!me.ok) {
        toast.error("Debés iniciar sesión para solicitar un rental.", {
          duration: 5000,
          action: { label: "Iniciar sesión", onClick: () => navigate({ to: "/cliente/login" }) },
        });
        return;
      }
    } catch {
      toast.error("Sin conexión. Verificá tu internet.", { duration: 4000 });
      return;
    } finally {
      // only clear submitting if we returned early above
    }
    try {
      await createOrder({
        status: "solicitado",
        startDate: fechaDesde,
        endDate: fechaHasta,
        startTime: horaDesde,
        endTime: horaHasta,
        days: jornadas,
        resolvedItems: entries.map(({ eq, qty }) => ({
          id: eq.id,
          name: eq.name,
          brand: eq.brand,
          category: eq.category,
          qty,
          pricePerDay: eq.pricePerDay,
          backendId: eq._backendId,
        })),
      });
      setSolicitado(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al enviar el pedido";
      toast.error(msg, { duration: 6000 });
    } finally {
      setSubmitting(false);
    }
  }

  const waMessage = [
    "¡Hola! Acabo de solicitar un rental en Rambla:",
    ...entries.map(({ eq, qty }) => `• ${qty}× ${eq.brand} ${eq.name}`),
    fechaDesde ? `Fechas: ${fmtDate(fechaDesde)} → ${fmtDate(fechaHasta)} (${jornadas} jorn.)` : "",
    `Total estimado: ${formatARS(totalNeto)}${conIva ? " + IVA" : ""}`,
  ]
    .filter(Boolean)
    .join("\n");
  const waHref =
    whatsappLink({ phone: WA_PHONE, message: waMessage }) ??
    `https://wa.me/${normalizePhone(WA_PHONE)}`;

  return (
    <>
      <div
        className="fixed inset-0 z-[60] animate-in fade-in duration-200"
        style={{ background: "rgba(20,16,12,0.5)" }}
        onClick={onClose}
      />
      <div
        className="fixed inset-x-0 bottom-0 z-[61] bg-card flex flex-col animate-in slide-in-from-bottom duration-[260ms]"
        style={{
          height: "72%",
          maxHeight: "72%",
          borderRadius: "24px 24px 0 0",
          boxShadow: "0 -8px 40px rgba(0,0,0,0.18)",
        }}
      >
        <div className="w-9 h-1 rounded-full bg-hairline mx-auto mt-2.5 shrink-0" />
        <div className="flex items-center justify-between px-5 py-3 border-b border-hairline shrink-0">
          <span className="font-sans text-base font-bold text-ink">Tu rental</span>
          <SheetClose onClose={onClose} />
        </div>

        {/* Period summary */}
        {fechaDesde ? (
          <div
            className="flex items-center gap-0 px-5 py-3 shrink-0 border-b border-hairline"
            style={{ background: "var(--amber-soft)" }}
          >
            <div className="flex-1 flex items-center gap-2.5">
              <div>
                <div className="font-mono text-[8px] tracking-[0.2em] uppercase text-muted-foreground mb-0.5">
                  Salida
                </div>
                <div className="font-sans text-sm font-bold leading-tight text-ink">
                  {fmtDate(fechaDesde)}
                </div>
                <div className="font-mono text-[11px] text-muted-foreground mt-0.5">
                  {horaDesde}
                </div>
              </div>
              <ChevronRight size={14} className="text-muted-foreground/50 shrink-0" />
              <div>
                <div className="font-mono text-[8px] tracking-[0.2em] uppercase text-muted-foreground mb-0.5">
                  Devolución
                </div>
                <div className="font-sans text-sm font-bold leading-tight text-ink">
                  {fmtDate(fechaHasta)}
                </div>
                <div className="font-mono text-[11px] text-muted-foreground mt-0.5">
                  {horaHasta}
                </div>
              </div>
            </div>
            <div
              className="text-center shrink-0 pl-3 border-l"
              style={{ borderColor: "color-mix(in oklch, var(--amber) 40%, transparent)" }}
            >
              <div className="font-mono text-[8px] tracking-[0.2em] uppercase text-muted-foreground mb-0.5">
                Jorn.
              </div>
              <div
                style={{
                  fontFamily: "var(--font-display)",
                  fontSize: 24,
                  fontWeight: 900,
                  color: "var(--ink)",
                  lineHeight: 1,
                }}
              >
                {jornadas}
              </div>
            </div>
          </div>
        ) : (
          <div
            className="flex items-center gap-3 px-5 py-3.5 shrink-0 border-b border-hairline"
            style={{
              background: "var(--amber-soft)",
              borderTopColor: "color-mix(in oklch, var(--amber) 35%, transparent)",
            }}
          >
            <div className="flex-1">
              <div className="font-sans text-[13px] font-bold text-ink leading-tight">
                Elegí las fechas para ver el precio total
              </div>
              <div className="font-mono text-[9px] tracking-[0.15em] uppercase text-muted-foreground mt-0.5">
                Precios mostrados por jornada
              </div>
            </div>
            <button
              className="px-3.5 py-1.5 rounded-full bg-ink text-amber text-xs font-bold font-sans shrink-0 hover:bg-amber hover:text-ink transition-colors whitespace-nowrap"
              onClick={() => {
                onClose();
                onOpenDateSheet();
              }}
            >
              Asignar fechas
            </button>
          </div>
        )}

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto flex flex-col" style={{ scrollbarWidth: "none" }}>
          {/* Items */}
          {entries.map(({ eq, qty }) => (
            <CartItem
              key={eq.id}
              eq={eq}
              qty={qty}
              fechaDesde={fechaDesde}
              jornadas={jornadas}
              jornadasEfectivas={totales.jornadas}
            />
          ))}

          {/* Totals — auto margin pushes to bottom when few items */}
          <div className="border-t border-hairline mt-auto">
            <div className="flex flex-col gap-2 px-5 py-3.5">
              <div className="flex justify-between items-baseline">
                <span className="font-sans text-[13px] text-muted-foreground">
                  {hayFechas
                    ? `Subtotal · ${jornadas} ${jornadas === 1 ? "jornada" : "jornadas"}`
                    : "Subtotal · por jornada"}
                </span>
                <span className="font-mono text-[13px] font-semibold text-ink tabular-nums">
                  {formatARS(subtotal)}
                </span>
              </div>

              {descuentoPct > 0 && (
                <div className="flex items-center justify-between py-1">
                  <div className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
                    {descuentoLabel(descuentoOrigen, jornadas, clienteSession?.nombre)}
                    <span
                      className={cn(
                        "inline-flex items-center px-1.5 py-px rounded-full font-mono text-[9px] font-bold",
                        descuentoOrigen === "cliente"
                          ? "bg-verde/10 text-verde"
                          : "bg-azul/10 text-azul",
                      )}
                    >
                      −{descuentoPct}%
                    </span>
                  </div>
                  <span className="font-mono text-[13px] font-semibold text-verde tabular-nums">
                    −{formatARS(descuentoMonto)}
                  </span>
                </div>
              )}

              <div className="flex justify-between items-baseline opacity-45">
                <span className="font-sans text-[13px] text-muted-foreground">
                  Depósito de seguridad
                </span>
                <span className="font-mono text-[13px] text-muted-foreground">A definir</span>
              </div>

              <div className="flex justify-between items-baseline pt-2 border-t border-hairline mt-1">
                <span className="font-sans text-[15px] font-bold text-ink">
                  {hayFechas ? "Total" : "Estimado / jornada"}
                </span>
                <span
                  style={{
                    fontFamily: "var(--font-display)",
                    fontSize: 24,
                    fontWeight: 900,
                    color: "var(--ink)",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {formatARS(totalNeto)}
                  {conIva && (
                    <span className="font-sans text-sm font-normal text-muted-foreground">
                      {" "}
                      + IVA
                    </span>
                  )}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 pt-3 border-t border-hairline shrink-0" style={{ paddingBottom: 20 }}>
          {solicitado ? (
            <div className="flex flex-col gap-2.5">
              <div
                className="px-4 py-3 rounded-[var(--radius-lg)] border"
                style={{
                  background: "var(--amber-soft)",
                  borderColor: "color-mix(in oklch, var(--amber) 40%, transparent)",
                }}
              >
                <div className="font-sans text-sm font-bold text-ink mb-0.5">
                  ¡Listo! Rental solicitado.
                </div>
                <div className="font-sans text-xs text-muted-foreground leading-relaxed">
                  Lo revisamos manualmente y te confirmamos a la brevedad.
                </div>
              </div>
              <a
                href={waHref}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full py-3 rounded-full border-[1.5px] border-hairline bg-transparent text-ink font-sans text-sm font-semibold flex items-center justify-center gap-2 hover:border-ink hover:bg-muted transition-colors"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z" />
                  <path
                    d="M12 0C5.373 0 0 5.373 0 12c0 2.122.558 4.112 1.528 5.836L.057 23.857a.5.5 0 00.609.61l6.098-1.458A11.945 11.945 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.818 9.818 0 01-5.006-1.368l-.36-.214-3.722.89.921-3.618-.234-.373A9.818 9.818 0 1112 21.818z"
                    fillRule="evenodd"
                    clipRule="evenodd"
                  />
                </svg>
                Consultanos por WhatsApp
              </a>
            </div>
          ) : (
            <button
              className="w-full py-3.5 rounded-full bg-ink text-amber font-sans text-[15px] font-bold hover:bg-amber hover:text-ink transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={handleSubmit}
              disabled={submitting}
            >
              {submitting ? (
                <Loader2 size={18} className="animate-spin mx-auto" />
              ) : (
                "Solicitar rental"
              )}
            </button>
          )}
        </div>
      </div>
    </>
  );
}

/* ── FichaSheet ──────────────────────────────────────────────────── */
interface FichaSheetProps {
  eq: Equipment;
  onClose: () => void;
  onAddToCart: (id: string, delta: number) => void;
  inCart: number;
  jornadas: number;
  fechaDesde: Date | null;
}

function FichaSheet({ eq, onClose, onAddToCart, inCart, jornadas, fechaDesde }: FichaSheetProps) {
  const [imgFailed, setImgFailed] = useState(false);
  const specsText = eq.specs.map((s) => `${s.label}: ${s.value}`).join(" · ");

  return (
    <>
      <div
        className="fixed inset-0 z-[60] animate-in fade-in duration-200"
        style={{ background: "rgba(20,16,12,0.5)" }}
        onClick={onClose}
      />
      <div
        className="fixed inset-x-0 bottom-0 z-[61] bg-card flex flex-col animate-in slide-in-from-bottom duration-[260ms]"
        style={{
          height: "72%",
          maxHeight: "72%",
          borderRadius: "24px 24px 0 0",
          boxShadow: "0 -8px 40px rgba(0,0,0,0.18)",
        }}
      >
        <div className="w-9 h-1 rounded-full bg-hairline mx-auto mt-2.5 shrink-0" />
        <div className="flex items-start justify-between px-5 py-3 border-b border-hairline shrink-0">
          <div>
            <div className="font-mono text-[8px] tracking-[0.2em] uppercase text-muted-foreground">
              {eq.brand} · {eq.category}
            </div>
            <div className="font-sans text-base font-bold text-ink mt-0.5">{eq.name}</div>
          </div>
          <SheetClose onClose={onClose} />
        </div>

        <div className="flex-1 overflow-y-auto" style={{ scrollbarWidth: "none" }}>
          {/* Photo */}
          <div
            className="mx-5 mt-3.5 rounded-[var(--radius-lg)] border border-hairline bg-surface flex items-center justify-center text-muted-foreground overflow-hidden"
            style={{ aspectRatio: "4/3" }}
          >
            {eq.fotoUrl && !imgFailed ? (
              <img
                src={eq.fotoUrl}
                alt={eq.name}
                className="w-full h-full object-contain p-4"
                loading="lazy"
                onError={() => setImgFailed(true)}
              />
            ) : (
              <CatIcon cat={eq.category} size={48} />
            )}
          </div>

          {/* Price */}
          <div className="px-5 pt-3.5 flex justify-between items-baseline">
            <div>
              <div
                className="font-mono font-bold leading-none"
                style={{ fontSize: 22, fontVariantNumeric: "tabular-nums" }}
              >
                {fechaDesde ? formatARS(eq.pricePerDay * jornadas) : formatARS(eq.pricePerDay)}
              </div>
              <div className="font-mono text-[8px] tracking-[0.18em] uppercase text-muted-foreground mt-0.5">
                {fechaDesde ? `${jornadas} jornadas` : "/ jornada"}
              </div>
            </div>
            {eq.cantidad != null && (
              <div className="font-mono text-xs text-muted-foreground">
                {eq.cantidad} disponibles
              </div>
            )}
          </div>

          {/* Specs */}
          <div className="px-5 py-3 border-b border-hairline">
            <div className="font-mono text-[8px] tracking-[0.2em] uppercase text-muted-foreground mb-1">
              Especificaciones
            </div>
            <div className="font-sans text-[13px] text-muted-foreground leading-relaxed">
              {eq.description || specsText || "—"}
            </div>
            {eq.specs.length > 0 && (
              <div className="mt-2 flex flex-col gap-0.5">
                {eq.specs.map((s, i) => (
                  <div key={i} className="font-sans text-xs text-muted-foreground">
                    <span className="font-semibold text-ink/70">{s.label}:</span> {s.value}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Includes */}
          {eq.includes && eq.includes.length > 0 && (
            <div className="px-5 py-3 border-b border-hairline">
              <div className="font-mono text-[8px] tracking-[0.2em] uppercase text-muted-foreground mb-1.5">
                Incluye
              </div>
              <div className="flex flex-wrap gap-1.5">
                {eq.includes.map((item, i) => (
                  <span
                    key={i}
                    className="px-2.5 py-1 rounded-full border border-hairline bg-surface font-sans text-xs text-ink"
                  >
                    ✓ {item.name}
                  </span>
                ))}
              </div>
            </div>
          )}
          <div className="h-4" />
        </div>

        {/* Footer */}
        <div className="px-5 pt-3 border-t border-hairline shrink-0" style={{ paddingBottom: 20 }}>
          {inCart > 0 ? (
            <div
              className="flex items-center justify-between px-3.5 py-2.5 rounded-full"
              style={{ background: "var(--amber)", border: "1.5px solid var(--amber)" }}
            >
              <button
                className="w-9 h-9 grid place-items-center text-ink font-bold text-xl"
                onClick={() => onAddToCart(eq.id, -1)}
              >
                −
              </button>
              <span className="font-mono text-sm font-bold text-ink">{inCart} en carrito</span>
              <button
                className="w-9 h-9 grid place-items-center text-ink font-bold text-xl disabled:opacity-40"
                onClick={() => onAddToCart(eq.id, 1)}
                disabled={eq.cantidad != null && inCart >= eq.cantidad}
              >
                +
              </button>
            </div>
          ) : (
            <button
              className="w-full py-3.5 rounded-full bg-ink text-amber font-sans text-[15px] font-bold hover:bg-amber hover:text-ink transition-colors"
              onClick={() => {
                onAddToCart(eq.id, 1);
                onClose();
              }}
            >
              Agregar al carrito
            </button>
          )}
        </div>
      </div>
    </>
  );
}

/* ── EquipmentRow ────────────────────────────────────────────────── */
interface EquipmentRowProps {
  eq: Equipment;
  inCart: number;
  isExpanded: boolean;
  jornadas: number;
  fechaDesde: Date | null;
  onTap: () => void;
  onAdd: (delta: number) => void;
  onFicha: () => void;
}

function EquipmentRow({
  eq,
  inCart,
  isExpanded,
  jornadas,
  fechaDesde,
  onTap,
  onAdd,
  onFicha,
}: EquipmentRowProps) {
  const [imgFailed, setImgFailed] = useState(false);
  const { data: clienteSession } = useClienteSession();
  const conIva = aplicaIva(clienteSession?.perfil_impuestos);

  // Stock derivado de eq.cantidad (en mobile no se pasa disponibilidad por fecha).
  const sinStock = eq.cantidad === 0;
  const pocoStock = eq.cantidad != null && eq.cantidad > 0 && eq.cantidad <= 2;
  const reachedMax = eq.cantidad != null && inCart >= eq.cantidad;

  const nombrePublico = `${eq.brand} ${eq.name}`;

  const quickFacts = (
    eq.specsDestacados && eq.specsDestacados.length > 0
      ? eq.specsDestacados
      : [
          eq.montura && { label: "Montura", value: eq.montura },
          eq.formato && { label: "Formato", value: eq.formato },
          eq.resolucion && { label: "Resolución", value: eq.resolucion },
          eq.peso && { label: "Peso", value: eq.peso },
          eq.alimentacion && { label: "Alimentación", value: eq.alimentacion },
        ].filter((x): x is { label: string; value: string } => !!x)
  ).slice(0, 4);

  return (
    <div
      className={cn(
        "mb-1.5 overflow-hidden rounded-lg border transition-all duration-150",
        isExpanded
          ? "border-ink/40 bg-accent/30"
          : inCart > 0
            ? "border-amber/60 bg-amber-soft/30"
            : sinStock
              ? "hairline opacity-50"
              : "hairline bg-card",
      )}
    >
      {/* Main row */}
      <div
        className="flex cursor-pointer select-none items-center gap-2.5 p-[10px_12px_10px_10px]"
        style={{ WebkitTapHighlightColor: "transparent" }}
        onClick={onTap}
      >
        {/* Thumb cuadrado 1:1 + FavButton */}
        <div className="relative shrink-0">
          <div className="flex aspect-square w-12 items-center justify-center overflow-hidden rounded-md bg-white text-muted-foreground">
            {eq.fotoUrl && !imgFailed ? (
              <img
                src={eq.fotoUrl}
                alt={nombrePublico}
                className="h-full w-full object-contain p-1.5"
                loading="lazy"
                onError={() => setImgFailed(true)}
              />
            ) : (
              <CatIcon cat={eq.category} size={20} />
            )}
          </div>
          <FavButton itemId={String(eq.id)} size="sm" className="absolute -right-1.5 -top-1.5" />
        </div>

        {/* Info */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 font-mono text-[8px] uppercase leading-none tracking-[0.18em] text-muted-foreground">
            <span className="truncate">{eq.category}</span>
            {(sinStock || pocoStock) && (
              <span className={cn("shrink-0", sinStock ? "text-destructive" : "text-amber")}>
                · {sinStock ? "no disponible" : `${eq.cantidad} disp.`}
              </span>
            )}
          </div>
          <div className="mt-0.5 flex items-center gap-1.5">
            <span className="truncate font-sans text-[15px] font-bold leading-tight text-ink">
              {nombrePublico}
            </span>
            <ChevronDown
              className={cn(
                "h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform",
                isExpanded && "rotate-180",
              )}
            />
          </div>
        </div>

        {/* Price */}
        <PriceBlock
          perDay={eq.pricePerDay}
          jornadas={fechaDesde ? jornadas : 0}
          qty={inCart || 1}
          conIva={conIva}
          size="sm"
          align="right"
          className="shrink-0"
        />

        {/* Action */}
        <div onClick={(e) => e.stopPropagation()}>
          {inCart > 0 ? (
            <StepperPill
              qty={inCart}
              onIncrement={() => onAdd(1)}
              onDecrement={() => onAdd(-1)}
              maxReached={reachedMax}
              size="md"
            />
          ) : (
            <button
              type="button"
              aria-label={`Agregar ${nombrePublico}`}
              disabled={sinStock}
              className="grid h-[34px] w-[34px] shrink-0 place-items-center rounded-full border hairline bg-background text-ink transition-colors hover:border-amber hover:bg-amber active:scale-90 disabled:cursor-not-allowed disabled:opacity-40"
              onClick={(e) => {
                e.stopPropagation();
                if (sinStock) return;
                onAdd(1);
                onTap(); // also expand
              }}
            >
              <Plus size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Expansion panel */}
      {isExpanded && (
        <div
          className="border-t px-3.5 py-3"
          style={{
            borderTop: "1px dashed color-mix(in oklch, var(--amber) 50%, var(--hairline))",
            background: "color-mix(in oklch, var(--amber) 5%, var(--background))",
            animation: "expand-in 0.18s ease-out",
          }}
        >
          {/* Total */}
          <div className="mb-2.5 flex items-baseline justify-between border-b border-hairline pb-2.5">
            <PriceBlock
              perDay={eq.pricePerDay}
              jornadas={fechaDesde ? jornadas : 0}
              qty={inCart || 1}
              conIva={conIva}
              size="lg"
            />
            {inCart > 1 && (
              <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground">
                {inCart} unidades
              </span>
            )}
          </div>

          {/* Includes — 2 columnas */}
          {eq.includes && eq.includes.length > 0 && (
            <div className="mb-2">
              <div className="mb-1.5 font-mono text-[8px] uppercase tracking-[0.2em] text-muted-foreground">
                Incluye
              </div>
              <div className="grid grid-cols-2 gap-1">
                {eq.includes.map((item, i) => (
                  <span
                    key={i}
                    className="rounded-full border border-hairline bg-card px-2.5 py-0.5 font-sans text-[11px] text-ink"
                  >
                    <svg
                      width="8"
                      height="8"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="3"
                      strokeLinecap="round"
                      className="inline mr-1 align-middle"
                    >
                      <path d="M20 6L9 17l-5-5" />
                    </svg>
                    {item.qty ?? 1}× {item.name}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Specs destacados (top 4) */}
          {quickFacts.length > 0 && (
            <div className="mb-2.5 flex flex-wrap gap-1">
              {quickFacts.map((f) => {
                const hasValue = !!f.value?.trim();
                return (
                  <span
                    key={f.label}
                    className="inline-flex items-center gap-1.5 rounded-full border border-hairline bg-card px-2 py-0.5 font-sans text-[11px]"
                  >
                    <span className="font-mono uppercase tracking-wider text-[9px] text-muted-foreground">
                      {f.label}
                    </span>
                    {hasValue && <span className="font-medium text-ink">{f.value}</span>}
                  </span>
                );
              })}
            </div>
          )}

          {/* Ficha link */}
          <button
            className="inline-flex items-center gap-1 font-sans text-xs font-semibold text-ink border-b border-b-ink pb-px hover:text-amber hover:border-amber transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              onFicha();
            }}
          >
            Ver ficha técnica
            <ChevronRight size={12} />
          </button>
        </div>
      )}
    </div>
  );
}

/* ── Main CatalogoMovil component ────────────────────────────────── */
export function CatalogoMovil() {
  // Equipment data
  const { data: allEquipos, isLoading } = useEquipos();
  // Marcas: misma source que BrandCarousel del desktop + admin/marcas.
  // Trae logo_url, destacada, orden, popularidad_score, etc.
  const { data: marcasData } = useMarcas();
  const marcasCanonicas = useMemo(() => marcasData?.items ?? [], [marcasData?.items]);
  // Categorías canónicas (con parent_id) — usamos solo las root para los
  // cat-tabs, así no se mezclan sub-cats como "82mm" o "Montura E" que
  // aparecían cuando derivábamos del e.category del equipo.
  const { data: categoriasCanonicas = [] } = useCategorias();

  // Cart store — selector granular para evitar re-render del catálogo completo
  // ante cualquier cambio en el store (abrir drawer, cambiar fechas, etc.).
  const cart = useCart(
    useShallow((s) => ({
      items: s.items,
      add: s.add,
      remove: s.remove,
      startDate: s.startDate,
      endDate: s.endDate,
      startTime: s.startTime,
      endTime: s.endTime,
      days: s.days,
      clear: s.clear,
    })),
  );

  // Catalog state
  const [activeTab, setActiveTab] = useState("Todo");
  const [query, setQuery] = useState("");
  const [stockOnly, setStockOnly] = useState(false);
  const [selectedBrand, setSelectedBrand] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  // Date state
  // Fuente única: las fechas del alquiler viven en el cart store y las edita
  // el RentalDateModal compartido (mismo calendario que desktop). Acá solo se
  // leen para mostrarlas; la query de días bloqueados corre dentro del modal.
  const fechaDesde = cart.startDate ?? null;
  const fechaHasta = cart.endDate ?? null;
  const horaDesde = cart.startTime;
  const horaHasta = cart.endTime;
  const jornadas = cart.days();

  // Sheet state
  const [showDateSheet, setShowDateSheet] = useState(false);
  const [showCartSheet, setShowCartSheet] = useState(false);
  const [showBrandSheet, setShowBrandSheet] = useState(false);
  const [showFiltrosSheet, setShowFiltrosSheet] = useState(false);
  const [fichaEq, setFichaEq] = useState<Equipment | null>(null);

  const navigate = useNavigate();

  // Scroll state
  const scrollRef = useRef<HTMLDivElement>(null);
  const topbarRef = useRef<HTMLElement>(null);
  const heroRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    const topbar = topbarRef.current;
    if (!el) return;
    const onScroll = () => {
      // Amber-on-scroll: el topbar se tiñe amber gradualmente conforme el
      // hero amber scrollea hacia arriba. Mientras el bottom del hero está
      // bien debajo de la topbar (~53px) el progreso es 0; cuando llega
      // al topbar, progreso 1. Misma lógica que el mock hifi.
      // En 65% del progreso, el seal y el date-pill invierten colores.
      const hero = heroRef.current;
      if (topbar && hero) {
        const heroRect = hero.getBoundingClientRect();
        const containerRect = el.getBoundingClientRect();
        const relBottom = heroRect.bottom - containerRect.top;
        const progress = Math.min(1, Math.max(0, 1 - (relBottom - 53) / (heroRect.height * 0.5)));
        topbar.style.setProperty("--amber-pct", `${Math.round(progress * 100)}%`);
        topbar.classList.toggle("topbar-snap", progress > 0.65);
      }
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  const datePillLabel = useMemo(() => {
    if (!fechaDesde) return "Elegir fechas";
    const fmt = (d: Date) => {
      const dias = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
      return `${dias[d.getDay()]} ${d.getDate()}`;
    };
    return `${fmt(fechaDesde)} · ${fmt(fechaHasta!)}`;
  }, [fechaDesde, fechaHasta]);

  // Cat-tabs: solo roots (parent_id IS NULL) en orden del backend
  // (prioridad → popularidad → nombre). Antes derivábamos del e.category
  // pero el mapper a veces devolvía sub-cats ("82mm", "Montura E"),
  // entonces aparecían mezcladas en la barra.
  const categories = useMemo(() => {
    type Cat = { id?: number; nombre: string; parent_id?: number | null; total?: number };
    const cats = categoriasCanonicas as Cat[];
    const roots = cats
      .filter((c) => c.parent_id == null && (c.total ?? 0) > 0)
      .map((c) => c.nombre);
    return ["Todo", ...roots];
  }, [categoriasCanonicas]);

  // Brands para el sheet: parte del cat\u00e1logo can\u00f3nico (useMarcas, misma
  // source que BrandCarousel del desktop y /admin/equipos/marcas) y le
  // agrega el count en la categor\u00eda activa. Filtra las que no tienen
  // ning\u00fan equipo en la cat seleccionada (sino al clickearlas el listado
  // queda vac\u00edo). Orden: destacadas primero (por orden manual del admin),
  // resto alfab\u00e9tico.
  const brands = useMemo(() => {
    const counts = new Map<string, number>();
    for (const e of allEquipos) {
      if (!e.brand) continue;
      const inTab =
        activeTab === "Todo" ||
        e.category === activeTab ||
        (e.categorias ?? []).some((c) => c.nombre === activeTab);
      if (!inTab) continue;
      const k = e.brand.toLowerCase();
      counts.set(k, (counts.get(k) ?? 0) + 1);
    }

    const enriched = marcasCanonicas
      .map((m) => ({
        nombre: m.nombre,
        logo_url: m.logo_url ?? null,
        destacada: !!m.destacada,
        orden: m.orden ?? 100,
        count: counts.get(m.nombre.toLowerCase()) ?? 0,
      }))
      .filter((m) => m.count > 0);

    enriched.sort((a, b) => {
      if (a.destacada !== b.destacada) return a.destacada ? -1 : 1;
      if (a.destacada && b.destacada) return a.orden - b.orden;
      return a.nombre.localeCompare(b.nombre, "es");
    });

    return enriched;
  }, [allEquipos, activeTab, marcasCanonicas]);

  // Filtered equipment
  // Helper: matchea el activeTab contra el root del equipo o su M2M.
  // useCallback keyed en activeTab → identidad estable salvo cambio de tab,
  // así puede entrar en las deps del useMemo de filteredEquipos sin invalidarlo
  // en cada render (conducta idéntica: el filtrado ya dependía de activeTab).
  const matchesActiveTab = useCallback(
    (e: Equipment): boolean => {
      if (activeTab === "Todo") return true;
      if (e.category === activeTab) return true;
      return (e.categorias ?? []).some((c) => c.nombre === activeTab);
    },
    [activeTab],
  );

  const filteredEquipos = useMemo(() => {
    const norm = (s: string) =>
      (s ?? "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");
    return allEquipos.filter((e) => {
      const matchCat = matchesActiveTab(e);
      const matchQ =
        query === "" ||
        norm([e.name, e.brand, e.category, e.description ?? ""].join(" ")).includes(norm(query));
      const matchStock = !stockOnly || e.cantidad == null || e.cantidad > 0;
      const matchBrand = !selectedBrand || e.brand === selectedBrand;
      return matchCat && matchQ && matchStock && matchBrand;
    });
  }, [allEquipos, matchesActiveTab, query, stockOnly, selectedBrand]);

  // Filtros activos (para el badge del botón "Filtros"). Excluye categoría
  // (esa la elige el tab) y búsqueda (esa tiene su propio input visible).
  const activeFiltersCount = (stockOnly ? 1 : 0) + (selectedBrand ? 1 : 0);

  // Cart totals
  const totalItems = Object.values(cart.items).reduce((s, q) => s + q, 0);
  const totalARS = Object.entries(cart.items).reduce((s, [id, q]) => {
    const eq = allEquipos.find((e) => e.id === id);
    return s + (eq ? eq.pricePerDay * q * jornadas : 0);
  }, 0);

  const handleAddToCart = useCallback(
    (id: string, delta: number) => {
      if (delta > 0) cart.add(id);
      else cart.remove(id);
    },
    [cart],
  );

  const handleRowTap = useCallback((id: string) => {
    setExpanded((prev) => (prev === id ? null : id));
  }, []);

  const handleTabChange = useCallback((cat: string) => {
    setActiveTab(cat);
    setExpanded(null);
  }, []);

  // Height of compact search (used for category tabs top offset)
  // Cat-tabs sticky bajo el topbar (54px) + barra de búsqueda sticky (~65px).
  const TOPBAR_HEIGHT = 53;
  const SEARCH_BAR_HEIGHT = 65;
  const CAT_TABS_STICKY_TOP = TOPBAR_HEIGHT + SEARCH_BAR_HEIGHT;

  // h-dvh (dynamic viewport) respeta la URL bar de safari iOS — antes
  // h-screen dejaba el cart-bar tapado cuando safari mostraba su UI.
  return (
    <div className="flex flex-col h-dvh overflow-hidden bg-background relative">
      {/* Scroll container */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto overflow-x-hidden"
        style={{ WebkitOverflowScrolling: "touch", scrollbarWidth: "none" }}
      >
        {/* TopBar — amber-on-scroll: el background mezcla amber según
            el progreso de scroll (--amber-pct, seteado en el onScroll).
            En el snap (>65%), el seal invierte sus colores via la clase
            topbar-snap. */}
        <header
          ref={topbarRef}
          className="topbar-mobile sticky top-0 z-40 flex items-center gap-2.5 px-4 py-[10px] border-b border-hairline backdrop-blur-xl transition-colors"
          style={{
            background:
              "color-mix(in oklch, var(--amber) var(--amber-pct, 0%), color-mix(in oklch, var(--background) 90%, transparent))",
            paddingTop: "max(10px, calc(env(safe-area-inset-top) + 4px))",
          }}
        >
          <RamblaSeal />

          <button
            className="date-pill-snap flex-1 flex items-center justify-center gap-1.5 py-1.5 px-3.5 rounded-full font-sans text-xs font-semibold text-ink transition-all whitespace-nowrap"
            style={{
              border: "1.5px solid color-mix(in oklch, var(--amber) 55%, transparent)",
              background: "var(--amber-soft)",
            }}
            onClick={() => setShowDateSheet(true)}
          >
            <Calendar
              size={14}
              style={{ color: "color-mix(in oklch, var(--amber) 80%, var(--ink))", flexShrink: 0 }}
            />
            <span>{datePillLabel}</span>
            {fechaDesde && (
              <span className="font-mono text-[9px] tracking-[0.2em] uppercase text-muted-foreground">
                · {jornadas} jorn.
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => navigate({ to: "/cliente" })}
            className="user-btn-snap p-1.5 rounded-full border border-hairline text-ink hover:border-ink transition-colors"
            aria-label="Acceso clientes"
          >
            <User size={15} />
          </button>
        </header>

        {/* Hero banner amber — eyebrow + headline brand + CTA.
            Anclado al heroRef del amber-on-scroll del topbar. */}
        <HeroBanner
          heroRef={heroRef}
          equipCount={allEquipos?.length ?? 0}
          onDateOpen={() => setShowDateSheet(true)}
        />

        {/* Search bar — sticky bajo el topbar. Los chips de "Populares"
            scrollean fuera (no son sticky). */}
        <div
          className="sticky z-[39] px-4 pt-3 pb-2 backdrop-blur"
          style={{ top: TOPBAR_HEIGHT, background: TABS_BG }}
        >
          <div className="relative">
            <Search
              size={15}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"
            />
            <input
              className="w-full rounded-[var(--radius-lg)] border-[1.5px] border-hairline bg-surface font-sans text-sm py-[11px] pl-[38px] pr-9 text-ink placeholder:text-muted-foreground outline-none transition-all focus:border-amber"
              style={{ fontFamily: "var(--font-sans)" }}
              aria-label="Buscar equipos"
              placeholder="Buscar equipo, marca, pack…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery("")}
                aria-label="Limpiar búsqueda"
                className="absolute right-2 top-1/2 -translate-y-1/2 grid h-6 w-6 place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-ink transition-colors"
              >
                <X size={14} />
              </button>
            )}
          </div>
        </div>

        {/* Popular chips — scrollean fuera con el contenido */}
        <div className="px-4 pt-1 pb-2">
          <div className="flex gap-1.5 overflow-x-auto pb-0.5" style={{ scrollbarWidth: "none" }}>
            <span className="font-mono text-[8px] tracking-[0.2em] uppercase text-muted-foreground whitespace-nowrap self-center shrink-0">
              Populares:
            </span>
            {POPULAR_CHIPS.map((chip) => (
              <button
                key={chip}
                className="px-[11px] py-1 rounded-full border border-hairline bg-surface font-sans text-[11px] font-medium text-ink whitespace-nowrap shrink-0 hover:border-ink hover:bg-muted transition-all"
                onClick={() => setQuery(chip)}
              >
                {chip}
              </button>
            ))}
          </div>
        </div>

        {/* Category tabs */}
        <div
          className="sticky z-[39] border-b border-hairline backdrop-blur transition-[top] duration-150"
          style={{
            top: CAT_TABS_STICKY_TOP,
            background: TABS_BG,
          }}
        >
          <div className="flex overflow-x-auto px-4" style={{ scrollbarWidth: "none", gap: 0 }}>
            {categories.map((cat) => {
              const count =
                cat === "Todo"
                  ? allEquipos.length
                  : allEquipos.filter(
                      (e) =>
                        e.category === cat || (e.categorias ?? []).some((c) => c.nombre === cat),
                    ).length;
              return (
                <button
                  key={cat}
                  className={cn(
                    "flex items-baseline gap-1 py-[10px] pb-[9px] px-3 whitespace-nowrap shrink-0 border-b-[2.5px] transition-all",
                    activeTab === cat ? "border-amber" : "border-transparent",
                  )}
                  onClick={() => handleTabChange(cat)}
                >
                  <span
                    className={cn(
                      "font-sans text-[13px] leading-none",
                      activeTab === cat
                        ? "font-bold text-ink"
                        : "font-medium text-muted-foreground",
                    )}
                  >
                    {cat}
                  </span>
                  <span className="font-mono text-[8px] tracking-[0.15em] text-muted-foreground leading-none">
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Filter row */}
        <div className="flex items-center gap-1.5 px-4 py-2">
          <button
            className={cn(
              "flex items-center gap-1.5 px-[11px] py-[5px] rounded-full border font-sans text-[11px] font-medium text-ink transition-all",
              stockOnly
                ? "bg-amber-soft border-amber/60 font-semibold"
                : "border-hairline bg-transparent hover:border-ink hover:bg-muted",
            )}
            onClick={() => setStockOnly((s) => !s)}
          >
            {stockOnly && (
              <svg
                width="10"
                height="10"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
                strokeLinecap="round"
              >
                <path d="M20 6L9 17l-5-5" />
              </svg>
            )}
            Disponibles
          </button>
          <button
            type="button"
            onClick={() => setShowBrandSheet(true)}
            className={cn(
              "flex items-center gap-1.5 px-[11px] py-[5px] rounded-full border font-sans text-[11px] font-medium text-ink transition-all",
              selectedBrand
                ? "bg-amber-soft border-amber/60 font-semibold"
                : "border-hairline bg-transparent hover:border-ink hover:bg-muted",
            )}
          >
            {selectedBrand ?? "Marca"} ▾
          </button>
          <div className="flex-1" />
          <button
            type="button"
            onClick={() => setShowFiltrosSheet(true)}
            className={cn(
              "relative flex items-center gap-1.5 px-[11px] py-[5px] rounded-full border font-sans text-[11px] font-medium transition-all",
              activeFiltersCount > 0
                ? "border-ink text-ink"
                : "border-hairline text-muted-foreground hover:border-ink hover:text-ink",
            )}
          >
            <SlidersHorizontal size={11} />
            Filtros
            {activeFiltersCount > 0 && (
              <span className="inline-flex h-[14px] min-w-[14px] items-center justify-center rounded-full bg-ink px-1 font-mono text-[8px] font-bold text-amber">
                {activeFiltersCount}
              </span>
            )}
          </button>
        </div>

        {/* Equipment list — paddingBottom respeta safe-area-inset-bottom
            de iOS para que cuando no hay cart bar visible, el último item
            no quede tapado por el home indicator. */}
        <div
          className="flex flex-col px-4"
          style={{ paddingBottom: "calc(120px + env(safe-area-inset-bottom))" }}
        >
          {isLoading && (
            <div className="text-center py-8 text-muted-foreground font-sans text-sm">
              Cargando equipos…
            </div>
          )}
          {!isLoading && filteredEquipos.length === 0 && (
            <div className="text-center py-8 text-muted-foreground font-sans text-sm">
              Sin resultados. Probá con otra categoría o término.
            </div>
          )}
          {filteredEquipos.map((eq) => (
            <EquipmentRow
              key={eq.id}
              eq={eq}
              inCart={cart.items[eq.id] ?? 0}
              isExpanded={expanded === eq.id}
              jornadas={jornadas}
              fechaDesde={fechaDesde}
              onTap={() => handleRowTap(eq.id)}
              onAdd={(delta) => handleAddToCart(eq.id, delta)}
              onFicha={() => setFichaEq(eq)}
            />
          ))}
        </div>

        {/* CartMiniBar — paddingBottom respeta env(safe-area-inset-bottom)
            para que el home indicator de iPhone no tape el contenido. */}
        {totalItems > 0 && (
          <div
            className="sticky bottom-0 z-40 flex items-center gap-2.5 px-4 cursor-pointer border-t-[1.5px] border-amber backdrop-blur-lg transition-colors hover:bg-amber/5"
            style={{
              background: CARTBAR_BG,
              boxShadow: "0 -8px 24px -8px rgba(0,0,0,0.12)",
              paddingTop: 10,
              paddingBottom: "max(14px, calc(env(safe-area-inset-bottom) + 8px))",
              animation: "slide-up 0.2s cubic-bezier(.32,.72,0,1)",
              WebkitTapHighlightColor: "transparent",
            }}
            onClick={() => setShowCartSheet(true)}
          >
            <div className="flex-1">
              <div className="font-sans text-[13px] font-bold text-ink leading-tight">
                {totalItems} {totalItems === 1 ? "ítem" : "ítems"}
              </div>
              <div className="font-mono text-[8px] tracking-[0.2em] uppercase text-muted-foreground mt-0.5">
                {fechaDesde ? `${jornadas} jornadas` : "elegí fechas"}
              </div>
            </div>
            <div className="flex-1" />
            <div className="text-right">
              <div className="font-mono text-[8px] tracking-[0.2em] uppercase text-muted-foreground">
                Total
              </div>
              <div
                className="font-mono font-bold text-ink leading-none"
                style={{ fontSize: 18, fontVariantNumeric: "tabular-nums" }}
              >
                {formatARS(totalARS)}
              </div>
            </div>
            <ChevronUp
              size={16}
              className="text-muted-foreground hover:text-ink transition-colors shrink-0"
            />
          </div>
        )}
      </div>

      {/* Sheets */}
      {fichaEq && (
        <FichaSheet
          eq={fichaEq}
          onClose={() => setFichaEq(null)}
          onAddToCart={handleAddToCart}
          inCart={cart.items[fichaEq.id] ?? 0}
          jornadas={jornadas}
          fechaDesde={fechaDesde}
        />
      )}
      <RentalDateModal open={showDateSheet} onOpenChange={setShowDateSheet} />
      {showCartSheet && (
        <CartSheet
          onClose={() => setShowCartSheet(false)}
          onOpenDateSheet={() => setShowDateSheet(true)}
          equipos={allEquipos}
          cartItems={cart.items}
          jornadas={jornadas}
          fechaDesde={fechaDesde}
          fechaHasta={fechaHasta}
          horaDesde={horaDesde}
          horaHasta={horaHasta}
        />
      )}
      <BrandSheet
        open={showBrandSheet}
        onOpenChange={setShowBrandSheet}
        brands={brands}
        selected={selectedBrand}
        onSelect={setSelectedBrand}
      />
      <FiltrosSheet
        open={showFiltrosSheet}
        onOpenChange={setShowFiltrosSheet}
        stockOnly={stockOnly}
        onStockToggle={() => setStockOnly((v) => !v)}
        selectedBrand={selectedBrand}
        onBrandClear={() => setSelectedBrand(null)}
        onOpenBrandSheet={() => {
          setShowFiltrosSheet(false);
          setShowBrandSheet(true);
        }}
        activeFiltersCount={activeFiltersCount}
        onClearAll={() => {
          setStockOnly(false);
          setSelectedBrand(null);
          setShowFiltrosSheet(false);
        }}
      />
    </div>
  );
}

/* ── BrandSheet ──────────────────────────────────────────────────── */
type BrandSheetItem = {
  nombre: string;
  logo_url: string | null;
  destacada: boolean;
  count: number;
};

function BrandSheet({
  open,
  onOpenChange,
  brands,
  selected,
  onSelect,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  brands: BrandSheetItem[];
  selected: string | null;
  onSelect: (brand: string | null) => void;
}) {
  return (
    <BottomSheet open={open} onOpenChange={onOpenChange} title="Marca" showClose>
      <div className="px-4 py-3 space-y-1">
        <button
          type="button"
          onClick={() => {
            onSelect(null);
            onOpenChange(false);
          }}
          className={cn(
            "w-full flex items-center justify-between gap-2 rounded-lg px-3 py-3 text-left transition",
            selected === null
              ? "bg-amber-soft border border-amber/40"
              : "border border-hairline hover:bg-muted",
          )}
        >
          <span className="font-sans text-sm font-semibold text-ink">Todas las marcas</span>
          {selected === null && <Check className="h-4 w-4 text-amber" />}
        </button>
        {brands.map((b) => {
          const active = selected === b.nombre;
          return (
            <button
              key={b.nombre}
              type="button"
              onClick={() => {
                onSelect(active ? null : b.nombre);
                onOpenChange(false);
              }}
              className={cn(
                "w-full flex items-center justify-between gap-2 rounded-lg px-3 py-2.5 text-left transition",
                active
                  ? "bg-amber-soft border border-amber/40"
                  : "border border-hairline hover:bg-muted",
              )}
            >
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <BrandLogo nombre={b.nombre} logo_url={b.logo_url} />
                <div className="min-w-0 flex-1">
                  <div className="font-sans text-sm font-semibold text-ink truncate">
                    {b.nombre}
                  </div>
                  {b.destacada && (
                    <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-amber/80 mt-0.5">
                      Destacada
                    </div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                  {b.count}
                </span>
                {active && <Check className="h-4 w-4 text-amber" />}
              </div>
            </button>
          );
        })}
        {brands.length === 0 && (
          <div className="text-center py-8 text-sm text-muted-foreground">
            No hay marcas con equipos en la categoría actual.
          </div>
        )}
      </div>
    </BottomSheet>
  );
}

function BrandLogo({ nombre, logo_url }: { nombre: string; logo_url: string | null }) {
  const [failed, setFailed] = useState(false);
  if (logo_url && !failed) {
    return (
      <div className="h-9 w-9 rounded-md bg-white border border-hairline grid place-items-center shrink-0 overflow-hidden p-1">
        <img
          src={logo_url}
          alt={nombre}
          className="max-h-full max-w-full object-contain"
          loading="lazy"
          onError={() => setFailed(true)}
        />
      </div>
    );
  }
  // Fallback: cuadradito con las iniciales (estilo de BrandCard del desktop).
  const inicial = (nombre[0] ?? "?").toUpperCase();
  return (
    <div className="h-9 w-9 rounded-md bg-muted border border-hairline grid place-items-center shrink-0 font-display text-base font-black text-ink">
      {inicial}
    </div>
  );
}

/* ── FiltrosSheet ────────────────────────────────────────────────── */
function FiltrosSheet({
  open,
  onOpenChange,
  stockOnly,
  onStockToggle,
  selectedBrand,
  onBrandClear,
  onOpenBrandSheet,
  activeFiltersCount,
  onClearAll,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  stockOnly: boolean;
  onStockToggle: () => void;
  selectedBrand: string | null;
  onBrandClear: () => void;
  onOpenBrandSheet: () => void;
  activeFiltersCount: number;
  onClearAll: () => void;
}) {
  return (
    <BottomSheet
      open={open}
      onOpenChange={onOpenChange}
      title="Filtros"
      showClose
      footer={
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onClearAll}
            disabled={activeFiltersCount === 0}
            className="flex-1 py-3 rounded-full border-[1.5px] border-hairline font-sans text-sm font-semibold text-ink transition hover:border-ink hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Limpiar
          </button>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="flex-1 py-3 rounded-full bg-ink text-amber font-sans text-sm font-bold transition hover:bg-amber hover:text-ink"
          >
            Aplicar
          </button>
        </div>
      }
    >
      <div className="px-4 py-3 space-y-3">
        {/* Disponibles toggle */}
        <div className="rounded-lg border border-hairline px-3.5 py-3 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="font-sans text-sm font-semibold text-ink">Disponibles</div>
            <div className="font-mono text-[10px] text-muted-foreground mt-0.5">
              Esconder equipos sin stock para tus fechas
            </div>
          </div>
          <button
            type="button"
            onClick={onStockToggle}
            role="switch"
            aria-checked={stockOnly}
            className={cn(
              "relative h-6 w-11 rounded-full transition shrink-0",
              stockOnly ? "bg-amber" : "bg-muted",
            )}
          >
            <span
              className={cn(
                "absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform",
                stockOnly && "translate-x-5",
              )}
            />
          </button>
        </div>

        {/* Marca selector */}
        <button
          type="button"
          onClick={onOpenBrandSheet}
          className="w-full rounded-lg border border-hairline px-3.5 py-3 flex items-center justify-between gap-3 hover:bg-muted transition text-left"
        >
          <div className="min-w-0">
            <div className="font-sans text-sm font-semibold text-ink">Marca</div>
            <div className="font-mono text-[10px] text-muted-foreground mt-0.5 truncate">
              {selectedBrand ?? "Todas"}
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {selectedBrand && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onBrandClear();
                }}
                className="grid h-6 w-6 place-items-center rounded-full bg-muted text-muted-foreground hover:bg-ink/10 hover:text-ink"
                aria-label="Limpiar marca"
              >
                <X className="h-3 w-3" />
              </button>
            )}
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          </div>
        </button>
      </div>
    </BottomSheet>
  );
}
