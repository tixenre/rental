import { useState, useCallback, useMemo, useRef, useEffect } from "react";
import {
  Camera, Sun, Mic, Layers, Monitor, Zap, Battery,
  Package, SlidersHorizontal, Search, User, Plus,
  ChevronUp, ChevronRight, X, Calendar,
} from "lucide-react";
import { useEquipos } from "@/hooks/useEquipos";
import { useCart } from "@/lib/cart-store";
import { formatARS } from "@/lib/format";
import { type Equipment } from "@/data/equipment";
import { cn } from "@/lib/utils";

/* ── Helpers ─────────────────────────────────────────────────────── */
function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

function fmtDate(d: Date | null): string {
  if (!d) return "—";
  const dias = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
  const meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  return `${dias[d.getDay()]} ${d.getDate()} ${meses[d.getMonth()]}`;
}

function ymd(d: Date | null): string {
  if (!d) return "";
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

const HORAS = [
  "08:00", "09:00", "10:00", "11:00", "12:00",
  "13:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00",
];

const POPULAR_CHIPS = ["Sony FX3", "Aputure 600d", "RØDE", "Pack boda", "Pack entrevista"];

/* ── Category icon ───────────────────────────────────────────────── */
type IconComp = React.ComponentType<{ size?: number; className?: string; strokeWidth?: number }>;

const CAT_ICONS: Record<string, IconComp> = {
  "Cámaras": Camera,
  "Lentes": Sun,  // Aperture not in lucide-react standard; Sun as fallback
  "Luces": Sun,
  "Iluminación": Sun,
  "Tungsteno": Sun,
  "Sonido": Mic,
  "Audio": Mic,
  "Trípode": Layers,
  "Soportes": Layers,
  "Stands": Layers,
  "Monitores": Monitor,
  "Flash": Zap,
  "Baterías": Battery,
  "Filtros": SlidersHorizontal,
  "Comunicación": Monitor,
  "Modificadores": Sun,
  "Brazo Mágico": Layers,
  "Grips": Layers,
};

function CatIcon({ cat, size = 20 }: { cat: string; size?: number }) {
  const Icon = CAT_ICONS[cat] ?? Package;
  return <Icon size={size} strokeWidth={1.5} />;
}

/* ── Shared styles ───────────────────────────────────────────────── */
const TOPBAR_BG = "color-mix(in oklch, var(--background) 90%, transparent)";
const SEARCH_BG = "color-mix(in oklch, var(--background) 94%, transparent)";
const TABS_BG = "color-mix(in oklch, var(--background) 90%, transparent)";
const CARTBAR_BG = "color-mix(in oklch, var(--background) 96%, transparent)";

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
  onConfirm: (v: { fechaDesde: Date; jornadas: number; horaDesde: string; horaHasta: string }) => void;
  initial: { fechaDesde: Date | null; jornadas: number; horaDesde: string; horaHasta: string };
}

