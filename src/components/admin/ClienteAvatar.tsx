/**
 * ClienteAvatar — círculo con iniciales y color determinístico por nombre.
 *
 * Da reconocimiento visual rápido del cliente en listas/headers (idea tomada de
 * Booqable). El color sale de un hash del nombre sobre una paleta acotada del DS
 * (tokens de marca/secundarios, todos con buen contraste), así un mismo cliente
 * siempre cae en el mismo color. Tamaño/typo se controlan por `className`.
 */

import { cn } from "@/lib/utils";

// Paleta categórica (tier-3): tokens del DS con texto de alto contraste.
const AVATAR_COLORS = [
  "bg-azul text-background",
  "bg-verde text-background",
  "bg-naranja text-background",
  "bg-rosa text-ink",
  "bg-ink text-amber",
];

function hashIndex(s: string, n: number): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h % n;
}

function iniciales(nombre: string): string {
  const parts = nombre.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function ClienteAvatar({
  nombre,
  className,
}: {
  nombre?: string | null;
  className?: string;
}) {
  const safe = (nombre ?? "").trim() || "?";
  const color = AVATAR_COLORS[hashIndex(safe, AVATAR_COLORS.length)];
  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full font-medium leading-none",
        color,
        className,
      )}
      aria-hidden
    >
      {iniciales(safe)}
    </div>
  );
}
