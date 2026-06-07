import { Calendar, Phone, MapPin, ArrowRight } from "lucide-react";

interface ComoFuncionaProps {
  onDateOpen: () => void;
}

export function ComoFunciona({ onDateOpen }: ComoFuncionaProps) {
  const pasos = [
    {
      n: "01",
      Icon: Calendar,
      title: "Seleccioná fechas y equipos",
      desc: "Elegí tus fechas de retiro y devolución, sumá los equipos al carrito y armá tu pedido.",
      cta: true,
    },
    {
      n: "02",
      Icon: Phone,
      title: "Lo confirmamos con vos",
      desc: "Revisamos tu pedido, te contactamos y coordinamos todos los detalles.",
      cta: false,
    },
    {
      n: "03",
      Icon: MapPin,
      title: "Retiralo por Rambla Estudio",
      desc: "Pasá a buscar los equipos al estudio en Mar del Plata. Confirmás y listo.",
      cta: false,
    },
  ];

  return (
    <section className="py-[clamp(1.25rem,2.5vw,1.75rem)] bg-background">
      <div className="max-w-[1180px] mx-auto px-[clamp(16px,4vw,28px)]">
        <div className="mb-[clamp(0.7rem,1.8vw,1rem)]">
          <p className="font-mono text-[0.6875rem] tracking-[0.25em] uppercase text-muted-foreground">
            Cómo funciona
          </p>
          <h2 className="font-sans font-bold text-[clamp(1.7rem,4.2vw,2.6rem)] tracking-[-0.02em] leading-[1.05] mt-2 text-balance">
            Alquilar es en tres pasos.
          </h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {pasos.map(({ n, Icon: PasoIcon, title, desc, cta }) => (
            <div
              key={n}
              className="bg-card border hairline rounded-2xl p-3.5 flex flex-col gap-1 transition-[transform,box-shadow] duration-200 hover:-translate-y-[3px] hover:shadow-md"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-[0.8125rem] font-bold tracking-[0.1em] text-amber">
                  {n}
                </span>
                <span className="w-[38px] h-[38px] rounded-[10px] bg-amber-soft text-amber grid place-items-center">
                  <PasoIcon size={20} strokeWidth={1.8} />
                </span>
              </div>
              <h3 className="text-[1.0625rem] font-bold tracking-[-0.01em]">{title}</h3>
              <p className="text-[0.84rem] leading-[1.5] text-muted-foreground">{desc}</p>
              {cta && (
                <button
                  onClick={onDateOpen}
                  className="mt-1 inline-flex items-center gap-1.5 text-[0.8125rem] font-bold text-ink w-fit transition-[gap] duration-150 hover:gap-2.5"
                >
                  Elegí fechas <ArrowRight size={13} strokeWidth={2.4} />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
