import { Link } from "@tanstack/react-router";
import { useCart } from "@/lib/cart-store";
import { useState } from "react";
import { useAuth } from "@/hooks/use-auth";
import {
  Calendar as CalendarIcon,
  ShoppingBag,
  User,
  HelpCircle,
  Menu,
  LogIn,
  ClipboardList,
  LogOut,
} from "lucide-react";
import { RentalDateModal } from "./RentalDateModal";
import { formatRentalRange } from "@/lib/format";
import wordmark from "@/assets/rambla-wordmark.png";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const WA_PHONE = "5492235852510";
const WA_DISPLAY = "+54 9 223 585 2510";
const WA_HREF = `https://wa.me/${WA_PHONE}`;

function WhatsAppIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
      <path d="M19.11 4.91A10 10 0 0 0 2.1 16.06L1 21l5.06-1.07A10 10 0 0 0 22 12a9.93 9.93 0 0 0-2.89-7.09Zm-7.1 15.18a8.31 8.31 0 0 1-4.23-1.16l-.3-.18-3 .63.64-2.92-.2-.31a8.32 8.32 0 1 1 7.09 4Zm4.56-6.22c-.25-.13-1.48-.73-1.71-.81s-.4-.13-.56.12-.65.81-.79.97-.29.19-.54.06a6.84 6.84 0 0 1-2-1.24 7.5 7.5 0 0 1-1.4-1.74c-.14-.25 0-.39.11-.51s.25-.29.37-.43a1.62 1.62 0 0 0 .25-.41.46.46 0 0 0 0-.43c-.06-.13-.56-1.34-.76-1.83s-.4-.42-.55-.43h-.48a.93.93 0 0 0-.67.31 2.79 2.79 0 0 0-.87 2.07 4.85 4.85 0 0 0 1 2.57 11.13 11.13 0 0 0 4.28 3.78c.6.26 1.07.41 1.43.53a3.46 3.46 0 0 0 1.58.1 2.59 2.59 0 0 0 1.69-1.19 2.1 2.1 0 0 0 .15-1.19c-.06-.11-.23-.17-.48-.3Z" />
    </svg>
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
  } = useCart();
  const [dateOpen, setDateOpen] = useState(false);
  const count = totalItems();
  const hasDates = !!(startDate && endDate);
  const label = formatRentalRange(startDate, endDate, startTime, endTime);

  return (
    <header className="sticky top-0 z-40 border-b hairline bg-background/85 backdrop-blur-xl">
      {/* Single row centered en sm+; en mobile la pill de fecha pasa a una segunda fila */}
      <div className="relative hidden sm:flex items-center justify-between gap-3 px-4 py-3 md:px-6">
        <Link to="/" className="flex items-center shrink-0" aria-label="Rambla Rental">
          <img src={wordmark} alt="Rambla Rental" className="h-9 w-auto" />
        </Link>

        <button
          onClick={() => setDateOpen(true)}
          className={
            "absolute left-1/2 -translate-x-1/2 flex items-center gap-2.5 rounded-full px-5 py-2.5 text-sm shadow-sm transition " +
            (hasDates
              ? "bg-foreground text-background font-semibold hover:bg-amber hover:text-ink"
              : "bg-amber text-ink font-semibold hover:bg-amber/90 ring-1 ring-amber/40")
          }
        >
          <CalendarIcon className="h-4 w-4" />
          <span>{label}</span>
        </button>

        <RightActions
          count={count}
          onCartOpen={() => setDrawerOpen(true)}
        />
      </div>

      {/* Mobile: dos filas */}
      <div className="sm:hidden flex items-center justify-between gap-2 px-4 pt-3">
        <Link to="/" className="flex items-center shrink-0" aria-label="Rambla Rental">
          <img src={wordmark} alt="Rambla Rental" className="h-8 w-auto" />
        </Link>
        <RightActions
          count={count}
          onCartOpen={() => setDrawerOpen(true)}
          compact
        />
      </div>
      <div className="sm:hidden px-4 pb-3 pt-2">
        <button
          onClick={() => setDateOpen(true)}
          className={
            "w-full flex items-center justify-center gap-2 rounded-full px-4 py-2.5 text-sm shadow-sm transition " +
            (hasDates
              ? "bg-foreground text-background font-semibold"
              : "bg-amber text-ink font-semibold ring-1 ring-amber/40")
          }
        >
          <CalendarIcon className="h-4 w-4" />
          <span className="truncate">{hasDates ? label : "Elegir fechas"}</span>
        </button>
      </div>

      <RentalDateModal open={dateOpen} onOpenChange={setDateOpen} />
    </header>
  );
}

function RightActions({
  count,
  onCartOpen,
  compact = false,
}: {
  count: number;
  onCartOpen: () => void;
  compact?: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      {!compact && (
        <a
          href={WA_HREF}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`WhatsApp ${WA_DISPLAY}`}
          title={`WhatsApp ${WA_DISPLAY}`}
          className="flex h-9 w-9 items-center justify-center rounded-full border hairline text-muted-foreground transition hover:border-ink hover:text-ink"
        >
          <WhatsAppIcon className="h-4 w-4" />
        </a>
      )}

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            aria-label="Menú"
            className="flex h-9 w-9 items-center justify-center rounded-full border hairline text-muted-foreground transition hover:border-ink hover:text-ink"
          >
            <Menu className="h-4 w-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuItem asChild>
            <a href="#como-funciona" className="flex items-center gap-2">
              <HelpCircle className="h-4 w-4" />
              ¿Cómo funciona?
            </a>
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <a
              href={WA_HREF}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2"
            >
              <WhatsAppIcon className="h-4 w-4" />
              WhatsApp
            </a>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem className="flex items-center gap-2">
            <User className="h-4 w-4" />
            Invitado
          </DropdownMenuItem>
          <DropdownMenuItem className="flex items-center gap-2">
            <LogIn className="h-4 w-4" />
            Iniciar sesión
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <button
        onClick={onCartOpen}
        aria-label={`Carrito (${count})`}
        className="relative flex items-center gap-2 rounded-full bg-foreground px-3 py-2 text-sm font-medium text-background transition hover:bg-amber hover:text-ink sm:px-4"
      >
        <ShoppingBag className="h-4 w-4" />
        <span className="tabular">{count}</span>
        <span className="hidden md:inline">{count === 1 ? "ítem" : "ítems"}</span>
      </button>
    </div>
  );
}

