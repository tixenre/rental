import { useEffect, useRef, useState } from "react";
import { Calendar, ShoppingBag, User } from "lucide-react";
import { cn } from "./lib/cn";

/**
 * TopBar — pattern compuesto del header sticky con la jugada "amber-scroll":
 * en mobile, mientras hacés scroll, el bloque amber sube desde abajo y a 65%
 * del progreso los chips (date-pill + user-btn + seal) se invierten a bone-on-amber.
 *
 * Anatomía:
 *   ┌──────────────────────────────────────────────────────────┐
 *   │  [seal] rambla   [📅 Elegir fechas]   [🛒 0]  [👤 Ingresar] │
 *   └──────────────────────────────────────────────────────────┘
 *
 * Usa CSS var `--amber-pct` (0%→100%) que se actualiza en scroll listener.
 * A 65% se agrega `.topbar-snap` al header que dispara los color swaps.
 *
 * Versión simplificada: recibe slots por props (logoSrc, dateLabel, onDate,
 * cartCount, onCart, userLabel, onUser). Para uso real, conectá con tu store.
 *
 * @example
 *   <TopBar
 *     logoSrc="/assets/rambla-wordmark.webp"
 *     dateLabel="Elegir fechas"
 *     onDate={() => setOpen(true)}
 *     cartCount={0}
 *     onCart={() => setCart(true)}
 *     userLabel="Ingresar"
 *     onUser={() => navigate("/cliente")}
 *   />
 */
export function TopBar({
  logoSrc,
  logoAlt = "Rambla Rental",
  dateLabel = "Elegir fechas",
  hasDates = false,
  onDate,
  cartCount = 0,
  onCart,
  userLabel = "Ingresar",
  onUser,
  className,
}: {
  logoSrc: string;
  logoAlt?: string;
  dateLabel?: string;
  hasDates?: boolean;
  onDate?: () => void;
  cartCount?: number;
  onCart?: () => void;
  userLabel?: string;
  onUser?: () => void;
  className?: string;
}) {
  const ref = useRef<HTMLElement>(null);
  const [snap, setSnap] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onScroll = () => {
      const max = 120; // px to fully amber-ify
      const y = Math.min(window.scrollY, max);
      const pct = (y / max) * 100;
      el.style.setProperty("--amber-pct", `${pct}%`);
      setSnap(pct >= 65);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      ref={ref}
      className={cn(
        "topbar-amber sticky top-0 z-50 w-full border-b border-hairline transition-colors safe-t",
        snap && "topbar-snap",
        className,
      )}
      style={{
        background:
          "linear-gradient(to top, var(--amber) 0%, var(--amber) var(--amber-pct, 0%), var(--background) var(--amber-pct, 0%), var(--background) 100%)",
        backdropFilter: "blur(12px)",
      }}
    >
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:px-6 lg:px-12">
        {/* Logo / wordmark */}
        <a
          href="/"
          aria-label={logoAlt}
          className="flex shrink-0 items-center gap-2"
        >
          <img src={logoSrc} alt={logoAlt} className="h-6 w-auto sm:h-7" />
        </a>

        {/* Date pill — la pieza central, se invierte en snap */}
        <button
          onClick={onDate}
          aria-label={hasDates ? "Editar fechas" : "Elegir fechas"}
          className={cn(
            "date-pill-snap mx-auto inline-flex h-10 items-center gap-2 rounded-full border-2 border-ink bg-background px-4 font-sans text-sm font-medium text-ink transition-colors",
            "hover:bg-amber hover:border-amber",
            hasDates && "bg-amber border-amber",
          )}
        >
          <Calendar className="h-4 w-4" />
          <span>{dateLabel}</span>
        </button>

        {/* Acciones derecha */}
        <div className="flex shrink-0 items-center gap-2">
          {/* Cart */}
          <button
            onClick={onCart}
            aria-label={`Carrito (${cartCount})`}
            className="user-btn-snap inline-flex h-10 items-center gap-1.5 rounded-full border border-hairline bg-background px-3 font-sans text-sm font-medium text-ink transition-colors hover:border-ink hover:bg-amber-soft"
          >
            <ShoppingBag className="h-4 w-4" />
            <span className="tabular">{cartCount}</span>
          </button>

          {/* User */}
          <button
            onClick={onUser}
            className="user-btn-snap hidden h-10 items-center gap-1.5 rounded-full border border-hairline bg-background px-3 font-sans text-sm font-medium text-ink transition-colors hover:border-ink hover:bg-amber-soft sm:inline-flex"
          >
            <User className="h-4 w-4" />
            <span>{userLabel}</span>
          </button>
        </div>
      </div>
    </header>
  );
}
