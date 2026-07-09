import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Spinner } from "@/design-system/ui/spinner";

import { adminApi, type EquipoInput } from "@/lib/admin/api";
import { EquipoFormDialogV2 } from "@/components/admin/equipo-form-v2/EquipoFormDialogV2";
import { popEquiposReturnSearch } from "@/lib/admin/equiposReturnSearch";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export const Route = createLazyFileRoute("/admin/equipos/$id/editar")({
  component: EditarEquipoRoute,
});

function EditarEquipoRoute() {
  useDocumentTitle("Editar equipo · Back Office");
  const { id } = Route.useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const equipoId = parseInt(id, 10);

  const equipoQ = useQuery({
    queryKey: ["admin", "equipo", equipoId],
    queryFn: () => adminApi.getEquipo(equipoId),
    enabled: !!equipoId,
  });

  const saveMut = useMutation({
    mutationFn: (data: EquipoInput) => adminApi.updateEquipo(equipoId, data),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
      qc.invalidateQueries({ queryKey: ["admin", "equipo", equipoId] });
    },
  });

  // Volver a la lista restaurando los filtros/búsqueda/sort que tenía cuando
  // se entró a editar (sessionStorage seteada por equipos.index).
  const goBack = () =>
    navigate({ to: "/admin/equipos", search: popEquiposReturnSearch() as never });

  if (!equipoId) {
    return <div className="p-6 text-sm text-destructive">ID inválido</div>;
  }
  if (equipoQ.isLoading) {
    return (
      <div className="p-10 grid place-items-center">
        <Spinner size="lg" className="text-muted-foreground" />
      </div>
    );
  }
  if (equipoQ.error || !equipoQ.data) {
    return <div className="p-6 text-sm text-destructive">No se pudo cargar el equipo.</div>;
  }

  return (
    <EquipoFormDialogV2
      open
      initial={equipoQ.data}
      saving={saveMut.isPending}
      onSubmit={(data) => saveMut.mutateAsync(data)}
      onOpenChange={(v) => {
        if (!v) goBack();
      }}
    />
  );
}
