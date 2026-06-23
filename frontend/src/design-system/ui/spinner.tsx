import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Spinner — primitivo de carga canónico del repo.
 *
 * Consolida los 34 usos de `<Loader2 className="animate-spin …" />` dispersos
 * en el repo. Importar de `@/design-system/ui/spinner` (o del barrel `@/design-system`).
 *
 * Velocidad: usa `--duration-xslow` (550ms/vuelta) del token de motion del DS,
 * más lenta que el default de Tailwind (1s) → sensación "suave" sin lentitud.
 */

const SIZE = {
  xs: "size-3",
  sm: "size-4",
  md: "size-5",
  lg: "size-6",
} as const;

export function Spinner({
  size = "md",
  className,
}: {
  size?: keyof typeof SIZE;
  className?: string;
}) {
  return (
    <Loader2
      className={cn(
        "animate-spin text-current",
        "[animation-duration:var(--duration-xslow)]",
        SIZE[size],
        className,
      )}
      aria-hidden="true"
    />
  );
}
