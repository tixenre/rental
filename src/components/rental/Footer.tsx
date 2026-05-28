import { Link } from "@tanstack/react-router";
import { Instagram, MessageCircle, MapPin, Phone, Mail, Clock } from "lucide-react";

import { CONTACT, whatsappUrl } from "@/data/contact";
import { useBusinessContact } from "@/hooks/useBusinessContact";
import logoWordmark from "@/assets/rambla-wordmark.webp";

/**
 * Footer público — usado en home, catálogo, estudio, FAQ, portal cliente.
 *
 * Dos layouts:
 * - Mobile (< md): compacto. Logo + WhatsApp CTA, contacto en línea,
 *   links en chips horizontales. Menos info pero todo accesible.
 * - Desktop (md+): completo. Grid de 3 columnas con todos los datos
 *   (dirección con maps, horarios desglosados, navegación full, etc.).
 *
 * NO incluir en páginas /admin/* (tienen su propio layout de back-office).
 */
export function Footer() {
  return (
    <>
      <FooterMobile />
      <FooterDesktop />
    </>
  );
}

// ── Mobile compact ──────────────────────────────────────────────────────────

function FooterMobile() {
  const contact = useBusinessContact();
  return (
    <footer className="md:hidden border-t hairline bg-background">
      <div className="px-4 py-6 space-y-4">
        {/* Logo + WhatsApp CTA en una fila */}
        <div className="flex items-center justify-between gap-3">
          <img src={logoWordmark} alt="Rambla Rental" className="h-7 w-auto" loading="lazy" />
          <a
            href={whatsappUrl("Hola! Tengo una consulta.")}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-full bg-ink text-amber px-3 py-1.5 text-xs font-medium"
          >
            <MessageCircle className="h-3.5 w-3.5" />
            WhatsApp
          </a>
        </div>

        {/* Links de navegación en chips */}
        <nav className="flex flex-wrap gap-x-3 gap-y-1.5 text-xs">
          <Link to="/" className="text-ink hover:text-amber transition">
            Catálogo
          </Link>
          <span className="text-muted-foreground/40">·</span>
          <Link to="/estudio" className="text-ink hover:text-amber transition">
            Estudio
          </Link>
          <span className="text-muted-foreground/40">·</span>
          <Link to="/preguntas-frecuentes" className="text-ink hover:text-amber transition">
            FAQ
          </Link>
          <span className="text-muted-foreground/40">·</span>
          <a
            href={`https://instagram.com/${contact.instagram}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-ink hover:text-amber transition"
          >
            <Instagram className="h-3 w-3" />
            Instagram
          </a>
        </nav>

        {/* Legal */}
        <nav className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
          <Link to="/privacidad" className="hover:text-ink transition">
            Privacidad
          </Link>
          <span className="text-muted-foreground/40">·</span>
          <Link to="/terminos" className="hover:text-ink transition">
            Términos
          </Link>
        </nav>

        {/* Contacto compacto */}
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
          <a
            href={contact.mapsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 hover:text-ink transition"
          >
            <MapPin className="h-3 w-3 shrink-0" />
            {contact.address}
          </a>
          <a
            href={`mailto:${contact.email}`}
            className="inline-flex items-center gap-1 hover:text-ink transition"
          >
            <Mail className="h-3 w-3 shrink-0" />
            {contact.email}
          </a>
        </div>

        {/* Copyright */}
        <div className="pt-3 border-t hairline font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
          © {new Date().getFullYear()} Rambla Rental
        </div>
      </div>
    </footer>
  );
}

// ── Desktop full ────────────────────────────────────────────────────────────

function FooterDesktop() {
  const contact = useBusinessContact();
  return (
    <footer className="hidden md:block border-t hairline bg-background">
      <div className="mx-auto max-w-7xl px-6 lg:px-12 py-12">
        <div className="grid gap-10 md:grid-cols-12">
          {/* Branding + tagline */}
          <div className="md:col-span-4">
            <img src={logoWordmark} alt="Rambla Rental" className="h-12 w-auto" loading="lazy" />
            <p className="mt-3 text-sm text-muted-foreground max-w-xs">
              Equipos audiovisuales y estudio de foto/video en Mar del Plata. Producciones de
              cualquier escala.
            </p>

            <a
              href={whatsappUrl("Hola! Tengo una consulta.")}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-5 inline-flex items-center gap-2 rounded-full bg-ink text-amber px-4 py-2 text-sm font-medium transition hover:brightness-110"
            >
              <MessageCircle className="h-4 w-4" />
              Consultanos por WhatsApp
            </a>
          </div>

          {/* Contacto */}
          <div className="md:col-span-4">
            <h3 className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground mb-4">
              Contacto
            </h3>
            <ul className="space-y-3 text-sm">
              <li className="flex items-start gap-2.5">
                <MapPin className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
                <a
                  href={contact.mapsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-ink hover:text-amber transition whitespace-pre-line"
                >
                  {contact.address}
                </a>
              </li>
              <li className="flex items-start gap-2.5">
                <Phone className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
                <a
                  href={whatsappUrl()}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-mono tabular text-ink hover:text-amber transition"
                >
                  {contact.phoneDisplay}
                </a>
              </li>
              <li className="flex items-start gap-2.5">
                <Mail className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
                <a
                  href={`mailto:${contact.email}`}
                  className="text-ink hover:text-amber transition"
                >
                  {contact.email}
                </a>
              </li>
              <li className="flex items-start gap-2.5">
                <Clock className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
                <div className="text-muted-foreground space-y-0.5">
                  {CONTACT.hours.map((h) => (
                    <div key={h.days}>
                      <span className="text-ink">{h.days}:</span> {h.hours}
                    </div>
                  ))}
                </div>
              </li>
            </ul>
          </div>

          {/* Navegación */}
          <div className="md:col-span-4">
            <h3 className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground mb-4">
              Navegación
            </h3>
            <ul className="space-y-2.5 text-sm">
              <li>
                <Link to="/" className="text-ink hover:text-amber transition">
                  Catálogo
                </Link>
              </li>
              <li>
                <Link to="/estudio" className="text-ink hover:text-amber transition">
                  El Estudio
                </Link>
              </li>
              <li>
                <Link to="/preguntas-frecuentes" className="text-ink hover:text-amber transition">
                  Preguntas frecuentes
                </Link>
              </li>
              <li>
                <a
                  href={`https://instagram.com/${contact.instagram}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-ink hover:text-amber transition"
                >
                  <Instagram className="h-4 w-4" />@{contact.instagram}
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-10 pt-6 border-t hairline flex flex-col-reverse gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            <span>© {new Date().getFullYear()} Rambla Rental</span>
            <Link to="/privacidad" className="hover:text-ink transition">
              Privacidad
            </Link>
            <Link to="/terminos" className="hover:text-ink transition">
              Términos
            </Link>
          </div>

          <div className="flex flex-wrap gap-x-4 gap-y-2 items-center font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            <span>Aceptamos:</span>
            {CONTACT.paymentMethods.map((m) => (
              <span key={m} className="text-ink">
                {m}
              </span>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}
