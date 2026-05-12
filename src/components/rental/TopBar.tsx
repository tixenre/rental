import { Link } from "@tanstack/react-router";
import { useCart } from "@/lib/cart-store";
import { useState } from "react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { Calendar as CalendarIcon, ShoppingBag, User, LogOut } from "lucide-react";
import { RentalDateModal } from "./RentalDateModal";
import { Logo } from "./Logo";

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
};

export function TopBar({ variant = "default", userName, onLogout }: TopBarProps = {}) {
  if (variant === "cliente") {
    return <ClienteTopBar userName={userName} onLogout={onLogout} />;
  }
  return <DefaultTopBar />;
}

function DefaultTopBar() {
  const {
    startDate,
    endDate,
    startTime,
    endTime,
    setDrawerOpen,
    totalItems,
    days,
  } = useCart();
  const [dateModalOpen, setDateModalOpen] = useState(false);
  const count = totalItems();
  const hasDates = !!(startDate && endDate);
  const jornadas = days();

  return (
    <>
      <RentalDateModal open={dateModalOpen} onOpenChange={setDateModalOpen} />
      <header className="sticky top-0 z-40 border-b hairline bg-background/95 backdrop-blur-md md:bg-background/85 md:backdrop-blur-xl">
        <div className="px-4 py-3 md:px-6 md:grid md:grid-cols-[auto_1fr_auto] md:gap-4 md:items-center">

          {/* Mobile: logo centrado con ícono de usuario a la derecha */}
          <div className="flex items-center md:hidden">
            {/* Espaciador izquierdo igual al ancho del ícono derecho */}
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

          {/* Desktop: logo izquierda */}
          <div className="hidden md:flex items-center gap-2 shrink-0">
            <Logo size="md" linkTo="/" />
          </div>

          {/* Pill de fechas — solo desktop */}
          <div className="hidden md:flex px-4">
            <button
              onClick={() => setDateModalOpen(true)}
              className="w-full flex items-center justify-center gap-3 rounded-full border-2 border-amber/50 bg-amber/10 px-6 py-2 transition hover:border-amber hover:bg-amber/20 shadow-sm"
              aria-label={hasDates ? "Editar fechas y horarios" : "Elegir fechas"}
            >
              <CalendarIcon className="h-5 w-5 shrink-0 text-amber" />
              {hasDates ? (
                <span className="text-base font-semibold tabular-nums">
                  {format(startDate!, "EEE dd MMM", { locale: es })} {startTime}
                  <span className="mx-2 text-muted-foreground">→</span>
                  {format(endDate!, "EEE dd MMM", { locale: es })} {endTime}
                  <span className="ml-2 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                    · {jornadas} {jornadas === 1 ? "jornada" : "jornadas"}
                  </span>
                </span>
              ) : (
                <span className="text-base font-semibold">Elegir fechas</span>
              )}
            </button>
          </div>

          {/* Acciones desktop */}
          <div className="hidden md:flex items-center gap-2 shrink-0">
            <button
              onClick={() => setDrawerOpen(true, "bottom")}
              className="flex items-center gap-2 rounded-full bg-foreground px-4 py-2 text-sm font-medium text-background transition hover:bg-amber hover:text-ink"
              aria-label={`Carrito (${count})`}
            >
              <ShoppingBag className="h-4 w-4" />
              <span className="tabular-nums">{count}</span>
              <span>{count === 1 ? "ítem" : "ítems"}</span>
            </button>
            <Link
              to="/cliente"
              className="flex items-center gap-1.5 rounded-full border hairline px-3 py-2 text-sm hover:border-foreground/40"
            >
              <User className="h-4 w-4" />
              <span>Ingresar</span>
            </Link>
          </div>

        </div>
      </header>
    </>
  );
}

function ClienteTopBar({
  userName,
  onLogout,
}: {
  userName?: string;
  onLogout?: () => void;
}) {
  return (
    <header className="sticky top-0 z-40 border-b hairline bg-background/95 backdrop-blur-md md:bg-background/85 md:backdrop-blur-xl">
      <div className="px-4 py-3 md:px-6 flex items-center gap-3">
        {/* Logo */}
        <div className="shrink-0">
          <Logo size="md" linkTo="/" />
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Nombre + perfil (solo si hay nombre) */}
        {userName && (
          <Link
            to="/cliente/perfil"
            className="hidden sm:inline-flex items-center text-sm text-muted-foreground hover:text-ink transition"
            title="Editar mi perfil"
          >
            {userName}
          </Link>
        )}
        <Link
          to="/cliente/perfil"
          className="sm:hidden inline-flex items-center justify-center w-10 h-10 rounded-full border hairline hover:border-foreground/40"
          aria-label="Perfil"
        >
          <User className="h-5 w-5" />
        </Link>

        {/* Salir */}
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
