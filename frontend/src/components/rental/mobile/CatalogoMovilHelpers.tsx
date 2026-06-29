import { useState, useEffect, useMemo } from "react";
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
  X,
  Calendar,
  Loader2,
  ChevronRight,
  ChevronDown,
  Check,
  Plus,
} from "lucide-react";
import { BottomSheet } from "@/components/mobile/BottomSheet";
import { Button } from "@/design-system/ui/button";
import { useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { formatARS } from "@/lib/format";
import { type Equipment } from "@/data/equipment";
import { cn } from "@/lib/utils";
import { StepperPill } from "@/components/rental/equipment/shared/StepperPill";
import { PriceBlock } from "@/components/rental/equipment/shared/PriceBlock";
import { FavButton } from "@/components/rental/equipment/shared/FavButton";
import { ShareButton } from "@/components/rental/equipment/shared/ShareButton";
import { createOrder, OrderVerificationError } from "@/lib/orders";
import { chequearEstadoCuenta, iniciarVerificacionIdentidad } from "@/lib/verificacion";
import { VerificacionRequeridaPanel } from "@/components/rental/VerificacionRequeridaPanel";
import { HERO_TAGLINES_DEFAULT, parseHeroTaglines } from "@/lib/hero-taglines";
import { useHeroPhotos, heroImgProps } from "@/lib/studio/hero-photos";
import { whatsappLink, normalizePhone } from "@/lib/whatsapp";
import { BUSINESS_PHONE } from "@/lib/business";
import { useClienteSession, aplicaIva } from "@/lib/iva";
import { toLocalISO } from "@/lib/rental-dates";
import { useCotizacion, descuentoLabel, lineaPorEquipo } from "@/lib/cotizacion";
import { EquipoFoto } from "@/components/rental/EquipoFoto";

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

/* ── Rambla Seal SVG ─────────────────────────────────────────────── */
/* ── HeroBanner ──────────────────────────────────────────────────── */
// Hero amber del catálogo móvil. Foto rotante + eyebrow + headline + CTA "Elegir fechas".
// El heroRef ancla el amber-on-scroll del topbar. Las fotos salen de R2 (admin)
// vía useHeroPhotos — misma fuente que el hero desktop y la página /estudio.
export function HeroBanner({
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
      {/* Foto rotante 16:9 full-bleed (banner cinematográfico). Crossfade con
          <img> object-fit:cover — equivalente a background-size:cover pero permite
          srcset/sizes y fetchpriority, lo que habilita al browser a elegir la
          variante 800px en mobile (vs 1600px antes → ~4× menos bytes).
          bg-ink tapa cualquier gap subpíxel. */}
      <div
        className="relative overflow-hidden bg-ink"
        style={{ width: "100%", aspectRatio: "16 / 9" }}
        aria-label="El Estudio — Rambla Rental"
      >
        {photos.map((photo, i) => (
          <img
            key={photo.url}
            {...heroImgProps(photo, { eager: i === 0 })}
            alt="El Estudio — Rambla Rental"
            aria-hidden={i !== photoIdx}
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
              objectPosition: "center",
              opacity: i === photoIdx ? 1 : 0,
              transition: "opacity 900ms",
            }}
          />
        ))}
        {/* Gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-ink/30" />
        <Button
          type="button"
          variant="primary"
          shape="pill"
          onClick={() => navigate({ to: "/estudio" })}
          className="absolute left-4 bottom-4 min-h-[44px] h-auto gap-1.5 font-bold tracking-[-0.01em] px-4 py-2.5"
          style={{ zIndex: 1 }}
        >
          Conocé el estudio
          <ChevronRight size={13} strokeWidth={2.5} />
        </Button>
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
        <div className="font-mono text-xs uppercase tracking-[0.24em] text-ink/55 mb-3">
          Catálogo · {equipCount} equipos · Mar del Plata
        </div>

        {/* eslint-disable-next-line no-restricted-syntax -- display hero number: entre text-4xl (36px) y text-5xl (48px), óptico */}
        <div className="font-display text-[42px] font-black text-ink leading-[1] tracking-[-0.02em] mb-4">
          {tagline[0]}
          <br />
          {tagline[1]}
        </div>

        <p className="font-sans text-sm leading-[1.55] text-ink/72 mb-8">
          Cámaras, ópticas, luces, audio y soportes para producciones audiovisuales en Mar del
          Plata.
        </p>

        {/* CTA principal */}
        <Button
          type="button"
          variant="primary"
          shape="pill"
          onClick={onDateOpen}
          className="w-full h-auto py-4 text-15 font-bold"
        >
          <Calendar size={16} />
          Elegir fechas
        </Button>
      </div>
    </div>
  );
}

