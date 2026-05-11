import { createFileRoute } from "@tanstack/react-router";
import { MessageCircle } from "lucide-react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Footer } from "@/components/rental/Footer";
import { TopBar } from "@/components/rental/TopBar";
import { FAQ_GROUPS } from "@/data/faq";
import { whatsappUrl } from "@/data/contact";

export const Route = createFileRoute("/preguntas-frecuentes")({
  head: () => ({
    meta: [
      { title: "Preguntas frecuentes — Rambla Rental" },
      {
        name: "description",
        content:
          "Respuestas a las preguntas más comunes sobre alquiler de equipos audiovisuales en Rambla Rental: reservas, pago, retiro, devolución, seguros.",
      },
    ],
  }),
  component: FaqPage,
});

function FaqPage() {
  return (
    <div className="min-h-screen flex flex-col bg-background">
      <TopBar />

      <main className="flex-1 px-6 lg:px-12 py-12 max-w-3xl mx-auto w-full">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Ayuda
        </div>
        <h1 className="mt-2 wordmark text-5xl text-ink">
          Preguntas frecuentes
        </h1>
        <p className="mt-3 text-muted-foreground">
          Todo lo que solés preguntar antes de reservar. Si tu duda no está
          acá, escribinos por WhatsApp y te respondemos.
        </p>

        <div className="mt-10 space-y-10">
          {FAQ_GROUPS.map((group) => (
            <section key={group.title}>
              <h2 className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground mb-3">
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
          <p className="text-sm text-ink">
            ¿No encontraste lo que buscabas?
          </p>
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
      </main>

      <Footer />
    </div>
  );
}
