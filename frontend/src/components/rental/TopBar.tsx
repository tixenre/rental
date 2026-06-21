import { Link } from "@tanstack/react-router";
import { useCart } from "@/lib/cart-store";
import { useState, type ReactNode } from "react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { Calendar as CalendarIcon, ShoppingBag, User, LogOut } from "lucide-react";
import { RentalDateModal } from "./RentalDateModal";
import { Logo } from "./Logo";
import { LogoMark } from "./LogoMark";
import { AreaMenu } from "./AreaMenu";
import { cn } from "@/lib/utils";

// ── Dimensiones compartidas del topbar (fuente única) ──────────────────────────
// Todas las variantes salen del mismo shell → mismo alto y padding en toda la web.
const TOPBAR_H = "h-16";
const TOPBAR_PX = "px-4 md:px-8";

// ── Config por sección ──────────────────────────────────────────────────────────
// Cada área tiene su color de marca de fondo y el logo en blanco. Una sola lógica.
const SECTION_CONFIG = {
  rental: {
    label: "rental.",
    href: "/catalogo",
    bg: "bg-amber",
    ctaColor: "bg-ink text-amber hover:opacity-90",
  },
  estudio: {
    label: "estudio.",
    href: "/estudio",
    bg: "bg-naranja",
    ctaColor: "bg-white text-ink hover:bg-white/90",
  },
  workshops: {
    label: "workshops.",
    href: "/talleres",
    bg: "bg-rosa",
    ctaColor: "bg-white text-ink hover:bg-white/90",
  },
  cliente: {
    label: "portal.",
    href: "/cliente/portal",
    bg: "bg-verde",
    ctaColor: "bg-white text-ink hover:bg-white/90",
  },
} as const;

export type Section = keyof typeof SECTION_CONFIG;

const SECTION_DEFAULT_CTA: Record<Section, { label: string; href: string } | null> = {
  rental: null,
  estudio: { label: "Reservar el estudio", href: "/estudio#reserva" },
  workshops: null,
  cliente: null,
};

export type TopBarProps = {
  /**
   * - "default" / "rental": catálogo (dates pill + carrito + Ingresar).
   * - "estudio" / "workshops": topbar de sección + CTA.
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
};

export function TopBar({
  variant = "default",
  cta,
  userName,
  onLogout,
  onProfileClick,
}: TopBarProps = {}) {
  if (variant === "cliente") {
    return (
      <ClienteTopBar userName={userName} onLogout={onLogout} onProfileClick={onProfileClick} />
    );
  }
  if (variant === "estudio") return <SectionTopBar section="estudio" ctaOverride={cta} />;
  if (variant === "workshops") return <SectionTopBar section="workshops" ctaOverride={cta} />;
  // "default" | "rental"
  return <RentalTopBar />;
}

// ── Shell único del topbar ───────────────────────────────────────────────────────
// Estructura compartida: <header> sticky con alto/padding/bg de marca fijos, logo a
// la izquierda, slot central opcional y slot derecho. De acá salen TODAS las barras
// (incluido el catálogo mobile, que lo importa directo con sus propios slots).
export function TopBarShell({
  section,
  center,
  centerClassName = "flex",
  right,
  headerRef,
}: {
  section: Section;
  center?: ReactNode;
  /** Clases del contenedor central — el caller decide su visibilidad (ej. "hidden md:flex"). */
  centerClassName?: string;
  right?: ReactNode;
  /** Para medir la altura real del topbar (ej. sticky tops del catálogo mobile). */
  headerRef?: React.Ref<HTMLElement>;
}) {
  const { bg } = SECTION_CONFIG[section];
  return (
    <header
      ref={headerRef}
      className={cn("sticky top-0 z-[var(--z-topbar)] pt-[env(safe-area-inset-top)]", bg)}
    >
      <div className={cn("flex items-center gap-3", TOPBAR_H, TOPBAR_PX)}>
        {/* Sin label en mobile cuando hay date pill central (no hay espacio). */}
        <SectionLogo section={section} labelMobile={!center} />
        {center && (
          <div className={cn("flex-1 justify-center px-2 min-w-0", centerClassName)}>{center}</div>
        )}
        <div className="ml-auto flex items-center gap-2 shrink-0">
          {right}
          <AreaMenu current={section} />
        </div>
      </div>
    </header>
  );
}