/* ── SheetClose button ───────────────────────────────────────────── */
function SheetClose({ onClose }: { onClose: () => void }) {
  return (
    <button
      onClick={onClose}
      className="relative w-[30px] h-[30px] rounded-full bg-muted grid place-items-center text-muted-foreground hover:bg-ink/10 hover:text-ink transition-colors before:absolute before:left-1/2 before:top-1/2 before:h-11 before:w-11 before:-translate-x-1/2 before:-translate-y-1/2 before:content-['']"
    >
      <X size={14} strokeWidth={2.5} />
    </button>
  );
}

/* ── CartItem ────────────────────────────────────────────────────── */
function CartItem({
  eq,
  qty,
  fechaDesde,
  jornadas,
  precioJornada,
  periodTotal,
}: {
  eq: Equipment;
  qty: number;
  fechaDesde: Date | null;
  jornadas: number;
  // Precio efectivo por jornada + total del período, YA resueltos por el backend
  // (FASE 3: el front muestra, no calcula; combo-aware).
  precioJornada: number;
  periodTotal: number;
}) {
  return (
    <div className="flex items-center gap-3 px-5 py-3.5 border-b border-hairline last:border-b-0">
      <div className="w-11 h-11 rounded-lg bg-surface border border-hairline flex items-center justify-center text-muted-foreground shrink-0 overflow-hidden">
        <EquipoFoto
          foto={eq}
          alt={eq.name}
          sizes="44px"
          blur={false}
          loading="lazy"
          className="w-full h-full object-contain p-1"
          fallback={<CatIcon cat={eq.category} size={18} />}
        />
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-mono text-2xs tracking-[0.18em] uppercase text-muted-foreground">
          {eq.brand}
        </div>
        <div className="font-sans text-sm font-bold text-ink leading-tight mt-0.5 truncate">
          {eq.name}
        </div>
        <div className="font-mono text-2xs text-muted-foreground mt-0.5">
          {fechaDesde
            ? `${qty} × ${formatARS(precioJornada)} / jorn.`
            : `${formatARS(precioJornada)} / jornada`}
        </div>
      </div>
      <div className="shrink-0 text-right">
        <div
          className="font-mono text-sm font-bold text-ink"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {formatARS(periodTotal)}
        </div>
        <div className="font-mono text-xs tracking-[0.1em] text-muted-foreground mt-0.5">
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

export function CartSheet({
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
  const [needsVerif, setNeedsVerif] = useState(false);
  const [iniciandoVerif, setIniciandoVerif] = useState(false);

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
    setNeedsVerif(false);

    // Pre-check de cuenta (fuente única en verificacion.ts). Sin sesión →
    // toast con link a login; logueado pero sin DNI validado → panel de
    // verificación; en vez del 401/403 críptico.
    const estado = await chequearEstadoCuenta();
    if (estado === "no-logueado") {
      toast.error("Debés iniciar sesión para solicitar un rental.", {
        duration: 5000,
        action: {
          label: "Iniciar sesión",
          onClick: () => navigate({ to: "/cliente/login", search: { from: "carrito" } }),
        },
      });
      setSubmitting(false);
      return;
    }
    if (estado === "error") {
      toast.error("Sin conexión. Verificá tu internet.", { duration: 4000 });
      setSubmitting(false);
      return;
    }
    if (estado === "no-verificado") {
      setNeedsVerif(true);
      setSubmitting(false);
      return;
    }
    // "logueado-verificado" → sigue al createOrder

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
      // Backstop: si el backend rechaza por identidad (403), mostramos el panel
      // de verificación en vez del toast genérico.
      if (err instanceof OrderVerificationError) {
        setNeedsVerif(true);
        return;
      }
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
                <div className="font-mono text-2xs tracking-[0.2em] uppercase text-muted-foreground mb-0.5">
                  Salida
                </div>
                <div className="font-sans text-sm font-bold leading-tight text-ink">
                  {fmtDate(fechaDesde)}
                </div>
                <div className="font-mono text-xs text-muted-foreground mt-0.5">{horaDesde}</div>
              </div>
              <ChevronRight size={14} className="text-muted-foreground/50 shrink-0" />
              <div>
                <div className="font-mono text-2xs tracking-[0.2em] uppercase text-muted-foreground mb-0.5">
                  Devolución
                </div>
                <div className="font-sans text-sm font-bold leading-tight text-ink">
                  {fmtDate(fechaHasta)}
                </div>
                <div className="font-mono text-xs text-muted-foreground mt-0.5">{horaHasta}</div>
              </div>
            </div>
            <div
              className="text-center shrink-0 pl-3 border-l"
              style={{ borderColor: "color-mix(in oklch, var(--amber) 40%, transparent)" }}
            >
              <div className="font-mono text-2xs tracking-[0.2em] uppercase text-muted-foreground mb-0.5">
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
              <div className="font-sans text-sm font-bold text-ink leading-tight">
                Elegí las fechas para ver el precio total
              </div>
              <div className="font-mono text-xs tracking-[0.15em] uppercase text-muted-foreground mt-0.5">
                Precios mostrados por jornada
              </div>
            </div>
            <Button
              variant="primary"
              shape="pill"
              className="h-auto px-3.5 py-1.5 text-xs font-bold font-sans shrink-0 whitespace-nowrap"
              onClick={() => {
                onClose();
                onOpenDateSheet();
              }}
            >
              Asignar fechas
            </Button>
          </div>
        )}

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto flex flex-col" style={{ scrollbarWidth: "none" }}>
          {/* Items */}
          {entries.map(({ eq, qty }) => {
            // Precio/total desde el backend (FASE 3); placeholder transitorio
            // (precio catálogo) solo hasta que llega la cotización.
            const linea = lineaPorEquipo(totales, eq._backendId ?? Number(eq.id));
            return (
              <CartItem
                key={eq.id}
                eq={eq}
                qty={qty}
                fechaDesde={fechaDesde}
                jornadas={jornadas}
                precioJornada={linea?.precioJornada ?? eq.pricePerDay}
                periodTotal={linea?.bruto ?? eq.pricePerDay * qty * totales.jornadas}
              />
            );
          })}

          {/* Totals — auto margin pushes to bottom when few items */}
          <div className="border-t border-hairline mt-auto">
            <div className="flex flex-col gap-2 px-5 py-3.5">
              <div className="flex justify-between items-baseline">
                <span className="font-sans text-sm text-muted-foreground">
                  {hayFechas
                    ? `Subtotal · ${jornadas} ${jornadas === 1 ? "jornada" : "jornadas"}`
                    : "Subtotal · por jornada"}
                </span>
                <span className="font-mono text-sm font-semibold text-ink tabular-nums">
                  {formatARS(subtotal)}
                </span>
              </div>

              {descuentoPct > 0 && (
                <div className="flex items-center justify-between py-1">
                  <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                    {descuentoLabel(descuentoOrigen, jornadas, clienteSession?.nombre)}
                    <span
                      className={cn(
                        "inline-flex items-center px-1.5 py-px rounded-full font-mono text-xs font-bold",
                        descuentoOrigen === "cliente"
                          ? "bg-verde/10 text-verde-ink"
                          : "bg-azul/10 text-azul",
                      )}
                    >
                      −{descuentoPct}%
                    </span>
                  </div>
                  <span className="font-mono text-sm font-semibold text-verde-ink tabular-nums">
                    −{formatARS(descuentoMonto)}
                  </span>
                </div>
              )}

              <div className="flex justify-between items-baseline opacity-45">
                <span className="font-sans text-sm text-muted-foreground">
                  Depósito de seguridad
                </span>
                <span className="font-mono text-sm text-muted-foreground">A definir</span>
              </div>

              <div className="flex justify-between items-baseline pt-2 border-t border-hairline mt-1">
                <span className="font-sans text-15 font-bold text-ink">
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
          ) : needsVerif ? (
            <VerificacionRequeridaPanel
              iniciando={iniciandoVerif}
              onVerificar={async () => {
                setIniciandoVerif(true);
                try {
                  await iniciarVerificacionIdentidad("/?openCarrito=1");
                } catch {
                  /* el helper ya hizo toast */
                } finally {
                  setIniciandoVerif(false);
                }
              }}
            />
          ) : (
            <Button
              variant="primary"
              shape="pill"
              className="w-full h-auto py-3.5 font-sans text-15 font-bold disabled:cursor-not-allowed"
              onClick={handleSubmit}
              disabled={submitting}
            >
              {submitting ? (
                <Loader2 size={18} className="animate-spin mx-auto" />
              ) : (
                "Solicitar rental"
              )}
            </Button>
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

export function FichaSheet({
  eq,
  onClose,
  onAddToCart,
  inCart,
  jornadas,
  fechaDesde,
}: FichaSheetProps) {
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
            <div className="font-mono text-2xs tracking-[0.2em] uppercase text-muted-foreground">
              {eq.brand} · {eq.category}
            </div>
            <div className="font-sans text-base font-bold text-ink mt-0.5">{eq.name}</div>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <ShareButton item={eq} size="md" />
            <SheetClose onClose={onClose} />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto" style={{ scrollbarWidth: "none" }}>
          {/* Photo */}
          <div
            className="mx-5 mt-3.5 rounded-[var(--radius-lg)] border border-hairline bg-surface flex items-center justify-center text-muted-foreground overflow-hidden"
            style={{ aspectRatio: "4/3" }}
          >
            <EquipoFoto
              foto={eq}
              alt={eq.name}
              sizes="(max-width: 640px) 92vw, 400px"
              loading="lazy"
              className="w-full h-full object-contain p-4"
              fallback={<CatIcon cat={eq.category} size={48} />}
            />
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
              <div className="font-mono text-2xs tracking-[0.18em] uppercase text-muted-foreground mt-0.5">
                {fechaDesde
                  ? `${jornadas} ${jornadas === 1 ? "jornada" : "jornadas"}`
                  : "/ jornada"}
              </div>
            </div>
            {eq.cantidad != null && (
              <div className="font-mono text-xs text-muted-foreground">
                {eq.cantidad} {eq.cantidad === 1 ? "disponible" : "disponibles"}
              </div>
            )}
          </div>

          {/* Specs */}
          <div className="px-5 py-3 border-b border-hairline">
            <div className="font-mono text-2xs tracking-[0.2em] uppercase text-muted-foreground mb-1">
              Especificaciones
            </div>
            <div className="font-sans text-sm text-muted-foreground leading-relaxed">
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
              <div className="font-mono text-2xs tracking-[0.2em] uppercase text-muted-foreground mb-1.5">
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
            <Button
              variant="primary"
              shape="pill"
              className="w-full h-auto py-3.5 font-sans text-15 font-bold"
              onClick={() => {
                onAddToCart(eq.id, 1);
                onClose();
              }}
            >
              Agregar al carrito
            </Button>
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

export function EquipmentRow({
  eq,
  inCart,
  isExpanded,
  jornadas,
  fechaDesde,
  onTap,
  onAdd,
  onFicha,
}: EquipmentRowProps) {
  const { data: clienteSession } = useClienteSession();
  const conIva = aplicaIva(clienteSession?.perfil_impuestos);

  // Stock derivado de eq.cantidad (en mobile no se pasa disponibilidad por fecha).
  const sinStock = eq.cantidad === 0;
  const pocoStock = eq.cantidad != null && eq.cantidad > 0 && eq.cantidad <= 2;
  const reachedMax = eq.cantidad != null && inCart >= eq.cantidad;

  // Evita el "— Nombre" cuando el equipo no tiene marca (brand vacío o "—").
  const nombrePublico = [eq.brand, eq.name]
    .filter((p) => p && p.trim() && p.trim() !== "—")
    .join(" ")
    .trim();

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
            <EquipoFoto
              foto={eq}
              alt={nombrePublico}
              sizes="48px"
              blur={false}
              loading="lazy"
              className="h-full w-full object-contain p-1.5"
              fallback={<CatIcon cat={eq.category} size={20} />}
            />
          </div>
          <FavButton itemId={String(eq.id)} size="sm" className="absolute -right-1.5 -top-1.5" />
        </div>

        {/* Info */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 font-mono text-2xs uppercase leading-none tracking-[0.1em] text-muted-foreground">
            <span className="min-w-0 truncate">{eq.category}</span>
            {/* Solo el estado accionable (agotado) en el listado; el stock bajo
                queda para el panel expandido y la ficha, evitando ruido. */}
            {sinStock && (
              <span className="shrink-0 whitespace-nowrap text-destructive">· agotado</span>
            )}
          </div>
          <div className="mt-0.5 flex items-start gap-1.5">
            <span className="line-clamp-2 font-sans text-15 font-bold leading-[1.2] text-ink">
              {nombrePublico}
            </span>
            <ChevronDown
              className={cn(
                "mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform",
                isExpanded && "rotate-180",
              )}
            />
          </div>
        </div>

        {/* Price — compacto en la fila densa: total + jornadas, sin la 3ª línea
            (el desglose por jornada queda en el panel expandido). */}
        <PriceBlock
          perDay={eq.pricePerDay}
          jornadas={fechaDesde ? jornadas : 0}
          qty={inCart || 1}
          conIva={conIva}
          size="sm"
          align="right"
          compact
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
              className="grid h-11 w-11 shrink-0 place-items-center rounded-full border hairline bg-background text-ink transition-colors hover:border-amber hover:bg-amber active:scale-90 disabled:cursor-not-allowed disabled:opacity-40"
              onClick={(e) => {
                e.stopPropagation();
                if (sinStock) return;
                onAdd(1);
                onTap(); // also expand
              }}
            >
              <Plus size={16} />
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
            {inCart > 1 ? (
              <span className="font-mono text-xs uppercase tracking-[0.15em] text-muted-foreground">
                {inCart} unidades
              </span>
            ) : pocoStock ? (
              <span className="font-mono text-xs uppercase tracking-[0.15em] text-amber">
                {/* Rental, no e-commerce: mostramos el stock como dato neutro
                    ("1 disponible"), no escasez tipo "última unidad" — tener 1
                    unidad es lo normal acá. El stepper ya capa en el stock. */}
                {eq.cantidad} {eq.cantidad === 1 ? "disponible" : "disponibles"}
              </span>
            ) : null}
          </div>

          {/* Includes — 2 columnas */}
          {eq.includes && eq.includes.length > 0 && (
            <div className="mb-2">
              <div className="mb-1.5 font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
                Incluye
              </div>
              <div className="grid grid-cols-2 gap-1">
                {eq.includes.map((item, i) => (
                  <span
                    key={i}
                    className="rounded-full border border-hairline bg-card px-2.5 py-0.5 font-sans text-xs text-ink"
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
                    className="inline-flex items-center gap-1.5 rounded-full border border-hairline bg-card px-2 py-0.5 font-sans text-xs"
                  >
                    <span className="font-mono uppercase tracking-wider text-xs text-muted-foreground">
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

/* ── BrandSheet ──────────────────────────────────────────────────── */
type BrandSheetItem = {
  nombre: string;
  logo_url: string | null;
  destacada: boolean;
  count: number;
};

export function BrandSheet({
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
                    <div className="font-mono text-xs uppercase tracking-[0.18em] text-amber/80 mt-0.5">
                      Destacada
                    </div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="font-mono text-2xs tabular-nums text-muted-foreground">
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
export function FiltrosSheet({
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
          <Button
            type="button"
            variant="primary"
            shape="pill"
            onClick={() => onOpenChange(false)}
            className="flex-1 h-auto py-3 font-sans text-sm font-bold"
          >
            Aplicar
          </Button>
        </div>
      }
    >
      <div className="px-4 py-3 space-y-3">
        {/* Disponibles toggle */}
        <div className="rounded-lg border border-hairline px-3.5 py-3 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="font-sans text-sm font-semibold text-ink">Disponibles</div>
            <div className="font-mono text-2xs text-muted-foreground mt-0.5">
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
            <div className="font-mono text-2xs text-muted-foreground mt-0.5 truncate">
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
