import { Link } from "@tanstack/react-router";
import { Instagram, MessageCircle, MapPin, Phone, Mail, Clock } from "lucide-react";

import { CONTACT, whatsappUrl } from "@/data/contact";
import logoWordmark from "@/assets/rambla-wordmark.png";

/**
 * Footer público — usado en home, catálogo, estudio, FAQ, portal cliente.
 *
 * NO incluir en páginas /admin/* (tienen su propio layout de back-office).
 */
export function Footer() {
  return (
    <footer className="border-t hairline bg-background">
      <div className="mx-auto max-w-7xl px-6 lg:px-12 py-12">
        <div className="grid gap-10 md:grid-cols-12">
          {/* Branding + tagline */}
          <div className="md:col-span-4">
            <img
              src={logoWordmark}
              alt="Rambla Rental"
              className="h-12 w-auto"
              loading="lazy"
            />
            <p className="mt-3 text-sm text-muted-foreground max-w-xs">
              Equipos audiovisuales y estudio de foto/video en Mar del Plata.
              Producciones de cualquier escala.
            </p>

            {/* WhatsApp CTA prominente */}
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
                  href={CONTACT.address.mapsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-ink hover:text-amber transition"
                >
                  {CONTACT.address.line2 ? (
                    <>
                      {CONTACT.address.line2}
                      <br />
                      <span className="text-muted-foreground">
                        {CONTACT.address.city}, {CONTACT.address.province}
                      </span>
                    </>
                  ) : (
                    `${CONTACT.address.city}, ${CONTACT.address.province}`
                  )}
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
                  {CONTACT.phoneDisplay}
                </a>
              </li>
              <li className="flex items-start gap-2.5">
                <Mail className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
                <a
                  href={`mailto:${CONTACT.email}`}
                  className="text-ink hover:text-amber transition"
                >
                  {CONTACT.email}
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
                <Link
                  to="/preguntas-frecuentes"
                  className="text-ink hover:text-amber transition"
                >
                  Preguntas frecuentes
                </Link>
              </li>
              <li>
                <a
                  href={`https://instagram.com/${CONTACT.social.instagram}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-ink hover:text-amber transition"
                >
                  <Instagram className="h-4 w-4" />
                  @{CONTACT.social.instagram}
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="mt-10 pt-6 border-t hairline flex flex-col-reverse gap-4 md:flex-row md:items-center md:justify-between">
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            © {new Date().getFullYear()} Rambla Rental
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
