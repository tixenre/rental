import { Link } from "@tanstack/react-router";
import { useCart } from "@/lib/cart-store";
import { useEffect, useRef, useState } from "react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { Calendar as CalendarIcon, ShoppingBag, User, LogOut } from "lucide-react";
import { RentalDateModal } from "./RentalDateModal";
import { Logo } from "./Logo";
import { LogoMark } from "./LogoMark";
import { cn } from "@/lib/utils";
import { useClienteSession } from "@/lib/iva";

// ── Config por sección ────────────────────────────────────────────────────────
const SECTION_CONFIG = {
  rental:    { label: "rental.",    labelColor: "text-amber", href: "/catalogo", bg: "",             ctaColor: "" },
  estudio:   { label: "estudio.",   labelColor: "text-white", href: "/estudio",  bg: "bg-naranja",   ctaColor: "bg-white text-ink hover:bg-white/90" },
  workshops: { label: "workshops.", labelColor: "text-white", href: "/talleres", bg: "bg-rosa",      ctaColor: "bg-white text-ink hover:bg-white/90" },
} as const;

type Section = keyof typeof SECTION_CONFIG;

export type TopBarProps = {
  /**
   * - "default" / "rental": catálogo público (dates pill + carrito + Ingresar).
   * - "estudio" / "workshops": topbar de sección con fondo de color.
   * - "cliente": post-login del portal (sin dates pill ni carrito).
   */
  variant?: "default" | "rental" | "estudio" | "workshops" | "cliente";
  /** CTA override para section bars. Si no se pasa se usa el default de la sección. */
  cta?: { label: string; href: string };
  /** Solo aplica cuando variant === "cliente". */
  userName?: string;
  /** Solo aplica cuando variant === "cliente". */
  onLogout?: () => void;
  onProfileClick?: () => void;
  /**
   * Cuando true, el TopBar se tiñe de amber gradualmente conforme el hero scrollea.
   * Solo aplica en variant "rental" / "default".
   */
  amberOnScroll?: boolean;
};

export function TopBar({
  variant = "default",
  cta,
  userName,
  onLogout,
  onProfileClick,
  amberOnScroll,
}: TopBarProps = {}) {
  if (variant === "cliente") {
    return (
      <ClienteTopBar userName={userName} onLogout={onLogout} onProfileClick={onProfileClick} />
    );
  }
  if (variant === "estudio") return <SectionTopBar section="estudio" ctaOverride={cta} />;
  if (variant === "workshops") return <SectionTopBar section="workshops" ctaOverride={cta} />;
  // "default" | "rental"
  return <RentalTopBar amberOnScroll={amberOnScroll} />;
}

// ── Logo compuesto: RAMBLA + área ─────────────────────────────────────────────
function SectionLogo({ section }: { section: Section }) {
  const { label, labelColor, href, bg } = SECTION_CONFIG[section];
  const logoColor = bg ? "text-white" : "text-amber";
  return (
    <Link to={href} className="inline-flex items-end gap-3 group">
      {/* Mobile: isologo (R) */}
      <LogoMark className="sm:hidden" />
      {/* Desktop: wordmark completo */}
      <Logo linkTo={null} size="sm" color={logoColor} className="max-sm:hidden" />
      <span
        className={`font-display font-black lowercase leading-none ${labelColor}`}
        style={{ fontSize: "1rem" }}
      >
        {label}
      </span>
    </Link>
  );
}

// ── TopBar de secciones (estudio / workshops) ─────────────────────────────────
const SECTION_DEFAULT_CTA: Record<Section, { label: string; href: string } | null> = {
  rental:    null,
  estudio:   { label: "Reservar el estudio", href: "/estudio#reserva" },
  workshops: null,
};

// ── TopBar de sección: logo izquierda · CTA derecha ──────────────────────────
// El logo ES la navegación de vuelta al root del área (workshops → /talleres).
function SectionTopBar({
  section,
  ctaOverride,
}: {
  section: Section;
  ctaOverride?: { label: string; href: string };
}) {
  const { bg, ctaColor } = SECTION_CONFIG[section];
  const cta = ctaOverride ?? SECTION_DEFAULT_CTA[section];

  return (
    <header className={`sticky top-0 z-[var(--z-topbar)] h-20 ${bg}`}>
      <div className="h-full px-8 md:px-12 flex items-center justify-between gap-4">
        <SectionLogo section={section} />
        {cta && (
          <a
            href={cta.href}
            className={`inline-flex items-center gap-1.5 rounded-full px-5 py-2 text-sm font-bold transition ${ctaColor}`}
          >
            {cta.label}
          </a>
        )}
      </div>
    </header>
  );
}

