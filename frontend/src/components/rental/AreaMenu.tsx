import { useState } from "react";
import { Link } from "@tanstack/react-router";
import {
  Menu,
  ArrowRight,
  Check,
  Home,
  User,
  HelpCircle,
  MessageCircle,
  FileText,
} from "lucide-react";
import { Sheet, SheetContent, SheetTrigger, SheetTitle, SheetClose } from "@/components/ui/sheet";
import { useClienteSession } from "@/lib/iva";
import { whatsappUrl } from "@/data/contact";
import { cn } from "@/lib/utils";

type AreaKey = "rental" | "estudio" | "workshops";

// Las 3 áreas con su color de marca — misma identidad que el hub (/).
const AREAS: { key: AreaKey; label: string; desc: string; href: string; bg: string; fg: string }[] =
  [
    {
      key: "rental",
      label: "rental.",
      desc: "Alquiler de equipos",
      href: "/catalogo",
      bg: "bg-amber",
      fg: "text-ink",
    },
    {
      key: "estudio",
      label: "estudio.",
      desc: "Set de foto y video",
      href: "/estudio",
      bg: "bg-naranja",
      fg: "text-white",
    },
    {
      key: "workshops",
      label: "workshops.",
      desc: "Talleres y formación",
      href: "/talleres",
      bg: "bg-rosa",
      fg: "text-ink",
    },
  ];

const SECONDARY = [
  { label: "Preguntas frecuentes", href: "/preguntas-frecuentes", icon: HelpCircle },
  { label: "Términos", href: "/terminos", icon: FileText },
];

/**
 * Menú de navegación entre áreas (hamburguesa + sheet lateral).
 * Vive a la derecha del topbar en todas las áreas. Reúsa la identidad del hub:
 * las 3 áreas como ítems de color, el área actual marcada. Incluye Inicio, acceso
 * al portal cliente y links secundarios.
 */
export function AreaMenu({ current }: { current?: AreaKey | "cliente" }) {
  const [open, setOpen] = useState(false);
  const { data: clienteSession } = useClienteSession();
  const isLogged = !!clienteSession;
  const firstName = clienteSession?.nombre?.trim().split(" ")[0] ?? null;

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button
          type="button"
          aria-label="Menú de navegación"
          className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-white/15 text-white transition hover:bg-white/25"
        >
          <Menu className="h-5 w-5" />
        </button>
      </SheetTrigger>
      <SheetContent side="right" className="w-[88vw] max-w-sm overflow-y-auto p-0">
        <SheetTitle className="sr-only">Navegación entre áreas</SheetTitle>

        <div className="flex flex-col gap-6 p-5 pt-12">
          {/* Áreas */}
          <div className="flex flex-col gap-2">
            <p className="px-1 font-mono text-[0.625rem] uppercase tracking-[0.25em] text-muted-foreground">
              Áreas
            </p>
            {AREAS.map((a) => {
              const active = current === a.key;
              return (
                <SheetClose asChild key={a.key}>
                  <Link
                    to={a.href}
                    className={cn(
                      "group flex items-center justify-between gap-3 rounded-2xl px-4 py-3.5 transition",
                      a.bg,
                      a.fg,
                      active
                        ? "ring-2 ring-ink/70 ring-offset-2 ring-offset-background"
                        : "hover:brightness-105",
                    )}
                  >
                    <span className="min-w-0">
                      <span className="font-display text-lg font-black lowercase leading-none">
                        {a.label}
                      </span>
                      <span className="mt-1 block text-xs opacity-70">{a.desc}</span>
                    </span>
                    {active ? (
                      <Check className="h-5 w-5 shrink-0" />
                    ) : (
                      <ArrowRight className="h-5 w-5 shrink-0 transition-transform group-hover:translate-x-0.5" />
                    )}
                  </Link>
                </SheetClose>
              );
            })}
          </div>

          {/* Inicio + portal cliente */}
          <div className="flex flex-col gap-1 border-t hairline pt-4">
            <SheetClose asChild>
              <Link
                to="/"
                className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-ink transition hover:bg-muted"
              >
                <Home className="h-4 w-4 shrink-0 text-muted-foreground" />
                Inicio
              </Link>
            </SheetClose>
            <SheetClose asChild>
              <Link
                to={isLogged ? "/cliente/portal" : "/cliente"}
                className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-ink transition hover:bg-muted"
              >
                <User className="h-4 w-4 shrink-0 text-muted-foreground" />
                {isLogged ? `Mi cuenta${firstName ? ` · ${firstName}` : ""}` : "Ingresar"}
              </Link>
            </SheetClose>
          </div>

          {/* Links secundarios */}
          <div className="flex flex-col gap-1 border-t hairline pt-4">
            <a
              href={whatsappUrl("Hola! Tengo una consulta.")}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-ink transition hover:bg-muted"
            >
              <MessageCircle className="h-4 w-4 shrink-0 text-muted-foreground" />
              Consultanos por WhatsApp
            </a>
            {SECONDARY.map((s) => (
              <SheetClose asChild key={s.href}>
                <Link
                  to={s.href}
                  className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-ink transition hover:bg-muted"
                >
                  <s.icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                  {s.label}
                </Link>
              </SheetClose>
            ))}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
