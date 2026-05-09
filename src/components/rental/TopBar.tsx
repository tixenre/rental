import { Link } from "@tanstack/react-router";
import { useCart } from "@/lib/cart-store";
import { useState } from "react";
import { Calendar as CalendarIcon, ShoppingBag, User, HelpCircle } from "lucide-react";
import { WhatsappPill } from "./WhatsappPill";
import { RentalDateModal } from "./RentalDateModal";
import { formatRentalRange } from "@/lib/format";
import wordmark from "@/assets/rambla-wordmark.png";

export function TopBar() {
  const {
    startDate,
    endDate,
    startTime,
    endTime,
    setDrawerOpen,
    totalItems,
  } = useCart();
  const [user] = useState("Invitado");
  const [dateOpen, setDateOpen] = useState(false);
  const count = totalItems();
  const hasDates = !!(startDate && endDate);
  const label = formatRentalRange(startDate, endDate, startTime, endTime);

  return (
    <header className="sticky top-0 z-40 border-b hairline bg-background/85 backdrop-blur-xl">
      <div className="flex items-center gap-4 px-6 py-3">
        <Link to="/" className="flex items-center" aria-label="Rambla Rental">
          <img src={wordmark} alt="Rambla Rental" className="h-9 w-auto" />
        </Link>

        <button
          onClick={() => setDateOpen(true)}
          className={
            "ml-2 flex items-center gap-2 rounded-full border hairline bg-surface px-4 py-2 text-sm transition hover:border-amber/60 hover:bg-amber/10 " +
            (hasDates ? "text-foreground font-medium" : "text-muted-foreground")
          }
        >
          <CalendarIcon className="h-4 w-4" />
          <span className="hidden sm:inline">{label}</span>
          <span className="sm:hidden">{hasDates ? label : "Fechas"}</span>
        </button>

        <div className="ml-auto flex items-center gap-2">
          <div className="hidden md:block">
            <WhatsappPill />
          </div>
          <a
            href="#como-funciona"
            className="hidden md:flex items-center gap-1.5 rounded-full border hairline px-3 py-1.5 text-xs hover:border-ink"
          >
            <HelpCircle className="h-3.5 w-3.5" />
            ¿Cómo funciona?
          </a>
          <button
            onClick={() => setDrawerOpen(true)}
            className="relative flex items-center gap-2 rounded-full bg-foreground px-4 py-2 text-sm font-medium text-background transition hover:bg-amber hover:text-ink"
          >
            <ShoppingBag className="h-4 w-4" />
            <span className="tabular">{count}</span>
            <span>{count === 1 ? "ítem" : "ítems"}</span>
          </button>
          <button className="hidden sm:flex items-center gap-2 rounded-full border hairline px-3 py-2 text-sm hover:border-foreground/40">
            <User className="h-4 w-4" />
            {user}
          </button>
        </div>
      </div>

      <RentalDateModal open={dateOpen} onOpenChange={setDateOpen} />
    </header>
  );
}
