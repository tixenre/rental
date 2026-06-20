import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { Logo } from "@/components/rental/Logo";
import { Footer } from "@/components/rental/Footer";
import { SITE_URL } from "@/lib/site";
import { useHeroPhotos } from "@/lib/studio/hero-photos";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Rambla — Equipos, Estudio y Talleres en Mar del Plata" },
      {
        name: "description",
        content:
          "Alquilá equipos audiovisuales, reservá el estudio de foto y video, y sumate a un workshop. Todo en Rambla, Mar del Plata.",
      },
      { property: "og:type", content: "website" },
      { property: "og:url", content: `${SITE_URL}/` },
      { property: "og:title", content: "Rambla — Equipos, Estudio y Talleres" },
      {
        property: "og:description",
        content:
          "Alquilá equipos audiovisuales, reservá el estudio y sumate a un workshop. Mar del Plata.",
      },
      { property: "og:locale", content: "es_AR" },
    ],
    links: [{ rel: "canonical", href: `${SITE_URL}/` }],
  }),
  component: LandingHub,
});

function LandingHub() {
  const photos = useHeroPhotos();
  const studioPic = photos[0];

  return (
    <div className="min-h-screen flex flex-col">
      {/* TopBar mínima — logo + nav */}
      <header className="sticky top-0 z-40 border-b hairline bg-background/95 backdrop-blur-xl">
        <div className="flex items-center justify-between px-4 sm:px-6 lg:px-12 h-16">
          <Logo size="sm" linkTo={null} />
          <nav className="flex items-center gap-4 text-sm font-medium">
            <Link to="/catalogo" className="text-muted-foreground hover:text-ink transition hidden sm:block">
              Catálogo
            </Link>
            <Link to="/estudio" className="text-muted-foreground hover:text-ink transition hidden sm:block">
              Estudio
            </Link>
            <Link to="/talleres" className="text-muted-foreground hover:text-ink transition hidden sm:block">
              Talleres
            </Link>
            <Link
              to="/catalogo"
              className="inline-flex items-center gap-1.5 rounded-full bg-ink text-amber px-4 py-2 text-xs font-semibold transition hover:brightness-110"
            >
              Ver catálogo
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1 flex flex-col">
        {/* ── Hero ─────────────────────────────────────────────────────────── */}
        <section className="flex flex-col items-center justify-center text-center px-4 py-16 sm:py-24 bg-background">
          <p className="font-mono text-[0.625rem] tracking-[0.35em] uppercase text-muted-foreground mb-6">
            Chaco 1392 — Mar del Plata
          </p>
          <h1
            className="font-display font-black lowercase leading-[0.88] tracking-[-0.02em] text-ink"
            style={{ fontSize: "clamp(3.5rem, 14vw, 9rem)" }}
          >
            rambla.
          </h1>
          <p className="mt-5 text-base sm:text-lg text-muted-foreground max-w-md leading-relaxed">
            Equipos audiovisuales, estudio de foto y video, y workshops — todo en un lugar.
          </p>
        </section>

        {/* ── Tres propuestas ──────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-3 flex-1 min-h-[55vh]">

          {/* Rental */}
          <Link
            to="/catalogo"
            className="group relative flex flex-col justify-end p-8 sm:p-10 bg-amber text-ink min-h-[320px] md:min-h-0 transition-[filter] hover:brightness-105 active:brightness-95"
          >
            <p className="font-mono text-[0.625rem] tracking-[0.28em] uppercase text-ink/55 mb-5">
              Equipos audiovisuales
            </p>
            <h2
              className="font-display font-black lowercase leading-[0.9] tracking-[-0.02em] text-ink mb-4"
              style={{ fontSize: "clamp(1.75rem, 3.5vw, 2.5rem)" }}
            >
              rental.<br /><span className="opacity-60">alquilá lo<br />que necesitás.</span>
            </h2>
            <p className="text-ink/65 text-sm mb-7 leading-relaxed max-w-xs">
              Cámaras, lentes, iluminación, audio y soportes. Retiro en el estudio.
            </p>
            <span className="inline-flex items-center gap-2 w-fit rounded-full bg-ink text-background px-5 py-2.5 text-sm font-bold tracking-[-0.01em] transition-[gap] duration-150 group-hover:gap-3.5">
              Ver catálogo <ArrowRight className="h-3.5 w-3.5" />
            </span>
          </Link>

          {/* Estudio */}
          <Link
            to="/estudio"
            className="group relative flex flex-col justify-end p-8 sm:p-10 min-h-[320px] md:min-h-0 overflow-hidden transition-[filter] hover:brightness-105 active:brightness-95"
            style={{ backgroundColor: "var(--color-naranja)" }}
          >
            {studioPic && (
              <img
                src={studioPic}
                alt="Rambla Estudio"
                className="absolute inset-0 w-full h-full object-cover opacity-[0.12] transition-transform duration-700 group-hover:scale-[1.04]"
                loading="lazy"
              />
            )}
            <div className="relative">
              <p className="font-mono text-[0.625rem] tracking-[0.28em] uppercase mb-5 text-white/65">
                El Estudio
              </p>
              <h2
                className="font-display font-black lowercase leading-[0.9] tracking-[-0.02em] text-white mb-4"
                style={{ fontSize: "clamp(1.75rem, 3.5vw, 2.5rem)" }}
              >
                estudio.<br /><span className="opacity-70">un lugar donde<br />pasan cosas.</span>
              </h2>
              <p className="text-white/70 text-sm mb-7 leading-relaxed max-w-xs">
                Set con fondo infinito, ciclorama y luz natural. Por hora.
              </p>
              <span className="inline-flex items-center gap-2 w-fit rounded-full bg-white text-ink px-5 py-2.5 text-sm font-bold tracking-[-0.01em] transition-[gap] duration-150 group-hover:gap-3.5">
                Ver el estudio <ArrowRight className="h-3.5 w-3.5" />
              </span>
            </div>
          </Link>

          {/* Talleres */}
          <Link
            to="/talleres"
            className="group relative flex flex-col justify-end p-8 sm:p-10 text-ink min-h-[320px] md:min-h-0 transition-[filter] hover:brightness-105 active:brightness-95"
            style={{ backgroundColor: "var(--color-rosa)" }}
          >
            <p className="font-mono text-[0.625rem] tracking-[0.28em] uppercase text-ink/55 mb-5">
              Workshops & Talleres
            </p>
            <h2
              className="font-display font-black lowercase leading-[0.9] tracking-[-0.02em] text-ink mb-4"
              style={{ fontSize: "clamp(1.75rem, 3.5vw, 2.5rem)" }}
            >
              workshops.<br /><span className="opacity-60">aprender<br />haciendo.</span>
            </h2>
            <p className="text-ink/65 text-sm mb-7 leading-relaxed max-w-xs">
              Clases prácticas de dirección de arte, foto y video. Cupos limitados.
            </p>
            <span className="inline-flex items-center gap-2 w-fit rounded-full bg-ink text-background px-5 py-2.5 text-sm font-bold tracking-[-0.01em] transition-[gap] duration-150 group-hover:gap-3.5">
              Ver talleres <ArrowRight className="h-3.5 w-3.5" />
            </span>
          </Link>
        </div>
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
}
