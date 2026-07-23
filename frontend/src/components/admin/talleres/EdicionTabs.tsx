import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { talleresAdminApi } from "@/lib/admin/api/talleres";
import type { ClaseBody, EdicionAdmin, ModalidadPagoBody } from "@/lib/admin/api/types";
import { Button } from "@/design-system/ui/button";
import { IconButton } from "@/design-system/ui/icon-button";
import { Input } from "@/design-system/ui/input";
import { Spinner } from "@/design-system/ui/spinner";
import { TallerCalendario } from "@/components/talleres/TallerCalendario";
import { ClasesAsistente } from "./ClasesAsistente";
import { updateEdicionInCache } from "./cache";

export function ClasesSection({ edicion }: { edicion: EdicionAdmin }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [tipo, setTipo] = useState(edicion.tipo_taller || "intensivo");
  const [clases, setClases] = useState<ClaseBody[]>(edicion.clases ?? []);

  useEffect(() => {
    setTipo(edicion.tipo_taller || "intensivo");
    setClases(edicion.clases ?? []);
  }, [edicion.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const mut = useMutation({
    mutationFn: (body: { tipo_taller: string; clases: ClaseBody[] }) =>
      talleresAdminApi.updateEdicionClases(edicion.id, body),
    onSuccess: (updated) => {
      toast.success("Clases guardadas");
      setEditing(false);
      updateEdicionInCache(qc, updated);
    },
    onError: (e) => toast.error((e as Error).message),
  });

  function handleSave() {
    if (clases.length === 0) {
      toast.error("Agregá al menos una clase");
      return;
    }
    mut.mutate({ tipo_taller: tipo, clases });
  }

  function handleCancel() {
    setTipo(edicion.tipo_taller || "intensivo");
    setClases(edicion.clases ?? []);
    setEditing(false);
  }

  return !editing ? (
    <div className="flex flex-col gap-4">
      {edicion.clases && edicion.clases.length > 0 ? (
        <TallerCalendario sesiones={edicion.clases} horario={edicion.horario} />
      ) : (
        <p className="text-sm text-muted-foreground italic">Sin clases cargadas.</p>
      )}
      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
          Editar clases
        </Button>
      </div>
    </div>
  ) : (
    <div className="flex flex-col gap-5">
      <ClasesAsistente tipo={tipo} onTipoChange={setTipo} clases={clases} onChange={setClases} />
      {clases.length > 0 && (
        <div className="pointer-events-none select-none">
          <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground mb-3">
            Preview
          </p>
          <TallerCalendario sesiones={clases} />
        </div>
      )}
      <div className="flex gap-2 justify-end pt-2">
        <Button variant="ghost" size="sm" onClick={handleCancel}>
          Cancelar
        </Button>
        <Button onClick={handleSave} disabled={mut.isPending} size="sm" className="gap-2">
          {mut.isPending ? <Spinner size="xs" /> : <Save className="h-3.5 w-3.5" />}
          Guardar clases
        </Button>
      </div>
    </div>
  );
}

export function PreciosSection({ edicion }: { edicion: EdicionAdmin }) {
  const qc = useQueryClient();
  const [precioTotal, setPrecioTotal] = useState(String(edicion.precio_total));
  const [precioSena, setPrecioSena] = useState(String(edicion.precio_sena));
  const [cuposTotal, setCuposTotal] = useState(String(edicion.cupos_total));

  useEffect(() => {
    setPrecioTotal(String(edicion.precio_total));
    setPrecioSena(String(edicion.precio_sena));
    setCuposTotal(String(edicion.cupos_total));
  }, [edicion.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const mut = useMutation({
    mutationFn: (body: { precio_total: number; precio_sena: number; cupos_total: number }) =>
      talleresAdminApi.updateEdicion(edicion.id, body),
    onSuccess: (updated) => {
      toast.success("Precios actualizados");
      updateEdicionInCache(qc, updated);
    },
    onError: (e) => toast.error((e as Error).message),
  });

  function handleSave() {
    const total = parseInt(precioTotal, 10);
    const sena = parseInt(precioSena, 10);
    const cupos = parseInt(cuposTotal, 10);
    if (isNaN(total) || isNaN(sena) || isNaN(cupos) || cupos < 1) {
      toast.error("Ingresá números válidos");
      return;
    }
    if (cupos < edicion.cupos_confirmados) {
      toast.error(`No podés bajar cupos a ${cupos}: hay ${edicion.cupos_confirmados} confirmados`);
      return;
    }
    mut.mutate({ precio_total: total, precio_sena: sena, cupos_total: cupos });
  }

  return (
    <div className="flex flex-col gap-4">
      {edicion.cupos_confirmados >= edicion.cupos_total && (
        <div className="rounded-lg bg-amber/10 border border-amber/30 px-4 py-3 text-sm text-ink">
          ⚠ Edición completa — {edicion.cupos_confirmados}/{edicion.cupos_total} cupos ocupados
        </div>
      )}
      <div className="grid sm:grid-cols-3 gap-4">
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
            Precio total (ARS)
          </label>
          <Input
            type="number"
            min={0}
            value={precioTotal}
            onChange={(e) => setPrecioTotal(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
            Seña (ARS)
          </label>
          <Input
            type="number"
            min={0}
            value={precioSena}
            onChange={(e) => setPrecioSena(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
            Cupos totales
          </label>
          <Input
            type="number"
            min={1}
            value={cuposTotal}
            onChange={(e) => setCuposTotal(e.target.value)}
          />
        </div>
      </div>
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={mut.isPending} className="gap-2">
          {mut.isPending ? <Spinner size="sm" /> : <Save className="h-4 w-4" />}
          Guardar
        </Button>
      </div>
    </div>
  );
}

export function PagosSection({ edicion }: { edicion: EdicionAdmin }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    pago_alias: edicion.pago_alias ?? "",
    pago_cbu: edicion.pago_cbu ?? "",
    pago_banco: edicion.pago_banco ?? "",
    direccion: edicion.direccion ?? "",
  });

  useEffect(() => {
    setForm({
      pago_alias: edicion.pago_alias ?? "",
      pago_cbu: edicion.pago_cbu ?? "",
      pago_banco: edicion.pago_banco ?? "",
      direccion: edicion.direccion ?? "",
    });
  }, [edicion.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const mut = useMutation({
    mutationFn: (body: typeof form) => talleresAdminApi.updateEdicion(edicion.id, body),
    onSuccess: (updated) => {
      toast.success("Guardado");
      updateEdicionInCache(qc, updated);
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const tf = (label: string, key: keyof typeof form) => (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
        {label}
      </label>
      <Input
        value={form[key]}
        onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
      />
    </div>
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="grid sm:grid-cols-2 gap-4">{tf("Dirección", "direccion")}</div>
      <div className="grid sm:grid-cols-3 gap-4">
        {tf("Alias de pago", "pago_alias")}
        {tf("CBU", "pago_cbu")}
        {tf("Banco", "pago_banco")}
      </div>
      <div className="flex justify-end">
        <Button onClick={() => mut.mutate(form)} disabled={mut.isPending} className="gap-2">
          {mut.isPending ? <Spinner size="sm" /> : <Save className="h-4 w-4" />}
          Guardar
        </Button>
      </div>
    </div>
  );
}

// F4a: modalidades de pago — sin motor de descuentos, el admin carga el
// monto final de cada opción a mano ("3 cuotas", "un pago con descuento",
// "ex alumnos"); los "%" de ahorro son texto libre en `nota`. Sin ninguna
// configurada, el público ve 1 sola opción sintética ("Pago total").
type ModalidadForm = {
  id?: number | null;
  codigo: string;
  label: string;
  nota: string;
  monto_total: string;
};

function toModalidadForm(m: ModalidadPagoBody): ModalidadForm {
  return {
    id: m.id,
    codigo: m.codigo,
    label: m.label,
    nota: m.nota ?? "",
    monto_total: String(m.monto_total),
  };
}

export function ModalidadesSection({ edicion }: { edicion: EdicionAdmin }) {
  const qc = useQueryClient();
  const [rows, setRows] = useState<ModalidadForm[]>(
    (edicion.modalidades ?? []).map(toModalidadForm),
  );

  useEffect(() => {
    setRows((edicion.modalidades ?? []).map(toModalidadForm));
  }, [edicion.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const mut = useMutation({
    mutationFn: (modalidades: ModalidadPagoBody[]) =>
      talleresAdminApi.updateEdicion(edicion.id, { modalidades }),
    onSuccess: (updated) => {
      toast.success("Modalidades guardadas");
      updateEdicionInCache(qc, updated);
    },
    onError: (e) => toast.error((e as Error).message),
  });

  function agregar() {
    setRows((r) => [
      ...r,
      { codigo: "", label: "", nota: "", monto_total: String(edicion.precio_total || "") },
    ]);
  }

  function quitar(idx: number) {
    setRows((r) => r.filter((_, i) => i !== idx));
  }

  function actualizar(idx: number, patch: Partial<ModalidadForm>) {
    setRows((r) => r.map((row, i) => (i === idx ? { ...row, ...patch } : row)));
  }

  function handleSave() {
    const parsed: ModalidadPagoBody[] = [];
    for (const row of rows) {
      const codigo = row.codigo.trim();
      const label = row.label.trim();
      const monto = parseInt(row.monto_total, 10);
      if (!codigo || !label) {
        toast.error("Cada modalidad necesita código y label");
        return;
      }
      if (isNaN(monto) || monto <= 0) {
        toast.error(`La modalidad "${label}" necesita un monto válido`);
        return;
      }
      parsed.push({ id: row.id, codigo, label, nota: row.nota.trim(), monto_total: monto });
    }
    const codigos = parsed.map((m) => m.codigo);
    if (new Set(codigos).size !== codigos.length) {
      toast.error("Hay códigos de modalidad repetidos");
      return;
    }
    mut.mutate(parsed);
  }

  return (
    <div className="flex flex-col gap-4">
      {rows.length === 0 && (
        <p className="text-sm text-muted-foreground italic">
          Sin modalidades configuradas — el público ve 1 sola opción ("Pago total", el precio de
          arriba). Agregá modalidades si querés ofrecer cuotas o descuentos por forma de pago.
        </p>
      )}
      {rows.map((row, idx) => (
        <div
          key={row.id ?? `nueva-${idx}`}
          className="grid sm:grid-cols-[1fr_1fr_1fr_140px_auto] gap-2 items-end"
        >
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
              Código
            </label>
            <Input
              value={row.codigo}
              onChange={(e) => actualizar(idx, { codigo: e.target.value })}
              placeholder="3-cuotas"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
              Label
            </label>
            <Input
              value={row.label}
              onChange={(e) => actualizar(idx, { label: e.target.value })}
              placeholder="3 cuotas"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
              Nota
            </label>
            <Input
              value={row.nota}
              onChange={(e) => actualizar(idx, { nota: e.target.value })}
              placeholder="10% off"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
              Monto (ARS)
            </label>
            <Input
              type="number"
              min={1}
              value={row.monto_total}
              onChange={(e) => actualizar(idx, { monto_total: e.target.value })}
            />
          </div>
          <IconButton
            aria-label="Quitar modalidad"
            size="sm"
            onClick={() => quitar(idx)}
            className="text-muted-foreground hover:text-destructive mb-0.5"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </IconButton>
        </div>
      ))}
      <div className="flex justify-between pt-1">
        <Button variant="outline" size="sm" onClick={agregar} className="gap-1.5">
          <Plus className="h-3.5 w-3.5" />
          Agregar modalidad
        </Button>
        <Button onClick={handleSave} disabled={mut.isPending} className="gap-2">
          {mut.isPending ? <Spinner size="sm" /> : <Save className="h-4 w-4" />}
          Guardar modalidades
        </Button>
      </div>
    </div>
  );
}
