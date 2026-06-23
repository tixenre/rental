import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import { Plus, ChevronDown, ArrowRight } from "lucide-react";
import { useCart } from "@/lib/cart-store";
import { type Equipment } from "@/data/equipment";
import { useClienteSession, aplicaIva } from "@/lib/iva";
import { buildEquipoSlug } from "@/lib/equipo-slug";
import { EmptyImage } from "./EmptyImage";
import { AddonPills } from "./AddonPills";
import { KitSection } from "./KitSection";
import { IncludedList } from "./IncludedList";
import { cn } from "@/lib/utils";
import { StepperPill } from "./equipment/shared/StepperPill";
import { PriceBlock } from "./equipment/shared/PriceBlock";
import { FavButton } from "./equipment/shared/FavButton";
import { buildFotoSrcSet } from "@/lib/srcset";

/**
 * EquipmentRow — vista de lista del catálogo (desktop + mobile responsive).
 *
 * Click en thumb/info → expande inline una mini-ficha (kit + specs clave) en
 * mobile/tablet; en desktop (lg+) el detalle lo muestra el PreviewPane lateral,
 * así que el expand queda oculto. Dentro del expand, "Ver ficha técnica" navega
 * a /equipo/<slug>.
 *
 * Reusa la librería de assets compartidos `equipment/shared` (StepperPill,
 * PriceBlock, FavButton) — no recrear variantes (docs/MEMORIA.md 2026-05-29).
 */
