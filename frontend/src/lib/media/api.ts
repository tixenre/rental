import type { EntityMediaResponse } from "./types";

export async function fetchEntityMedia(
  kind: string,
  entityId: number,
): Promise<EntityMediaResponse> {
  const res = await fetch(`/api/media/entity/${encodeURIComponent(kind)}/${entityId}`);
  if (!res.ok) {
    throw new Error(`media/entity: ${res.status} para ${kind}/${entityId}`);
  }
  return res.json() as Promise<EntityMediaResponse>;
}
