import { Link } from "@tanstack/react-router";
import { useCart } from "@/lib/cart-store";
import { useState } from "react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { Calendar as CalendarIcon, ShoppingBag, User } from "lucide-react";
import { RentalDateModal } from "./RentalDateModal";
import { useQuery } from "@tanstack/react-query";

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
        <div className="flex items-center justify-between gap-2 px-4 py-3 md:grid md:grid-cols-[auto_1fr_auto] md:gap-4 md:px-6">

          {/* Logo */}
          <Link to="/" className="flex items-center gap-2 shrink-0">
            {logoUrl ? (
              <img
                src={logoUrl}
                alt="Rambla Rental"
                className="h-10 sm:h-11 w-auto object-contain"
              />
            ) : (
              <>
                <span className="wordmark text-2xl sm:text-3xl text-amber leading-none">rambla</span>
                <span className="font-mono text-[9px] sm:text-[10px] uppercase tracking-[0.3em] text-foreground/70 border-l hairline pl-2">
                  Rental
                </span>
              </>
            )}
          </Link>

          {/* Pill de fechas — centrado en desktop, oculto en mobile */}
          <div className="hidden md:flex px-4">
            <button
              onClick={() => setDateModalOpen(true)}
              className="w-full flex items-center justify-center gap-3 rounded-full border-2 border-amber/50 bg-amber/10 px-6 py-2 transition hover:border-amber hover:bg-amber/20 shadow-sm"
              aria-label={hasDates ? "Editar fechas y horarios" : "Elegir fechas"}
            >
              <CalendarIcon className="h-5 w-5 shrink-0 text-amber" />
              {hasDates ? (
                <span className="text-base font-semibold tabular-nums">
                  {format(startDate!, "dd MMM", { locale: es })} {startTime}
                  <span className="mx-2 text-muted-foreground">→</span>
                  {format(endDate!, "dd MMM", { locale: es })} {endTime}
                  <span className="ml-2 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                    · {jornadas}j
                  </span>
                </span>
              ) : (
                <span className="text-base font-semibold">Elegir fechas</span>
              )}
            </button>
          </div>

          {/* Acciones */}
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => setDrawerOpen(true, "bottom")}
              className="relative flex items-center gap-2 rounded-full bg-foreground px-3 py-1.5 text-xs sm:text-sm md:px-4 md:py-2 font-medium text-background transition hover:bg-amber hover:text-ink"
              aria-label={`Carrito (${count})`}
            >
              <ShoppingBag className="h-4 w-4" />
              <span className="tabular hidden md:inline">{count}</span>
              <span className="hidden md:inline">{count === 1 ? "ítem" : "ítems"}</span>
              {count > 0 && (
                <span className="md:hidden absolute -right-1 -top-1 grid h-4 min-w-[16px] place-items-center rounded-full bg-amber px-1 font-mono text-[10px] font-semibold leading-none text-ink">
                  {count}
                </span>
              )}
            </button>
            <Link
              to="/cliente"
              className="flex items-center gap-1.5 rounded-full border hairline px-2 py-1.5 text-xs md:px-3 md:py-2 md:text-sm hover:border-foreground/40"
            >
              <User className="h-3.5 w-3.5 md:h-4 md:w-4" />
              <span className="hidden md:inline">Ingresar</span>
            </Link>
          </div>

        </div>
      </header>
    </>
  );
}
