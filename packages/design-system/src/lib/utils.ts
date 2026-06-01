import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * cn — merge de clases Tailwind con resolución de conflictos.
 * Patrón shadcn estándar. Usado por todos los componentes del kit.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
