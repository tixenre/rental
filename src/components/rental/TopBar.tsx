import { Link } from "@tanstack/react-router";
import { useCart } from "@/lib/cart-store";
import { useState } from "react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { Calendar as CalendarIcon, ShoppingBag, User } from "lucide-react";
import { RentalDateModal } from "./RentalDateModal";
import { useQuery } from "@tanstack/react-query";

import logoWordmark from "@/assets/rambla-wordmark.png";

function LogoContent({ logoUrl }: { logoUrl: string | null }) {
  // logoUrl viene de settings (admin puede sobrescribir desde back-office).
  // Si no hay, usamos el PNG del repo — consistente con el footer.
  const src = logoUrl || logoWordmark;
  return (
    <img
      src={src}
      alt="Rambla Rental"
      className="h-9 sm:h-11 w-auto object-contain"
    />
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
    // 30s — si el admin sube un logo nuevo, en menos de medio minuto se ve.
    // El URL del setting trae cache buster (?v=<timestamp>) que invalida
    // el cache del navegador / CDN automáticamente. Issue #127.
    staleTime: 30_000,
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
            <div className="w-10" />
            <Link to="/" className="flex-1 flex justify-center">
              <LogoContent logoUrl={logoUrl} />
            </Link>
            <Link
              to="/cliente"
              className="flex items-center justify-center w-10 h-10 rounded-full border hairline hover:border-foreground/40"
              aria-label="Ingresar"
            >
              <User className="h-5 w-5" />
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
