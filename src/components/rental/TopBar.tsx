import { Link } from "@tanstack/react-router";
import { useCart } from "@/lib/cart-store";
import { useState } from "react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { Calendar as CalendarIcon, ShoppingBag, User } from "lucide-react";
import { RentalDateModal } from "./RentalDateModal";
import { useQuery } from "@tanstack/react-query";

function LogoContent({ logoUrl }: { logoUrl: string | null }) {
  if (logoUrl) {
    return <img src={logoUrl} alt="Rambla Rental" className="h-10 sm:h-11 w-auto object-contain" />;
  }
  return (
    <>
      <span className="wordmark text-2xl sm:text-3xl text-amber leading-none">rambla</span>
      <span className="font-mono text-[9px] sm:text-[10px] uppercase tracking-[0.3em] text-foreground/70 border-l hairline pl-2">
        Rental
      </span>
    </>
  );
}

export function TopBar() {
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

  const { data: logoSetting } = useQuery({
    queryKey: ["settings", "logo_url"],
    queryFn: () =>
      fetch("/api/settings/logo_url").then((r) => (r.ok ? r.json() : null)).catch(() => null),
    staleTime: 5 * 60 * 1000,
  });
  const logoUrl: string | null = logoSetting?.value ?? null;

  return (
    <>
      <RentalDateModal open={dateModalOpen} onOpenChange={setDateModalOpen} />
      <header className="sticky top-0 z-40 border-b hairline bg-background/95 backdrop-blur-md md:bg-background/85 md:backdrop-blur-xl">
        <div className="px-4 py-3 md:px-6 md:grid md:grid-cols-[auto_1fr_auto] md:gap-4 md:items-center">

          {/* Mobile: logo centrado con ícono de usuario a la derecha */}
          <div className="flex items-center md:hidden">
            {/* Espaciador izquierdo igual al ancho del ícono derecho */}
            <div className="w-8" />
            <Link to="/" className="flex-1 flex justify-center">
              <LogoContent logoUrl={logoUrl} />
            </Link>
            <Link
              to="/cliente"
              className="flex items-center justify-center w-8 h-8 rounded-full border hairline hover:border-foreground/40"
              aria-label="Ingresar"
            >
              <User className="h-4 w-4" />
            </Link>
          </div>

          {/* Desktop: logo izquierda */}
          <Link to="/" className="hidden md:flex items-center gap-2 shrink-0">
            <LogoContent logoUrl={logoUrl} />
          </Link>

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
