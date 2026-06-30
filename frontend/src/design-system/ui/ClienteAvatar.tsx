/**
 * ClienteAvatar — círculo con foto o iniciales y color determinístico por nombre.
 *
 * Da reconocimiento visual rápido de una persona/cliente en listas y headers
 * (idea tomada de Booqable). Si se pasa `src`, muestra la imagen; si no carga
 * (o no se pasa), cae a iniciales con color determinístico por hash del nombre.
 * El color sale de una paleta acotada del DS (tokens de marca/secundarios, todos
 * con buen contraste), así un mismo nombre siempre cae en el mismo color.
 * Tamaño y typo se controlan por `className`. Reusable en cualquier superficie.
 */

import { useState } from "react";
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
  src,
  className,
}: {
  nombre?: string | null;
  src?: string | null;
  className?: string;
}) {
  const [imgError, setImgError] = useState(false);
  const safe = (nombre ?? "").trim() || "?";
  const color = AVATAR_COLORS[hashIndex(safe, AVATAR_COLORS.length)];
  const showImg = !!src && !imgError;

  return (
    <div
      className={cn(
        "relative flex shrink-0 items-center justify-center overflow-hidden rounded-full font-medium leading-none",
        !showImg && color,
        className,
      )}
      aria-hidden
    >
      {showImg ? (
        <img
          src={src}
          alt=""
          className="h-full w-full object-cover"
          onError={() => setImgError(true)}
        />
      ) : (
        iniciales(safe)
      )}
    </div>
  );
}
