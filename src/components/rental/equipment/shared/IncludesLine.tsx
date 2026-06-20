import { type IncludedItem } from "@/data/equipment";
import { cn } from "@/lib/utils";

/**
 * IncludesLine — renglón COMPACTO de lo que trae un combo/kit: "A · B · C · +N".
 *
 * Asset canónico reutilizable (docs/MEMORIA.md 2026-05-29): la misma línea
 * compacta se usa en la card del catálogo (EquipmentCard) y en el carrito
 * (CartDrawer) — no recrear la variante inline en cada superficie. Solo
 * renderiza cuando hay componentes (los equipos simples no traen `includes`),
 * así que filtra a combos/kits sin chequear `tipo`.
 *
 * Estática y truncada a una línea (font-mono, como el resto de los metadatos).
 * `max` controla cuántos componentes se listan antes del sufijo "+N"; `label`
 * antepone un rótulo opcional (ej. "Incluye:"); `className` ajusta por superficie.
 */
export function IncludesLine({
  includes,
  max = 3,
  label,
  className,
}: {
  includes?: IncludedItem[];
  max?: number;
  label?: string;
  className?: string;
}) {
  if (!includes?.length) return null;
  const shown = includes
    .slice(0, max)
    .map((i) => (i.qty && i.qty > 1 ? `${i.name} ×${i.qty}` : i.name))
    .join(" · ");
  const rest = includes.length > max ? ` · +${includes.length - max}` : "";
  return (
    <p
      className={cn(
        "truncate font-mono text-[11px] tracking-[0.1em] text-muted-foreground",
        className,
      )}
    >
      {label && <span className="opacity-70">{label} </span>}
      {shown + rest}
    </p>
  );
}
