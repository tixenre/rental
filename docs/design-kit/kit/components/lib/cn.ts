/**
 * cn — shadcn-style class-name merger.
 * Wraps clsx + tailwind-merge so duplicate Tailwind utilities are de-duped
 * (e.g. cn("p-2", "p-4") → "p-4").
 *
 * Requires `clsx` and `tailwind-merge` as deps (already in the rental repo).
 */
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
