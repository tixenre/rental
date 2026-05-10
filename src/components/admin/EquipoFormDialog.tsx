import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { Equipo, EquipoInput } from "@/lib/admin/api";

const schema = z.object({
  nombre: z.string().min(1, "Nombre requerido"),
  marca: z.string().optional().nullable(),
  modelo: z.string().optional().nullable(),
  cantidad: z.coerce.number().int().min(0).default(1),
  precio_jornada: z.coerce.number().int().min(0).optional().nullable(),
  precio_usd: z.coerce.number().min(0).optional().nullable(),
  serie: z.string().optional().nullable(),
  dueno: z.string().optional().nullable(),
  estado: z.enum(["operativo", "en_mantenimiento", "fuera_servicio"]).default("operativo"),
  visible_catalogo: z.boolean().default(true),
  etiquetas_csv: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

export function EquipoFormDialog({
  open,
  onOpenChange,
  initial,
  onSubmit,
  saving,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  initial?: Equipo | null;
  onSubmit: (data: EquipoInput, etiquetas: string[]) => void | Promise<void>;
  saving?: boolean;
}) {
  const isEdit = !!initial;
  const form = useForm<FormValues>({
    resolver: zodResolver(schema) as any,
    defaultValues: {
      nombre: initial?.nombre ?? "",
      marca: initial?.marca ?? "",
      modelo: initial?.modelo ?? "",
      cantidad: initial?.cantidad ?? 1,
      precio_jornada: initial?.precio_jornada ?? undefined,
      precio_usd: initial?.precio_usd ?? undefined,
      serie: initial?.serie ?? "",
      dueno: initial?.dueno ?? "Rambla",
      estado: (initial?.estado as FormValues["estado"]) ?? "operativo",
      visible_catalogo: initial ? Boolean(initial.visible_catalogo) : true,
      etiquetas_csv: initial?.etiquetas?.join(", ") ?? "",
    },
  });

  const submit = form.handleSubmit(async (values) => {
    const etiquetas = (values.etiquetas_csv ?? "")
      .split(",")
      .map((s: string) => s.trim())
      .filter(Boolean);
    const { etiquetas_csv: _omit, visible_catalogo, ...rest } = values;
    void _omit;
    const payload: EquipoInput = {
      nombre: rest.nombre,
      cantidad: rest.cantidad,
      estado: rest.estado,
      marca: rest.marca || null,
      modelo: rest.modelo || null,
      serie: rest.serie || null,
      dueno: rest.dueno || null,
      precio_jornada: rest.precio_jornada ?? null,
      precio_usd: rest.precio_usd ?? null,
      visible_catalogo: visible_catalogo ? 1 : 0,
    };
    await onSubmit(payload, etiquetas);
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">
            {isEdit ? "Editar equipo" : "Nuevo equipo"}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="space-y-4">
          <Field label="Nombre" error={form.formState.errors.nombre?.message}>
            <Input {...form.register("nombre")} />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Marca">
              <Input {...form.register("marca")} />
            </Field>
            <Field label="Modelo">
              <Input {...form.register("modelo")} />
            </Field>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <Field label="Cantidad">
              <Input type="number" min={0} {...form.register("cantidad")} />
            </Field>
            <Field label="Precio/día (ARS)">
              <Input type="number" min={0} {...form.register("precio_jornada")} />
            </Field>
            <Field label="Valor (USD)">
              <Input type="number" min={0} step="0.01" {...form.register("precio_usd")} />
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Serie">
              <Input {...form.register("serie")} />
            </Field>
            <Field label="Dueño">
              <Input {...form.register("dueno")} />
            </Field>
          </div>

          <Field label="Etiquetas (separadas por coma — la primera es la categoría principal)">
            <Input
              placeholder="Ej: cámara, dslr, canon"
              {...form.register("etiquetas_csv")}
            />
          </Field>

          <div className="grid grid-cols-2 gap-3 items-end">
            <Field label="Estado">
              <Select
                value={form.watch("estado")}
                onValueChange={(v) => form.setValue("estado", v as FormValues["estado"])}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="operativo">Operativo</SelectItem>
                  <SelectItem value="en_mantenimiento">En mantenimiento</SelectItem>
                  <SelectItem value="fuera_servicio">Fuera de servicio</SelectItem>
                </SelectContent>
              </Select>
            </Field>
            <label className="flex items-center justify-between rounded-md border hairline px-3 py-2 text-sm">
              <span>Visible en catálogo</span>
              <Switch
                checked={form.watch("visible_catalogo")}
                onCheckedChange={(v) => form.setValue("visible_catalogo", v)}
              />
            </label>
          </div>

          <DialogFooter className="gap-2">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Guardando…" : isEdit ? "Guardar cambios" : "Crear equipo"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </Label>
      {children}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
