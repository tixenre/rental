import { Link } from "@tanstack/react-router";
import { useCart } from "@/lib/cart-store";
import { useState } from "react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { Calendar as CalendarIcon, ShoppingBag, User } from "lucide-react";
import { RentalDateModal } from "./RentalDateModal";

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
  const [user] = useState("Invitado");
  const [dateModalOpen, setDateModalOpen] = useState(false);
  const count = totalItems();
  const hasDates = !!(startDate && endDate);
  const jornadas = days();

  return (
    <>
      <RentalDateModal open={dateModalOpen} onOpenChange={setDateModalOpen} />
      <header className="sticky top-0 z-40 border-b hairline bg-background/95 backdrop-blur-md md:bg-background/85 md:backdrop-blur-xl">
        <div className="flex flex-col gap-2 px-4 py-3 sm:gap-3 md:flex-row md:items-center md:gap-6 md:px-6">
          {/* Fila 1 mobile / izq desktop: logo + acciones */}
          <div className="flex items-center justify-between gap-2 md:contents">
            <Link to="/" className="flex items-center gap-2 group shrink-0">
              <span className="wordmark text-2xl sm:text-3xl text-amber leading-none">
                rambla
              </span>
              <span className="font-mono text-[9px] sm:text-[10px] uppercase tracking-[0.3em] text-foreground/70 border-l hairline pl-2">
                Rental
              </span>
            </Link>

            <button
              onClick={() => setDateModalOpen(true)}
              className="hidden md:flex items-center gap-2 rounded-full border border-amber/40 bg-amber/5 px-3 py-2 text-left transition hover:border-amber ml-4"
              aria-label={hasDates ? "Editar fechas y horarios" : "Elegir fechas"}
            >
              <CalendarIcon className="h-4 w-4 shrink-0" />
              {hasDates ? (
                <span className="text-[13px] font-medium tabular-nums">
                  {format(startDate!, "dd MMM", { locale: es })} {startTime}
                  <span className="mx-1 text-muted-foreground">→</span>
                  {format(endDate!, "dd MMM", { locale: es })} {endTime}
                  <span className="ml-1.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    · {jornadas}j
                  </span>
                </span>
              ) : (
                <span className="text-[13px] font-medium text-muted-foreground">Elegir fechas</span>
              )}
            </button>

            {/* Acciones — junto al logo en mobile, a la derecha en desktop */}
            <div className="flex items-center gap-2 md:ml-auto">
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
              <button
                className="flex items-center gap-1.5 rounded-full border hairline px-2 py-1.5 text-xs md:px-3 md:py-2 md:text-sm hover:border-foreground/40"
                aria-label={user}
              >
                <User className="h-3.5 w-3.5 md:h-4 md:w-4" />
                <span className="hidden md:inline">{user}</span>
              </button>
            </div>
          </div>

        </div>
      </header>
      
    </>
  );
}
