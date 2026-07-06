import { createFileRoute } from "@tanstack/react-router";
import { useEffect } from "react";
import { MessageCircle } from "lucide-react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/design-system/ui/accordion";
import { PublicLayout } from "@/components/rental/shell/PublicLayout";
import { useFaqGroups } from "@/data/faq";
import { whatsappUrl } from "@/data/contact";
import { SITE_URL } from "@/lib/site";

export const Route = createFileRoute("/preguntas-frecuentes")({
  head: () => ({
    meta: [
      { title: "Preguntas frecuentes — Rambla Rental" },
      {
        name: "description",
        content:
          "Respuestas a las preguntas más comunes sobre alquiler de equipos audiovisuales en Rambla Rental: reservas, pago, retiro, devolución, seguros.",
      },
      { property: "og:type", content: "website" },
      { property: "og:url", content: `${SITE_URL}/preguntas-frecuentes` },
      { property: "og:title", content: "Preguntas frecuentes — Rambla Rental" },
      {
        property: "og:description",
        content: "Reservas, pago, retiro, devolución, seguros.",
      },
      { property: "og:image", content: `${SITE_URL}/icon-512.png` },
      { property: "og:locale", content: "es_AR" },
      { name: "twitter:card", content: "summary" },
      { name: "twitter:title", content: "Preguntas frecuentes — Rambla Rental" },
      { name: "twitter:description", content: "Reservas, pago, retiro, devolución, seguros." },
    ],
    // El structured data FAQPage (JSON-LD) se inyecta en el componente desde
    // las FAQ EN VIVO (editables en el back-office), no acá — así los rich
    // snippets de Google reflejan lo que el admin configuró. Ver FaqPage.
    links: [{ rel: "canonical", href: `${SITE_URL}/preguntas-frecuentes` }],
  }),
  component: FaqPage,
});

function FaqPage() {
  const groups = useFaqGroups();

  // Structured data FAQPage (rich snippets de Google) inyectado desde las FAQ
  // en vivo, así refleja lo editado en el back-office. SPA sin SSR: se inyecta
  // client-side (Google ejecuta JS al indexar).
  useEffect(() => {
    const schema = {
      "@context": "https://schema.org",
      "@type": "FAQPage",
      mainEntity: groups.flatMap((g) =>
        g.items.map((it) => ({
          "@type": "Question",
          name: it.q,
          acceptedAnswer: { "@type": "Answer", text: it.a },
        })),
      ),
    };
    const el = document.createElement("script");
    el.type = "application/ld+json";
    el.dataset.faqJsonld = "true";
    el.textContent = JSON.stringify(schema);
    document.head.appendChild(el);
    return () => {
      el.remove();
    };
  }, [groups]);

  return (
    <PublicLayout>
      <div className="px-6 lg:px-12 py-12 max-w-3xl mx-auto w-full">
        <div className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
          Ayuda
        </div>
        <h1 className="mt-2 wordmark text-5xl text-ink">Preguntas frecuentes</h1>
        <p className="mt-3 text-muted-foreground">
          Todo lo que solés preguntar antes de reservar. Si tu duda no está acá, escribinos por
          WhatsApp y te respondemos.
        </p>

        <div className="mt-10 space-y-10">
          {groups.map((group) => (
            <section key={group.title}>
              <h2 className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground mb-3">
                {group.title}
              </h2>
              <Accordion type="multiple" className="rounded-lg border hairline divide-y hairline">
                {group.items.map((item, i) => (
                  <AccordionItem
                    key={item.q}
                    value={`${group.title}-${i}`}
                    className="border-0 px-4"
                  >
                    <AccordionTrigger className="text-left text-sm font-medium text-ink hover:no-underline py-4">
                      {item.q}
                    </AccordionTrigger>
                    <AccordionContent className="text-sm text-muted-foreground pb-4 leading-relaxed">
                      {item.a}
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </section>
          ))}
        </div>

        {/* CTA al final */}
        <div className="mt-12 rounded-lg border hairline bg-muted/30 p-6 text-center">
          <p className="text-sm text-ink">¿No encontraste lo que buscabas?</p>
          <a
            href={whatsappUrl(
              "Hola! Tengo una consulta que no está en la sección de preguntas frecuentes.",
            )}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-4 inline-flex items-center gap-2 rounded-full bg-ink text-amber px-5 py-2.5 text-sm font-medium transition hover:brightness-110"
          >
            <MessageCircle className="h-4 w-4" />
            Escribinos por WhatsApp
          </a>
        </div>
      </div>
    </PublicLayout>
  );
}