// ── TopBar del rental (variante original) ─────────────────────────────────────
function RentalTopBar({ amberOnScroll }: { amberOnScroll?: boolean }) {
  const { startDate, endDate, startTime, endTime, setDrawerOpen, totalItems, days } = useCart();
  const [dateModalOpen, setDateModalOpen] = useState(false);
  const headerRef = useRef<HTMLElement>(null);
  const [snapped, setSnapped] = useState(false);
  const count = totalItems();
  const hasDates = !!(startDate && endDate);
  const jornadas = days();

  const { data: clienteSession } = useClienteSession();
  const isLogged = !!clienteSession;
  const initial = clienteSession?.nombre?.trim()[0]?.toUpperCase() ?? null;
  const firstName = clienteSession?.nombre?.trim().split(" ")[0] ?? null;
  const userLinkTo = isLogged ? "/cliente/portal" : "/cliente";
  const userLinkLabel = isLogged ? `Mi cuenta · ${firstName ?? ""}`.trim() : "Ingresar";

  useEffect(() => {
    if (!amberOnScroll) return;
    const header = headerRef.current;
    if (!header) return;

    const onScroll = () => {
      const pct = parseFloat(
        getComputedStyle(document.documentElement).getPropertyValue("--amber-pct") || "0",
      );
      header.style.background = `color-mix(in oklch, var(--amber) ${pct}%, color-mix(in oklch, var(--background) 92%, transparent))`;
      setSnapped(pct >= 65);
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, [amberOnScroll]);

  return (
    <>
      <RentalDateModal open={dateModalOpen} onOpenChange={setDateModalOpen} />
      <header
        ref={headerRef}
        className="sticky top-0 z-[var(--z-topbar)] h-16 border-b hairline backdrop-blur-xl transition-[background,border-color]"
      >
        <div
          className={cn(
            "h-full px-4 md:px-6 md:grid md:grid-cols-[auto_1fr_auto] md:gap-4 md:items-center",
            !amberOnScroll && "bg-background/95 md:bg-background/85",
          )}
        >
          {/* Mobile: logo centrado + botón sesión derecha */}
          <div className="flex h-full w-full items-center md:hidden">
            <div className="w-10" />
            <div className="flex-1 flex justify-center">
              <Logo
                size="md"
                linkTo="/"
                className={cn(
                  "transition-[filter] duration-150",
                  snapped && "[filter:brightness(0)_invert(1)]",
                )}
              />
            </div>
            <Link
              to={userLinkTo}
              className={cn(
                "flex items-center justify-center w-11 h-11 rounded-full border hairline transition",
                isLogged
                  ? "bg-amber text-ink border-amber hover:opacity-90"
                  : "hover:border-foreground/40",
              )}
              aria-label={userLinkLabel}
              title={userLinkLabel}
            >
              {isLogged && initial ? (
                <span className="font-display text-sm font-black">{initial}</span>
              ) : (
                <User className="h-5 w-5" />
              )}
            </Link>
          </div>

          {/* Desktop col izquierda: logo + rental. */}
          <div className="hidden md:flex items-end gap-3 shrink-0">
            <Logo
              size="md"
              linkTo="/"
              className={cn(
                "transition-[filter] duration-150",
                snapped && "[filter:brightness(0)_invert(1)]",
              )}
            />
            <span
              className={cn(
                "font-display font-black lowercase leading-none transition-colors",
                snapped ? "text-background" : "text-amber",
              )}
              style={{ fontSize: "1rem" }}
            >
              rental.
            </span>
          </div>

          {/* Desktop col central: pill de fechas */}
          <div className="hidden md:flex px-4">
            <button
              onClick={() => setDateModalOpen(true)}
              className={cn(
                "w-full flex items-center justify-center gap-3 rounded-full border-2 px-6 py-2 transition shadow-sm",
                snapped
                  ? "border-background/80 bg-background text-ink hover:bg-background/90"
                  : "border-amber/50 bg-amber/10 hover:border-amber hover:bg-amber/20",
              )}
              aria-label={hasDates ? "Editar fechas y horarios" : "Elegir fechas"}
            >
              <CalendarIcon className="h-5 w-5 shrink-0 text-amber" />
              {hasDates ? (
                <span className="text-base font-semibold tabular-nums">
                  {format(startDate!, "EEE dd MMM", { locale: es })} {startTime}
                  <span className="mx-2 opacity-50">→</span>
                  {format(endDate!, "EEE dd MMM", { locale: es })} {endTime}
                  <span
                    className={cn(
                      "ml-2 font-mono text-[11px] uppercase tracking-wider",
                      snapped ? "text-ink/60" : "text-muted-foreground",
                    )}
                  >
                    · {jornadas} {jornadas === 1 ? "jornada" : "jornadas"}
                  </span>
                </span>
              ) : (
                <span className="text-base font-semibold">Elegir fechas</span>
              )}
            </button>
          </div>

          {/* Desktop col derecha: carrito + sesión */}
          <div className="hidden md:flex items-center gap-2 shrink-0">
            <button
              onClick={() => setDrawerOpen(true, "bottom")}
              className={cn(
                "flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition relative",
                snapped
                  ? "bg-ink text-amber hover:opacity-90"
                  : "bg-foreground text-background hover:bg-amber hover:text-ink",
              )}
              aria-label={`Carrito (${count})`}
            >
              <ShoppingBag className="h-4 w-4" />
              {count > 0 && <span className="tabular-nums">{count}</span>}
              <span>{count > 0 ? (count === 1 ? "ítem" : "ítems") : "Tu rental"}</span>
            </button>
            <Link
              to={userLinkTo}
              className={cn(
                "flex items-center gap-2 rounded-full border transition",
                isLogged ? "px-2 py-1.5 pr-3" : "px-0 py-0 w-9 h-9 justify-center",
                snapped
                  ? "border-background/80 bg-background text-ink hover:bg-background/90"
                  : isLogged
                    ? "border-amber/50 bg-amber/10 hover:bg-amber/20"
                    : "hairline hover:border-foreground/40",
              )}
              aria-label={userLinkLabel}
              title={userLinkLabel}
            >
              {isLogged && initial ? (
                <>
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-amber text-ink font-display text-[11px] font-black">
                    {initial}
                  </span>
                  {firstName && (
                    <span className="text-sm font-semibold leading-none">{firstName}</span>
                  )}
                </>
              ) : (
                <User className="h-4 w-4" />
              )}
            </Link>
          </div>
        </div>
      </header>
    </>
  );
}

// ── TopBar del portal cliente ─────────────────────────────────────────────────
function ClienteTopBar({
  userName,
  onLogout,
  onProfileClick,
}: {
  userName?: string;
  onLogout?: () => void;
  onProfileClick?: () => void;
}) {
  const initial = userName ? userName[0].toUpperCase() : null;
  const firstName = userName ? userName.split(" ")[0] : null;

  const pillContent = (
    <>
      <div className="flex h-[26px] w-[26px] items-center justify-center rounded-full bg-amber text-ink font-display text-xs font-black shrink-0">
        {initial ?? <User className="h-3.5 w-3.5" />}
      </div>
      {firstName && (
        <span className="hidden sm:block pr-1 text-sm font-semibold text-ink">{firstName}</span>
      )}
    </>
  );

  return (
    <header className="sticky top-0 z-[var(--z-topbar)] border-b hairline bg-background/95 backdrop-blur-md md:bg-background/85 md:backdrop-blur-xl">
      <div className="px-4 py-3 md:px-6 flex items-center gap-3">
        <div className="shrink-0">
          <Logo size="md" linkTo="/" />
        </div>
        <div className="flex-1" />

        {onProfileClick ? (
          <button
            type="button"
            onClick={onProfileClick}
            className="inline-flex items-center gap-2 rounded-full border hairline px-2 py-1 hover:border-ink/30 transition"
            title="Ver mi cuenta"
          >
            {pillContent}
          </button>
        ) : (
          <Link
            to="/cliente/perfil"
            className="inline-flex items-center gap-2 rounded-full border hairline px-2 py-1 hover:border-ink/30 transition"
            title="Editar mi perfil"
          >
            {pillContent}
          </Link>
        )}

        {onLogout && (
          <button
            type="button"
            onClick={onLogout}
            className="inline-flex items-center gap-1.5 rounded-full border hairline px-3 py-2 text-sm hover:border-foreground/40"
            aria-label="Salir"
          >
            <LogOut className="h-4 w-4" />
            <span className="hidden sm:inline">Salir</span>
          </button>
        )}
      </div>
    </header>
  );
}
