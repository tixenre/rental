import { LogOut, ShoppingBag, User } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * TopBar — barra de navegación principal de la app pública y portal cliente.
 *
 * Variantes:
 *   - "default"  → catálogo público. Muestra date pill + cart button + user icon.
 *   - "cliente"  → portal de pedidos. Muestra avatar con nombre + logout.
 *
 * amberOnScroll:
 *   Escucha el scroll. Al superar el 65% del scroll total de la página,
 *   el fondo snappea a --amber y el logo se invierte (brightness(0) invert(1)).
 *   Implementado con CSS var --amber-pct en el elemento raíz.
 *   Se usa en la home del catálogo con hero amber.
 *
 * z-index: --z-topbar (50) para el header; --z-topbar-amber (49) para la
 * capa de transición de fondo (si la hay). Ver spacing-zindex.html.
 *
 * Mobile:
 *   - Logo → badge seal (32px) en vez de wordmark.
 *   - Date pill → compacto (truncado).
 *   - Cart → icon button con badge dot, sin texto.
 *
 * Source visual: `preview/components-topbar.html` y `preview/components-topbar-cart.html`
 */

export interface TopBarProps {
  variant?: "default" | "cliente";
  /** Texto del pill de fechas. Undefined = estado vacío "Elegí tus fechas". */
  dateLabel?: string;
  onDateClick?: () => void;
  onCartClick?: () => void;
  cartCount?: number;
  /** Variante cliente — nombre visible del usuario. */
  userName?: string;
  /** Variante cliente — handler de logout. */
  onLogout?: () => void;
  /**
   * Activa efecto amber-on-scroll: al llegar al 65% del scroll
   * de la página el fondo se convierte en --amber sólido.
   * Usar sólo en la ruta `/` con hero amber.
   */
  amberOnScroll?: boolean;
  className?: string;
}

export function TopBar({
  variant = "default",
  dateLabel,
  onDateClick,
  onCartClick,
  cartCount = 0,
  userName,
  onLogout,
  amberOnScroll = false,
  className,
}: TopBarProps) {
  const [amberPct, setAmberPct] = useState(0);

  useEffect(() => {
    if (!amberOnScroll) return;

    const onScroll = () => {
      const scrollable = document.body.scrollHeight - window.innerHeight;
      if (scrollable <= 0) return;
      setAmberPct(Math.min(100, (window.scrollY / scrollable) * 100));
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [amberOnScroll]);

  const isAmber = amberOnScroll && amberPct >= 65;

  return (
    <header
      style={{ "--amber-pct": `${amberPct}%` } as React.CSSProperties}
      className={cn(
        "sticky top-0 z-[var(--z-topbar)]",
        "flex h-16 items-center gap-3 border-b px-5",
        "backdrop-blur-md transition-colors duration-300",
        isAmber ? "border-transparent bg-amber" : "border-hairline bg-background/95",
        className,
      )}
    >
      {/* Logo */}
      <a href="/" aria-label="Rambla Rental — inicio" className="flex-shrink-0">
        <img
          src="/assets/rambla-wordmark.svg"
          alt="Rambla"
          className={cn(
            "hidden h-[30px] w-auto md:block transition-[filter] duration-300",
            isAmber && "[filter:brightness(0)_invert(1)]",
          )}
        />
        <img src="/assets/rambla-badge.png" alt="Rambla" className="h-8 w-8 md:hidden" />
      </a>

      {/* ── VARIANTE DEFAULT ── */}
      {variant === "default" && (
        <>
          {/* Date pill */}
          <button
            type="button"
            onClick={onDateClick}
            aria-label="Seleccionar fechas de alquiler"
            className={cn(
              "flex flex-1 items-center gap-2 rounded-full px-3 py-1.5",
              "font-sans text-sm transition-colors duration-[var(--duration-base)]",
              dateLabel
                ? "border-[1.5px] border-amber/50 bg-amber/10 font-semibold text-ink"
                : "border border-hairline bg-surface font-normal text-muted-foreground",
              isAmber && "border-ink/15 bg-ink/10 text-ink",
              "md:max-w-sm",
              "active:scale-[0.98]",
            )}
          >
            {/* Calendar icon */}
            <svg
              className="h-3.5 w-3.5 flex-shrink-0"
              viewBox="0 0 24 24"
              fill="none"
              stroke={
                dateLabel ? (isAmber ? "oklch(0.14 0.01 60)" : "var(--amber)") : "currentColor"
              }
              strokeWidth={2}
            >
              <rect x="3" y="4" width="18" height="18" rx="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
            <span className="truncate">{dateLabel ?? "Elegí tus fechas"}</span>
          </button>

          {/* Cart + User */}
          <div className="ml-auto flex items-center gap-2">
            {/* Cart button */}
            <button
              type="button"
              onClick={onCartClick}
              aria-label={`Carrito — ${cartCount} ítems`}
              className={cn(
                "flex h-9 items-center gap-2 rounded-full px-4",
                "font-sans text-sm font-semibold",
                "transition-all duration-[var(--duration-base)] active:scale-[0.97]",
                isAmber
                  ? "bg-ink text-amber"
                  : "bg-ink text-background hover:bg-amber hover:text-ink",
              )}
            >
              <ShoppingBag className="h-4 w-4" />
              {/* Desktop: texto */}
              <span className="hidden md:inline">
                {cartCount > 0 ? `${cartCount} ítem${cartCount !== 1 ? "s" : ""}` : "Tu rental"}
              </span>
              {/* Mobile: badge dot */}
              {cartCount > 0 && (
                <span className="inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-amber px-1 font-mono text-[10px] font-bold text-ink md:hidden">
                  {cartCount}
                </span>
              )}
            </button>

            {/* User icon */}
            <button
              type="button"
              aria-label="Mi cuenta"
              className={cn(
                "grid h-9 w-9 place-items-center rounded-full border transition-colors",
                isAmber
                  ? "border-ink/15 bg-ink/10 text-ink hover:bg-ink/20"
                  : "border-hairline bg-surface text-muted-foreground hover:text-ink",
              )}
            >
              <User className="h-4 w-4" />
            </button>
          </div>
        </>
      )}

      {/* ── VARIANTE CLIENTE ── */}
      {variant === "cliente" && (
        <div className="ml-auto flex items-center gap-2">
          {userName && (
            <div className="flex items-center gap-2 rounded-full border border-hairline py-1 pl-1 pr-3">
              <div className="grid h-7 w-7 place-items-center rounded-full bg-amber font-bold text-ink text-xs select-none">
                {userName[0].toUpperCase()}
              </div>
              <span className="text-sm font-semibold text-ink">{userName}</span>
            </div>
          )}
          {onLogout && (
            <button
              type="button"
              onClick={onLogout}
              aria-label="Cerrar sesión"
              className="grid h-9 w-9 place-items-center rounded-full border border-hairline text-muted-foreground transition-colors hover:text-destructive hover:border-destructive/30"
            >
              <LogOut className="h-4 w-4" />
            </button>
          )}
        </div>
      )}
    </header>
  );
}
