import { Link } from "@tanstack/react-router";
import { useCart } from "@/lib/cart-store";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { Calendar as CalendarIcon, ShoppingBag, User, LogOut } from "lucide-react";
import { RentalDateModal } from "./RentalDateModal";
import { Logo } from "./Logo";
import { LogoMark } from "./LogoMark";
import { cn } from "@/lib/utils";
import { useClienteSession } from "@/lib/iva";

// ── Dimensiones compartidas del topbar (fuente única) ──────────────────────────
// Todas las variantes salen del mismo shell → mismo alto y padding en toda la web.
const TOPBAR_H = "h-16";
const TOPBAR_PX = "px-4 md:px-8";

// ── Config por sección ──────────────────────────────────────────────────────────
// `bg` vacío = fondo claro (logo amber); `bg` de color = fondo de marca (logo blanco).
const SECTION_CONFIG = {
  rental: { label: "rental.", labelColor: "text-amber", href: "/catalogo", bg: "", ctaColor: "" },
  estudio: {
    label: "estudio.",
    labelColor: "text-white",
    href: "/estudio",
    bg: "bg-naranja",
    ctaColor: "bg-white text-ink hover:bg-white/90",
  },
  workshops: {
    label: "workshops.",
    labelColor: "text-white",
    href: "/talleres",
    bg: "bg-rosa",
    ctaColor: "bg-white text-ink hover:bg-white/90",
  },
  cliente: {
    label: "portal.",
    labelColor: "text-amber",
    href: "/cliente/portal",
    bg: "",
    ctaColor: "",
  },
} as const;

type Section = keyof typeof SECTION_CONFIG;

const SECTION_DEFAULT_CTA: Record<Section, { label: string; href: string } | null> = {
  rental: null,
  estudio: { label: "Reservar el estudio", href: "/estudio#reserva" },
  workshops: null,
  cliente: null,
};

export type TopBarProps = {
  /**
   * - "default" / "rental": catálogo público (dates pill + carrito + Ingresar).
   * - "estudio" / "workshops": topbar de sección con fondo de color + CTA.
   * - "cliente": post-login del portal (perfil + salir).
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

// ── Shell único del topbar ───────────────────────────────────────────────────────
// Estructura compartida: <header> sticky con alto/padding fijos, logo a la izquierda,
// slot central opcional (desktop) y slot derecho. De acá salen TODAS las variantes.
function TopBarShell({
  section,
  snapped = false,
  dynamicBg = false,
  headerRef,
  center,
  right,
}: {
  section: Section;
  snapped?: boolean;
  /** El rental tiñe el fondo por scroll vía style inline → el shell no fija bg. */
  dynamicBg?: boolean;
  headerRef?: React.Ref<HTMLElement>;
  center?: ReactNode;
  right?: ReactNode;
}) {
  const { bg } = SECTION_CONFIG[section];
  const colored = !!bg;
  return (
    <header
      ref={headerRef}
      className={cn(
        "sticky top-0 z-[var(--z-topbar)] transition-[background,border-color]",
        TOPBAR_H,
        colored && bg,
        !colored && "border-b hairline backdrop-blur-xl",
        !colored && !dynamicBg && "bg-background/95",
      )}
    >
      <div className={cn("h-full flex items-center justify-between gap-4", TOPBAR_PX)}>
        <SectionLogo section={section} snapped={snapped} />
        {center && (
          <div className="hidden md:flex flex-1 justify-center px-4 min-w-0">{center}</div>
        )}
        {right}
      </div>
    </header>
  );
}

// ── Logo compuesto: isologo (mobile) / wordmark (desktop) + label de área ─────────
// El logo ES la navegación de vuelta al root del área.
function SectionLogo({ section, snapped = false }: { section: Section; snapped?: boolean }) {
  const { label, labelColor, href, bg } = SECTION_CONFIG[section];
  const logoColor = bg ? "text-white" : "text-amber";
  return (
    <Link to={href} className="inline-flex items-end gap-2.5 group shrink-0">
      {/* Mobile: isologo (R) */}
      <LogoMark className="sm:hidden" />
      {/* Desktop: wordmark completo */}
      <Logo
        linkTo={null}
        size="sm"
        color={logoColor}
        className={cn("max-sm:hidden", snapped && "[filter:brightness(0)_invert(1)]")}
      />
      <span
        className={cn(
          "font-display font-black lowercase leading-none transition-colors",
          snapped ? "text-background" : labelColor,
        )}
        style={{ fontSize: "1rem" }}
      >
        {label}
      </span>
    </Link>
  );
}

// ── TopBar de secciones (estudio / workshops): logo + CTA ─────────────────────────
function SectionTopBar({
  section,
  ctaOverride,
}: {
  section: Section;
  ctaOverride?: { label: string; href: string };
}) {
  const { ctaColor } = SECTION_CONFIG[section];
  const cta = ctaOverride ?? SECTION_DEFAULT_CTA[section];
  return (
    <TopBarShell
      section={section}
      right={
        cta && (
          <a
            href={cta.href}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-5 py-2 text-sm font-bold transition shrink-0",
              ctaColor,
            )}
          >
            {cta.label}
          </a>
        )
      }
    />
  );
}

// ── TopBar del rental (catálogo): dates pill central + carrito + sesión ───────────
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

  const datesPill = (
    <button
      onClick={() => setDateModalOpen(true)}
      className={cn(
        "w-full max-w-xl flex items-center justify-center gap-3 rounded-full border-2 px-6 py-2 transition shadow-sm",
        snapped
          ? "border-background/80 bg-background text-ink hover:bg-background/90"
          : "border-amber/50 bg-amber/10 hover:border-amber hover:bg-amber/20",
      )}
      aria-label={hasDates ? "Editar fechas y horarios" : "Elegir fechas"}
    >
      <CalendarIcon className="h-5 w-5 shrink-0 text-amber" />
      {hasDates ? (
        <span className="text-base font-semibold tabular-nums truncate">
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
  );

  const actions = (
    <div className="flex items-center gap-2 shrink-0">
      {/* Carrito: solo desktop (en mobile vive en MobileStickyBar / CartMiniBar) */}
      <button
        onClick={() => setDrawerOpen(true, "bottom")}
        className={cn(
          "hidden md:flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition relative",
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
      {/* Sesión: siempre */}
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
              <span className="hidden sm:block text-sm font-semibold leading-none">
                {firstName}
              </span>
            )}
          </>
        ) : (
          <User className="h-4 w-4" />
        )}
      </Link>
    </div>
  );

  return (
    <>
      <RentalDateModal open={dateModalOpen} onOpenChange={setDateModalOpen} />
      <TopBarShell
        section="rental"
        headerRef={headerRef}
        snapped={snapped}
        dynamicBg={!!amberOnScroll}
        center={datesPill}
        right={actions}
      />
    </>
  );
}

// ── TopBar del portal cliente: logo + perfil + salir ──────────────────────────────
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

  const actions = (
    <div className="flex items-center gap-2 shrink-0">
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
  );

  return <TopBarShell section="cliente" right={actions} />;
}
