import { authedJson } from "@/lib/authedFetch";

export type MediaStats = {
  total_assets: number;
  total_variants: number;
  total_bytes: number;
  assets_with_lqip: number;
  orphans: number;
  assets_no_variants: number;
};

export type GcResult = {
  orphans_found: number;
  orphans_purged: number;
  r2_keys_deleted: number;
  errors: string[];
  dry_run: boolean;
};

export type RederiveResult = {
  asset_id: number;
  variants_derived: number;
  variants: { name: string; url: string; width: number; height: number }[];
};

export const mediaMethods = {
  getStats: () => authedJson<MediaStats>("/api/admin/media/stats"),

  runGc: (opts: { dry_run?: boolean; kind?: string } = {}) =>
    authedJson<GcResult>("/api/admin/media/gc", {
      method: "POST",
      body: JSON.stringify({ dry_run: opts.dry_run ?? true, kind: opts.kind ?? null }),
    }),

  rederive: (assetId: number) =>
    authedJson<RederiveResult>(`/api/admin/media/rederive/${assetId}`, {
      method: "POST",
    }),
};
