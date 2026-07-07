import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { Spinner } from "@/design-system/ui/spinner";
import { EmptyState } from "@/design-system/composites/EmptyState";
import { ListSkeleton } from "@/components/admin/skeletons";
import { useConfirm } from "@/components/admin/useConfirm";
import { cn } from "@/lib/utils";
import { formatARS } from "@/lib/format";
import { estudioAdminApi, type EstudioSlotFijo } from "@/lib/admin/api";
import { Field, Section } from "./shared";

const DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

const slotSchema = z
  .object({
    cliente: z.string().min(1, "Requerido"),
    dia_semana: z.coerce.number().int().min(0).max(6),
    hora_desde: z.coerce.number().int().min(0).max(24),
    hora_hasta: z.coerce.number().int().min(0).max(24),
    valor_mensual: z.coerce.number().int().min(0),
    mes_desde: z.string().regex(/^\d{4}-(0[1-9]|1[0-2])$/, "YYYY-MM"),
    mes_hasta: z.string().regex(/^\d{4}-(0[1-9]|1[0-2])$/, "YYYY-MM"),
    activo: z.boolean(),
  })
  .refine((v) => v.hora_desde < v.hora_hasta, {
    message: "El horario de cierre debe ser posterior",
    path: ["hora_hasta"],
  })
  .refine((v) => v.mes_desde <= v.mes_hasta, {
    message: "El mes hasta no puede ser anterior",
    path: ["mes_hasta"],
  });

type SlotFormValues = z.infer<typeof slotSchema>;

function pad2(n: number) {
  return n.toString().padStart(2, "0");
}

export function SlotsSection() {
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [editando, setEditando] = useState<EstudioSlotFijo | null>(null);
  const [creando, setCreando] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "estudio", "slots"],
    queryFn: () => estudioAdminApi.listSlots(),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "estudio", "slots"] });
    setEditando(null);
    setCreando(false);
  };

  const delMut = useMutation({
    mutationFn: (id: number) => estudioAdminApi.deleteSlot(id),
    onSuccess: () => {
      toast.success("Slot eliminado");
      invalidate();
    },
    onError: (e) => toast.error("Error al eliminar", { description: (e as Error).message }),
  });

  const slots = data?.slots ?? [];

  return (
    <Section title="Slots fijos (usos recurrentes mensuales)">
      <p className="-mt-2 mb-3 text-sm text-muted-foreground">
        Bloquean su franja para el público y generan un pedido por mes (estadísticas + cobros).
      </p>

      {isLoading ? (
        <ListSkeleton rows={3} />
      ) : (
        <div className="space-y-2">
          {slots.length === 0 && (
            <EmptyState
              icon={<Plus className="h-6 w-6" />}
              title="Sin slots fijos"
              sub="Creá un slot recurrente con el botón de abajo."
            />
          )}
          {slots.map((s) => (
            <div
              key={s.id}
              className={cn(
                "flex flex-wrap items-center justify-between gap-2 rounded-lg border hairline px-3 py-2 text-sm",
                !s.activo && "opacity-60",
              )}
            >
              <div>
                <span className="font-semibold">{s.cliente}</span>{" "}
                <span className="text-muted-foreground">
                  · {DIAS_SEMANA[s.dia_semana]} {pad2(s.hora_desde)}–{pad2(s.hora_hasta)}h ·{" "}
                  {formatARS(s.valor_mensual)}/mes · {s.mes_desde} → {s.mes_hasta}
                  {!s.activo && " · inactivo"}
                </span>
              </div>
              <div className="flex gap-1">
                <Button variant="outline" size="sm" onClick={() => setEditando(s)}>
                  Editar
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={async () => {
                    if (
                      await confirm({
                        title: `¿Borrar el slot de ${s.cliente}?`,
                        description: "Se eliminan los pedidos futuros impagos.",
                        danger: true,
                        confirmLabel: "Eliminar",
                      })
                    )
                      delMut.mutate(s.id);
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {creando || editando ? (
        <SlotForm slot={editando} onDone={invalidate} onCancel={() => invalidate()} />
      ) : (
        <Button variant="outline" className="mt-3" onClick={() => setCreando(true)}>
          <Plus className="mr-2 h-4 w-4" /> Nuevo slot
        </Button>
      )}
    </Section>
  );
}

function SlotForm({
  slot,
  onDone,
  onCancel,
}: {
  slot: EstudioSlotFijo | null;
  onDone: () => void;
  onCancel: () => void;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SlotFormValues>({
    resolver: zodResolver(slotSchema),
    defaultValues: slot
      ? {
          cliente: slot.cliente,
          dia_semana: slot.dia_semana,
          hora_desde: slot.hora_desde,
          hora_hasta: slot.hora_hasta,
          valor_mensual: slot.valor_mensual,
          mes_desde: slot.mes_desde,
          mes_hasta: slot.mes_hasta,
          activo: slot.activo,
        }
      : {
          cliente: "",
          dia_semana: 2,
          hora_desde: 8,
          hora_hasta: 20,
          valor_mensual: 0,
          mes_desde: "",
          mes_hasta: "",
          activo: true,
        },
  });

  const mutation = useMutation({
    mutationFn: (v: SlotFormValues) =>
      slot ? estudioAdminApi.updateSlot(slot.id, v) : estudioAdminApi.createSlot(v),
    onSuccess: () => {
      toast.success(slot ? "Slot actualizado" : "Slot creado");
      onDone();
    },
    onError: (e) => toast.error("Error al guardar", { description: (e as Error).message }),
  });

  return (
    <form
      onSubmit={handleSubmit((v) => mutation.mutate(v))}
      className="mt-3 space-y-3 rounded-lg border hairline p-4"
    >
      <Field label="Cliente" error={errors.cliente?.message}>
        <Input {...register("cliente")} placeholder="Ej. Filmar" />
      </Field>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Día" error={errors.dia_semana?.message}>
          <select
            {...register("dia_semana")}
            className="h-10 w-full rounded-md border hairline bg-background px-2 text-sm"
          >
            {DIAS_SEMANA.map((d, i) => (
              <option key={d} value={i}>
                {d}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Desde (h)" error={errors.hora_desde?.message}>
          <Input type="number" min={0} max={24} {...register("hora_desde")} />
        </Field>
        <Field label="Hasta (h)" error={errors.hora_hasta?.message}>
          <Input type="number" min={0} max={24} {...register("hora_hasta")} />
        </Field>
        <Field label="Valor mensual ($)" error={errors.valor_mensual?.message}>
          <Input type="number" min={0} {...register("valor_mensual")} />
        </Field>
        <Field label="Mes desde" error={errors.mes_desde?.message}>
          <Input type="month" {...register("mes_desde")} />
        </Field>
        <Field label="Mes hasta" error={errors.mes_hasta?.message}>
          <Input type="month" {...register("mes_hasta")} />
        </Field>
      </div>
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        {/* eslint-disable-next-line no-restricted-syntax -- checkbox nativo: el DS Checkbox es Radix (otra API) */}
        <input type="checkbox" {...register("activo")} className="h-4 w-4 rounded" />
        Activo
      </label>
      <div className="flex gap-2">
        <Button type="submit" disabled={mutation.isPending} size="sm">
          {mutation.isPending ? (
            <Spinner size="sm" className="mr-2" />
          ) : (
            <Save className="mr-2 h-4 w-4" />
          )}
          Guardar
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={onCancel}>
          Cancelar
        </Button>
      </div>
    </form>
  );
}
