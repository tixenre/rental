import { authedFetch } from "@/lib/authedFetch";

export const dataioAdminApi = {
  /** Devuelve el Response crudo — el consumidor arma el blob de descarga. */
  exportEntity: (entity: string) => authedFetch(`/api/admin/dataio/export?entity=${entity}`),

  importScope: (scope: string, file: File, dryRun: boolean) => {
    const fd = new FormData();
    fd.append("file", file);
    const url = `/api/admin/dataio/import?scope=${scope}${dryRun ? "&dry_run=true" : ""}`;
    return authedFetch(url, { method: "POST", body: fd });
  },

  resetOperacional: (confirm: string) =>
    authedFetch("/api/admin/dataio/reset-operacional", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm }),
    }),
};
