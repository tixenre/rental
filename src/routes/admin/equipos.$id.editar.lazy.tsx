import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { adminApi, type EquipoInput } from "@/lib/admin/api";
import { EquipoFormDialogV2 } from "@/components/admin/equipo-form-v2/EquipoFormDialogV2";
import { useDocumentTitle } from "@/lib/use-document-title";

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
    mutationFn: async ({ data, etiquetas }: { data: EquipoInput; etiquetas: string[] }) => {
      const eq = await adminApi.updateEquipo(equipoId, data);
      await adminApi.setEtiquetas(eq.id, etiquetas);
      return eq;
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
      qc.invalidateQueries({ queryKey: ["admin", "equipo", equipoId] });
    },
  });

  const goBack = () => navigate({ to: "/admin/equipos" });

  if (!equipoId) {
    return <div className="p-6 text-sm text-destructive">ID inválido</div>;
  }
  if (equipoQ.isLoading) {
    return (
      <div className="p-10 grid place-items-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (equipoQ.error || !equipoQ.data) {
    return <div className="p-6 text-sm text-destructive">No se pudo cargar el equipo.</div>;
  }

  return (
    <EquipoFormDialogV2
      variant="page"
      open
      initial={equipoQ.data}
      saving={saveMut.isPending}
      onSubmit={(data, etiquetas) => saveMut.mutateAsync({ data, etiquetas })}
      onOpenChange={(v) => {
        if (!v) goBack();
      }}
    />
  );
}
