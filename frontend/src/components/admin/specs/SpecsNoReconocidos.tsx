/**
 * SpecsNoReconocidos.tsx — panel admin de specs sin match (#1203).
 *
 * Lista agrupada por label (no por equipo): cada fila es un candidato a spec
 * nuevo o alias, con los equipos que lo encontraron. Vive como tab dentro de
 * `/admin/specs` (specs.index.lazy.tsx) — comparte página con los tabs por
 * categoría, que son la referencia para juzgar "¿ya existe algo parecido?".
 *
 * Resolver acá es bookkeeping puro (aplicar_propuesta/descartar_propuesta —
 * ver `services/specs/commands/propuestas.py`): el spec/alias real se agrega
 * al registry Python a mano y se re-siembra: esto solo cierra el ítem de la
 * cola una vez que ya se hizo.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { toast } from "sonner";
import { ChevronDown, ChevronRight } from "lucide-react";

import { Button } from "@/design-system/ui/button";
import { Badge } from "@/design-system/ui/badge";
import { Pill } from "@/design-system/ui/Pill";
import { adminApi } from "@/lib/admin/api";
import type { NoReconocidoGrupo } from "@/lib/admin/api/types";

export function SpecsNoReconocidos() {
  const queryClient = useQueryClient();
  const q = useQuery({
    queryKey: ["admin", "specs-no-reconocidos"],
    queryFn: () => adminApi.listarNoReconocidos(),
  });

  const resolverMutation = useMutation({
    mutationFn: ({ ids, accion }: { ids: number[]; accion: "aplicado" | "descartado" }) =>
      adminApi.resolverNoReconocidos(ids, accion),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "specs-no-reconocidos"] });
    },
    onError: (e) => {
      toast.error(`No se pudo resolver: ${e instanceof Error ? e.message : "error desconocido"}`);
    },
  });

  const items = q.data?.items ?? [];

  if (q.isLoading) {
    return <div className="text-sm text-muted-foreground">Cargando…</div>;
  }
  if (q.isError) {
    return (
      <div className="text-sm text-destructive">
        Error cargando specs no reconocidas: {(q.error as Error)?.message ?? "desconocido"}
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <div className="text-sm text-muted-foreground border rounded-lg p-6 text-center">
        Sin specs pendientes de clasificar.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground max-w-3xl">
        Labels que aparecieron al subir HTML de un equipo pero no matchean ningún spec conocido de
        su categoría — agrupados por label, con los equipos que lo encontraron. Antes de marcar "es
        nuevo", revisá el tab de la categoría: puede ser el mismo dato con otro nombre — en ese caso
        agregalo como alias en vez de un spec nuevo, y descartá acá.
      </p>
      <div className="space-y-2">
        {items.map((g) => (
          <GrupoRow
            key={`${g.categoria}::${g.label_normalizado}`}
            grupo={g}
            onResolver={(accion) => resolverMutation.mutate({ ids: g.propuesta_ids, accion })}
            resolviendo={resolverMutation.isPending}
          />
        ))}
      </div>
    </div>
  );
}

function GrupoRow({
  grupo,
  onResolver,
  resolviendo,
}: {
  grupo: NoReconocidoGrupo;
  onResolver: (accion: "aplicado" | "descartado") => void;
  resolviendo: boolean;
}) {
  const [expandido, setExpandido] = useState(false);

  return (
    <div className="rounded-lg border p-3 space-y-2">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0 flex-1">
          <button
            type="button"
            onClick={() => setExpandido((v) => !v)}
            className="flex items-center gap-1.5 text-left"
          >
            {expandido ? (
              <ChevronDown className="size-3.5 text-muted-foreground shrink-0" />
            ) : (
              <ChevronRight className="size-3.5 text-muted-foreground shrink-0" />
            )}
            <span className="font-medium text-sm">{grupo.label}</span>
            <Badge variant="secondary" className="text-2xs">
              {grupo.categoria}
            </Badge>
            {grupo.equipo_ids.length > 0 && (
              <span className="text-2xs text-muted-foreground">
                {grupo.equipo_ids.length} equipo{grupo.equipo_ids.length === 1 ? "" : "s"}
              </span>
            )}
          </button>
          {grupo.ejemplos.length > 0 && (
            <p className="text-xs text-muted-foreground mt-1 pl-5 truncate">
              Ej: {grupo.ejemplos.join(" · ")}
            </p>
          )}
        </div>
        <div className="flex gap-2 shrink-0">
          <Button
            size="sm"
            variant="outline"
            disabled={resolviendo}
            onClick={() => onResolver("descartado")}
          >
            Descartar
          </Button>
          <Button
            size="sm"
            variant="primary"
            disabled={resolviendo}
            onClick={() => onResolver("aplicado")}
          >
            Marcar aplicado
          </Button>
        </div>
      </div>

      {expandido && (
        <div className="pl-5 space-y-2 pt-1 border-t">
          {grupo.equipo_ids.length > 0 ? (
            <div className="flex flex-wrap gap-1 pt-2">
              {grupo.equipo_ids.map((id, i) => (
                <Link key={id} to="/admin/equipos/$id/editar" params={{ id: String(id) }}>
                  <Pill className="hover:bg-muted cursor-pointer">
                    {grupo.equipo_nombres[i] ?? `#${id}`}
                  </Pill>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-2xs text-muted-foreground pt-2">
              Propuesta agregada (sin equipo específico atribuido).
            </p>
          )}
          <SpecsExistentesDeCategoria categoria={grupo.categoria} />
        </div>
      )}
    </div>
  );
}

/** Referencia de solo-lectura: specs que YA tiene la categoría, para juzgar
 * si el label sin match es en realidad uno de estos con otro nombre. Lazy
 * (solo se pide al expandir la fila) — no dispara una query por grupo visible. */
function SpecsExistentesDeCategoria({ categoria }: { categoria: string }) {
  const categoriasQ = useQuery({
    queryKey: ["admin", "spec-categorias"],
    queryFn: () => adminApi.listSpecCategorias(),
    staleTime: 5 * 60 * 1000,
  });
  const categoriaId = categoriasQ.data?.categorias.find((c) => c.nombre === categoria)?.id ?? null;

  const templatesQ = useQuery({
    queryKey: ["admin", "spec-templates", categoriaId],
    queryFn: () => adminApi.listSpecTemplates(categoriaId!),
    enabled: categoriaId != null,
  });

  if (categoriaId == null || templatesQ.isLoading) {
    return <p className="text-2xs text-muted-foreground">Cargando specs existentes…</p>;
  }
  const labels = (templatesQ.data?.items ?? []).map((t) => t.label);
  if (labels.length === 0) return null;

  return (
    <div className="text-2xs text-muted-foreground">
      <span className="font-medium">Specs que ya tiene "{categoria}": </span>
      {labels.join(", ")}
    </div>
  );
}
