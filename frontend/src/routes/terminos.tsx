import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";

import { PublicLayout } from "@/components/rental/PublicLayout";
import { LAST_UPDATED, TERMS_SECTIONS } from "@/data/legal";
import { SITE_URL } from "@/lib/site";

export const Route = createFileRoute("/terminos")({
  head: () => ({
    meta: [
      { title: "Términos y condiciones — Rambla Rental" },
      {
        name: "description",
        content:
          "Términos y condiciones de alquiler de equipos audiovisuales en Rambla Rental, Mar del Plata. Reservas, pago, daños, cancelaciones.",
      },
      { property: "og:title", content: "Términos y condiciones — Rambla Rental" },
      { property: "og:type", content: "website" },
      { property: "og:url", content: `${SITE_URL}/terminos` },
    ],
    links: [{ rel: "canonical", href: `${SITE_URL}/terminos` }],
  }),
  component: TerminosPage,
});

function TerminosPage() {
  return (
    <PublicLayout>
      <div className="max-w-3xl mx-auto w-full px-4 md:px-6 py-8 md:py-12">
        <Link
          to="/rental"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-ink transition mb-6"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Volver al catálogo
        </Link>

        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Legal
        </div>
        <h1 className="font-display text-3xl md:text-4xl text-ink mt-1">Términos y condiciones</h1>
        <p className="text-sm text-muted-foreground mt-2">Última actualización: {LAST_UPDATED}</p>

        <article className="mt-8 space-y-6 text-[15px] leading-relaxed text-foreground/90">
          {TERMS_SECTIONS.map((s) => (
            <section key={s.id} id={s.id}>
              <h2 className="font-display text-xl text-ink mb-2">{s.title}</h2>
              <p className="whitespace-pre-line">{s.content}</p>
            </section>
          ))}
        </article>

        <div className="mt-12 pt-6 border-t hairline text-xs text-muted-foreground">
          Si tenés dudas sobre algún punto, escribinos antes de reservar — los datos de contacto
          están en la sección 14.
        </div>
      </div>
    </PublicLayout>
  );
}
