import { Instagram, MessageCircle, MapPin } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Footer — pie de página del catálogo público y portal cliente.
 *
 * Dos layouts:
 *   - Mobile (< md): columna única compacta, sin la columna de links de navegación.
 *   - Desktop (≥ md): grid 3 columnas — brand | navegación | contacto.
 *
 * Usar sobre fondo --surface (no --background) para un leve contraste
 * que separa el footer del contenido principal.
 *
 * El copyright se genera con new Date().getFullYear() — no hardcodear el año.
 *
 * Source visual: `preview/components-footer.html`
 */
export function Footer({ className }: { className?: string }) {
  const year = new Date().getFullYear();

  return (
    <footer
      className={cn(
        "border-t border-hairline bg-surface",
        "px-5 py-10 md:px-8 md:py-14",
        className,
      )}
    >
      <div className="mx-auto max-w-5xl">
        {/* Grid */}
        <div className="grid grid-cols-1 gap-10 md:grid-cols-3">
          {/* Col 1 — Brand */}
          <div className="flex flex-col gap-4">
            <img
              src="/assets/rambla-wordmark.svg"
              alt="Rambla Rental"
              className="h-8 w-auto object-left object-contain"
            />
            <p className="text-sm leading-relaxed text-muted-foreground">
              Alquiler de equipos audiovisuales en Mar del Plata.
            </p>
            <p
              className="font-display text-sm lowercase text-muted-foreground"
              style={{ fontFamily: "var(--font-display)" }}
            >
              un lugar donde pasan cosas.
            </p>
          </div>

          {/* Col 2 — Navegación (solo desktop) */}
          <div className="hidden md:flex flex-col gap-3">
            <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
              Navegación
            </p>
            <nav className="flex flex-col gap-2" aria-label="Footer navigation">
              {[
                { href: "/", label: "Catálogo" },
                { href: "/estudio", label: "Estudio" },
                { href: "/preguntas-frecuentes", label: "Preguntas frecuentes" },
                { href: "/privacidad", label: "Privacidad" },
                { href: "/terminos", label: "Términos y condiciones" },
              ].map(({ href, label }) => (
                <a
                  key={href}
                  href={href}
                  className="text-sm text-muted-foreground transition-colors hover:text-ink"
                >
                  {label}
                </a>
              ))}
            </nav>
          </div>

          {/* Col 3 — Contacto */}
          <div className="flex flex-col gap-3">
            <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
              Contacto
            </p>
            <div className="flex flex-col gap-2.5">
              <a
                href="https://instagram.com/ramblarental"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-ink"
              >
                <Instagram className="h-4 w-4 flex-shrink-0" />
                @ramblarental
              </a>
              <a
                href="https://wa.me/5492235000000"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-ink"
              >
                <MessageCircle className="h-4 w-4 flex-shrink-0" />
                WhatsApp
              </a>
              <div className="flex items-start gap-2 text-sm text-muted-foreground">
                <MapPin className="mt-0.5 h-4 w-4 flex-shrink-0" />
                Mar del Plata, Buenos Aires
              </div>
            </div>
          </div>
        </div>

        {/* Mobile nav links */}
        <nav
          className="mt-8 flex flex-wrap gap-x-4 gap-y-2 border-t border-hairline pt-6 md:hidden"
          aria-label="Footer navigation mobile"
        >
          {[
            { href: "/estudio", label: "Estudio" },
            { href: "/preguntas-frecuentes", label: "FAQ" },
            { href: "/privacidad", label: "Privacidad" },
            { href: "/terminos", label: "Términos" },
          ].map(({ href, label }) => (
            <a
              key={href}
              href={href}
              className="text-xs text-muted-foreground transition-colors hover:text-ink"
            >
              {label}
            </a>
          ))}
        </nav>

        {/* Bottom bar */}
        <div
          className={cn(
            "mt-8 border-t border-hairline pt-6",
            "flex flex-col gap-1 md:flex-row md:items-center md:justify-between",
          )}
        >
          <p className="font-mono text-[10px] text-muted-foreground">
            © {year} Rambla Rental — Mar del Plata, Argentina
          </p>
          <p className="font-mono text-[10px] text-muted-foreground/60">
            Todos los precios son en ARS + IVA.
          </p>
        </div>
      </div>
    </footer>
  );
}
