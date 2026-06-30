import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { ChevronDown, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { useFaqGroups } from "@/data/faq";

export function FaqTeaser() {
  const groups = useFaqGroups();
  const faqs = groups.flatMap((g) => g.items).slice(0, 4);
  const [open, setOpen] = useState(0);

  return (
    <section id="faq" className="py-[clamp(2.75rem,6vw,4.5rem)] bg-surface">
      <div className="max-w-[760px] mx-auto px-[clamp(16px,4vw,28px)]">
        <div className="mb-[clamp(1.5rem,4vw,2.5rem)]">
          <p className="font-mono text-xs tracking-[0.2em] uppercase text-muted-foreground">
            Preguntas frecuentes
          </p>
          <h2 className="font-sans font-bold text-[clamp(1.7rem,4.2vw,2.6rem)] tracking-[-0.02em] leading-[1.05] mt-2 text-balance">
            Lo que más nos preguntan.
          </h2>
        </div>
        <div className="flex flex-col">
          {faqs.map((f, i) => {
            const isOpen = open === i;
            return (
              <div key={i} className="border-b hairline">
                <button
                  className="w-full flex items-center justify-between gap-4 py-[18px] px-1 text-left text-lg font-bold tracking-[-0.01em] text-ink"
                  onClick={() => setOpen(isOpen ? -1 : i)}
                  aria-expanded={isOpen}
                >
                  <span>{f.q}</span>
                  <ChevronDown
                    size={18}
                    className={cn(
                      "shrink-0 transition-[color,transform] duration-[250ms]",
                      isOpen ? "text-amber rotate-180" : "text-muted-foreground",
                    )}
                  />
                </button>
                <div
                  className="overflow-hidden transition-[max-height] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]"
                  style={{ maxHeight: isOpen ? 200 : 0 }}
                >
                  <p className="px-1 pb-[18px] text-15 leading-[1.6] text-muted-foreground max-w-[60ch]">
                    {f.a}
                  </p>
                </div>
              </div>
            );
          })}
          <Link
            to="/preguntas-frecuentes"
            className="inline-flex items-center gap-[7px] mt-5 font-mono text-xs font-semibold uppercase tracking-[0.16em] text-ink transition-[gap] duration-150 hover:gap-[11px]"
          >
            Ver todas las preguntas <ArrowRight size={14} strokeWidth={2.2} />
          </Link>
        </div>
      </div>
    </section>
  );
}