// ── Logo compuesto: isologo (mobile) / wordmark (desktop) + label de área ─────────
// El logo ES la navegación de vuelta al root del área. Siempre blanco sobre el color.
export function SectionLogo({
  section,
  labelMobile = true,
}: {
  section: Section;
  /** Mostrar el label del área en mobile. False cuando el topbar ya tiene un
   *  control central (date pill) que no deja espacio. */
  labelMobile?: boolean;
}) {
  const { label, href } = SECTION_CONFIG[section];
  return (
    <Link
      to={href}
      className="inline-flex items-center sm:items-end gap-2 sm:gap-2.5 group shrink-0"
    >
      {/* Mobile: isologo (R) — mono blanco, la R muestra el color del área */}
      <LogoMark mono className="sm:hidden text-white h-9 w-9" />
      {/* Desktop: wordmark completo */}
      <Logo linkTo={null} size="sm" color="text-white" className="max-sm:hidden" />
      <span
        className={cn(
          "font-display font-black lowercase leading-none text-white text-base",
          !labelMobile && "max-sm:hidden",
        )}
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
// Fondo amber sólido (color del área) → controles en blanco/ink para contrastar.
function RentalTopBar() {
  const { startDate, endDate, startTime, endTime, setDrawerOpen, totalItems, days } = useCart();
  const [dateModalOpen, setDateModalOpen] = useState(false);
  const count = totalItems();
  const hasDates = !!(startDate && endDate);
  const jornadas = days();

  const datesPill = (
    <button
      onClick={() => setDateModalOpen(true)}
      className="inline-flex items-center justify-center gap-2 rounded-full border border-background/70 bg-background px-5 py-2 text-ink shadow-sm transition hover:bg-background/90"
      aria-label={hasDates ? "Editar fechas y horarios" : "Elegir fechas"}
    >
      <CalendarIcon className="h-4 w-4 shrink-0 text-amber" />
      {hasDates ? (
        <span className="text-sm font-semibold tabular-nums truncate">
          {format(startDate!, "EEE dd MMM", { locale: es })} {startTime}
          <span className="mx-1.5 opacity-50">→</span>
          {format(endDate!, "EEE dd MMM", { locale: es })} {endTime}
          <span className="ml-2 font-mono text-[10px] uppercase tracking-wider text-ink/60">
            · {jornadas} {jornadas === 1 ? "jornada" : "jornadas"}
          </span>
        </span>
      ) : (
        <span className="text-sm font-semibold">Elegir fechas</span>
      )}
    </button>
  );

  const actions = (
    // Carrito solo desktop (en mobile vive en MobileStickyBar / CartMiniBar).
    // El acceso cliente se movió al menú (AreaMenu).
    <button
      onClick={() => setDrawerOpen(true, "bottom")}
      className="hidden md:flex items-center gap-2 rounded-full bg-ink px-4 py-2 text-sm font-medium text-amber transition relative hover:opacity-90"
      aria-label={`Carrito (${count})`}
    >
      <ShoppingBag className="h-4 w-4" />
      {count > 0 && <span className="tabular-nums">{count}</span>}
      <span>{count > 0 ? (count === 1 ? "ítem" : "ítems") : "Tu rental"}</span>
    </button>
  );

  return (
    <>
      <RentalDateModal open={dateModalOpen} onOpenChange={setDateModalOpen} />
      <TopBarShell
        section="rental"
        center={datesPill}
        centerClassName="hidden md:flex"
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
      <div className="flex h-[26px] w-[26px] items-center justify-center rounded-full bg-verde text-white font-display text-xs font-black shrink-0">
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
          className="inline-flex items-center gap-2 rounded-full bg-background px-2 py-1 hover:bg-background/90 transition"
          title="Ver mi cuenta"
        >
          {pillContent}
        </button>
      ) : (
        <Link
          to="/cliente/perfil"
          className="inline-flex items-center gap-2 rounded-full bg-background px-2 py-1 hover:bg-background/90 transition"
          title="Editar mi perfil"
        >
          {pillContent}
        </Link>
      )}

      {onLogout && (
        <button
          type="button"
          onClick={onLogout}
          className="inline-flex items-center gap-1.5 rounded-full bg-white/15 text-white px-3 py-2 text-sm hover:bg-white/25 transition"
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
