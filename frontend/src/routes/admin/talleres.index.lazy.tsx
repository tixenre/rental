import { useEffect, useRef, useState } from "react";
import { createLazyFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { QueryClient } from "@tanstack/react-query";
import {
  Users,
  ExternalLink,
  Clock,
  CheckCircle2,
  Upload,
  Save,
  Plus,
  Trash2,
  Download,
  Bell,
  EyeOff,
  Eye,
} from "lucide-react";
import { toast } from "sonner";

import { authedFetch, authedJson } from "@/lib/authedFetch";
import { useDocumentTitle } from "@/lib/use-document-title";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { Pill, type PillTone } from "@/design-system/kit/Pill";
import { Spinner } from "@/design-system/ui/spinner";
import { Switch } from "@/design-system/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from "@/design-system/ui/dialog";
import { TallerCalendario } from "@/components/talleres/TallerCalendario";
import { useConfirm } from "@/components/admin/useConfirm";
import { AdminTable, type Column } from "@/components/admin/AdminTable";

export const Route = createLazyFileRoute("/admin/talleres/")({
  component: TalleresAdminPage,
});

// ── Types ────────────────────────────────────────────────────────────────────

type ClaseBody = { fecha: string; hora_inicio: number; hora_fin: number };

type EdicionAdmin = {
  id: number;
  taller_id: number;
  numero_edicion: number;
  slug: string;
  tipo_taller: string;
  fecha_inicio: string;
  fecha_fin: string;
  horario: string;
  cupos_total: number;
  cupos_confirmados: number;
  cupos_disponibles: number;
  precio_total: number;
  precio_sena: number;
  pago_alias: string;
  pago_cbu: string;
  pago_banco: string;
  direccion: string;
  activo: boolean;
  frozen_at: string | null;
  clases: ClaseBody[];
};

type TallerConcepto = {
  id: number;
  slug_base: string;
  nombre: string;
  subtitulo: string;
  instructor_nombre: string;
  instructor_bio: string;
  instructor_proyectos: string;
  descripcion: string;
  publico_objetivo: string;
  programa_teorica: string[];
  programa_practica: string[];
  instructor_foto_url: string;
  instructor_media_id: number | null;
  notif_email: string;
  ediciones: EdicionAdmin[];
};

type Inscripcion = {
  id: number;
  nombre: string;
  email: string;
  telefono: string;
  experiencia: string | null;
  comprobante_url: string | null;
  en_lista_espera: boolean;
  estado: string | null;
  edicion_id: number | null;
  numero_edicion: number | null;
  edicion_slug: string | null;
  created_at: string | null;
};

// ── Cache helpers ─────────────────────────────────────────────────────────────

function updateEdicionInCache(qc: QueryClient, updated: EdicionAdmin) {
  qc.setQueryData(["admin", "talleres"], (prev: TallerConcepto[] | undefined) =>
    prev?.map((c) => ({
      ...c,
      ediciones: c.ediciones.map((e) => (e.id === updated.id ? updated : e)),
    })),
  );
}

function updateConceptoInCache(qc: QueryClient, updated: TallerConcepto) {
  qc.setQueryData(["admin", "talleres"], (prev: TallerConcepto[] | undefined) =>
    prev?.map((c) => (c.id === updated.id ? updated : c)),
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

function badgeEstadoEdicion(edicion: EdicionAdmin): { label: string; tone: PillTone } {
  const today = new Date().toISOString().slice(0, 10);
  if (!edicion.activo) return { label: "INACTIVA", tone: "neutral" };
  if (edicion.frozen_at) return { label: "CONGELADA", tone: "neutral" };
  if (edicion.fecha_inicio > today) return { label: "PRÓXIMAMENTE", tone: "warning" };
  if (edicion.fecha_fin >= today) return { label: "EN CURSO", tone: "success" };
  return { label: "FINALIZADA", tone: "neutral" };
}

function CuposPill({ confirmados, total }: { confirmados: number; total: number }) {
  const ratio = total > 0 ? confirmados / total : 0;
  const tone: PillTone = ratio >= 1 ? "danger" : ratio >= 0.8 ? "warning" : "success";
  return (
    <Pill tone={tone} className="font-mono font-semibold tabular-nums">
      {confirmados}/{total}
    </Pill>
  );
}

function generarClasesSemanales(
  diaSemana: number,
  mesDesde: string,
  mesHasta: string,
  horaInicio: number,
  horaFin: number,
): ClaseBody[] {
  const [yD, mD] = mesDesde.split("-").map(Number);
  const [yH, mH] = mesHasta.split("-").map(Number);
  const end = new Date(yH, mH, 0);
  const jsDay = (diaSemana + 1) % 7;
  const cur = new Date(yD, mD - 1, 1);
  while (cur.getDay() !== jsDay) cur.setDate(cur.getDate() + 1);
  const result: ClaseBody[] = [];
  while (cur <= end) {
    result.push({
      fecha: cur.toISOString().slice(0, 10),
      hora_inicio: horaInicio,
      hora_fin: horaFin,
    });
    cur.setDate(cur.getDate() + 7);
  }
  return result;
}

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("es-AR", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtDay(iso: string) {
  return new Date(iso + "T12:00:00").toLocaleDateString("es-AR", {
    day: "numeric",
    month: "short",
  });
}

// ── HoraSelect ───────────────────────────────────────────────────────────────

function HoraSelect({
  value,
  onChange,
  min = 0,
  max = 24,
  className,
}: {
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  className?: string;
}) {
  const hours = Array.from({ length: max - min + 1 }, (_, i) => min + i);
  return (
    <Select value={String(value)} onValueChange={(v) => onChange(Number(v))}>
      <SelectTrigger className={className ?? "w-[90px]"}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {hours.map((h) => (
          <SelectItem key={h} value={String(h)}>
            {String(h).padStart(2, "0")}:00
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

// ── ClasesAsistente ───────────────────────────────────────────────────────────

function ClasesAsistente({
  tipo,
  onTipoChange,
  clases,
  onChange,
}: {
  tipo: string;
  onTipoChange: (t: string) => void;
  clases: ClaseBody[];
  onChange: (s: ClaseBody[]) => void;
}) {
  const [newFecha, setNewFecha] = useState("");
  const [newIni, setNewIni] = useState(9);
  const [newFin, setNewFin] = useState(13);
  const [diaSemana, setDiaSemana] = useState(0);
  const [mesDesde, setMesDesde] = useState("");
  const [mesHasta, setMesHasta] = useState("");
  const [semIni, setSemIni] = useState(9);
  const [semFin, setSemFin] = useState(13);

  function addIntensivo() {
    if (!newFecha) {
      toast.error("Ingresá una fecha");
      return;
    }
    if (newIni >= newFin) {
      toast.error("Hora inicio debe ser menor a hora fin");
      return;
    }
    if (clases.find((s) => s.fecha === newFecha)) {
      toast.error("Esa fecha ya está en la lista");
      return;
    }
    onChange(
      [...clases, { fecha: newFecha, hora_inicio: newIni, hora_fin: newFin }].sort((a, b) =>
        a.fecha.localeCompare(b.fecha),
      ),
    );
    setNewFecha("");
  }

  function generateSemanal() {
    if (!mesDesde || !mesHasta) {
      toast.error("Ingresá ambos meses");
      return;
    }
    if (mesDesde > mesHasta) {
      toast.error("El mes desde debe ser anterior al hasta");
      return;
    }
    if (semIni >= semFin) {
      toast.error("Hora inicio debe ser menor a hora fin");
      return;
    }
    const generated = generarClasesSemanales(diaSemana, mesDesde, mesHasta, semIni, semFin);
    const existingDates = new Set(generated.map((g) => g.fecha));
    const kept = clases.filter((s) => !existingDates.has(s.fecha));
    onChange([...kept, ...generated].sort((a, b) => a.fecha.localeCompare(b.fecha)));
    toast.success(`${generated.length} clases generadas`);
  }

  function remove(fecha: string) {
    onChange(clases.filter((s) => s.fecha !== fecha));
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground shrink-0">
          Tipo
        </span>
        <Select value={tipo} onValueChange={onTipoChange}>
          <SelectTrigger className="w-[180px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="intensivo">Intensivo</SelectItem>
            <SelectItem value="semanal">Semanal</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {tipo === "intensivo" && (
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Fecha</label>
            <Input
              type="date"
              value={newFecha}
              onChange={(e) => setNewFecha(e.target.value)}
              className="w-[160px]"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Desde (h)</label>
            <HoraSelect value={newIni} onChange={setNewIni} min={0} max={23} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Hasta (h)</label>
            <HoraSelect value={newFin} onChange={setNewFin} min={1} max={24} />
          </div>
          <Button variant="outline" size="sm" onClick={addIntensivo} className="gap-1.5">
            <Plus className="h-3.5 w-3.5" />
            Agregar fecha
          </Button>
        </div>
      )}

      {tipo === "semanal" && (
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Día</label>
            <Select value={String(diaSemana)} onValueChange={(v) => setDiaSemana(Number(v))}>
              <SelectTrigger className="w-[130px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DIAS.map((d, i) => (
                  <SelectItem key={i} value={String(i)}>
                    {d}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Desde (mes)</label>
            <Input
              type="month"
              value={mesDesde}
              onChange={(e) => setMesDesde(e.target.value)}
              className="w-[140px]"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Hasta (mes)</label>
            <Input
              type="month"
              value={mesHasta}
              onChange={(e) => setMesHasta(e.target.value)}
              className="w-[140px]"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Desde (h)</label>
            <HoraSelect value={semIni} onChange={setSemIni} min={0} max={23} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Hasta (h)</label>
            <HoraSelect value={semFin} onChange={setSemFin} min={1} max={24} />
          </div>
          <Button variant="outline" size="sm" onClick={generateSemanal} className="gap-1.5">
            <Plus className="h-3.5 w-3.5" />
            Generar
          </Button>
        </div>
      )}

      {clases.length > 0 ? (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
            {clases.length} clase{clases.length !== 1 ? "s" : ""} · bloquean el estudio en esas
            franjas
          </p>
          <div className="flex flex-wrap gap-1.5">
            {clases.map((s) => (
              <span
                key={s.fecha}
                className="inline-flex items-center gap-1.5 rounded-full bg-muted/40 border border-border/50 px-3 py-1 text-xs"
              >
                {new Date(s.fecha + "T12:00:00").toLocaleDateString("es-AR", {
                  weekday: "short",
                  day: "numeric",
                  month: "short",
                })}
                <span className="text-muted-foreground">
                  {s.hora_inicio}–{s.hora_fin}h
                </span>
                <button
                  onClick={() => remove(s.fecha)}
                  className="ml-0.5 h-6 w-6 flex items-center justify-center text-muted-foreground/60 hover:text-destructive transition rounded"
                  aria-label="Quitar"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground/60 italic">
          Sin clases. Agregá al menos una para bloquear el estudio.
        </p>
      )}
    </div>
  );
}

// ── ClasesSection ─────────────────────────────────────────────────────────────

function ClasesSection({ edicion }: { edicion: EdicionAdmin }) {
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
      authedJson<EdicionAdmin>(`/api/admin/ediciones/${edicion.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
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

// ── PreciosSection ────────────────────────────────────────────────────────────

function PreciosSection({ edicion }: { edicion: EdicionAdmin }) {
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
      authedJson<EdicionAdmin>(`/api/admin/ediciones/${edicion.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
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

// ── PagosSection ──────────────────────────────────────────────────────────────

function PagosSection({ edicion }: { edicion: EdicionAdmin }) {
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
    mutationFn: (body: typeof form) =>
      authedJson<EdicionAdmin>(`/api/admin/ediciones/${edicion.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
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

// ── FotoSection ───────────────────────────────────────────────────────────────

function FotoSection({ concepto }: { concepto: TallerConcepto }) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);

  async function handleUpload(file: File) {
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await authedFetch(`/api/admin/talleres/${concepto.id}/upload-foto-instructor`, {
        method: "POST",
        body: fd,
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json?.detail ?? `Error ${res.status}`);
      toast.success("Foto actualizada");
      qc.invalidateQueries({ queryKey: ["admin", "talleres"] });
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="flex items-start gap-6">
      {concepto.instructor_foto_url ? (
        <img
          src={concepto.instructor_foto_url}
          alt={concepto.instructor_nombre}
          className="w-24 h-24 rounded-full object-cover object-top border border-border/40 shrink-0"
        />
      ) : (
        <div className="w-24 h-24 rounded-full bg-muted/40 border border-dashed border-border/60 flex items-center justify-center shrink-0">
          <span className="text-xs text-muted-foreground text-center px-2">Sin foto</span>
        </div>
      )}
      <div className="flex flex-col gap-2">
        <p className="text-sm text-muted-foreground">
          JPG, PNG o WebP · máx. 8 MB. Se muestra en la sección "Sobre" de la landing del workshop.
        </p>
        <div>
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleUpload(f);
            }}
          />
          <Button
            variant="outline"
            size="sm"
            disabled={uploading}
            onClick={() => fileRef.current?.click()}
            className="gap-2"
          >
            {uploading ? <Spinner size="xs" /> : <Upload className="h-3.5 w-3.5" />}
            {concepto.instructor_foto_url ? "Cambiar foto" : "Subir foto"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── ContenidoSection ──────────────────────────────────────────────────────────

function ContenidoSection({ concepto }: { concepto: TallerConcepto }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    nombre: concepto.nombre,
    subtitulo: concepto.subtitulo,
    instructor_nombre: concepto.instructor_nombre,
    descripcion: concepto.descripcion,
    publico_objetivo: concepto.publico_objetivo,
    instructor_bio: concepto.instructor_bio,
    instructor_proyectos: concepto.instructor_proyectos,
    programa_teorica: (concepto.programa_teorica ?? []).join("\n"),
    programa_practica: (concepto.programa_practica ?? []).join("\n"),
    notif_email: concepto.notif_email ?? "",
  });

  useEffect(() => {
    setForm({
      nombre: concepto.nombre,
      subtitulo: concepto.subtitulo,
      instructor_nombre: concepto.instructor_nombre,
      descripcion: concepto.descripcion,
      publico_objetivo: concepto.publico_objetivo,
      instructor_bio: concepto.instructor_bio,
      instructor_proyectos: concepto.instructor_proyectos,
      programa_teorica: (concepto.programa_teorica ?? []).join("\n"),
      programa_practica: (concepto.programa_practica ?? []).join("\n"),
      notif_email: concepto.notif_email ?? "",
    });
  }, [concepto.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const mut = useMutation({
    mutationFn: (body: object) =>
      authedJson<TallerConcepto>(`/api/admin/talleres/${concepto.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: (updated) => {
      toast.success("Guardado");
      updateConceptoInCache(qc, updated);
    },
    onError: (e) => toast.error((e as Error).message),
  });

  function handleSave() {
    mut.mutate({
      nombre: form.nombre,
      subtitulo: form.subtitulo,
      instructor_nombre: form.instructor_nombre,
      descripcion: form.descripcion,
      publico_objetivo: form.publico_objetivo,
      instructor_bio: form.instructor_bio,
      instructor_proyectos: form.instructor_proyectos,
      programa_teorica: form.programa_teorica
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
      programa_practica: form.programa_practica
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
      notif_email: form.notif_email,
    });
  }

  const field = (
    label: string,
    key: keyof typeof form,
    opts?: { rows?: number; hint?: string; type?: string },
  ) => (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
        {label}
      </label>
      {opts?.hint && <p className="text-xs text-muted-foreground/70 -mt-1">{opts.hint}</p>}
      {(opts?.rows ?? 1) === 1 ? (
        <Input
          type={opts?.type ?? "text"}
          value={form[key] as string}
          onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
        />
      ) : (
        <textarea
          rows={opts?.rows}
          value={form[key] as string}
          onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-ink placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-y"
        />
      )}
    </div>
  );

  return (
    <div className="flex flex-col gap-5">
      <div className="grid sm:grid-cols-2 gap-4">
        {field("Nombre", "nombre")}
        {field("Subtítulo", "subtitulo")}
      </div>
      {field("Instructor/a", "instructor_nombre")}
      {field("Descripción", "descripcion", { rows: 4 })}
      {field("¿Para quiénes?", "publico_objetivo", {
        rows: 3,
        hint: "Texto que aparece en el box 'Orientado a'",
      })}
      {field("Bio del/la instructor/a", "instructor_bio", { rows: 4 })}
      {field("Proyectos (separados por coma)", "instructor_proyectos", {
        rows: 2,
        hint: "Se muestran como pills.",
      })}
      {field("Programa clase teórica (1 ítem por línea)", "programa_teorica", { rows: 6 })}
      {field("Programa clase práctica (1 ítem por línea)", "programa_practica", { rows: 6 })}
      {field("Email del instructor/a", "notif_email", {
        type: "email",
        hint: "Recibe las notificaciones de inscripción.",
      })}
      <div className="flex justify-end pt-2">
        <Button onClick={handleSave} disabled={mut.isPending} className="gap-2">
          {mut.isPending ? <Spinner size="sm" /> : <Save className="h-4 w-4" />}
          Guardar cambios
        </Button>
      </div>
    </div>
  );
}

// ── InscripcionesSection ──────────────────────────────────────────────────────

function InscripcionesSection({
  edicion,
  concepto,
  inscripciones,
  loading,
}: {
  edicion: EdicionAdmin;
  concepto: TallerConcepto;
  inscripciones: Inscripcion[];
  loading: boolean;
}) {
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [notifMsg, setNotifMsg] = useState("");
  const [notifOpen, setNotifOpen] = useState(false);

  const confirmadas = inscripciones.filter((i) => !i.en_lista_espera);
  const espera = inscripciones.filter((i) => i.en_lista_espera);

  const eliminarMut = useMutation({
    mutationFn: (insId: number) =>
      authedJson<{ ok: boolean }>(`/api/admin/talleres/${concepto.id}/inscripciones/${insId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      toast.success("Inscripción eliminada");
      qc.invalidateQueries({ queryKey: ["admin", "ediciones", edicion.id, "inscripciones"] });
      qc.invalidateQueries({ queryKey: ["admin", "talleres"] });
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const confirmarMut = useMutation({
    mutationFn: (insId: number) =>
      authedJson<{ ok: boolean }>(
        `/api/admin/talleres/${concepto.id}/inscripciones/${insId}/confirmar`,
        { method: "POST" },
      ),
    onSuccess: () => {
      toast.success("Inscripción confirmada");
      qc.invalidateQueries({ queryKey: ["admin", "ediciones", edicion.id, "inscripciones"] });
      qc.invalidateQueries({ queryKey: ["admin", "talleres"] });
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const notificarMut = useMutation({
    mutationFn: (mensaje: string) =>
      authedJson<{ enviados: number; fallidos: number }>(
        `/api/admin/talleres/${concepto.id}/notificar-cambios`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mensaje: mensaje || undefined }),
        },
      ),
    onSuccess: (r) => {
      toast.success(`Notificaciones enviadas: ${r.enviados} ok, ${r.fallidos} fallidas`);
      setNotifOpen(false);
      setNotifMsg("");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  async function handleCsvDownload() {
    try {
      const res = await authedFetch(`/api/admin/talleres/${concepto.id}/inscripciones/export-csv`);
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `inscripciones-${concepto.slug_base}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function handleEliminar(ins: Inscripcion) {
    const label = ins.en_lista_espera ? "de lista de espera" : "confirmada";
    if (
      !(await confirm({
        title: "¿Eliminar inscripción?",
        description: `Se eliminará la inscripción ${label} de ${ins.nombre}.`,
        danger: true,
        confirmLabel: "Eliminar",
      }))
    )
      return;
    eliminarMut.mutate(ins.id);
  }

  if (loading) return <p className="text-sm text-muted-foreground">Cargando inscripciones…</p>;

  if (inscripciones.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border/60 py-12 text-center text-sm text-muted-foreground">
        No hay inscripciones todavía.
      </div>
    );
  }

  const insTable = (rows: Inscripcion[], showConfirmar: boolean) => {
    const columns: Column<Inscripcion>[] = [
      {
        header: "Nombre",
        cell: (ins) => ins.nombre,
        className: "font-medium text-ink",
      },
      {
        header: "Email",
        cell: (ins) => (
          <a href={`mailto:${ins.email}`} className="hover:text-ink transition">
            {ins.email}
          </a>
        ),
        className: "text-muted-foreground",
      },
      {
        header: "Teléfono",
        cell: (ins) => ins.telefono,
        className: "text-muted-foreground hidden sm:table-cell",
        headClassName: "hidden sm:table-cell",
      },
      {
        header: "Experiencia",
        cell: (ins) => ins.experiencia || "—",
        className: "text-muted-foreground hidden lg:table-cell max-w-[180px] truncate",
        headClassName: "hidden lg:table-cell",
      },
      {
        header: "Comp.",
        cell: (ins) =>
          ins.comprobante_url ? (
            <a
              href={ins.comprobante_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-ink hover:text-ink transition"
            >
              <CheckCircle2 className="h-3.5 w-3.5 text-verde-ink" strokeWidth={1.5} />
              <ExternalLink className="h-3 w-3" />
            </a>
          ) : (
            <span className="text-muted-foreground/50 text-xs">—</span>
          ),
      },
      {
        header: "Fecha",
        cell: (ins) => (
          <span className="inline-flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {fmtDate(ins.created_at)}
          </span>
        ),
        className: "text-muted-foreground text-xs",
      },
      {
        header: "",
        cell: (ins) => (
          <div className="flex items-center gap-1">
            {showConfirmar && (
              <Button
                variant="outline"
                size="sm"
                className="h-7 px-2 text-xs"
                disabled={confirmarMut.isPending}
                onClick={() => confirmarMut.mutate(ins.id)}
              >
                Confirmar
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
              disabled={eliminarMut.isPending}
              onClick={() => handleEliminar(ins)}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        ),
      },
    ];
    return <AdminTable columns={columns} rows={rows} getRowKey={(ins) => ins.id} />;
  };

  return (
    <>
      {confirmadas.length > 0 && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
              Confirmadas ({confirmadas.length})
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5 h-7 text-xs"
                onClick={handleCsvDownload}
              >
                <Download className="h-3 w-3" />
                CSV
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5 h-7 text-xs"
                onClick={() => setNotifOpen(true)}
              >
                <Bell className="h-3 w-3" />
                Notificar cambios
              </Button>
            </div>
          </div>
          {insTable(confirmadas, false)}
        </div>
      )}

      {espera.length > 0 && (
        <div
          className={`flex flex-col gap-3${confirmadas.length > 0 ? " border-t border-border/40 pt-5 mt-2" : ""}`}
        >
          <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
            Lista de espera ({espera.length})
          </p>
          {insTable(espera, true)}
        </div>
      )}

      <Dialog open={notifOpen} onOpenChange={setNotifOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Notificar cambios a inscriptos</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-2">
            <p className="text-sm text-muted-foreground">
              Se enviará un email a los {confirmadas.length} inscriptos confirmados.
            </p>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                Mensaje (opcional)
              </label>
              <textarea
                rows={4}
                value={notifMsg}
                onChange={(e) => setNotifMsg(e.target.value)}
                placeholder="Ej: Cambiamos el horario a las 10 hs."
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-ink placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none"
              />
            </div>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="ghost">Cancelar</Button>
            </DialogClose>
            <Button
              onClick={() => notificarMut.mutate(notifMsg)}
              disabled={notificarMut.isPending}
              className="gap-2"
            >
              {notificarMut.isPending ? <Spinner size="sm" /> : <Bell className="h-4 w-4" />}
              Enviar notificaciones
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ── EdicionSubRow ─────────────────────────────────────────────────────────────

function EdicionSubRow({
  edicion,
  concepto,
  onDelete,
}: {
  edicion: EdicionAdmin;
  concepto: TallerConcepto;
  onDelete: (edicionId: number) => void;
}) {
  const qc = useQueryClient();
  const confirm = useConfirm();
  const badge = badgeEstadoEdicion(edicion);
  const [expanded, setExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<"clases" | "precios" | "inscripciones">("clases");

  const { data: inscripciones = [], isLoading: loadingIns } = useQuery({
    queryKey: ["admin", "ediciones", edicion.id, "inscripciones"],
    queryFn: () => authedJson<Inscripcion[]>(`/api/admin/ediciones/${edicion.id}/inscripciones`),
    enabled: expanded && activeTab === "inscripciones",
    staleTime: 1000 * 30,
  });

  const toggleActivoMut = useMutation({
    mutationFn: (activo: boolean) =>
      authedJson<EdicionAdmin>(`/api/admin/ediciones/${edicion.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ activo }),
      }),
    onSuccess: (updated) => {
      toast.success(updated.activo ? "Edición activada" : "Edición desactivada");
      updateEdicionInCache(qc, updated);
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const deleteMut = useMutation({
    mutationFn: () =>
      authedJson<{ ok: boolean }>(`/api/admin/ediciones/${edicion.id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("Edición eliminada");
      onDelete(edicion.id);
    },
    onError: (e) => toast.error((e as Error).message),
  });

  async function handleToggleActivo(v: boolean) {
    if (!v && edicion.cupos_confirmados > 0) {
      const ok = await confirm({
        title: `¿Desactivar la edición #${edicion.numero_edicion}?`,
        description: `Hay ${edicion.cupos_confirmados} inscriptos confirmados.`,
        danger: true,
        confirmLabel: "Desactivar",
      });
      if (!ok) return;
    }
    toggleActivoMut.mutate(v);
  }

  async function handleDelete() {
    if (edicion.cupos_confirmados > 0) {
      toast.error(`No se puede eliminar: hay ${edicion.cupos_confirmados} inscriptos confirmados`);
      return;
    }
    if (
      !(await confirm({
        title: `¿Eliminar la edición #${edicion.numero_edicion}?`,
        description: `Se eliminará la edición de "${concepto.nombre}".`,
        danger: true,
        confirmLabel: "Eliminar",
      }))
    )
      return;
    deleteMut.mutate();
  }

  return (
    <div
      className={`rounded-lg border transition-colors ${
        expanded ? "border-ink/20 bg-ink/3" : "border-border/50"
      }`}
    >
      {/* Edition header */}
      <div
        className="flex items-center gap-2.5 px-3 py-2.5 cursor-pointer select-none"
        onClick={() => setExpanded((v) => !v)}
      >
        <span className="shrink-0 text-xs font-mono font-semibold text-muted-foreground">
          #{edicion.numero_edicion}
        </span>
        <Pill tone={badge.tone} className="font-mono uppercase tracking-wider">
          {badge.label}
        </Pill>

        {/* Date range */}
        {edicion.fecha_inicio && (
          <span className="flex-1 min-w-0 text-xs text-muted-foreground truncate">
            {fmtDay(edicion.fecha_inicio)}
            {edicion.fecha_fin && edicion.fecha_fin !== edicion.fecha_inicio && (
              <> – {fmtDay(edicion.fecha_fin)}</>
            )}
          </span>
        )}

        <CuposPill confirmados={edicion.cupos_confirmados} total={edicion.cupos_total} />

        <div className="flex items-center gap-1.5 shrink-0" onClick={(e) => e.stopPropagation()}>
          {edicion.activo ? (
            <Eye className="h-3 w-3 text-muted-foreground" />
          ) : (
            <EyeOff className="h-3 w-3 text-muted-foreground/40" />
          )}
          <Switch
            checked={edicion.activo}
            onCheckedChange={handleToggleActivo}
            disabled={toggleActivoMut.isPending}
            aria-label={edicion.activo ? "Desactivar edición" : "Activar edición"}
          />
          <a
            href={`/workshops/${edicion.slug}`}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1 rounded text-muted-foreground hover:text-ink transition"
            title="Ver en web"
            aria-label="Ver edición en web"
          >
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>

        <svg
          className={`h-3.5 w-3.5 text-muted-foreground/60 shrink-0 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {/* Edition detail */}
      {expanded && (
        <div className="border-t border-border/40">
          <div className="flex border-b border-border/50 overflow-x-auto">
            {(
              [
                { id: "clases", label: "Fechas y clases" },
                { id: "precios", label: "Precios y pago" },
                {
                  id: "inscripciones",
                  label: `Inscripciones${edicion.cupos_confirmados > 0 ? ` (${edicion.cupos_confirmados})` : ""}`,
                },
              ] as { id: "clases" | "precios" | "inscripciones"; label: string }[]
            ).map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`shrink-0 px-3 py-2 text-sm border-b-2 -mb-[1px] transition-colors ${
                  activeTab === tab.id
                    ? "border-ink text-ink font-medium"
                    : "border-transparent text-muted-foreground hover:text-ink"
                }`}
              >
                {tab.label}
              </button>
            ))}
            <div className="flex-1" />
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleDelete();
              }}
              disabled={deleteMut.isPending}
              className="px-3 py-2 text-xs text-muted-foreground/60 hover:text-destructive transition shrink-0"
              title="Eliminar edición"
            >
              {deleteMut.isPending ? <Spinner size="xs" /> : <Trash2 className="h-3.5 w-3.5" />}
            </button>
          </div>

          <div className="px-4 pb-5 pt-4">
            {activeTab === "clases" && <ClasesSection edicion={edicion} />}
            {activeTab === "precios" && (
              <div className="flex flex-col gap-0">
                <PreciosSection edicion={edicion} />
                <div className="border-t border-border/40 mt-6 pt-6">
                  <PagosSection edicion={edicion} />
                </div>
              </div>
            )}
            {activeTab === "inscripciones" && (
              <InscripcionesSection
                edicion={edicion}
                concepto={concepto}
                inscripciones={inscripciones}
                loading={loadingIns}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── TallerConceptoRow ─────────────────────────────────────────────────────────

function TallerConceptoRow({
  concepto,
  expanded,
  onToggle,
  onNuevaEdicion,
}: {
  concepto: TallerConcepto;
  expanded: boolean;
  onToggle: () => void;
  onNuevaEdicion: (c: TallerConcepto) => void;
}) {
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<"ediciones" | "taller">("ediciones");

  const totalConfirmados = concepto.ediciones.reduce((s, e) => s + e.cupos_confirmados, 0);
  const activeEdiciones = concepto.ediciones.filter((e) => e.activo);

  function handleDeleteEdicion(edicionId: number) {
    qc.setQueryData(["admin", "talleres"], (prev: TallerConcepto[] | undefined) =>
      prev?.map((c) =>
        c.id === concepto.id
          ? { ...c, ediciones: c.ediciones.filter((e) => e.id !== edicionId) }
          : c,
      ),
    );
  }

  return (
    <div
      className={`rounded-xl border transition-colors ${
        expanded ? "border-ink/30 bg-ink/5" : "border-border/60"
      }`}
    >
      {/* Concept header */}
      <div
        className="flex items-center gap-3 px-4 py-3.5 cursor-pointer select-none"
        onClick={onToggle}
      >
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-ink text-sm truncate leading-tight">{concepto.nombre}</p>
          <p className="text-xs text-muted-foreground truncate mt-0.5">
            {concepto.instructor_nombre}
          </p>
        </div>

        <span className="hidden md:block shrink-0 text-2xs font-mono text-muted-foreground bg-muted/40 rounded-full px-2 py-0.5">
          {concepto.ediciones.length === 1 ? "1 edición" : `${concepto.ediciones.length} ediciones`}
          {activeEdiciones.length !== concepto.ediciones.length &&
            ` · ${activeEdiciones.length} activa${activeEdiciones.length !== 1 ? "s" : ""}`}
        </span>

        {totalConfirmados > 0 && (
          <span className="shrink-0 text-2xs font-mono text-muted-foreground bg-muted/40 rounded-full px-2 py-0.5 tabular-nums">
            {totalConfirmados} inscripto{totalConfirmados !== 1 ? "s" : ""}
          </span>
        )}

        <svg
          className={`h-4 w-4 text-muted-foreground/60 shrink-0 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {/* Detail */}
      {expanded && (
        <div className="border-t border-border/40">
          <div className="flex border-b border-border/60 overflow-x-auto">
            {(
              [
                { id: "ediciones", label: "Ediciones" },
                { id: "taller", label: "El taller" },
              ] as { id: "ediciones" | "taller"; label: string }[]
            ).map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`shrink-0 px-4 py-2.5 text-sm border-b-2 -mb-[1px] transition-colors ${
                  activeTab === tab.id
                    ? "border-ink text-ink font-medium"
                    : "border-transparent text-muted-foreground hover:text-ink"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="px-4 pb-6 pt-5">
            {activeTab === "ediciones" && (
              <div className="flex flex-col gap-3">
                {concepto.ediciones.map((edicion) => (
                  <EdicionSubRow
                    key={edicion.id}
                    edicion={edicion}
                    concepto={concepto}
                    onDelete={handleDeleteEdicion}
                  />
                ))}
                {concepto.ediciones.length === 0 && (
                  <p className="text-sm text-muted-foreground italic">Sin ediciones.</p>
                )}
                <div className="flex justify-end pt-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onNuevaEdicion(concepto)}
                    className="gap-1.5"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Nueva edición
                  </Button>
                </div>
              </div>
            )}

            {activeTab === "taller" && (
              <div className="flex flex-col gap-0">
                <FotoSection concepto={concepto} />
                <div className="border-t border-border/40 mt-6 pt-6">
                  <ContenidoSection concepto={concepto} />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── NuevoConceptoDialog ───────────────────────────────────────────────────────

function NuevoConceptoDialog({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: (created: TallerConcepto) => void;
}) {
  const [nombre, setNombre] = useState("");
  const [instructorNombre, setInstructorNombre] = useState("");
  const [tipo, setTipo] = useState("intensivo");
  const [clases, setClases] = useState<ClaseBody[]>([]);
  const [cupos, setCupos] = useState("12");
  const [precioTotal, setPrecioTotal] = useState("0");
  const [precioSena, setPrecioSena] = useState("0");

  useEffect(() => {
    if (open) {
      setNombre("");
      setInstructorNombre("");
      setTipo("intensivo");
      setClases([]);
      setCupos("12");
      setPrecioTotal("0");
      setPrecioSena("0");
    }
  }, [open]);

  const mut = useMutation({
    mutationFn: (body: object) =>
      authedJson<TallerConcepto>("/api/admin/talleres", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: (created) => {
      toast.success(`Taller creado: ${created.nombre}`);
      onSuccess(created);
    },
    onError: (e) => toast.error((e as Error).message),
  });

  function handleSubmit() {
    if (!nombre.trim()) {
      toast.error("Ingresá el nombre del taller");
      return;
    }
    if (!instructorNombre.trim()) {
      toast.error("Ingresá el nombre del/la instructor/a");
      return;
    }
    if (clases.length === 0) {
      toast.error("Agregá al menos una clase");
      return;
    }
    const c = parseInt(cupos, 10);
    const pt = parseInt(precioTotal, 10);
    const ps = parseInt(precioSena, 10);
    if (isNaN(c) || c < 1) {
      toast.error("Cupos inválidos");
      return;
    }
    if (isNaN(pt) || isNaN(ps) || ps > pt) {
      toast.error("Precios inválidos (la seña no puede superar el total)");
      return;
    }
    mut.mutate({
      nombre: nombre.trim(),
      instructor_nombre: instructorNombre.trim(),
      edicion: {
        tipo_taller: tipo,
        clases,
        cupos_total: c,
        precio_total: pt,
        precio_sena: ps,
        numero_edicion: 1,
      },
    });
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Nuevo taller</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-5 py-2">
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                Nombre del taller *
              </label>
              <Input
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                placeholder="Ej: Dirección de arte"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                Instructor/a *
              </label>
              <Input
                value={instructorNombre}
                onChange={(e) => setInstructorNombre(e.target.value)}
                placeholder="Ej: Jime Troncoso"
              />
            </div>
          </div>

          <div className="border-t border-border/50 pt-4">
            <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground mb-3">
              Clases — 1.ª edición *
            </p>
            <ClasesAsistente
              tipo={tipo}
              onTipoChange={setTipo}
              clases={clases}
              onChange={setClases}
            />
            {clases.length > 0 && (
              <div className="mt-4 pointer-events-none select-none">
                <TallerCalendario sesiones={clases} />
              </div>
            )}
          </div>

          <div className="grid sm:grid-cols-3 gap-4 border-t border-border/50 pt-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                Cupos totales
              </label>
              <Input
                type="number"
                min={1}
                value={cupos}
                onChange={(e) => setCupos(e.target.value)}
              />
            </div>
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
          </div>
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="ghost">Cancelar</Button>
          </DialogClose>
          <Button onClick={handleSubmit} disabled={mut.isPending} className="gap-2">
            {mut.isPending ? <Spinner size="sm" /> : <Plus className="h-4 w-4" />}
            Crear taller
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── NuevaEdicionDialog ────────────────────────────────────────────────────────

function NuevaEdicionDialog({
  concepto,
  open,
  onClose,
  onSuccess,
}: {
  concepto: TallerConcepto | null;
  open: boolean;
  onClose: () => void;
  onSuccess: (created: EdicionAdmin) => void;
}) {
  const nextNumero =
    concepto && concepto.ediciones.length > 0
      ? Math.max(...concepto.ediciones.map((e) => e.numero_edicion)) + 1
      : 1;

  const [tipo, setTipo] = useState("intensivo");
  const [clases, setClases] = useState<ClaseBody[]>([]);
  const [cupos, setCupos] = useState("12");
  const [precioTotal, setPrecioTotal] = useState("0");
  const [precioSena, setPrecioSena] = useState("0");

  useEffect(() => {
    if (open) {
      setTipo("intensivo");
      setClases([]);
      setCupos("12");
      setPrecioTotal("0");
      setPrecioSena("0");
    }
  }, [open]);

  const mut = useMutation({
    mutationFn: (body: object) =>
      authedJson<EdicionAdmin>(`/api/admin/talleres/${concepto!.id}/ediciones`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: (created) => {
      toast.success(`Edición #${created.numero_edicion} creada`);
      onSuccess(created);
    },
    onError: (e) => toast.error((e as Error).message),
  });

  function handleSubmit() {
    if (clases.length === 0) {
      toast.error("Agregá al menos una clase");
      return;
    }
    const c = parseInt(cupos, 10);
    const pt = parseInt(precioTotal, 10);
    const ps = parseInt(precioSena, 10);
    if (isNaN(c) || c < 1) {
      toast.error("Cupos inválidos");
      return;
    }
    if (isNaN(pt) || isNaN(ps) || ps > pt) {
      toast.error("Precios inválidos (la seña no puede superar el total)");
      return;
    }
    mut.mutate({
      tipo_taller: tipo,
      clases,
      cupos_total: c,
      precio_total: pt,
      precio_sena: ps,
      numero_edicion: nextNumero,
    });
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            Nueva edición — {concepto?.nombre}
            <span className="ml-2 text-sm font-normal text-muted-foreground">#{nextNumero}</span>
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-5 py-2">
          <div className="border-b border-border/50 pb-4">
            <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground mb-3">
              Clases *
            </p>
            <ClasesAsistente
              tipo={tipo}
              onTipoChange={setTipo}
              clases={clases}
              onChange={setClases}
            />
            {clases.length > 0 && (
              <div className="mt-4 pointer-events-none select-none">
                <TallerCalendario sesiones={clases} />
              </div>
            )}
          </div>

          <div className="grid sm:grid-cols-3 gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                Cupos totales
              </label>
              <Input
                type="number"
                min={1}
                value={cupos}
                onChange={(e) => setCupos(e.target.value)}
              />
            </div>
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
          </div>
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="ghost">Cancelar</Button>
          </DialogClose>
          <Button onClick={handleSubmit} disabled={mut.isPending} className="gap-2">
            {mut.isPending ? <Spinner size="sm" /> : <Plus className="h-4 w-4" />}
            Crear edición
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── TalleresAdminPage ─────────────────────────────────────────────────────────

function TalleresAdminPage() {
  useDocumentTitle("Talleres — Admin");
  const qc = useQueryClient();
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [nuevoOpen, setNuevoOpen] = useState(false);
  const [nuevaEdicionConcepto, setNuevaEdicionConcepto] = useState<TallerConcepto | null>(null);

  const { data: conceptos = [], isLoading } = useQuery({
    queryKey: ["admin", "talleres"],
    queryFn: () => authedJson<TallerConcepto[]>("/api/admin/talleres"),
    staleTime: 1000 * 60,
  });

  function handleNuevoConceptoSuccess(created: TallerConcepto) {
    qc.setQueryData(["admin", "talleres"], (prev: TallerConcepto[] | undefined) =>
      prev ? [created, ...prev] : [created],
    );
    setNuevoOpen(false);
    setExpandedId(created.id);
  }

  function handleNuevaEdicionSuccess(created: EdicionAdmin) {
    qc.setQueryData(["admin", "talleres"], (prev: TallerConcepto[] | undefined) =>
      prev?.map((c) =>
        c.id === nuevaEdicionConcepto?.id
          ? {
              ...c,
              ediciones: [...c.ediciones, created].sort(
                (a, b) => a.numero_edicion - b.numero_edicion,
              ),
            }
          : c,
      ),
    );
    setNuevaEdicionConcepto(null);
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <Users className="h-5 w-5 text-muted-foreground" />
            <h1 className="text-xl font-semibold text-ink">Talleres</h1>
          </div>
          {conceptos.length > 0 && (
            <p className="text-xs text-muted-foreground mt-0.5 ml-7.5">
              {conceptos.length} concepto{conceptos.length !== 1 ? "s" : ""} ·{" "}
              {conceptos.reduce((s, c) => s + c.ediciones.length, 0)} ediciones
            </p>
          )}
        </div>
        <Button size="sm" className="gap-2" onClick={() => setNuevoOpen(true)}>
          <Plus className="h-4 w-4" />
          Nuevo taller
        </Button>
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div className="flex flex-col gap-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-xl border border-border/60 px-4 py-3.5 flex items-center gap-3 animate-pulse"
            >
              <div className="flex-1 flex flex-col gap-1.5 min-w-0">
                <div className="h-4 w-40 rounded bg-muted/60" />
                <div className="h-3 w-28 rounded bg-muted/40" />
              </div>
              <div className="h-5 w-20 rounded-full bg-muted/40 shrink-0 hidden md:block" />
              <div className="h-4 w-4 rounded bg-muted/30 shrink-0" />
            </div>
          ))}
        </div>
      )}

      {/* Lista */}
      {conceptos.length > 0 && (
        <div className="flex flex-col gap-2">
          {conceptos.map((concepto) => (
            <TallerConceptoRow
              key={concepto.id}
              concepto={concepto}
              expanded={expandedId === concepto.id}
              onToggle={() => setExpandedId(expandedId === concepto.id ? null : concepto.id)}
              onNuevaEdicion={(c) => setNuevaEdicionConcepto(c)}
            />
          ))}
        </div>
      )}

      {conceptos.length === 0 && !isLoading && (
        <div className="rounded-xl border border-dashed border-border/60 py-16 text-center flex flex-col items-center gap-4">
          <Users className="h-8 w-8 text-muted-foreground/40" />
          <div>
            <p className="text-sm font-medium text-ink">No hay talleres todavía</p>
            <p className="text-xs text-muted-foreground mt-1">
              Creá el primero para que aparezca en la web.
            </p>
          </div>
          <Button size="sm" onClick={() => setNuevoOpen(true)} className="gap-2">
            <Plus className="h-4 w-4" />
            Crear el primero
          </Button>
        </div>
      )}

      <NuevoConceptoDialog
        open={nuevoOpen}
        onClose={() => setNuevoOpen(false)}
        onSuccess={handleNuevoConceptoSuccess}
      />

      <NuevaEdicionDialog
        concepto={nuevaEdicionConcepto}
        open={nuevaEdicionConcepto !== null}
        onClose={() => setNuevaEdicionConcepto(null)}
        onSuccess={handleNuevaEdicionSuccess}
      />
    </div>
  );
}
