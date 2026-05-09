import { Link, useNavigate } from "@tanstack/react-router";
import { useCart } from "@/lib/cart-store";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { Calendar as CalendarIcon, ShoppingBag, User, LogOut, Package, UserCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { TimeStepSelect } from "./TimeStepSelect";

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
      <TimeStepSelect
        value={time}
        onChange={onTime}
        aria-label={`${label} hora`}
        className="rounded-md border hairline bg-surface px-2 py-1.5 text-sm focus:border-amber/40"
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
  const count = totalItems();
  const { user: authUser, signOut } = useAuth();
  const navigate = useNavigate();
  const isLoggedIn = !!authUser;
  const initial = (authUser?.email ?? "?").trim().charAt(0).toUpperCase();
  const handleSignOut = async () => {
    await signOut();
    navigate({ to: "/" });
  };

  return (
    <>
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
              {!isLoggedIn ? (
                <Link
                  to="/login"
                  className="flex items-center gap-1.5 rounded-full border hairline px-2 py-1.5 text-xs md:px-3 md:py-2 md:text-sm hover:border-foreground/40"
                  aria-label="Ingresar"
                >
                  <User className="h-3.5 w-3.5 md:h-4 md:w-4" />
                  <span className="hidden md:inline">Ingresar</span>
                </Link>
              ) : (
                <>
                  {/* Mobile: tap directo a mis pedidos */}
                  <Link
                    to="/mis-pedidos"
                    className="md:hidden grid h-8 w-8 place-items-center rounded-full bg-amber text-ink font-semibold text-xs"
                    aria-label="Mi cuenta"
                  >
                    {initial}
                  </Link>
                  {/* Desktop: dropdown */}
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button
                        className="hidden md:flex items-center gap-2 rounded-full border hairline px-2 py-1.5 text-xs md:px-3 md:py-2 md:text-sm hover:border-foreground/40"
                        aria-label={authUser?.email ?? "Mi cuenta"}
                      >
                        <span className="grid h-6 w-6 place-items-center rounded-full bg-amber text-ink font-semibold text-[11px]">
                          {initial}
                        </span>
                        <span className="hidden md:inline max-w-[140px] truncate">
                          {authUser?.email}
                        </span>
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-56">
                      <DropdownMenuItem asChild>
                        <Link to="/mis-pedidos" className="flex items-center gap-2">
                          <Package className="h-4 w-4" /> Mis pedidos
                        </Link>
                      </DropdownMenuItem>
                      <DropdownMenuItem asChild>
                        <Link to="/cuenta" className="flex items-center gap-2">
                          <UserCircle className="h-4 w-4" /> Mi cuenta
                        </Link>
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={handleSignOut} className="flex items-center gap-2 text-destructive focus:text-destructive">
                        <LogOut className="h-4 w-4" /> Cerrar sesión
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </>
              )}
            </div>
          </div>

        </div>
      </header>
      
    </>
  );
}
