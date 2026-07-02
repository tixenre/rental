import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Lock, Search } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/design-system/ui/dialog";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { Label } from "@/design-system/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";

import { adminApi, type Cliente, type ClienteInput } from "@/lib/admin/api";
import { usePadronLookup } from "@/lib/admin/usePadronLookup";

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
      nombre: "",
      apellido: "",
      telefono: "",
      email: "",
      direccion: "",
      cuit: "",
      descuento: 0,
      perfil_impuestos: "consumidor_final",
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
  const cuit = form.watch("cuit");

  const padron = usePadronLookup((datos) => {
    // Persona física (AFIP da nombre/apellido separados) → cada campo el
    // suyo; empresa (solo razón social) → todo a "nombre", sin inventar un
    // apellido que no existe.
    if (!form.getValues("nombre").trim()) {
      if (datos.nombre || datos.apellido) {
        if (datos.nombre) form.setValue("nombre", datos.nombre);
        if (datos.apellido) form.setValue("apellido", datos.apellido);
      } else if (datos.razon_social) {
        form.setValue("nombre", datos.razon_social);
      }
    }
    if (datos.domicilio) form.setValue("direccion", datos.domicilio);
    if (datos.condicion_iva) form.setValue("perfil_impuestos", datos.condicion_iva);
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{editing ? "Editar cliente" : "Nuevo cliente"}</DialogTitle>
          <DialogDescription>Datos de contacto y condiciones fiscales.</DialogDescription>
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
            <div className="flex gap-1.5">
              <Input {...form.register("cuit")} />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                disabled={padron.buscando || (cuit ?? "").replace(/\D/g, "").length !== 11}
                onClick={() => padron.buscar(cuit ?? "")}
                title="Autocompletar nombre/dirección/perfil fiscal desde ARCA"
                className="shrink-0"
              >
                <Search className="h-4 w-4" />
              </Button>
            </div>
            {padron.motivo && (
              <p className="text-xs text-destructive">
                ⚠️ No se pudo consultar ARCA: {padron.motivo}
              </p>
            )}
            {!padron.motivo && padron.noEncontrado && (
              <p className="text-xs text-muted-foreground">
                ARCA no tiene datos para este CUIT — cargá a mano.
              </p>
            )}
            {padron.inactivo && (
              <p className="text-xs text-destructive">⚠️ Este CUIT figura inactivo en AFIP.</p>
            )}
          </div>
          <div className="space-y-1">
            <Label>Descuento %</Label>
            <Input
              type="number"
              step="0.01"
              {...form.register("descuento", { valueAsNumber: true })}
            />
          </div>
          <div className="space-y-1 col-span-2">
            <Label>Perfil de impuestos</Label>
            <Select
              value={perfil ?? "consumidor_final"}
              onValueChange={(v) => form.setValue("perfil_impuestos", v)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PERFILES.map((p) => (
                  <SelectItem key={p.value} value={p.value}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Bloque de datos RENAPER — solo lectura cuando el cliente está verificado */}
          {editing && cliente?.dni_validado_at && (
            <div className="col-span-2 rounded-lg border border-verde/30 bg-verde/5 px-3 py-2.5 space-y-2">
              <div className="flex items-center gap-1.5 text-xs text-verde-ink font-semibold">
                <Lock className="h-3.5 w-3.5 shrink-0" />
                Datos verificados por RENAPER — solo lectura
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                {[
                  {
                    label: "Nombre legal",
                    value:
                      cliente.nombre_completo_renaper ||
                      [cliente.nombre_renaper, cliente.apellido_renaper]
                        .filter(Boolean)
                        .join(" ") ||
                      null,
                  },
                  { label: "DNI", value: cliente.dni },
                  { label: "CUIL", value: cliente.cuil },
                  { label: "Fecha de nacimiento", value: cliente.fecha_nacimiento_renaper },
                  {
                    label: "Género",
                    value:
                      cliente.genero_renaper === "M"
                        ? "Masculino"
                        : cliente.genero_renaper === "F"
                          ? "Femenino"
                          : cliente.genero_renaper,
                  },
                  { label: "Nacionalidad", value: cliente.nacionalidad_renaper },
                  { label: "Lugar de nacimiento", value: cliente.lugar_nacimiento_renaper },
                  { label: "Estado civil", value: cliente.estado_civil_renaper },
                  { label: "Tipo de documento", value: cliente.tipo_documento_renaper },
                  { label: "Emisión", value: cliente.emision_documento_renaper },
                  { label: "Vencimiento", value: cliente.vencimiento_documento_renaper },
                  { label: "Domicilio RENAPER", value: cliente.direccion_renaper, wide: true },
                ]
                  .filter((f) => f.value)
                  .map((f) => (
                    <div
                      key={f.label}
                      className={
                        (f as { wide?: boolean }).wide ? "col-span-2 space-y-1" : "space-y-1"
                      }
                    >
                      <div className="t-eyebrow">{f.label}</div>
                      <div className="rounded-md border border-border/50 bg-muted/40 px-2.5 py-1.5 text-xs text-ink font-mono select-all">
                        {f.value}
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}

          <DialogFooter className="col-span-2 mt-2">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={mut.isPending}>
              {mut.isPending ? "Guardando…" : editing ? "Guardar cambios" : "Crear cliente"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