export function EquipmentRow({
  item,
  disponible,
  index = 99,
}: {
  item: Equipment;
  disponible?: number;
  index?: number;
}) {
  const qty = useCart((s) => s.items[item.id] ?? 0);
  const add = useCart((s) => s.add);
  const remove = useCart((s) => s.remove);
  const jornadas = useCart((s) => s.days());
  const hasDateRange = useCart((s) => !!s.startDate && !!s.endDate);
  const selected = qty > 0;
  const navigate = useNavigate();
  const { data: clienteSession } = useClienteSession();
  const conIva = aplicaIva(clienteSession?.perfil_impuestos);
  const openDetail = () =>
    navigate({ to: "/equipo/$slug", params: { slug: buildEquipoSlug(item) } });

  const [expanded, setExpanded] = useState(false);
  const [imgFailed, setImgFailed] = useState(false);

  const cap = disponible ?? item.cantidad ?? Infinity;
  const sinStock = cap <= 0;
  const stockBajo = !sinStock && cap > 0 && cap <= 2;
  const reachedMax = qty >= cap;

  // Nombre público: `item.name` ya es el nombre público canónico —
  // `backendToEquipment` lo deriva vía `buildPublicName` (single source of
  // truth: usa `nombre_publico` del backend, que ya incluye la marca, con
  // fallback al nombre interno). No re-concatenar `item.brand` acá: duplicaba
  // la marca en los equipos con template configurado.
  const nombrePublico = item.name;

  // Quick facts para el expand: specs_destacados del template si las hay, si no
  // cae al conjunto fijo legacy.
  const quickFacts = (
    item.specsDestacados && item.specsDestacados.length > 0
      ? item.specsDestacados
      : [
          item.montura && { label: "Montura", value: item.montura },
          item.formato && { label: "Formato", value: item.formato },
          item.resolucion && { label: "Resolución", value: item.resolucion },
          item.peso && { label: "Peso", value: item.peso },
          item.alimentacion && { label: "Alimentación", value: item.alimentacion },
        ].filter((x): x is { label: string; value: string } => !!x)
  ).slice(0, 3);

  return (
    <div
      id={`eq-${item.id}`}
      className={cn(
        "rounded-lg border bg-surface transition-all",
        expanded
          ? "border-ink/40 bg-accent/30 shadow-[var(--shadow-sm)]"
          : selected
            ? "border-amber/60 bg-amber-soft/30"
            : sinStock
              ? "hairline opacity-50"
              : "hairline hover:border-foreground/20",
      )}
    >
      <div className="flex items-center gap-3 p-2.5 sm:gap-4 sm:px-3">
        {/* ── Thumb cuadrado 1:1 + FavButton ─────────────────── */}
        <div className="relative shrink-0">
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            aria-label={`${expanded ? "Cerrar" : "Ver"} info de ${nombrePublico}`}
            className="relative block aspect-square w-12 overflow-hidden rounded-md bg-white sm:w-[52px]"
          >
            {item.fotoUrl && !imgFailed ? (
              <img
                src={item.fotoUrl}
                srcSet={buildFotoSrcSet(item.fotoUrl, item.fotoUrlSm)}
                sizes="52px"
                alt={nombrePublico}
                className="h-full w-full object-contain p-1.5"
                loading={index < 4 ? "eager" : "lazy"}
                decoding="async"
                onError={() => setImgFailed(true)}
              />
            ) : (
              <EmptyImage category={item.category} brand={item.brand} />
            )}
          </button>
          <FavButton itemId={item.id} size="sm" className="absolute -right-1.5 -top-1.5" />
        </div>

        {/* ── Info + expand toggle ────────────────────────────── */}
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="flex min-w-0 flex-1 flex-col text-left"
        >
          {/* Categoría — solo la categoría (sin marca) */}
          <div className="flex items-center gap-1.5 font-mono text-2xs uppercase tracking-[0.18em] text-muted-foreground">
            <span className="truncate">{item.category}</span>
            {disponible !== undefined && (sinStock || stockBajo) && (
              <span className={cn("shrink-0", sinStock ? "text-destructive" : "text-amber")}>
                · {sinStock ? "no disponible" : `${disponible} disp.`}
              </span>
            )}
          </div>

          {/* Nombre: font-sans bold 15px */}
          <div className="flex items-center gap-1.5">
            <span className="truncate font-sans text-15 font-bold leading-tight text-ink">
              {nombrePublico}
            </span>
            <ChevronDown
              className={cn(
                "h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform lg:hidden",
                expanded && "rotate-180",
              )}
            />
          </div>

          {/* Precio inline mobile */}
          <div className="mt-0.5 sm:hidden">
            <PriceBlock
              perDay={item.pricePerDay}
              jornadas={hasDateRange ? jornadas : 0}
              qty={qty || 1}
              conIva={conIva}
              size="sm"
            />
          </div>
        </button>

        {/* ── Addon pills — solo desktop (lg+) ────────────────── */}
        <AddonPills items={item.includes} max={3} className="hidden max-w-[280px] lg:flex" />

        {/* ── Precio desktop ──────────────────────────────────── */}
        <div className="hidden sm:block">
          <PriceBlock
            perDay={item.pricePerDay}
            jornadas={hasDateRange ? jornadas : 0}
            qty={qty || 1}
            conIva={conIva}
            size="md"
            align="right"
          />
        </div>

        {/* ── CTA: Agregar o StepperPill ──────────────────────── */}
        {qty === 0 ? (
          <button
            type="button"
            onClick={() => !sinStock && add(item.id)}
            disabled={sinStock}
            aria-label={`Agregar ${nombrePublico}`}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full border hairline hover:border-amber hover:bg-amber hover:text-ink active:border-amber active:bg-amber active:text-ink disabled:cursor-not-allowed disabled:opacity-40 sm:h-auto sm:w-auto sm:rounded-md sm:px-3 sm:py-1.5"
          >
            <Plus className="h-4 w-4 sm:hidden" />
            <span className="hidden items-center gap-1.5 font-sans text-xs font-medium uppercase tracking-wider sm:flex">
              <Plus className="h-3 w-3" />
              {sinStock ? "Sin stock" : "Agregar"}
            </span>
          </button>
        ) : (
          <StepperPill
            qty={qty}
            onIncrement={() => !reachedMax && add(item.id)}
            onDecrement={() => remove(item.id)}
            maxReached={reachedMax}
            size="sm"
          />
        )}
      </div>

      {/* ── Expand inline — solo mobile (lg:hidden) ─────────── */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            key="expand"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="overflow-hidden lg:hidden"
          >
            <div className="space-y-3 border-t hairline px-3 py-3 sm:px-4 sm:py-4">
              {/* Quick facts */}
              {quickFacts.length > 0 && (
                <div className="hidden flex-wrap gap-1.5 sm:flex">
                  {quickFacts.map((f) => (
                    <span
                      key={f.label}
                      className="inline-flex items-center gap-1.5 rounded-full border hairline bg-background px-2 py-0.5 text-xs"
                    >
                      <span className="font-mono uppercase tracking-wider text-muted-foreground">
                        {f.label}
                      </span>
                      {f.value?.trim() && <span className="font-medium text-ink">{f.value}</span>}
                    </span>
                  ))}
                </div>
              )}

              {/* Kit + includes (includes en 2 columnas) */}
              <KitSection item={item} />
              <div className="[&_ul]:grid [&_ul]:grid-cols-2 [&_ul]:gap-x-4">
                <IncludedList item={item} />
              </div>

              {/* Ver ficha técnica — navega a /equipo/$slug */}
              <button
                type="button"
                onClick={openDetail}
                className="inline-flex items-center gap-1.5 font-mono text-xs uppercase tracking-widest text-ink transition hover:text-amber"
              >
                Ver ficha técnica
                <ArrowRight className="h-3 w-3" />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
