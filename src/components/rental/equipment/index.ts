/**
 * equipment/ — módulo de vistas del catálogo de equipos + librería de assets
 * visuales compartidos.
 *
 * Los componentes de vista (EquipmentCard, EquipmentRow) siguen viviendo en
 * src/components/rental/ para no romper imports existentes; este index los
 * re-exporta junto con los sub-componentes compartidos.
 *
 *   import { EquipmentCard, StepperPill, PriceBlock, FavButton }
 *     from "@/components/rental/equipment";
 *
 * StepperPill / PriceBlock / FavButton son los assets canónicos reutilizables:
 * usarlos en cualquier pantalla que necesite stepper de cantidad, bloque de
 * precio o botón favorito — no recrear variantes (docs/MEMORIA.md 2026-05-29).
 */
export { EquipmentCard } from "../EquipmentCard";
export { EquipmentRow } from "../EquipmentRow";
export { StepperPill } from "./shared/StepperPill";
export { PriceBlock } from "./shared/PriceBlock";
export { FavButton } from "./shared/FavButton";
export type { EquipmentViewMode } from "./types";
