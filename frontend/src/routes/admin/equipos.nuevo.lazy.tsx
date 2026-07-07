import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { adminApi, type Equipo, type EquipoInput } from "@/lib/admin/api";
import { EquipoFormDialogV2 } from "@/components/admin/equipo-form-v2/EquipoFormDialogV2";
import { popEquiposReturnSearch } from "@/lib/admin/equiposReturnSearch";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export const Route = createLazyFileRoute("/admin/equipos/nuevo")({
  component: NuevoEquipoRoute,
});

function NuevoEquipoRoute() {
  useDocumentTitle("Nuevo equipo · Back Office");
  const navigate = useNavigate();
  const qc = useQueryClient();

  const saveMut = useMutation({
    mutationFn: (data: EquipoInput) => adminApi.createEquipo(data),
    onSettled: () => qc.invalidateQueries({ queryKey: ["admin", "equipos"] }),
  });

  const goBack = () =>
    navigate({ to: "/admin/equipos", search: popEquiposReturnSearch() as never });

  return (
    <EquipoFormDialogV2
      variant="page"
      open
      initial={null}
      saving={saveMut.isPending}
      onSubmit={(data) => saveMut.mutateAsync(data)}
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
