import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";

import { PublicLayout } from "@/components/rental/PublicLayout";
import { LAST_UPDATED, PRIVACY_SECTIONS } from "@/data/legal";

const SITE_URL = "https://ramblarental.com";

export const Route = createFileRoute("/privacidad")({
  head: () => ({
    meta: [
      { title: "Política de privacidad — Rambla Rental" },
      {
        name: "description",
        content:
          "Cómo Rambla Rental recolecta, usa y protege la información de sus clientes. Cumple con la Ley 25.326 de Argentina.",
      },
      { property: "og:title", content: "Política de privacidad — Rambla Rental" },
      { property: "og:type", content: "website" },
      { property: "og:url", content: `${SITE_URL}/privacidad` },
    ],
    links: [{ rel: "canonical", href: `${SITE_URL}/privacidad` }],
  }),
  component: PrivacidadPage,
});

function PrivacidadPage() {
  return (
    <PublicLayout>
      <div className="max-w-3xl mx-auto w-full px-4 md:px-6 py-8 md:py-12">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-ink transition mb-6"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Volver al catálogo
        </Link>

        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Legal
        </div>
        <h1 className="font-display text-3xl md:text-4xl text-ink mt-1">Política de privacidad</h1>
        <p className="text-sm text-muted-foreground mt-2">Última actualización: {LAST_UPDATED}</p>

        <article className="mt-8 space-y-6 text-[15px] leading-relaxed text-foreground/90">
          {PRIVACY_SECTIONS.map((s) => (
            <section key={s.id} id={s.id}>
              <h2 className="font-display text-xl text-ink mb-2">{s.title}</h2>
              <p className="whitespace-pre-line">{s.content}</p>
            </section>
          ))}
        </article>

        <div className="mt-12 pt-6 border-t hairline text-xs text-muted-foreground">
          Si encontrás algo que querés revisar o consultar, escribinos por WhatsApp o email — los
          datos están en la sección 10.
        </div>
      </div>
    </PublicLayout>
  );
}