function DateSheet({ onClose, onConfirm, initial }: DateSheetProps) {
  const [fechaDesde, setFechaDesde] = useState<Date | null>(initial.fechaDesde);
  const [jornadas, setJornadas] = useState(initial.jornadas);
  const [horaDesde, setHoraDesde] = useState(initial.horaDesde);
  const [horaHasta, setHoraHasta] = useState(initial.horaHasta);

  const fechaHasta = useMemo(
    () => (fechaDesde ? addDays(fechaDesde, jornadas - 1) : null),
    [fechaDesde, jornadas],
  );

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
                  className="w-full px-3.5 py-[11px] rounded-[var(--radius-sm)] border-[1.5px] border-hairline bg-background text-ink text-sm outline-none focus:border-amber transition-colors"
                  style={{ ...selectStyle, fontFamily: "var(--font-sans)" }}
                  value={horaDesde}
                  onChange={(e) => setHoraDesde(e.target.value)}
                >
                  {HORAS.map((h) => <option key={h} value={h}>{h}</option>)}
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted-foreground">
                  Hora de devolución
                </span>
                <select
                  className="w-full px-3.5 py-[11px] rounded-[var(--radius-sm)] border-[1.5px] border-hairline bg-background text-ink text-sm outline-none focus:border-amber transition-colors"
                  style={{ ...selectStyle, fontFamily: "var(--font-sans)" }}
                  value={horaHasta}
                  onChange={(e) => setHoraHasta(e.target.value)}
                >
                  {HORAS.map((h) => <option key={h} value={h}>{h}</option>)}
                </select>
              </div>
            </div>

            {/* Jornadas stepper */}
            <div className="flex flex-col gap-1.5">
              <span className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted-foreground">
                Jornadas
              </span>
              <div
                className="flex items-center border-[1.5px] border-hairline rounded-[var(--radius-sm)] overflow-hidden bg-background"
              >
                <button
                  className="px-[18px] py-[10px] text-xl font-bold text-muted-foreground hover:bg-muted hover:text-ink transition-colors leading-none"
                  onClick={() => setJornadas((j) => Math.max(1, j - 1))}
                >
                  −
                </button>
                <div
                  className="flex-1 text-center border-x border-hairline py-1.5 leading-none"
                  style={{ fontFamily: "var(--font-display)", fontSize: 26, fontWeight: 900, color: "var(--ink)" }}
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
                style={{ background: "var(--amber-soft)", borderColor: "color-mix(in oklch, var(--amber) 40%, transparent)" }}
              >
                <div className="font-mono text-[8px] tracking-[0.2em] uppercase text-muted-foreground mb-1">
                  Devolución calculada
                </div>
                <div className="font-sans text-[15px] font-bold text-ink">{fmtDate(fechaHasta)}</div>
                <div className="font-mono text-[11px] text-muted-foreground mt-0.5">hasta las {horaHasta}</div>
              </div>
            )}
            <div className="h-2" />
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-hairline shrink-0" style={{ paddingBottom: 20 }}>
          <button
            disabled={!fechaDesde}
            className="w-full py-3.5 rounded-full bg-ink text-amber font-sans text-[15px] font-bold text-center hover:bg-amber hover:text-ink transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-ink disabled:hover:text-amber"
            onClick={() =>
              fechaDesde &&
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

function CartSheet({
  onClose, onOpenDateSheet, equipos, cartItems, jornadas,
  fechaDesde, horaDesde, horaHasta,
}: CartSheetProps) {
  const [solicitado, setSolicitado] = useState(false);

  const entries = Object.entries(cartItems)
    .map(([id, qty]) => ({ eq: equipos.find((e) => e.id === id)!, qty }))
    .filter((x) => x.eq);

  const jornadasEfectivas = fechaDesde ? jornadas : 1;
  const subtotal = entries.reduce((s, { eq, qty }) => s + eq.pricePerDay * qty * jornadasEfectivas, 0);
  const fechaHasta = fechaDesde ? addDays(fechaDesde, jornadas - 1) : null;

  const descJornadas = fechaDesde && jornadas >= 3 ? { pct: 10, label: "3+ jornadas" } : null;
  const descCliente = { pct: 5, label: "cliente registrado" };
  const montoDescJornadas = descJornadas ? Math.round(subtotal * descJornadas.pct / 100) : 0;
  const montoDescCliente = Math.round(subtotal * descCliente.pct / 100);
  const totalFinal = subtotal - montoDescJornadas - montoDescCliente;

  return (
    <>
      <div
        className="fixed inset-0 z-[60] animate-in fade-in duration-200"
        style={{ background: "rgba(20,16,12,0.5)" }}
        onClick={onClose}
      />
      <div
        className="fixed inset-x-0 bottom-0 z-[61] bg-card flex flex-col animate-in slide-in-from-bottom duration-[260ms]"
        style={{ height: "72%", maxHeight: "72%", borderRadius: "24px 24px 0 0", boxShadow: "0 -8px 40px rgba(0,0,0,0.18)" }}
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
                <div className="font-mono text-[8px] tracking-[0.2em] uppercase text-muted-foreground mb-0.5">Salida</div>
                <div className="font-sans text-sm font-bold leading-tight text-ink">{fmtDate(fechaDesde)}</div>
                <div className="font-mono text-[11px] text-muted-foreground mt-0.5">{horaDesde}</div>
              </div>
              <ChevronRight size={14} className="text-muted-foreground/50 shrink-0" />
              <div>
                <div className="font-mono text-[8px] tracking-[0.2em] uppercase text-muted-foreground mb-0.5">Devolución</div>
                <div className="font-sans text-sm font-bold leading-tight text-ink">{fmtDate(fechaHasta)}</div>
                <div className="font-mono text-[11px] text-muted-foreground mt-0.5">{horaHasta}</div>
              </div>
            </div>
            <div
              className="text-center shrink-0 pl-3 border-l"
              style={{ borderColor: "color-mix(in oklch, var(--amber) 40%, transparent)" }}
            >
              <div className="font-mono text-[8px] tracking-[0.2em] uppercase text-muted-foreground mb-0.5">Jorn.</div>
              <div style={{ fontFamily: "var(--font-display)", fontSize: 24, fontWeight: 900, color: "var(--ink)", lineHeight: 1 }}>
                {jornadas}
              </div>
            </div>
          </div>
        ) : (
          <div
            className="flex items-center gap-3 px-5 py-3.5 shrink-0 border-b border-hairline"
            style={{ background: "var(--amber-soft)", borderTopColor: "color-mix(in oklch, var(--amber) 35%, transparent)" }}
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
              onClick={() => { onClose(); onOpenDateSheet(); }}
            >
              Asignar fechas
            </button>
          </div>
        )}

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto flex flex-col" style={{ scrollbarWidth: "none" }}>
          {/* Items */}
          {entries.map(({ eq, qty }) => (
            <div key={eq.id} className="flex items-center gap-3 px-5 py-3.5 border-b border-hairline last:border-b-0">
              <div
                className="w-11 h-11 rounded-lg bg-surface border border-hairline flex items-center justify-center text-muted-foreground shrink-0"
              >
                <CatIcon cat={eq.category} size={18} />
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
                <div className="font-mono text-sm font-bold text-ink" style={{ fontVariantNumeric: "tabular-nums" }}>
                  {formatARS(eq.pricePerDay * qty * jornadasEfectivas)}
                </div>
                <div className="font-mono text-[9px] tracking-[0.1em] text-muted-foreground mt-0.5">
                  {fechaDesde ? `${jornadas} jorn.` : "/ jorn."}
                </div>
              </div>
            </div>
          ))}

          {/* Totals — auto margin pushes to bottom when few items */}
          <div className="border-t border-hairline mt-auto">
            <div className="flex flex-col gap-2 px-5 py-3.5">
              <div className="flex justify-between items-baseline">
                <span className="font-sans text-[13px] text-muted-foreground">Subtotal equipos</span>
                <span className="font-mono text-[13px] font-semibold text-ink tabular-nums">{formatARS(subtotal)}</span>
              </div>

              {descJornadas && (
                <div className="flex items-center justify-between py-1">
                  <div className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
                    Descuento jornadas
                    <span className="inline-flex items-center px-1.5 py-px rounded-full font-mono text-[9px] font-bold bg-blue-100 text-blue-700">
                      −{descJornadas.pct}% · {descJornadas.label}
                    </span>
                  </div>
                  <span className="font-mono text-[13px] font-semibold text-green-700 tabular-nums">
                    −{formatARS(montoDescJornadas)}
                  </span>
                </div>
              )}

              <div className="flex items-center justify-between py-1">
                <div className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
                  Descuento cliente
                  <span className="inline-flex items-center px-1.5 py-px rounded-full font-mono text-[9px] font-bold bg-green-100 text-green-700">
                    −{descCliente.pct}% · {descCliente.label}
                  </span>
                </div>
                <span className="font-mono text-[13px] font-semibold text-green-700 tabular-nums">
                  −{formatARS(montoDescCliente)}
                </span>
              </div>

              <div className="flex justify-between items-baseline opacity-45">
                <span className="font-sans text-[13px] text-muted-foreground">Depósito de seguridad</span>
                <span className="font-mono text-[13px] text-muted-foreground">A definir</span>
              </div>

              <div className="flex justify-between items-baseline pt-2 border-t border-hairline mt-1">
                <span className="font-sans text-[15px] font-bold text-ink">
                  {fechaDesde ? "Total estimado" : "Estimado / jornada"}
                </span>
                <span style={{ fontFamily: "var(--font-display)", fontSize: 24, fontWeight: 900, color: "var(--ink)", fontVariantNumeric: "tabular-nums" }}>
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
                style={{ background: "var(--amber-soft)", borderColor: "color-mix(in oklch, var(--amber) 40%, transparent)" }}
              >
                <div className="font-sans text-sm font-bold text-ink mb-0.5">¡Listo! Rental solicitado.</div>
                <div className="font-sans text-xs text-muted-foreground leading-relaxed">
                  Lo revisamos manualmente y te confirmamos a la brevedad.
                </div>
              </div>
              <button className="w-full py-3 rounded-full border-[1.5px] border-hairline bg-transparent text-ink font-sans text-sm font-semibold flex items-center justify-center gap-2 hover:border-ink hover:bg-muted transition-colors">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z" />
                  <path d="M12 0C5.373 0 0 5.373 0 12c0 2.122.558 4.112 1.528 5.836L.057 23.857a.5.5 0 00.609.61l6.098-1.458A11.945 11.945 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.818 9.818 0 01-5.006-1.368l-.36-.214-3.722.89.921-3.618-.234-.373A9.818 9.818 0 1112 21.818z" fillRule="evenodd" clipRule="evenodd" />
                </svg>
                Consultanos por WhatsApp
              </button>
            </div>
          ) : (
            <button
              className="w-full py-3.5 rounded-full bg-ink text-amber font-sans text-[15px] font-bold hover:bg-amber hover:text-ink transition-colors"
              onClick={() => setSolicitado(true)}
            >
              Solicitar rental
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
        style={{ height: "72%", maxHeight: "72%", borderRadius: "24px 24px 0 0", boxShadow: "0 -8px 40px rgba(0,0,0,0.18)" }}
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
          {/* Photo placeholder */}
          <div
            className="mx-5 mt-3.5 rounded-[var(--radius-lg)] border border-hairline bg-surface flex items-center justify-center text-muted-foreground"
            style={{ aspectRatio: "4/3" }}
          >
            <CatIcon cat={eq.category} size={48} />
          </div>

          {/* Price */}
          <div className="px-5 pt-3.5 flex justify-between items-baseline">
            <div>
              <div
                className="font-mono font-bold leading-none"
                style={{ fontSize: 22, fontVariantNumeric: "tabular-nums" }}
              >
                {fechaDesde
                  ? formatARS(eq.pricePerDay * jornadas)
                  : formatARS(eq.pricePerDay)}
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
              onClick={() => { onAddToCart(eq.id, 1); onClose(); }}
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

function EquipmentRow({ eq, inCart, isExpanded, jornadas, fechaDesde, onTap, onAdd, onFicha }: EquipmentRowProps) {
  const priceDisplay = fechaDesde
    ? formatARS(eq.pricePerDay * jornadas)
    : formatARS(eq.pricePerDay);
  const priceMeta = fechaDesde ? `${jornadas} jorn.` : "/ jornada";

  const expansionTotal = formatARS(eq.pricePerDay * (inCart || 1) * jornadas);

  return (
    <div
      className={cn(
        "mb-1.5 rounded-[var(--radius-lg)] overflow-hidden border bg-card transition-all duration-150",
        isExpanded
          ? "border-amber"
          : "border-hairline",
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
        <div className="w-12 h-12 rounded-full bg-surface border border-hairline flex items-center justify-center text-muted-foreground shrink-0">
          <CatIcon cat={eq.category} size={20} />
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
                    {item.name}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Specs */}
          <div className="font-sans text-[11px] text-muted-foreground leading-relaxed mb-2.5">
            {eq.description || eq.specs.map((s) => `${s.label}: ${s.value}`).join(" · ") || "—"}
          </div>

          {/* Ficha link */}
          <button
            className="inline-flex items-center gap-1 font-sans text-xs font-semibold text-ink border-b border-b-ink pb-px hover:text-amber hover:border-amber transition-colors"
            onClick={(e) => { e.stopPropagation(); onFicha(); }}
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

  // Cart store
  const cart = useCart();

  // Catalog state
  const [activeTab, setActiveTab] = useState("Todo");
  const [query, setQuery] = useState("");
  const [stockOnly, setStockOnly] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  // Date state
  const [fechaDesde, setFechaDesde] = useState<Date | null>(null);
  const [jornadas, setJornadas] = useState(3);
  const [horaDesde, setHoraDesde] = useState("10:00");
  const [horaHasta, setHoraHasta] = useState("10:00");

  // Sheet state
  const [showDateSheet, setShowDateSheet] = useState(false);
  const [showCartSheet, setShowCartSheet] = useState(false);
  const [fichaEq, setFichaEq] = useState<Equipment | null>(null);

  // Scroll state
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => setIsScrolled(el.scrollTop > 56);
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // Derived date values
  const fechaHasta = useMemo(
    () => (fechaDesde ? addDays(fechaDesde, jornadas - 1) : null),
    [fechaDesde, jornadas],
  );

  const datePillLabel = useMemo(() => {
    if (!fechaDesde) return "Elegir fechas";
    const fmt = (d: Date) => {
      const dias = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
      return `${dias[d.getDay()]} ${d.getDate()}`;
    };
    return `${fmt(fechaDesde)} · ${fmt(fechaHasta!)}`;
  }, [fechaDesde, fechaHasta]);

  // Unique categories from data
  const categories = useMemo(() => {
    const cats = new Set(allEquipos.map((e) => e.category));
    return ["Todo", ...Array.from(cats).sort()];
  }, [allEquipos]);

  // Filtered equipment
  const filteredEquipos = useMemo(() => {
    const norm = (s: string) =>
      (s ?? "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    return allEquipos.filter((e) => {
      const matchCat = activeTab === "Todo" || e.category === activeTab;
      const matchQ =
        query === "" ||
        norm([e.name, e.brand, e.category, e.description ?? ""].join(" ")).includes(norm(query));
      const matchStock = !stockOnly || (e.cantidad == null || e.cantidad > 0);
      return matchCat && matchQ && matchStock;
    });
  }, [allEquipos, activeTab, query, stockOnly]);

  // Cart totals
  const totalItems = Object.values(cart.items).reduce((s, q) => s + q, 0);
  const totalARS = Object.entries(cart.items).reduce((s, [id, q]) => {
    const eq = allEquipos.find((e) => e.id === id);
    return s + (eq ? eq.pricePerDay * q * jornadas : 0);
  }, 0);

  const handleAddToCart = useCallback((id: string, delta: number) => {
    if (delta > 0) cart.add(id);
    else cart.remove(id);
  }, [cart]);

  const handleRowTap = useCallback((id: string) => {
    setExpanded((prev) => (prev === id ? null : id));
  }, []);

  const handleTabChange = useCallback((cat: string) => {
    setActiveTab(cat);
    setExpanded(null);
  }, []);

  const handleConfirmDates = useCallback(
    ({ fechaDesde: fd, jornadas: j, horaDesde: hd, horaHasta: hh }: {
      fechaDesde: Date; jornadas: number; horaDesde: string; horaHasta: string;
    }) => {
      setFechaDesde(fd);
      setJornadas(j);
      setHoraDesde(hd);
      setHoraHasta(hh);
      // Sync to cart store for cross-page consistency
      cart.setDates(fd, addDays(fd, j - 1));
      cart.setStartTime(hd);
      cart.setEndTime(hh);
      setShowDateSheet(false);
    },
    [cart],
  );

  // Height of compact search (used for category tabs top offset)
  const searchStickyTop = isScrolled ? 97 : 53;

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-background relative">
      {/* Scroll container */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto overflow-x-hidden"
        style={{ WebkitOverflowScrolling: "touch", scrollbarWidth: "none" }}
      >
        {/* TopBar */}
        <header
          className="sticky top-0 z-40 flex items-center gap-2.5 px-4 py-[10px] border-b border-hairline backdrop-blur-xl"
          style={{ background: TOPBAR_BG }}
        >
          <img
            src="/rambla-icon-seal.png"
            alt="Rambla"
            width={34}
            height={34}
            className="shrink-0 block"
          />

          <button
            className="flex-1 flex items-center justify-center gap-1.5 py-1.5 px-3.5 rounded-full font-sans text-xs font-semibold text-ink transition-all whitespace-nowrap"
            style={{
              border: "1.5px solid color-mix(in oklch, var(--amber) 55%, transparent)",
              background: "var(--amber-soft)",
            }}
            onClick={() => setShowDateSheet(true)}
          >
            <Calendar size={14} style={{ color: "color-mix(in oklch, var(--amber) 80%, var(--ink))", flexShrink: 0 }} />
            <span>{datePillLabel}</span>
            {fechaDesde && (
              <span className="font-mono text-[9px] tracking-[0.2em] uppercase text-muted-foreground">
                · {jornadas} jorn.
              </span>
            )}
          </button>

          <button
            className="p-1.5 rounded-full border border-hairline text-ink hover:border-ink transition-colors"
          >
            <User size={15} />
          </button>
        </header>

        {/* SearchSection */}
        <div
          className={cn(
            "transition-all",
            isScrolled
              ? "sticky z-[38] backdrop-blur border-b border-hairline px-3.5 py-1.5"
              : "px-4 pt-3 pb-2",
          )}
          style={
            isScrolled
              ? { top: 53, background: SEARCH_BG }
              : undefined
          }
        >
          <div className="relative">
            <Search
              size={15}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"
            />
            <input
              className={cn(
                "w-full rounded-[var(--radius-lg)] border-[1.5px] border-hairline bg-surface font-sans text-ink placeholder:text-muted-foreground outline-none transition-all focus:border-amber",
                isScrolled ? "text-[13px] py-2 pl-[34px] pr-3" : "text-sm py-[11px] pl-[38px] pr-3",
              )}
              style={{
                fontFamily: "var(--font-sans)",
                boxShadow: undefined,
              }}
              placeholder="Buscar equipo, marca, pack…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>

          {/* Popular chips — hidden when compact */}
          {!isScrolled && (
            <div className="flex gap-1.5 mt-2 overflow-x-auto pb-0.5" style={{ scrollbarWidth: "none" }}>
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
          )}
        </div>

        {/* Category tabs */}
        <div
          className="sticky z-[39] border-b border-hairline backdrop-blur transition-[top] duration-150"
          style={{
            top: searchStickyTop,
            background: TABS_BG,
          }}
        >
          <div className="flex overflow-x-auto px-4" style={{ scrollbarWidth: "none", gap: 0 }}>
            {categories.map((cat) => {
              const count =
                cat === "Todo"
                  ? allEquipos.length
                  : allEquipos.filter((e) => e.category === cat).length;
              return (
                <button
                  key={cat}
                  className={cn(
                    "flex items-baseline gap-1 py-[10px] pb-[9px] px-3 whitespace-nowrap shrink-0 border-b-[2.5px] transition-all",
                    activeTab === cat
                      ? "border-amber"
                      : "border-transparent",
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
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
                <path d="M20 6L9 17l-5-5" />
              </svg>
            )}
            Disponibles
          </button>
          <button className="flex items-center gap-1.5 px-[11px] py-[5px] rounded-full border border-hairline font-sans text-[11px] font-medium text-ink hover:border-ink hover:bg-muted transition-all">
            Marca ▾
          </button>
          <div className="flex-1" />
          <button className="flex items-center gap-1.5 px-[11px] py-[5px] rounded-full border border-hairline font-sans text-[11px] font-medium text-muted-foreground hover:border-ink hover:text-ink transition-all">
            <SlidersHorizontal size={11} />
            Filtros
          </button>
        </div>

        {/* Equipment list */}
        <div className="flex flex-col px-4" style={{ paddingBottom: 120 }}>
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

        {/* CartMiniBar */}
        {totalItems > 0 && (
          <div
            className="sticky bottom-0 z-40 flex items-center gap-2.5 px-4 cursor-pointer border-t-[1.5px] border-amber backdrop-blur-lg transition-colors hover:bg-amber/5"
            style={{
              background: CARTBAR_BG,
              boxShadow: "0 -8px 24px -8px rgba(0,0,0,0.12)",
              paddingTop: 10,
              paddingBottom: 14,
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
            <ChevronUp size={16} className="text-muted-foreground hover:text-ink transition-colors shrink-0" />
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
    </div>
  );
}
