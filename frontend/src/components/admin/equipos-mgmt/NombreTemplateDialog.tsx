/**
 * NombreTemplateDialog — editor de plantilla de nombre público por categoría.
 *
 * El admin define un template con placeholders ({marca}, {modelo}, {spec:Label})
 * que se aplica al generar el nombre público de equipos de esa categoría en
 * el form (toggle "auto").
 */

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/design-system/ui/dialog";
import { Input } from "@/design-system/ui/input";
import { Button } from "@/design-system/ui/button";
import { adminApi } from "@/lib/admin/api";
import { renderNombrePublicoTemplate } from "@/lib/equipment/nombre-template";

export function NombreTemplateDialog({
  open,
  onOpenChange,
  categoriaId,
  categoriaNombre,
  initialTemplate,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  categoriaId: number;
  categoriaNombre: string;
  initialTemplate: string | null | undefined;
}) {
  const qc = useQueryClient();
  const [value, setValue] = useState(initialTemplate ?? "");

  useEffect(() => {
    if (open) setValue(initialTemplate ?? "");
  }, [open, initialTemplate]);

  // Specs disponibles para esta categoría → sugerencias de placeholders.
  const specsQ = useQuery({
    queryKey: ["admin", "spec-templates", categoriaId],
    queryFn: () => adminApi.listSpecTemplates(categoriaId),
    enabled: open,
  });

  const specLabels = useMemo(() => (specsQ.data?.items ?? []).map((t) => t.label), [specsQ.data]);

  const saveMut = useMutation({
    mutationFn: (template: string) =>
      adminApi.adminUpdateCategoria(categoriaId, {
        nombre_publico_template: template,
      }),
    onSuccess: () => {
      toast.success("Plantilla guardada");
      qc.invalidateQueries({ queryKey: ["admin", "categorias"] });
      qc.invalidateQueries({ queryKey: ["categorias"] });
      onOpenChange(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const insertPlaceholder = (p: string) => {
    setValue((cur) => (cur ? `${cur} ${p}` : p));
  };

  // Preview con datos dummy para que el admin vea cómo se ve.
  const preview = renderNombrePublicoTemplate(value, {
    marca: "Sony",
    modelo: "FX3",
    tipo: categoriaNombre,
    nombre: "Ejemplo Sony FX3",
    specs: specLabels.map((label) => ({ label, value: `<${label}>` })),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Plantilla de nombre — {categoriaNombre}</DialogTitle>
          <DialogDescription>
            Define cómo se arma el nombre público de los equipos en esta categoría. Si está vacío,
            se usa el nombre interno del equipo como fallback.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground font-mono uppercase tracking-wider">
              Plantilla
            </label>
            <Input
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Cámara {marca} {modelo} {spec:Montura}"
              className="font-mono text-sm"
            />
          </div>

          <div>
            <div className="text-xs text-muted-foreground mb-1.5">
              Click para insertar un placeholder:
            </div>
            <div className="flex flex-wrap gap-1.5">
              {(["{marca}", "{modelo}", "{tipo}", "{nombre}"] as const).map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => insertPlaceholder(p)}
                  className="rounded-md border hairline px-2 py-0.5 font-mono text-[11px] text-ink hover:bg-amber-soft transition"
                >
                  {p}
                </button>
              ))}
              {specLabels.map((label) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => insertPlaceholder(`{spec:${label}}`)}
                  className="rounded-md border hairline border-amber/40 bg-amber-soft/30 px-2 py-0.5 font-mono text-[11px] text-ink hover:bg-amber-soft transition"
                >
                  {`{spec:${label}}`}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="text-xs text-muted-foreground mb-1">Vista previa</div>
            <div className="rounded-md border hairline bg-muted/30 px-3 py-2 text-sm text-ink">
              {preview ?? (
                <span className="italic text-muted-foreground">
                  Sin template → usa nombre interno del equipo
                </span>
              )}
            </div>
            <p className="text-[10px] text-muted-foreground mt-1">
              Ejemplo simulado con marca "Sony", modelo "FX3". Los valores de specs muestran su
              label entre &lt;…&gt;.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button onClick={() => saveMut.mutate(value)} disabled={saveMut.isPending}>
            Guardar plantilla
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
