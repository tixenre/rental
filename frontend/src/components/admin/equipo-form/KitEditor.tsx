import { KitComponentEditor } from "./KitComponentEditor";

export function KitEditor({ equipoId }: { equipoId: number }) {
  return <KitComponentEditor equipoId={equipoId} mode="kit" />;
}
