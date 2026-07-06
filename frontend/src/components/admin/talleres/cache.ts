import type { QueryClient } from "@tanstack/react-query";
import type { EdicionAdmin, TallerConcepto } from "@/lib/admin/api/types";

export function updateEdicionInCache(qc: QueryClient, updated: EdicionAdmin) {
  qc.setQueryData(["admin", "talleres"], (prev: TallerConcepto[] | undefined) =>
    prev?.map((c) => ({
      ...c,
      ediciones: c.ediciones.map((e) => (e.id === updated.id ? updated : e)),
    })),
  );
}

export function updateConceptoInCache(qc: QueryClient, updated: TallerConcepto) {
  qc.setQueryData(["admin", "talleres"], (prev: TallerConcepto[] | undefined) =>
    prev?.map((c) => (c.id === updated.id ? updated : c)),
  );
}
