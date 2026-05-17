import { Link } from "@tanstack/react-router";
import { useCart } from "@/lib/cart-store";
import { useState } from "react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { Calendar as CalendarIcon, ShoppingBag, User, LogOut, Search, X } from "lucide-react";
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
  /** Valor del input de búsqueda en desktop (solo variant "default"). */
  searchValue?: string;
  /** Callback cuando el usuario escribe en la búsqueda del TopBar. */
  onSearch?: (value: string) => void;
};

export function TopBar({ variant = "default", userName, onLogout, searchValue, onSearch }: TopBarProps = {}) {
  if (variant === "cliente") {
    return <ClienteTopBar userName={userName} onLogout={onLogout} />;
  }
  return <DefaultTopBar searchValue={searchValue} onSearch={onSearch} />;
}

function DefaultTopBar({ searchValue, onSearch }: Pick<TopBarProps, "searchValue" | "onSearch">) {
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

          {/* Centro desktop: búsqueda (cuando se pasa onSearch) o pill de fechas */}
          {onSearch ? (
            <div className="hidden md:flex px-2">
              <div className="relative w-full max-w-[560px] mx-auto">
                <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  value={searchValue ?? ""}
                  onChange={(e) => onSearch(e.target.value)}
                  placeholder="Buscar equipo, marca…"
                  className="w-full rounded-full border-[1.5px] border-hairline bg-surface py-2.5 pl-10 pr-9 text-sm placeholder:text-muted-foreground focus:border-amber focus:ring-[3px] focus:ring-amber/20 focus:outline-none transition"
                />
                {searchValue && (
                  <button
                    onClick={() => onSearch("")}
                    aria-label="Limpiar búsqueda"
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-full p-0.5 text-muted-foreground hover:text-ink"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </div>
          ) : (
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
          )}

          {/* Acciones desktop */}
          <div className="hidden md:flex items-center gap-2 shrink-0">
            {/* Pill de fechas compacta — solo cuando búsqueda está en el centro */}
            {onSearch && (
              <button
                onClick={() => setDateModalOpen(true)}
                className={cn(
                  "inline-flex items-center gap-2 rounded-full border-[1.5px] px-3.5 py-2 text-sm font-semibold transition",
                  hasDates
                    ? "border-amber/50 bg-amber/10 hover:border-amber hover:bg-amber/20"
                    : "border-hairline bg-surface hover:border-amber/50",
                )}
                aria-label={hasDates ? "Editar fechas" : "Elegir fechas"}
              >
                <CalendarIcon className="h-4 w-4 shrink-0 text-amber" />
                {hasDates ? (
                  <span className="tabular-nums text-xs">
                    {format(startDate!, "dd MMM", { locale: es })}
                    <span className="mx-1.5 text-muted-foreground">→</span>
                    {format(endDate!, "dd MMM", { locale: es })}
                    <span className="ml-1.5 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                      · {jornadas}j
                    </span>
                  </span>
                ) : (
                  <span className="text-xs">Fechas</span>
                )}
              </button>
            )}
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
              className="flex items-center justify-center w-9 h-9 rounded-full border hairline hover:border-foreground/40"
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

        {/* User pill: avatar inicial + nombre */}
        <Link
          to="/cliente/perfil"
          className="inline-flex items-center gap-2 rounded-full border hairline px-2 py-1 hover:border-ink/30 transition"
          title="Editar mi perfil"
        >
          <div className="flex h-[26px] w-[26px] items-center justify-center rounded-full bg-amber text-ink font-display text-xs font-black shrink-0">
            {userName ? userName[0].toUpperCase() : <User className="h-3.5 w-3.5" />}
          </div>
          {userName && (
            <span className="hidden sm:block pr-1 text-sm font-semibold text-ink">
              {userName.split(" ")[0]}
            </span>
          )}
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
