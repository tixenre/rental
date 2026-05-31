import { KitComponentEditor } from "./KitComponentEditor";

export function ComboEditor({ equipoId }: { equipoId: number }) {
  return <KitComponentEditor equipoId={equipoId} mode="combo" />;
}
