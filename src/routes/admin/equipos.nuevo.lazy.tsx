import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { adminApi, type Equipo, type EquipoInput } from "@/lib/admin/api";
import { EquipoFormDialogV2 } from "@/components/admin/equipo-form-v2/EquipoFormDialogV2";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/equipos/nuevo")({
  component: NuevoEquipoRoute,
});

function NuevoEquipoRoute() {
  useDocumentTitle("Nuevo equipo · Back Office");
  const navigate = useNavigate();
  const qc = useQueryClient();

  const saveMut = useMutation({
    mutationFn: async ({ data, etiquetas }: { data: EquipoInput; etiquetas: string[] }) => {
      const eq = await adminApi.createEquipo(data);
      await adminApi.setEtiquetas(eq.id, etiquetas);
      return eq;
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["admin", "equipos"] }),
  });

  const goBack = () => navigate({ to: "/admin/equipos" });

  return (
    <EquipoFormDialogV2
      variant="page"
      open
      initial={null}
      saving={saveMut.isPending}
      onSubmit={(data, etiquetas) => saveMut.mutateAsync({ data, etiquetas })}
      onOpenChange={(v) => {
        if (!v) goBack();
      }}
      onCreatedWithMissingRecommended={(equipo: Equipo) => {
        // Tras crear, ir al editor del equipo nuevo para completar lo que falte.
        navigate({ to: "/admin/equipos/$id/editar", params: { id: String(equipo.id) } });
      }}
    />
  );
}
