import { Link } from "@tanstack/react-router";
import { useCart } from "@/lib/cart-store";
import { useState } from "react";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { Calendar as CalendarIcon, ShoppingBag, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { RentalDateModal } from "./RentalDateModal";

function DateField({
  label,
  date,
  time,
  onDate,
  onTime,
}: {
  label: string;
  date?: Date;
  time: string;
  onDate: (d?: Date) => void;
  onTime: (t: string) => void;
}) {
  return (
    <div className="flex items-center gap-3 border-l hairline pl-4 first:border-l-0 first:pl-0">
      <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </div>
      <Popover>
        <PopoverTrigger asChild>
          <button
            className={cn(
              "flex items-center gap-2 rounded-md border hairline bg-surface px-3 py-1.5 text-sm transition hover:border-amber/40",
              !date && "text-muted-foreground",
            )}
          >
            <CalendarIcon className="h-3.5 w-3.5" />
            {date ? format(date, "dd MMM", { locale: es }) : "elegir"}
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-auto p-0">
          <Calendar
            mode="single"
            selected={date}
            onSelect={onDate}
            locale={es}
            className={cn("p-3 pointer-events-auto")}
          />
        </PopoverContent>
      </Popover>
      <input
        type="time"
        value={time}
        onChange={(e) => onTime(e.target.value)}
        className="rounded-md border hairline bg-surface px-2 py-1.5 text-sm tabular focus:border-amber/40 focus:outline-none"
      />
    </div>
  );
}

export function TopBar() {
  const {
    startDate,
    endDate,
    startTime,
    endTime,
    setDates,
    setStartTime,
    setEndTime,
    setDrawerOpen,
    totalItems,
  } = useCart();
  const [user] = useState("Invitado");
  const [dateModalOpen, setDateModalOpen] = useState(false);
  const count = totalItems();

  return (
    <>
      <header className="sticky top-0 z-40 border-b hairline bg-background/85 backdrop-blur-xl">
        <div className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:gap-6 sm:px-6">
          <Link to="/" className="flex items-center gap-2 group shrink-0">
            <span className="wordmark text-2xl sm:text-3xl text-amber leading-none">
              rambla
            </span>
            <span className="font-mono text-[9px] sm:text-[10px] uppercase tracking-[0.3em] text-foreground/70 border-l hairline pl-2">
              Rental
            </span>
          </Link>

          <div className="hidden md:flex items-center gap-4 ml-4">
            <DateField
              label="Desde"
              date={startDate}
              time={startTime}
              onDate={(d) => setDates(d, endDate)}
              onTime={setStartTime}
            />
            <span className="text-muted-foreground">→</span>
            <DateField
              label="Hasta"
              date={endDate}
              time={endTime}
              onDate={(d) => setDates(startDate, d)}
              onTime={setEndTime}
            />
          </div>

          <button
            onClick={() => setDateModalOpen(true)}
            className="md:hidden flex-1 sm:flex-none flex items-center justify-center gap-2 rounded-full border border-amber/40 bg-amber/5 px-3 py-2 text-sm font-medium transition hover:border-amber hover:bg-amber hover:text-ink"
          >
            <CalendarIcon className="h-4 w-4" />
            {startDate && endDate
              ? `${format(startDate, "dd MMM", { locale: es })} → ${format(endDate, "dd MMM", { locale: es })}`
              : "Elegir fechas"}
          </button>

          <div className="flex items-center justify-end gap-2 sm:ml-auto">
            <button
              onClick={() => setDrawerOpen(true)}
              className="relative flex items-center gap-2 rounded-full bg-foreground px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm font-medium text-background transition hover:bg-amber hover:text-ink"
            >
              <ShoppingBag className="h-4 w-4" />
              <span className="tabular hidden sm:inline">{count}</span>
              <span className="hidden sm:inline">{count === 1 ? "ítem" : "ítems"}</span>
            </button>
            <button className="flex items-center gap-1.5 rounded-full border hairline px-2 py-1.5 text-xs sm:px-3 sm:py-2 sm:text-sm hover:border-foreground/40">
              <User className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">{user}</span>
            </button>
          </div>
      </div>
    </header>
      <RentalDateModal open={dateModalOpen} onOpenChange={setDateModalOpen} />
    </>
  );
}
