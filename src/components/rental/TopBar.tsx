import { Link } from "@tanstack/react-router";
import { useCart } from "@/lib/cart-store";
import { useEffect, useRef, useState } from "react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { Calendar as CalendarIcon, ShoppingBag, User, LogOut } from "lucide-react";
import { RentalDateModal } from "./RentalDateModal";
import { Logo } from "./Logo";
import { cn } from "@/lib/utils";

export type TopBarProps = {
  /**
   * - "default": catálogo público (dates pill + carrito + Ingresar).
   * - "cliente": post-login del portal (sin dates pill ni carrito; muestra
   *   nombre del usuario y botón Salir).
   */
  variant?: "default" | "cliente";
  /** Solo aplica cuando variant === "cliente". */
  userName?: string;
  /** Solo aplica cuando variant === "cliente". */
  onLogout?: () => void;
  /**
   * Si se provee, el pill del usuario abre un drawer en lugar de navegar
   * a `/cliente/perfil`. Lo usa el portal para mostrar el perfil sin
   * abandonar la lista de pedidos.
   */
  onProfileClick?: () => void;
  /**
   * Cuando true, el TopBar se tiñe de amber gradualmente conforme el hero
   * (primera sección de la página) scrollea hacia arriba.
   * El progreso se lee de `--amber-pct` en `document.documentElement`.
   */
  amberOnScroll?: boolean;
};

export function TopBar({ variant = "default", userName, onLogout, onProfileClick, amberOnScroll }: TopBarProps = {}) {
  if (variant === "cliente") {
    return <ClienteTopBar userName={userName} onLogout={onLogout} onProfileClick={onProfileClick} />;
  }
  return <DefaultTopBar amberOnScroll={amberOnScroll} />;
}

function DefaultTopBar({ amberOnScroll }: { amberOnScroll?: boolean }) {
  const { startDate, endDate, startTime, endTime, setDrawerOpen, totalItems, days } = useCart();
  const [dateModalOpen, setDateModalOpen] = useState(false);
  const headerRef = useRef<HTMLElement>(null);
  const [snapped, setSnapped] = useState(false);
  const count = totalItems();
  const hasDates = !!(startDate && endDate);
  const jornadas = days();

  // Amber-on-scroll: lee --amber-pct del <html> (puesto por la página)
  // y aplica el gradiente al header + calcula el snap a 65%.
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
    onScroll(); // sync inicial
    return () => window.removeEventListener("scroll", onScroll);
  }, [amberOnScroll]);

  return (
    <>
      <RentalDateModal open={dateModalOpen} onOpenChange={setDateModalOpen} />
      <header
        ref={headerRef}
        className="sticky top-0 z-[var(--z-topbar)] border-b hairline backdrop-blur-xl transition-[background,border-color]"
        style={amberOnScroll ? undefined : undefined}
      >
        <div
          className={cn(
            "px-4 py-3 md:px-6 md:grid md:grid-cols-[auto_1fr_auto] md:gap-4 md:items-center",
            !amberOnScroll && "bg-background/95 md:bg-background/85",
          )}
        >
          {/* Mobile: logo centrado + botón sesión derecha */}
          <div className="flex items-center md:hidden">
            <div className="w-10" />
            <div className="flex-1 flex justify-center">
              <Logo size="md" linkTo="/" />
            </div>
            <Link
              to="/cliente"
              className="flex items-center justify-center w-10 h-10 rounded-full border hairline hover:border-foreground/40"
              aria-label="Ingresar"
            >
              <User className="h-5 w-5" />
            </Link>
          </div>

          {/* Desktop col izquierda: logo */}
          <div className="hidden md:flex items-center shrink-0">
            <Logo size="md" linkTo="/" />
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
              <CalendarIcon className={cn("h-5 w-5 shrink-0", snapped ? "text-amber" : "text-amber")} />
              {hasDates ? (
                <span className="text-base font-semibold tabular-nums">
                  {format(startDate!, "EEE dd MMM", { locale: es })} {startTime}
                  <span className="mx-2 opacity-50">→</span>
                  {format(endDate!, "EEE dd MMM", { locale: es })} {endTime}
                  <span className={cn("ml-2 font-mono text-[11px] uppercase tracking-wider", snapped ? "text-ink/60" : "text-muted-foreground")}>
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
              to="/cliente"
              className={cn(
                "flex items-center justify-center w-9 h-9 rounded-full border transition",
                snapped
                  ? "border-background/80 bg-background text-ink hover:bg-background/90"
                  : "hairline hover:border-foreground/40",
              )}
              aria-label="Ingresar"
            >
              <User className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </header>
    </>
  );
}

function ClienteTopBar({ userName, onLogout, onProfileClick }: {
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
        <span className="hidden sm:block pr-1 text-sm font-semibold text-ink">
          {firstName}
        </span>
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

        {/* Avatar pill: si hay onProfileClick → abre drawer; sino → /cliente/perfil */}
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
