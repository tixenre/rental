import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

import { adminApi, type Cliente, type ClienteInput } from "@/lib/admin/api";

type Props = {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  cliente?: Cliente | null;
  onSaved?: (c: Cliente) => void;
};

const PERFILES = [
  { value: "consumidor_final", label: "Consumidor final" },
  { value: "monotributo", label: "Monotributo" },
  { value: "responsable_inscripto", label: "Responsable inscripto" },
  { value: "exento", label: "Exento" },
];

export function ClienteFormDialog({ open, onOpenChange, cliente, onSaved }: Props) {
  const qc = useQueryClient();
  const editing = !!cliente?.id;

  const form = useForm<ClienteInput>({
    defaultValues: {
      nombre: "", apellido: "", telefono: "", email: "",
      direccion: "", cuit: "", descuento: 0, perfil_impuestos: "consumidor_final",
    },
  });

  useEffect(() => {
    if (open) {
      form.reset({
        nombre: cliente?.nombre ?? "",
        apellido: cliente?.apellido ?? "",
        telefono: cliente?.telefono ?? "",
        email: cliente?.email ?? "",
        direccion: cliente?.direccion ?? "",
        cuit: cliente?.cuit ?? "",
        descuento: cliente?.descuento ?? 0,
        perfil_impuestos: cliente?.perfil_impuestos ?? "consumidor_final",
      });
    }
  }, [open, cliente, form]);

  const mut = useMutation({
    mutationFn: async (data: ClienteInput) =>
      editing ? adminApi.updateCliente(cliente!.id, data) : adminApi.createCliente(data),
    onSuccess: (c) => {
      toast.success(editing ? "Cliente actualizado" : "Cliente creado");
      qc.invalidateQueries({ queryKey: ["admin", "clientes"] });
      onSaved?.(c);
      onOpenChange(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const submit = form.handleSubmit((data) => {
    if (!data.nombre.trim()) {
      toast.error("Nombre requerido");
      return;
    }
    mut.mutate({
      ...data,
      descuento: Number(data.descuento) || 0,
    });
  });

  const perfil = form.watch("perfil_impuestos");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{editing ? "Editar cliente" : "Nuevo cliente"}</DialogTitle>
          <DialogDescription>
            Datos de contacto y condiciones fiscales.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label>Nombre *</Label>
            <Input {...form.register("nombre", { required: true })} />
          </div>
          <div className="space-y-1">
            <Label>Apellido</Label>
            <Input {...form.register("apellido")} />
          </div>
          <div className="space-y-1">
            <Label>Teléfono</Label>
            <Input {...form.register("telefono")} />
          </div>
          <div className="space-y-1">
            <Label>Email</Label>
            <Input type="email" {...form.register("email")} />
          </div>
          <div className="space-y-1 col-span-2">
            <Label>Dirección</Label>
            <Input {...form.register("direccion")} />
          </div>
          <div className="space-y-1">
            <Label>CUIT / DNI</Label>
            <Input {...form.register("cuit")} />
          </div>
          <div className="space-y-1">
            <Label>Descuento %</Label>
            <Input type="number" step="0.01" {...form.register("descuento", { valueAsNumber: true })} />
          </div>
          <div className="space-y-1 col-span-2">
            <Label>Perfil de impuestos</Label>
            <Select
              value={perfil ?? "consumidor_final"}
              onValueChange={(v) => form.setValue("perfil_impuestos", v)}
            >
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {PERFILES.map((p) => (
                  <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <DialogFooter className="col-span-2 mt-2">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button type="submit" disabled={mut.isPending}>
              {mut.isPending ? "Guardando…" : editing ? "Guardar cambios" : "Crear cliente"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
