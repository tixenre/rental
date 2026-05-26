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
} from "lucide-react";
import { BottomSheet } from "@/components/mobile/BottomSheet";
import { useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { useEquipos, useMarcas, useCategorias } from "@/hooks/useEquipos";
import { useCart } from "@/lib/cart-store";
import { formatARS } from "@/lib/format";
import { type Equipment } from "@/data/equipment";
import { cn } from "@/lib/utils";
import { createOrder } from "@/lib/orders";
import { authedFetch } from "@/lib/authedFetch";
import { whatsappLink, normalizePhone } from "@/lib/whatsapp";
import { BUSINESS_PHONE } from "@/lib/business";
import { apiGetDescuentosJornada, apiGetDiasBloqueados } from "@/lib/api";
import { useClienteSession, IVA_PCT } from "@/lib/iva";
import { computeCartTotal, descuentoLabel } from "@/lib/cart-total";
import { deriveEndDate, franjaParaFecha, diaAbierto, timeToMinutes } from "@/lib/rental-dates";
import { useHorarios } from "@/lib/horarios";

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

function ymd(d: Date | null): string {
  if (!d) return "";
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

function addDays120(d: Date): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + 120);
  return x;
}

const HORAS = [
  "08:00",
  "09:00",
  "10:00",
  "11:00",
  "12:00",
  "13:00",
  "14:00",
  "15:00",
  "16:00",
  "17:00",
  "18:00",
  "19:00",
];

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
// Hero amber del catálogo móvil (mock Catálogo Móvil - Lista.html §HeroBanner).
// Eyebrow + headline brand "un lugar / donde pasan / cosas" + body + card
// Estudio negro con CTA amber. El heroRef se usa para el amber-on-scroll del
// topbar (cuando el bottom del hero llega al topbar, el topbar está full
// amber y el seal/pill snapean a inverted).
function HeroBanner({
  heroRef,
  equipCount,
}: {
  heroRef: React.RefObject<HTMLDivElement | null>;
  equipCount: number;
}) {
  const navigate = useNavigate();
  return (
    <div ref={heroRef} className="relative bg-amber" style={{ padding: "28px 20px 32px" }}>
      <div className="font-mono text-[9px] uppercase tracking-[0.24em] text-ink/55 mb-4">
        Catálogo · {equipCount} equipos · Mar del Plata
      </div>

      <div className="font-display text-[46px] font-black text-ink leading-[1] tracking-[-0.02em] mb-[18px]">
        un lugar
        <br />
        donde pasan
        <br />
        cosas.
      </div>

      <p className="font-sans text-[15px] leading-[1.55] text-ink/75 mb-7">
        Cámaras, ópticas, luces, audio y soportes para producciones audiovisuales. Elegí fechas y
        armá tu pedido — te lo dejamos listo para retirar.
      </p>

      {/* Card Estudio — ink bg con CTA amber */}
      <div className="rounded-2xl bg-ink p-5">
        <div className="inline-flex items-center gap-1.5 rounded-full border border-[color-mix(in_oklch,var(--amber)_35%,transparent)] bg-[color-mix(in_oklch,var(--amber)_12%,transparent)] px-3 py-1 mb-3">
          <svg
            width="10"
            height="10"
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--amber)"
            strokeWidth="1.8"
            strokeLinecap="round"
          >
            <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z" />
          </svg>
          <span className="font-mono text-[9px] uppercase tracking-[0.22em] text-amber">
            Espacio Rambla
          </span>
        </div>

        <div className="font-display text-[28px] font-black text-amber leading-[1.1] mb-2">
          Conocé el Estudio
        </div>

        <p className="font-sans text-[13px] leading-[1.55] text-[color-mix(in_oklch,var(--amber)_65%,white)] mb-5">
          Foto y video · reservá por hora · pack de luces y grips opcional
        </p>

        <button
          type="button"
          onClick={() => navigate({ to: "/estudio" })}
          className="w-full flex items-center justify-center gap-1.5 py-3.5 rounded-full bg-amber text-ink font-sans text-[15px] font-bold transition hover:opacity-90"
        >
          Ver estudio
          <ChevronRight className="h-4 w-4" />
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

/* ── DateSheet ───────────────────────────────────────────────────── */
interface DateSheetProps {
  onClose: () => void;
  onConfirm: (v: {
    fechaDesde: Date;
    jornadas: number;
    horaDesde: string;
    horaHasta: string;
  }) => void;
  initial: { fechaDesde: Date | null; jornadas: number; horaDesde: string; horaHasta: string };
  /** Días (YYYY-MM-DD) sin disponibilidad para los equipos del carrito. */
  diasBloqueados: Set<string>;
}

function DateSheet({ onClose, onConfirm, initial, diasBloqueados }: DateSheetProps) {
  const [fechaDesde, setFechaDesde] = useState<Date | null>(initial.fechaDesde);
  const [jornadas, setJornadas] = useState(initial.jornadas);
  const [horaDesde, setHoraDesde] = useState(initial.horaDesde);
  const [horaHasta, setHoraHasta] = useState(initial.horaHasta);

  const fechaHasta = useMemo(
    () => (fechaDesde ? deriveEndDate(fechaDesde, jornadas, horaDesde, horaHasta) : null),
    [fechaDesde, jornadas, horaDesde, horaHasta],
  );

  // Horarios habilitados: filtramos las horas según la franja del día y
  // bloqueamos confirmar si retiro o devolución caen en día cerrado. El
  // backend valida igual; esto es el feedback en la UI.
  const horarios = useHorarios();
  const franjaDesde = franjaParaFecha(horarios, fechaDesde);
  const franjaHasta = franjaParaFecha(horarios, fechaHasta);
  const horasDesde = useMemo(
    () =>
      franjaDesde ? HORAS.filter((h) => h >= franjaDesde.desde && h <= franjaDesde.hasta) : HORAS,
    [franjaDesde],
  );
  const horasHasta = useMemo(
    () =>
      franjaHasta ? HORAS.filter((h) => h >= franjaHasta.desde && h <= franjaHasta.hasta) : HORAS,
    [franjaHasta],
  );
  const diaDesdeCerrado = !!fechaDesde && !diaAbierto(horarios, fechaDesde);
  const diaHastaCerrado = !!fechaHasta && !diaAbierto(horarios, fechaHasta);
  // ¿El período cruza un día sin disponibilidad para los equipos del carrito?
  const rangoCruzaBloqueado = useMemo(() => {
    if (!fechaDesde || !fechaHasta || diasBloqueados.size === 0) return false;
    const d = new Date(fechaDesde);
    d.setHours(0, 0, 0, 0);
    const fin = new Date(fechaHasta);
    fin.setHours(0, 0, 0, 0);
    while (d <= fin) {
      if (diasBloqueados.has(ymd(d))) return true;
      d.setDate(d.getDate() + 1);
    }
    return false;
  }, [fechaDesde, fechaHasta, diasBloqueados]);
  // Snap de la hora a una opción válida cuando cambia la franja del día.
  useEffect(() => {
    if (horasDesde.length && !horasDesde.includes(horaDesde)) setHoraDesde(horasDesde[0]);
  }, [horasDesde, horaDesde]);
  useEffect(() => {
    if (horasHasta.length && !horasHasta.includes(horaHasta)) setHoraHasta(horasHasta[0]);
  }, [horasHasta, horaHasta]);

  const selectStyle: React.CSSProperties = {
    cursor: "pointer",
    appearance: "none" as const,
    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23888' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`,
    backgroundRepeat: "no-repeat",
    backgroundPosition: "right 12px center",
    paddingRight: 32,
  };

  return (
    <>
      {/* Scrim */}
      <div
        className="fixed inset-0 z-[60] animate-in fade-in duration-200"
        style={{ background: "rgba(20,16,12,0.5)" }}
        onClick={onClose}
      />
      {/* Sheet */}
      <div
        className="fixed inset-x-0 bottom-0 z-[61] bg-card flex flex-col max-h-[88%] animate-in slide-in-from-bottom duration-[260ms]"
        style={{ borderRadius: "24px 24px 0 0", boxShadow: "0 -8px 40px rgba(0,0,0,0.18)" }}
      >
        {/* Handle */}
        <div className="w-9 h-1 rounded-full bg-hairline mx-auto mt-2.5 shrink-0" />
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-hairline shrink-0">
          <span className="font-sans text-base font-bold text-ink">Período de alquiler</span>
          <SheetClose onClose={onClose} />
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto" style={{ scrollbarWidth: "none" }}>
          <div className="flex flex-col gap-[18px] px-5 pt-[18px] pb-2">
            {/* Fecha de salida */}
            <div className="flex flex-col gap-1.5">
              <span className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted-foreground">
                Fecha de salida
              </span>
              <input
                type="date"
                className="w-full px-3.5 py-[11px] rounded-[var(--radius-sm)] border-[1.5px] border-hairline bg-background text-ink text-sm outline-none focus:border-amber transition-colors"
                style={{ fontFamily: "var(--font-sans)" }}
                value={ymd(fechaDesde)}
                min={ymd(new Date())}
                onChange={(e) =>
                  setFechaDesde(e.target.value ? new Date(e.target.value + "T12:00:00") : null)
                }
              />
            </div>

            {/* Hora de salida + devolución */}
            <div className="grid grid-cols-2 gap-2.5">
              <div className="flex flex-col gap-1.5">
                <span className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted-foreground">
                  Hora de salida
                </span>
                <select
                  aria-label="Hora de salida"
                  className="w-full px-3.5 py-[11px] rounded-[var(--radius-sm)] border-[1.5px] border-hairline bg-background text-ink text-sm outline-none focus:border-amber transition-colors"
                  style={{ ...selectStyle, fontFamily: "var(--font-sans)" }}
                  value={horaDesde}
                  onChange={(e) => setHoraDesde(e.target.value)}
                >
                  {horasDesde.map((h) => (
                    <option key={h} value={h}>
                      {h}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted-foreground">
                  Hora de devolución
                </span>
                <select
                  aria-label="Hora de devolución"
                  className="w-full px-3.5 py-[11px] rounded-[var(--radius-sm)] border-[1.5px] border-hairline bg-background text-ink text-sm outline-none focus:border-amber transition-colors"
                  style={{ ...selectStyle, fontFamily: "var(--font-sans)" }}
                  value={horaHasta}
                  onChange={(e) => setHoraHasta(e.target.value)}
                >
                  {horasHasta.map((h) => (
                    <option key={h} value={h}>
                      {h}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Jornadas stepper */}
            <div className="flex flex-col gap-1.5">
              <span className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted-foreground">
                Jornadas
              </span>
              <div className="flex items-center border-[1.5px] border-hairline rounded-[var(--radius-sm)] overflow-hidden bg-background">
                <button
                  className="px-[18px] py-[10px] text-xl font-bold text-muted-foreground hover:bg-muted hover:text-ink transition-colors leading-none"
                  onClick={() => setJornadas((j) => Math.max(1, j - 1))}
                >
                  −
                </button>
                <div
                  data-testid="jornadas-count"
                  className="flex-1 text-center border-x border-hairline py-1.5 leading-none"
                  style={{
                    fontFamily: "var(--font-display)",
                    fontSize: 26,
                    fontWeight: 900,
                    color: "var(--ink)",
                  }}
                >
                  {jornadas}
                  <span className="font-mono text-[8px] tracking-[0.2em] uppercase text-muted-foreground block">
                    jornadas
                  </span>
                </div>
                <button
                  className="px-[18px] py-[10px] text-xl font-bold text-muted-foreground hover:bg-amber hover:text-ink transition-colors leading-none"
                  onClick={() => setJornadas((j) => j + 1)}
                >
                  +
                </button>
              </div>
            </div>

            {/* Devolución calculada */}
            {fechaDesde && (
              <div
                className="px-3.5 py-3 rounded-[var(--radius-sm)] border"
                style={{
                  background: "var(--amber-soft)",
                  borderColor: "color-mix(in oklch, var(--amber) 40%, transparent)",
                }}
              >
                <div className="font-mono text-[8px] tracking-[0.2em] uppercase text-muted-foreground mb-1">
                  Devolución calculada
                </div>
                <div className="font-sans text-[15px] font-bold text-ink">
                  {fmtDate(fechaHasta)}
                </div>
                <div className="font-mono text-[11px] text-muted-foreground mt-0.5">
                  hasta las {horaHasta}
                </div>
                {timeToMinutes(horaHasta) > timeToMinutes(horaDesde) && (
                  <div className="mt-1.5 text-[11px] text-ink leading-snug">
                    Devolvés más tarde que tu retiro ({horaDesde}) → <strong>suma 1 jornada</strong>
                    . Devolvé {horaDesde} o antes para no sumarla.
                  </div>
                )}
              </div>
            )}
            <div className="h-2" />
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-hairline shrink-0" style={{ paddingBottom: 20 }}>
          {(diaDesdeCerrado || diaHastaCerrado || rangoCruzaBloqueado) && (
            <p className="mb-2 text-[12px] text-destructive text-center">
              {diaDesdeCerrado
                ? "El día de salida está cerrado — elegí otro."
                : diaHastaCerrado
                  ? `La devolución (${fmtDate(fechaHasta)}) cae en un día cerrado — ajustá las jornadas.`
                  : "El período incluye días sin disponibilidad para algún equipo del carrito."}
            </p>
          )}
          <button
            disabled={!fechaDesde || diaDesdeCerrado || diaHastaCerrado || rangoCruzaBloqueado}
            className="w-full py-3.5 rounded-full bg-ink text-amber font-sans text-[15px] font-bold text-center hover:bg-amber hover:text-ink transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-ink disabled:hover:text-amber"
            onClick={() =>
              fechaDesde &&
              !diaDesdeCerrado &&
              !diaHastaCerrado &&
              !rangoCruzaBloqueado &&
              onConfirm({ fechaDesde, jornadas, horaDesde, horaHasta })
            }
          >
            {fechaDesde
              ? `Confirmar — ${fmtDate(fechaDesde)} · ${jornadas} jorn.`
              : "Elegí una fecha de salida"}
          </button>
        </div>
      </div>
    </>
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
  horaDesde,
  horaHasta,
}: CartSheetProps) {
  const navigate = useNavigate();
  const [solicitado, setSolicitado] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const entries = Object.entries(cartItems)
    .map(([id, qty]) => ({ eq: equipos.find((e) => e.id === id)!, qty }))
    .filter((x) => x.eq);

  const fechaHasta = fechaDesde ? deriveEndDate(fechaDesde, jornadas, horaDesde, horaHasta) : null;

  // Total unificado con drawer desktop y minibar vía lib/cart-total.
  // Sin fechas: estimado por jornada (J=1) sin descuento ni IVA.
  const hayFechas = !!fechaDesde;
  const { data: descuentosPuntos = [] } = useQuery({
    queryKey: ["descuentos-jornada"],
    queryFn: apiGetDescuentosJornada,
    staleTime: 60_000,
  });
  const { data: clienteSession } = useClienteSession();
  const totales = computeCartTotal({
    lines: entries.map(({ eq, qty }) => ({ pricePerDay: eq.pricePerDay, qty })),
    jornadas: hayFechas ? jornadas : 1,
    descuentosPuntos,
    perfilImpuestos: hayFechas ? clienteSession?.perfil_impuestos : null,
    descuentoClientePct: hayFechas ? clienteSession?.descuento : 0,
  });
  const {
    subtotal,
    descuentoPct,
    descuentoOrigen,
    descuentoMonto,
    totalNeto,
    iva,
    conIva,
    total: totalFinal,
  } = totales;

  async function handleSubmit() {
    if (entries.length === 0) return;
    if (!fechaDesde) {
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
        endDate: deriveEndDate(fechaDesde, jornadas, horaDesde, horaHasta),
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
    `Total estimado: ${formatARS(totalFinal)}`,
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
                    {descuentoLabel(descuentoOrigen, jornadas)}
                    <span
                      className={cn(
                        "inline-flex items-center px-1.5 py-px rounded-full font-mono text-[9px] font-bold",
                        descuentoOrigen === "cliente"
                          ? "bg-green-100 text-green-700"
                          : "bg-blue-100 text-blue-700",
                      )}
                    >
                      −{descuentoPct}%
                    </span>
                  </div>
                  <span className="font-mono text-[13px] font-semibold text-green-700 tabular-nums">
                    −{formatARS(descuentoMonto)}
                  </span>
                </div>
              )}

              {conIva && (
                <>
                  <div className="flex justify-between items-baseline">
                    <span className="font-sans text-[13px] text-muted-foreground">
                      Subtotal neto
                    </span>
                    <span className="font-mono text-[13px] text-muted-foreground tabular-nums">
                      {formatARS(totalNeto)}
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline">
                    <span className="font-sans text-[13px] text-muted-foreground">
                      IVA {IVA_PCT}%
                    </span>
                    <span className="font-mono text-[13px] text-muted-foreground tabular-nums">
                      +{formatARS(iva)}
                    </span>
                  </div>
                </>
              )}

              <div className="flex justify-between items-baseline opacity-45">
                <span className="font-sans text-[13px] text-muted-foreground">
                  Depósito de seguridad
                </span>
                <span className="font-mono text-[13px] text-muted-foreground">A definir</span>
              </div>

              <div className="flex justify-between items-baseline pt-2 border-t border-hairline mt-1">
                <span className="font-sans text-[15px] font-bold text-ink">
                  {hayFechas ? `Total${conIva ? " · IVA incluído" : ""}` : "Estimado / jornada"}
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
                  {formatARS(totalFinal)}
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
  const priceDisplay = fechaDesde
    ? formatARS(eq.pricePerDay * jornadas)
    : formatARS(eq.pricePerDay);
  const priceMeta = fechaDesde ? `${jornadas} jorn.` : "/ jornada";

  const expansionTotal = formatARS(eq.pricePerDay * (inCart || 1) * jornadas);

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
        "mb-1.5 rounded-[var(--radius-lg)] overflow-hidden border bg-card transition-all duration-150",
        isExpanded ? "border-amber" : "border-hairline",
      )}
      style={isExpanded ? { boxShadow: "0 0 0 1.5px var(--amber)" } : undefined}
    >
      {/* Main row */}
      <div
        className="flex items-center gap-2.5 p-[10px_12px_10px_10px] cursor-pointer select-none"
        style={{ WebkitTapHighlightColor: "transparent" }}
        onClick={onTap}
      >
        {/* Thumbnail */}
        <div className="w-12 h-12 rounded-xl bg-surface border border-hairline flex items-center justify-center text-muted-foreground shrink-0 overflow-hidden">
          {eq.fotoUrl && !imgFailed ? (
            <img
              src={eq.fotoUrl}
              alt={eq.name}
              className="w-full h-full object-contain p-1.5"
              loading="lazy"
              onError={() => setImgFailed(true)}
            />
          ) : (
            <CatIcon cat={eq.category} size={20} />
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="font-mono text-[8px] tracking-[0.2em] uppercase text-muted-foreground leading-none">
            {eq.brand} · {eq.category}
          </div>
          <div className="font-sans text-[15px] font-bold text-ink leading-tight mt-0.5 truncate">
            {eq.name}
          </div>
        </div>

        {/* Price */}
        <div className="text-right shrink-0">
          <div
            className={cn(
              "font-mono font-bold leading-none",
              fechaDesde ? "text-sm text-ink" : "text-xs text-muted-foreground",
            )}
            style={{ fontSize: fechaDesde ? 14 : 12, fontVariantNumeric: "tabular-nums" }}
          >
            {priceDisplay}
          </div>
          <div className="font-mono text-[8px] tracking-[0.1em] uppercase text-muted-foreground mt-0.5">
            {priceMeta}
          </div>
        </div>

        {/* Action */}
        {inCart > 0 ? (
          <div
            className="flex items-center rounded-full overflow-hidden shrink-0"
            style={{ border: "1.5px solid var(--amber)", background: "var(--amber)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="w-[30px] h-8 grid place-items-center font-bold text-base text-ink hover:bg-ink/10 transition-colors leading-none"
              onClick={() => onAdd(-1)}
            >
              −
            </button>
            <span className="font-mono text-[13px] font-bold text-ink px-1.5 min-w-[28px] text-center">
              {inCart}
            </span>
            <button
              className="w-[30px] h-8 grid place-items-center font-bold text-base text-ink hover:bg-ink/10 transition-colors leading-none disabled:opacity-40"
              onClick={() => onAdd(1)}
              disabled={eq.cantidad != null && inCart >= eq.cantidad}
            >
              +
            </button>
          </div>
        ) : (
          <button
            className="w-[34px] h-[34px] rounded-full bg-ink text-background grid place-items-center shrink-0 transition-all duration-150 border-[1.5px] border-ink hover:bg-amber hover:border-amber hover:text-ink"
            onClick={(e) => {
              e.stopPropagation();
              onAdd(1);
              onTap(); // also expand
            }}
          >
            <Plus size={14} />
          </button>
        )}
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
          <div className="flex items-baseline justify-between pb-2.5 mb-2.5 border-b border-hairline">
            <div>
              <div
                className="font-mono font-bold leading-none text-ink"
                style={{ fontSize: 22, fontVariantNumeric: "tabular-nums" }}
              >
                {expansionTotal}
              </div>
              <div className="font-mono text-[8px] tracking-[0.18em] uppercase text-muted-foreground mt-0.5">
                {jornadas} jornadas{inCart > 1 ? ` · ${inCart} unidades` : ""}
              </div>
            </div>
            <div className="font-mono text-[11px] text-muted-foreground">
              {formatARS(eq.pricePerDay)}
              <span className="font-mono text-[9px] tracking-[0.15em] uppercase text-muted-foreground ml-1">
                /jorn.
              </span>
            </div>
          </div>

          {/* Includes */}
          {eq.includes && eq.includes.length > 0 && (
            <div className="mb-2">
              <div className="font-mono text-[8px] tracking-[0.2em] uppercase text-muted-foreground mb-1.5">
                Incluye
              </div>
              <div className="flex flex-wrap gap-1">
                {eq.includes.map((item, i) => (
                  <span
                    key={i}
                    className="px-2.5 py-0.5 rounded-full border border-hairline bg-card font-sans text-[11px] text-ink"
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
            Ver ficha completa
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

  // Cart store
  const cart = useCart();

  // Catalog state
  const [activeTab, setActiveTab] = useState("Todo");
  const [query, setQuery] = useState("");
  const [stockOnly, setStockOnly] = useState(false);
  const [selectedBrand, setSelectedBrand] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  // Date state
  const [fechaDesde, setFechaDesde] = useState<Date | null>(null);
  const [jornadas, setJornadas] = useState(3);
  const [horaDesde, setHoraDesde] = useState("10:00");
  const [horaHasta, setHoraHasta] = useState("10:00");

  // Días sin disponibilidad para los equipos del carrito (reservas reales).
  const itemsParam = useMemo(
    () =>
      Object.entries(cart.items)
        .filter(([id, qty]) => /^\d+$/.test(id) && qty > 0)
        .map(([id, qty]) => `${id}:${qty}`)
        .join(","),
    [cart.items],
  );
  const diasBloqueadosQ = useQuery({
    queryKey: ["dias-bloqueados", itemsParam],
    queryFn: () => apiGetDiasBloqueados(itemsParam, ymd(new Date()), ymd(addDays120(new Date()))),
    enabled: itemsParam !== "",
    staleTime: 60_000,
  });
  const diasBloqueados = useMemo(
    () => new Set(diasBloqueadosQ.data?.dias_bloqueados ?? []),
    [diasBloqueadosQ.data],
  );

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

  // Derived date values
  const fechaHasta = useMemo(
    () => (fechaDesde ? deriveEndDate(fechaDesde, jornadas, horaDesde, horaHasta) : null),
    [fechaDesde, jornadas, horaDesde, horaHasta],
  );

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

  const handleConfirmDates = useCallback(
    ({
      fechaDesde: fd,
      jornadas: j,
      horaDesde: hd,
      horaHasta: hh,
    }: {
      fechaDesde: Date;
      jornadas: number;
      horaDesde: string;
      horaHasta: string;
    }) => {
      setFechaDesde(fd);
      setJornadas(j);
      setHoraDesde(hd);
      setHoraHasta(hh);
      // Sync to cart store for cross-page consistency
      cart.setDates(fd, deriveEndDate(fd, j, hd, hh));
      cart.setStartTime(hd);
      cart.setEndTime(hh);
      setShowDateSheet(false);
    },
    [cart],
  );

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

        {/* Hero banner amber — eyebrow + headline brand + Estudio card.
            Anclado al heroRef del amber-on-scroll del topbar. */}
        <HeroBanner heroRef={heroRef} equipCount={allEquipos?.length ?? 0} />

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
                {jornadas} jornadas
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
      {showDateSheet && (
        <DateSheet
          onClose={() => setShowDateSheet(false)}
          onConfirm={handleConfirmDates}
          initial={{ fechaDesde, jornadas, horaDesde, horaHasta }}
          diasBloqueados={diasBloqueados}
        />
      )}
      {showCartSheet && (
        <CartSheet
          onClose={() => setShowCartSheet(false)}
          onOpenDateSheet={() => setShowDateSheet(true)}
          equipos={allEquipos}
          cartItems={cart.items}
          jornadas={jornadas}
          fechaDesde={fechaDesde}
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
