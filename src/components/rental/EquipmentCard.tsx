import { useState, type MouseEvent } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { useCart } from "@/lib/cart-store";
import { useFlyToCart } from "@/lib/fly-to-cart-store";
import { type Equipment } from "@/data/equipment";
import { useClienteSession, aplicaIva } from "@/lib/iva";
import { buildEquipoSlug } from "@/lib/equipo-slug";
import { EmptyImage } from "./EmptyImage";
import { cn } from "@/lib/utils";
import { StepperPill } from "./equipment/shared/StepperPill";
import { PriceBlock } from "./equipment/shared/PriceBlock";
import { FavButton } from "./equipment/shared/FavButton";

/**
 * EquipmentCard — grid card del catálogo público.
 *
 * Foto 1:1; nombre público (`item.name`) en font-sans bold (no Champ); precio vía
 * PriceBlock (font-mono); stepper vía StepperPill hairline; favorito real
 * (useFavoritos) arriba-derecha de la foto; "ver ficha técnica" en overlay al
 * hover; badge no-disponible en rojo suave.
 *
 * Reusa la librería de assets compartidos `equipment/shared` (StepperPill,
 * PriceBlock, FavButton) — no recrear variantes (docs/MEMORIA.md 2026-05-29).
 */
export function EquipmentCard({
  item,
  index,
  width,
  disponible,
}: {
  item: Equipment;
  index: number;
  /** Ancho fijo en px para uso dentro de carrusel; si no, ocupa la celda. */
  width?: number;
  /** Unidades disponibles en las fechas seleccionadas (undefined = no hay fechas) */
  disponible?: number;
}) {
  const qty = useCart((s) => s.items[item.id] ?? 0);
  const add = useCart((s) => s.add);
  const remove = useCart((s) => s.remove);
  const triggerFly = useFlyToCart((s) => s.triggerFly);
  const jornadas = useCart((s) => s.days());
  const hasDateRange = useCart((s) => !!s.startDate && !!s.endDate);
  const [imgFailed, setImgFailed] = useState(false);

  const { data: clienteSession } = useClienteSession();
  const conIva = aplicaIva(clienteSession?.perfil_impuestos);

  const navigate = useNavigate();
  const openDetail = () =>
    navigate({ to: "/equipo/$slug", params: { slug: buildEquipoSlug(item) } });

  const cap = disponible ?? item.cantidad ?? Infinity;
  const sinStock = cap <= 0;
  const reachedMax = qty >= cap;

  const selected = qty > 0;

  // Nombre público: `item.name` ya es el nombre público canónico —
  // `backendToEquipment` lo deriva vía `buildPublicName` (single source of
  // truth: usa `nombre_publico` del backend, que ya incluye la marca, con
  // fallback al nombre interno). No re-concatenar `item.brand` acá: duplicaba
  // la marca en los equipos con template configurado.
  const nombrePublico = item.name;

  // Incluye: texto inline de lo que viene con el equipo.
  const includesText = item.includes?.length
    ? item.includes
        .slice(0, 3)
        .map((i) => (i.qty && i.qty > 1 ? `${i.name} ×${i.qty}` : i.name))
        .join(" · ") + (item.includes.length > 3 ? ` · +${item.includes.length - 3}` : "")
    : null;

  const handleAdd = (e: MouseEvent<HTMLButtonElement>) => {
    if (sinStock || reachedMax) return;
    const rect = e.currentTarget.getBoundingClientRect();
    triggerFly({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
    add(item.id);
  };

  return (
    <motion.article
      id={`eq-${item.id}`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.012, 0.25) }}
      style={width ? { width } : undefined}
      className={cn(
        "group relative flex shrink-0 flex-col overflow-hidden rounded-lg border bg-surface-elevated shadow-[var(--shadow-sm)] transition-all snap-start",
        selected
          ? "border-amber/60"
          : sinStock
            ? "hairline"
            : "hairline hover:border-foreground/20 hover:-translate-y-0.5 hover:shadow-[var(--shadow-md)]",
        sinStock && "opacity-50",
      )}
    >
      {/* ── Foto ───────────────────────────────────────────────── */}
      <div className="relative aspect-square w-full overflow-hidden bg-surface">
        <button
          type="button"
          onClick={openDetail}
          aria-label={`Ver ficha técnica de ${nombrePublico}`}
          className="block h-full w-full"
        >
          {item.fotoUrl && !imgFailed ? (
            <img
              src={item.fotoUrl}
              alt={nombrePublico}
              loading={index < 4 ? "eager" : "lazy"}
              decoding="async"
              fetchPriority={index < 4 ? "high" : "low"}
              onError={() => setImgFailed(true)}
              className="h-full w-full object-contain p-3 transition group-hover:scale-[1.02]"
            />
          ) : (
            <EmptyImage category={item.category} brand={item.brand} />
          )}
        </button>

        {/* Overlays top-left apilados: categoría + (destacado) */}
        <div className="pointer-events-none absolute left-2 top-2 flex flex-col gap-1">
          <span className="rounded-full bg-surface-elevated/88 px-[7px] py-[3px] font-mono text-[8px] uppercase tracking-[0.18em] text-muted-foreground backdrop-blur-sm">
            {item.category}
          </span>
          {item.destacado && (
            <span className="self-start rounded-full bg-amber px-2 py-[3px] font-mono text-[8px] font-bold uppercase tracking-[0.18em] text-ink">
              ★ destacado
            </span>
          )}
        </div>

        {/* Favorito */}
        <FavButton itemId={item.id} className="absolute right-2 top-2" />

        {/* No disponible overlay — rojo suave */}
        {sinStock && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/60">
            <span className="rounded-full border border-destructive/30 bg-destructive/10 px-[10px] py-[5px] text-center font-mono text-[8px] uppercase leading-snug tracking-[0.15em] text-destructive">
              {disponible !== undefined
                ? "Sin disponibilidad en estas fechas"
                : "Sin stock disponible"}
            </span>
          </div>
        )}

        {/* Ver ficha técnica — overlay hover */}
        <button
          type="button"
          onClick={openDetail}
          className="absolute inset-x-0 bottom-0 flex h-[34px] items-center justify-center gap-1.5 bg-ink/72 font-mono text-[9px] uppercase tracking-[0.16em] text-white opacity-0 backdrop-blur-sm transition-opacity group-hover:opacity-100"
        >
          <span>—</span> ver ficha técnica
        </button>
      </div>

      {/* ── Body: nombre + includes ──────────────────────────── */}
      <div className="flex flex-col gap-1 px-3.5 pb-2.5 pt-3">
        <p className="line-clamp-2 font-sans text-[15px] font-bold leading-tight text-ink">
          {nombrePublico}
        </p>
        {includesText && (
          <p className="truncate font-mono text-[9px] tracking-[0.1em] text-muted-foreground">
            {includesText}
          </p>
        )}
      </div>

      {/* ── Footer: precio + acción ──────────────────────────── */}
      <div className="flex items-center justify-between gap-2 px-3.5 pb-3.5">
        <PriceBlock
          perDay={item.pricePerDay}
          jornadas={hasDateRange ? jornadas : 0}
          qty={qty || 1}
          conIva={conIva}
          size="lg"
        />

        {qty === 0 ? (
          <button
            type="button"
            onClick={handleAdd}
            disabled={sinStock}
            aria-label={`Agregar ${nombrePublico} al carrito`}
            className="grid h-[34px] w-[34px] shrink-0 place-items-center rounded-full border hairline bg-background text-ink transition-colors hover:border-amber hover:bg-amber active:scale-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Plus className="h-4 w-4" />
          </button>
        ) : (
          <StepperPill
            qty={qty}
            onIncrement={handleAdd}
            onDecrement={() => remove(item.id)}
            maxReached={reachedMax}
            size="sm"
          />
        )}
      </div>
    </motion.article>
  );
}
