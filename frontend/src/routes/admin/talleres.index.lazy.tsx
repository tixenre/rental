import { useEffect, useRef, useState } from "react";
import { createLazyFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Users,
  ExternalLink,
  Clock,
  CheckCircle2,
  Upload,
  Loader2,
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
import { AdminSection } from "@/components/admin/AdminSection";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
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
import { formatARS } from "@/lib/format";
import { TallerCalendario } from "@/components/talleres/TallerCalendario";

export const Route = createLazyFileRoute("/admin/talleres/")({
  component: TalleresAdminPage,
});

// ── Types ────────────────────────────────────────────────────────────────────

type SesionBody = { fecha: string; hora_inicio: number; hora_fin: number };

type TallerAdmin = {
  id: number;
  slug: string;
  nombre: string;
  subtitulo: string;
  instructor_nombre: string;
  instructor_bio: string;
  instructor_foto_url: string;
  instructor_proyectos: string;
  descripcion: string;
  publico_objetivo: string;
  programa_teorica: string[];
  programa_practica: string[];
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
  tipo_taller: string;
  notif_email: boolean;
  proxima_edicion_slug: string;
  numero_edicion: number;
  sesiones: SesionBody[];
};

type Inscripcion = {
  id: number;
  nombre: string;
  email: string;
  telefono: string;
  experiencia: string | null;
  comprobante_url: string | null;
  en_lista_espera: boolean;
  created_at: string | null;
};

type UpdateBody = {
  nombre?: string;
  subtitulo?: string;
  descripcion?: string;
  publico_objetivo?: string;
  instructor_nombre?: string;
  instructor_bio?: string;
  instructor_proyectos?: string;
  programa_teorica?: string[];
  programa_practica?: string[];
  horario?: string;
  precio_total?: number;
  precio_sena?: number;
  cupos_total?: number;
  pago_alias?: string;
  pago_cbu?: string;
  pago_banco?: string;
  direccion?: string;
  activo?: boolean;
  tipo_taller?: string;
  notif_email?: boolean;
  proxima_edicion_slug?: string;
  sesiones?: SesionBody[];
};

type CreateBody = {
  nombre: string;
  instructor_nombre: string;
  tipo_taller: string;
  sesiones: SesionBody[];
  cupos_total: number;
  precio_total: number;
  precio_sena: number;
};

// ── Helpers ──────────────────────────────────────────────────────────────────

const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

function badgeEstado(taller: TallerAdmin): { label: string; className: string } {
  const today = new Date().toISOString().slice(0, 10);
  if (!taller.activo)
    return { label: "INACTIVO", className: "bg-muted/40 text-muted-foreground" };
  if (taller.fecha_inicio > today)
    return { label: "PRÓXIMAMENTE", className: "bg-amber/20 text-amber-700" };
  if (taller.fecha_fin >= today)
    return { label: "EN CURSO", className: "bg-verde/20 text-verde-800" };
  return { label: "FINALIZADO", className: "bg-muted/40 text-muted-foreground" };
}

function generarSesionesSemanales(
  diaSemana: number,
  mesDesde: string,
  mesHasta: string,
  horaInicio: number,
  horaFin: number,
): SesionBody[] {
  const [yD, mD] = mesDesde.split("-").map(Number);
  const [yH, mH] = mesHasta.split("-").map(Number);
  const end = new Date(yH, mH, 0); // last day of mesHasta
  const jsDay = (diaSemana + 1) % 7; // Mon=0→1, ..., Sun=6→0
  const cur = new Date(yD, mD - 1, 1);
  while (cur.getDay() !== jsDay) cur.setDate(cur.getDate() + 1);
  const result: SesionBody[] = [];
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

// ── Session Assistant ─────────────────────────────────────────────────────────

function SesionAsistente({
  tipo,
  onTipoChange,
  sesiones,
  onChange,
}: {
  tipo: string;
  onTipoChange: (t: string) => void;
  sesiones: SesionBody[];
  onChange: (s: SesionBody[]) => void;
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
    if (sesiones.find((s) => s.fecha === newFecha)) {
      toast.error("Esa fecha ya está en la lista");
      return;
    }
    onChange(
      [...sesiones, { fecha: newFecha, hora_inicio: newIni, hora_fin: newFin }].sort((a, b) =>
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
    const generated = generarSesionesSemanales(diaSemana, mesDesde, mesHasta, semIni, semFin);
    const existingDates = new Set(generated.map((g) => g.fecha));
    const kept = sesiones.filter((s) => !existingDates.has(s.fecha));
    onChange([...kept, ...generated].sort((a, b) => a.fecha.localeCompare(b.fecha)));
    toast.success(`${generated.length} sesiones generadas`);
  }

  function remove(fecha: string) {
    onChange(sesiones.filter((s) => s.fecha !== fecha));
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
            <Input
              type="number"
              min={0}
              max={23}
              value={newIni}
              onChange={(e) => setNewIni(Number(e.target.value))}
              className="w-[80px]"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Hasta (h)</label>
            <Input
              type="number"
              min={1}
              max={24}
              value={newFin}
              onChange={(e) => setNewFin(Number(e.target.value))}
              className="w-[80px]"
            />
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
            <Input
              type="number"
              min={0}
              max={23}
              value={semIni}
              onChange={(e) => setSemIni(Number(e.target.value))}
              className="w-[75px]"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Hasta (h)</label>
            <Input
              type="number"
              min={1}
              max={24}
              value={semFin}
              onChange={(e) => setSemFin(Number(e.target.value))}
              className="w-[75px]"
            />
          </div>
          <Button variant="outline" size="sm" onClick={generateSemanal} className="gap-1.5">
            <Plus className="h-3.5 w-3.5" />
            Generar
          </Button>
        </div>
      )}

      {sesiones.length > 0 ? (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
            {sesiones.length} sesión{sesiones.length !== 1 ? "es" : ""} · bloquean el estudio en
            esas franjas
          </p>
          <div className="flex flex-wrap gap-1.5">
            {sesiones.map((s) => (
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
                  className="ml-0.5 text-muted-foreground/60 hover:text-destructive transition"
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
          Sin sesiones. Agregá al menos una para bloquear el estudio.
        </p>
      )}
    </div>
  );
}

// ── SesionesSection ───────────────────────────────────────────────────────────

function SesionesSection({ taller }: { taller: TallerAdmin }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [tipo, setTipo] = useState(taller.tipo_taller || "intensivo");
  const [sesiones, setSesiones] = useState<SesionBody[]>(taller.sesiones ?? []);

  useEffect(() => {
    setTipo(taller.tipo_taller || "intensivo");
    setSesiones(taller.sesiones ?? []);
  }, [taller.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const mut = useMutation({
    mutationFn: (body: UpdateBody) =>
      authedJson<TallerAdmin>(`/api/admin/talleres/${taller.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: (updated) => {
      toast.success("Sesiones guardadas");
      setEditing(false);
      qc.setQueryData(["admin", "talleres"], (prev: TallerAdmin[] | undefined) =>
        prev ? prev.map((t) => (t.id === updated.id ? { ...t, ...updated } : t)) : prev,
      );
    },
    onError: (e) => toast.error((e as Error).message),
  });

  function handleSave() {
    if (sesiones.length === 0) {
      toast.error("Agregá al menos una sesión");
      return;
    }
    mut.mutate({ tipo_taller: tipo, sesiones });
  }

  function handleCancel() {
    setTipo(taller.tipo_taller || "intensivo");
    setSesiones(taller.sesiones ?? []);
    setEditing(false);
  }

  return (
    <AdminSection storageKey="talleres:sesiones" title="Sesiones">
      {!editing ? (
        <div className="flex flex-col gap-4">
          {taller.sesiones && taller.sesiones.length > 0 ? (
            <TallerCalendario sesiones={taller.sesiones} horario={taller.horario} />
          ) : (
            <p className="text-sm text-muted-foreground italic">Sin sesiones cargadas.</p>
          )}
          <div className="flex justify-end">
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              Editar sesiones
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-5">
          <SesionAsistente
            tipo={tipo}
            onTipoChange={setTipo}
            sesiones={sesiones}
            onChange={setSesiones}
          />

          {sesiones.length > 0 && (
            <div className="pointer-events-none select-none">
              <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground mb-3">
                Preview
              </p>
              <TallerCalendario sesiones={sesiones} />
            </div>
          )}

          <div className="flex gap-2 justify-end pt-2">
            <Button variant="ghost" size="sm" onClick={handleCancel}>
              Cancelar
            </Button>
            <Button onClick={handleSave} disabled={mut.isPending} size="sm" className="gap-2">
              {mut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
              Guardar sesiones
            </Button>
          </div>
        </div>
      )}
    </AdminSection>
  );
}

// ── PagosSection ──────────────────────────────────────────────────────────────

function PagosSection({ taller }: { taller: TallerAdmin }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    horario: taller.horario ?? "",
    pago_alias: taller.pago_alias ?? "",
    pago_cbu: taller.pago_cbu ?? "",
    pago_banco: taller.pago_banco ?? "",
    direccion: taller.direccion ?? "",
    notif_email: taller.notif_email ?? false,
  });

  useEffect(() => {
    setForm({
      horario: taller.horario ?? "",
      pago_alias: taller.pago_alias ?? "",
      pago_cbu: taller.pago_cbu ?? "",
      pago_banco: taller.pago_banco ?? "",
      direccion: taller.direccion ?? "",
      notif_email: taller.notif_email ?? false,
    });
  }, [taller.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const mut = useMutation({
    mutationFn: (body: UpdateBody) =>
      authedJson<TallerAdmin>(`/api/admin/talleres/${taller.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: (updated) => {
      toast.success("Guardado");
      qc.setQueryData(["admin", "talleres"], (prev: TallerAdmin[] | undefined) =>
        prev ? prev.map((t) => (t.id === updated.id ? { ...t, ...updated } : t)) : prev,
      );
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const tf = (label: string, key: keyof typeof form) => (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
        {label}
      </label>
      <Input
        value={String(form[key])}
        onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
      />
    </div>
  );

  return (
    <AdminSection storageKey="talleres:pagos" title="Lugar y pagos">
      <div className="flex flex-col gap-4">
        <div className="grid sm:grid-cols-2 gap-4">
          {tf("Horario (texto libre)", "horario")}
          {tf("Dirección", "direccion")}
        </div>
        <div className="grid sm:grid-cols-3 gap-4">
          {tf("Alias de pago", "pago_alias")}
          {tf("CBU", "pago_cbu")}
          {tf("Banco", "pago_banco")}
        </div>
        <div className="flex items-center gap-3">
          <Switch
            checked={form.notif_email}
            onCheckedChange={(v) => setForm((f) => ({ ...f, notif_email: v }))}
          />
          <span className="text-sm text-muted-foreground">
            Enviar email de confirmación al inscribirse
          </span>
        </div>
        <div className="flex justify-end">
          <Button
            onClick={() => mut.mutate({ ...form })}
            disabled={mut.isPending}
            className="gap-2"
          >
            {mut.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Guardar
          </Button>
        </div>
      </div>
    </AdminSection>
  );
}

// ── FotoSection ───────────────────────────────────────────────────────────────

function FotoSection({ taller }: { taller: TallerAdmin }) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);

  async function handleUpload(file: File) {
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await authedFetch(`/api/admin/talleres/${taller.id}/upload-foto-instructor`, {
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
    <AdminSection storageKey="talleres:foto" title="Foto de instructora">
      <div className="flex items-start gap-6">
        {taller.instructor_foto_url ? (
          <img
            src={taller.instructor_foto_url}
            alt={taller.instructor_nombre}
            className="w-24 h-24 rounded-full object-cover object-top border border-border/40 shrink-0"
          />
        ) : (
          <div className="w-24 h-24 rounded-full bg-muted/40 border border-dashed border-border/60 flex items-center justify-center shrink-0">
            <span className="text-xs text-muted-foreground text-center px-2">Sin foto</span>
          </div>
        )}
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted-foreground">
            JPG, PNG o WebP · máx. 8 MB. Se muestra en la sección "Sobre" de la landing del
            workshop.
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
              {uploading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Upload className="h-3.5 w-3.5" />
              )}
              {taller.instructor_foto_url ? "Cambiar foto" : "Subir foto"}
            </Button>
          </div>
        </div>
      </div>
    </AdminSection>
  );
}

// ── ContenidoSection ──────────────────────────────────────────────────────────

function ContenidoSection({ taller }: { taller: TallerAdmin }) {
  const qc = useQueryClient();

  const [form, setForm] = useState({
    nombre: taller.nombre,
    subtitulo: taller.subtitulo,
    instructor_nombre: taller.instructor_nombre,
    descripcion: taller.descripcion,
    publico_objetivo: taller.publico_objetivo,
    instructor_bio: taller.instructor_bio,
    instructor_proyectos: taller.instructor_proyectos,
    programa_teorica: (taller.programa_teorica ?? []).join("\n"),
    programa_practica: (taller.programa_practica ?? []).join("\n"),
  });

  useEffect(() => {
    setForm({
      nombre: taller.nombre,
      subtitulo: taller.subtitulo,
      instructor_nombre: taller.instructor_nombre,
      descripcion: taller.descripcion,
      publico_objetivo: taller.publico_objetivo,
      instructor_bio: taller.instructor_bio,
      instructor_proyectos: taller.instructor_proyectos,
      programa_teorica: (taller.programa_teorica ?? []).join("\n"),
      programa_practica: (taller.programa_practica ?? []).join("\n"),
    });
  }, [taller.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const mut = useMutation({
    mutationFn: (body: UpdateBody) =>
      authedJson<TallerAdmin>(`/api/admin/talleres/${taller.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: (updated) => {
      toast.success("Guardado");
      qc.setQueryData(["admin", "talleres"], (prev: TallerAdmin[] | undefined) =>
        prev ? prev.map((t) => (t.id === updated.id ? { ...t, ...updated } : t)) : prev,
      );
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
    });
  }

  const field = (
    label: string,
    key: keyof typeof form,
    opts?: { rows?: number; hint?: string },
  ) => (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
        {label}
      </label>
      {opts?.hint && <p className="text-xs text-muted-foreground/70 -mt-1">{opts.hint}</p>}
      {(opts?.rows ?? 1) === 1 ? (
        <Input
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
    <AdminSection storageKey="talleres:contenido" title="Contenido del workshop">
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
        <div className="flex justify-end pt-2">
          <Button onClick={handleSave} disabled={mut.isPending} className="gap-2">
            {mut.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Guardar cambios
          </Button>
        </div>
      </div>
    </AdminSection>
  );
}

// ── PreciosSection ────────────────────────────────────────────────────────────

function PreciosSection({ taller }: { taller: TallerAdmin }) {
  const qc = useQueryClient();
  const [precioTotal, setPrecioTotal] = useState(String(taller.precio_total));
  const [precioSena, setPrecioSena] = useState(String(taller.precio_sena));
  const [cuposTotal, setCuposTotal] = useState(String(taller.cupos_total));

  useEffect(() => {
    setPrecioTotal(String(taller.precio_total));
    setPrecioSena(String(taller.precio_sena));
    setCuposTotal(String(taller.cupos_total));
  }, [taller.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const mut = useMutation({
    mutationFn: (body: UpdateBody) =>
      authedJson<TallerAdmin>(`/api/admin/talleres/${taller.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: (updated) => {
      toast.success("Precios actualizados");
      qc.setQueryData(["admin", "talleres"], (prev: TallerAdmin[] | undefined) =>
        prev ? prev.map((t) => (t.id === updated.id ? { ...t, ...updated } : t)) : prev,
      );
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
    if (cupos < taller.cupos_confirmados) {
      toast.error(
        `No podés bajar cupos a ${cupos}: hay ${taller.cupos_confirmados} confirmados`,
      );
      return;
    }
    mut.mutate({ precio_total: total, precio_sena: sena, cupos_total: cupos });
  }

  return (
    <AdminSection storageKey="talleres:precios" title="Precios y cupos">
      <div className="flex flex-col gap-4">
        {taller.cupos_confirmados >= taller.cupos_total && (
          <div className="rounded-lg bg-amber/10 border border-amber/30 px-4 py-3 text-sm text-amber-800">
            ⚠ Taller completo — {taller.cupos_confirmados}/{taller.cupos_total} cupos ocupados
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
            {mut.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Guardar
          </Button>
        </div>
      </div>
    </AdminSection>
  );
}

// ── InscripcionesSection ──────────────────────────────────────────────────────

function InscripcionesSection({
  taller,
  inscripciones,
  loading,
}: {
  taller: TallerAdmin;
  inscripciones: Inscripcion[];
  loading: boolean;
}) {
  const qc = useQueryClient();
  const [notifMsg, setNotifMsg] = useState("");
  const [notifOpen, setNotifOpen] = useState(false);

  const confirmadas = inscripciones.filter((i) => !i.en_lista_espera);
  const espera = inscripciones.filter((i) => i.en_lista_espera);

  const eliminarMut = useMutation({
    mutationFn: (insId: number) =>
      authedJson<TallerAdmin>(`/api/admin/talleres/${taller.id}/inscripciones/${insId}`, {
        method: "DELETE",
      }),
    onSuccess: (updated) => {
      toast.success("Inscripción eliminada");
      qc.setQueryData(["admin", "talleres"], (prev: TallerAdmin[] | undefined) =>
        prev ? prev.map((t) => (t.id === updated.id ? { ...t, ...updated } : t)) : prev,
      );
      qc.invalidateQueries({ queryKey: ["admin", "talleres", taller.id, "inscripciones"] });
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const confirmarMut = useMutation({
    mutationFn: (insId: number) =>
      authedJson<TallerAdmin>(
        `/api/admin/talleres/${taller.id}/inscripciones/${insId}/confirmar`,
        { method: "POST" },
      ),
    onSuccess: (updated) => {
      toast.success("Inscripción confirmada");
      qc.setQueryData(["admin", "talleres"], (prev: TallerAdmin[] | undefined) =>
        prev ? prev.map((t) => (t.id === updated.id ? { ...t, ...updated } : t)) : prev,
      );
      qc.invalidateQueries({ queryKey: ["admin", "talleres", taller.id, "inscripciones"] });
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const notificarMut = useMutation({
    mutationFn: (mensaje: string) =>
      authedJson<{ enviados: number; fallidos: number }>(
        `/api/admin/talleres/${taller.id}/notificar-cambios`,
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
      const res = await authedFetch(
        `/api/admin/talleres/${taller.id}/inscripciones/export-csv`,
      );
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `inscripciones-${taller.slug}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  function handleEliminar(ins: Inscripcion) {
    const label = ins.en_lista_espera ? "de lista de espera" : "confirmada";
    if (!window.confirm(`Eliminar inscripción ${label} de ${ins.nombre}?`)) return;
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

  const insTable = (rows: Inscripcion[], showConfirmar: boolean) => (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-left text-xs text-muted-foreground border-b border-border/60">
            <th className="pb-2 pr-4 font-medium">Nombre</th>
            <th className="pb-2 pr-4 font-medium">Email</th>
            <th className="pb-2 pr-4 font-medium">Teléfono</th>
            <th className="pb-2 pr-4 font-medium hidden lg:table-cell">Experiencia</th>
            <th className="pb-2 pr-4 font-medium">Comp.</th>
            <th className="pb-2 pr-4 font-medium">Fecha</th>
            <th className="pb-2 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((ins) => (
            <tr key={ins.id} className="border-b border-border/40 hover:bg-muted/20 transition">
              <td className="py-2.5 pr-4 font-medium text-ink">{ins.nombre}</td>
              <td className="py-2.5 pr-4 text-muted-foreground">
                <a href={`mailto:${ins.email}`} className="hover:text-ink transition">
                  {ins.email}
                </a>
              </td>
              <td className="py-2.5 pr-4 text-muted-foreground">{ins.telefono}</td>
              <td className="py-2.5 pr-4 text-muted-foreground hidden lg:table-cell max-w-[180px] truncate">
                {ins.experiencia || "—"}
              </td>
              <td className="py-2.5 pr-4">
                {ins.comprobante_url ? (
                  <a
                    href={ins.comprobante_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-ink hover:text-amber transition"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5 text-verde" strokeWidth={1.5} />
                    <ExternalLink className="h-3 w-3" />
                  </a>
                ) : (
                  <span className="text-muted-foreground/50 text-xs">—</span>
                )}
              </td>
              <td className="py-2.5 pr-4 text-muted-foreground text-xs">
                <span className="inline-flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {fmtDate(ins.created_at)}
                </span>
              </td>
              <td className="py-2.5">
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
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <>
      {confirmadas.length > 0 && (
        <AdminSection
          storageKey="talleres:confirmadas"
          title={`Inscripciones confirmadas (${confirmadas.length})`}
        >
          <div className="flex flex-col gap-3">
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
            {insTable(confirmadas, false)}
          </div>
        </AdminSection>
      )}

      {espera.length > 0 && (
        <AdminSection storageKey="talleres:espera" title={`Lista de espera (${espera.length})`}>
          {insTable(espera, true)}
        </AdminSection>
      )}

      {/* Notificar cambios dialog */}
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
              {notificarMut.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Bell className="h-4 w-4" />
              )}
              Enviar notificaciones
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ── EdicionesSection ──────────────────────────────────────────────────────────

function EdicionesSection({
  taller,
  onNuevaDuplica,
}: {
  taller: TallerAdmin;
  onNuevaDuplica: () => void;
}) {
  const qc = useQueryClient();
  const [proximaSlug, setProximaSlug] = useState(taller.proxima_edicion_slug ?? "");

  useEffect(() => {
    setProximaSlug(taller.proxima_edicion_slug ?? "");
  }, [taller.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const mut = useMutation({
    mutationFn: (proxima_edicion_slug: string) =>
      authedJson<TallerAdmin>(`/api/admin/talleres/${taller.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ proxima_edicion_slug }),
      }),
    onSuccess: (updated) => {
      toast.success("Guardado");
      qc.setQueryData(["admin", "talleres"], (prev: TallerAdmin[] | undefined) =>
        prev ? prev.map((t) => (t.id === updated.id ? { ...t, ...updated } : t)) : prev,
      );
    },
    onError: (e) => toast.error((e as Error).message),
  });

  return (
    <AdminSection storageKey="talleres:ediciones" title="Ediciones">
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-4 text-sm">
          <span className="text-muted-foreground">
            Edición actual:{" "}
            <strong className="text-ink">#{taller.numero_edicion}</strong>
          </span>
          <Link
            to="/workshops/$slug"
            params={{ slug: taller.slug }}
            target="_blank"
            className="inline-flex items-center gap-1 text-muted-foreground hover:text-ink transition text-xs"
          >
            ver en web <ExternalLink className="h-3 w-3" />
          </Link>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
            Slug de próxima edición
          </label>
          <p className="text-xs text-muted-foreground/70 -mt-1">
            Cuando esta edición está sold out, los visitantes verán un link a la próxima.
          </p>
          <div className="flex gap-2">
            <Input
              value={proximaSlug}
              onChange={(e) => setProximaSlug(e.target.value)}
              placeholder="Ej: direccion-de-arte-jime-troncoso-2"
              className="flex-1"
            />
            <Button
              variant="outline"
              onClick={() => mut.mutate(proximaSlug)}
              disabled={mut.isPending}
              size="sm"
            >
              {mut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Guardar"}
            </Button>
          </div>
        </div>

        <div className="pt-1">
          <Button variant="outline" size="sm" onClick={onNuevaDuplica} className="gap-2">
            <Plus className="h-3.5 w-3.5" />
            Nueva edición (duplicar este taller)
          </Button>
        </div>
      </div>
    </AdminSection>
  );
}

// ── NuevoTallerDialog ─────────────────────────────────────────────────────────

function NuevoTallerDialog({
  open,
  onClose,
  onSuccess,
  template,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: (slug: string) => void;
  template?: { nombre: string; instructor_nombre: string; tipo_taller: string };
}) {
  const [nombre, setNombre] = useState(template?.nombre ?? "");
  const [instructorNombre, setInstructorNombre] = useState(
    template?.instructor_nombre ?? "",
  );
  const [tipo, setTipo] = useState(template?.tipo_taller ?? "intensivo");
  const [sesiones, setSesiones] = useState<SesionBody[]>([]);
  const [cupos, setCupos] = useState("12");
  const [precioTotal, setPrecioTotal] = useState("0");
  const [precioSena, setPrecioSena] = useState("0");

  useEffect(() => {
    if (open) {
      setNombre(template?.nombre ?? "");
      setInstructorNombre(template?.instructor_nombre ?? "");
      setTipo(template?.tipo_taller ?? "intensivo");
      setSesiones([]);
      setCupos("12");
      setPrecioTotal("0");
      setPrecioSena("0");
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const mut = useMutation({
    mutationFn: (body: CreateBody) =>
      authedJson<TallerAdmin>("/api/admin/talleres", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: (created) => {
      toast.success(`Taller creado: ${created.nombre}`);
      onSuccess(created.slug);
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
    if (sesiones.length === 0) {
      toast.error("Agregá al menos una sesión");
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
      tipo_taller: tipo,
      sesiones,
      cupos_total: c,
      precio_total: pt,
      precio_sena: ps,
    });
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {template ? "Nueva edición (duplicar taller)" : "Nuevo taller"}
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-5 py-2">
          {template && (
            <div className="rounded-lg bg-muted/30 border border-border/50 px-4 py-3 text-sm text-muted-foreground">
              Copiando datos de <strong className="text-ink">{template.nombre}</strong>. Cambiá
              las sesiones para la nueva edición.
            </div>
          )}

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
              Sesiones *
            </p>
            <SesionAsistente
              tipo={tipo}
              onTipoChange={setTipo}
              sesiones={sesiones}
              onChange={setSesiones}
            />
            {sesiones.length > 0 && (
              <div className="mt-4 pointer-events-none select-none">
                <TallerCalendario sesiones={sesiones} />
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
            {mut.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            {template ? "Crear nueva edición" : "Crear taller"}
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
  const [tallerSeleccionado, setTallerSeleccionado] = useState<number | null>(null);
  const [nuevoOpen, setNuevoOpen] = useState(false);
  const [duplicaTemplate, setDuplicaTemplate] = useState<
    { nombre: string; instructor_nombre: string; tipo_taller: string } | undefined
  >(undefined);
  const [duplicaFromId, setDuplicaFromId] = useState<number | null>(null);

  const { data: talleres = [], isLoading: loadingTalleres } = useQuery({
    queryKey: ["admin", "talleres"],
    queryFn: () => authedJson<TallerAdmin[]>("/api/admin/talleres"),
    staleTime: 1000 * 60,
  });

  const tallerActivo = tallerSeleccionado ?? talleres[0]?.id ?? null;

  const { data: inscripciones = [], isLoading: loadingIns } = useQuery({
    queryKey: ["admin", "talleres", tallerActivo, "inscripciones"],
    queryFn: () =>
      tallerActivo
        ? authedJson<Inscripcion[]>(`/api/admin/talleres/${tallerActivo}/inscripciones`)
        : Promise.resolve([] as Inscripcion[]),
    enabled: !!tallerActivo,
    staleTime: 1000 * 30,
  });

  const toggleActivoMut = useMutation({
    mutationFn: ({ id, activo }: { id: number; activo: boolean }) =>
      authedJson<TallerAdmin>(`/api/admin/talleres/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ activo }),
      }),
    onSuccess: (updated) => {
      toast.success(updated.activo ? "Taller activado" : "Taller desactivado");
      qc.setQueryData(["admin", "talleres"], (prev: TallerAdmin[] | undefined) =>
        prev ? prev.map((t) => (t.id === updated.id ? { ...t, ...updated } : t)) : prev,
      );
    },
    onError: (e) => toast.error((e as Error).message),
  });

  function handleToggleActivo(t: TallerAdmin, newActivo: boolean) {
    if (!newActivo && t.cupos_confirmados > 0) {
      const ok = window.confirm(
        `¿Desactivar "${t.nombre}"?\n\n` +
          `Hay ${t.cupos_confirmados} inscriptos confirmados. Al desactivar:\n` +
          `• El taller desaparece de la web pública\n` +
          `• Se libera el bloqueo del estudio en esas fechas\n\n` +
          `¿Confirmar?`,
      );
      if (!ok) return;
    }
    toggleActivoMut.mutate({ id: t.id, activo: newActivo });
  }

  function handleNuevaDuplica(taller: TallerAdmin) {
    setDuplicaTemplate({
      nombre: taller.nombre,
      instructor_nombre: taller.instructor_nombre,
      tipo_taller: taller.tipo_taller,
    });
    setDuplicaFromId(taller.id);
    setNuevoOpen(true);
  }

  async function handleNuevoSuccess(slug: string) {
    qc.invalidateQueries({ queryKey: ["admin", "talleres"] });
    setNuevoOpen(false);
    setDuplicaTemplate(undefined);

    // Auto-link proxima_edicion_slug if duplicating and original has none
    if (duplicaFromId !== null) {
      const original = talleres.find((t) => t.id === duplicaFromId);
      if (original && !original.proxima_edicion_slug) {
        try {
          await authedJson(`/api/admin/talleres/${duplicaFromId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ proxima_edicion_slug: slug }),
          });
          qc.invalidateQueries({ queryKey: ["admin", "talleres"] });
          toast.success("Link a la nueva edición configurado automáticamente");
        } catch {
          // non-critical
        }
      }
      setDuplicaFromId(null);
    }
  }

  function handleNuevoClean() {
    setNuevoOpen(true);
    setDuplicaTemplate(undefined);
    setDuplicaFromId(null);
  }

  const taller = talleres.find((t) => t.id === tallerActivo);

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Users className="h-5 w-5 text-muted-foreground" />
          <h1 className="text-xl font-semibold text-ink">Talleres</h1>
        </div>
        <Button size="sm" className="gap-2" onClick={handleNuevoClean}>
          <Plus className="h-4 w-4" />
          Nuevo taller
        </Button>
      </div>

      {loadingTalleres && <p className="text-sm text-muted-foreground">Cargando talleres…</p>}

      {/* Lista de talleres */}
      {talleres.length > 0 && (
        <div className="flex flex-col gap-2">
          {talleres.map((t) => {
            const badge = badgeEstado(t);
            return (
              <div
                key={t.id}
                className={`flex items-center gap-3 rounded-xl border px-4 py-3 transition cursor-pointer ${
                  t.id === tallerActivo
                    ? "border-ink/30 bg-ink/5"
                    : "border-border/60 hover:border-border hover:bg-muted/10"
                }`}
                onClick={() => setTallerSeleccionado(t.id)}
              >
                {/* Badge */}
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold font-mono uppercase tracking-wider ${badge.className}`}
                >
                  {badge.label}
                </span>

                {/* Nombre */}
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-ink text-sm truncate">{t.nombre}</p>
                  <p className="text-xs text-muted-foreground truncate">{t.instructor_nombre}</p>
                </div>

                {/* Fechas */}
                {t.fecha_inicio && (
                  <span className="hidden sm:block text-xs text-muted-foreground shrink-0">
                    {new Date(t.fecha_inicio + "T12:00:00").toLocaleDateString("es-AR", {
                      day: "numeric",
                      month: "short",
                    })}
                  </span>
                )}

                {/* Actions */}
                <div
                  className="flex items-center gap-2 shrink-0"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="flex items-center gap-1.5">
                    {t.activo ? (
                      <Eye className="h-3.5 w-3.5 text-muted-foreground" />
                    ) : (
                      <EyeOff className="h-3.5 w-3.5 text-muted-foreground/50" />
                    )}
                    <Switch
                      checked={t.activo}
                      onCheckedChange={(v) => handleToggleActivo(t, v)}
                      disabled={toggleActivoMut.isPending}
                    />
                  </div>
                  <a
                    href={`/workshops/${t.slug}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-1 rounded text-muted-foreground hover:text-ink transition"
                    title="Ver en web"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {talleres.length === 0 && !loadingTalleres && (
        <div className="rounded-xl border border-dashed border-border/60 py-16 text-center">
          <p className="text-sm text-muted-foreground mb-4">No hay talleres todavía.</p>
          <Button size="sm" onClick={handleNuevoClean} className="gap-2">
            <Plus className="h-4 w-4" />
            Crear el primero
          </Button>
        </div>
      )}

      {/* Detalle del taller seleccionado */}
      {taller && (
        <>
          <SesionesSection taller={taller} />
          <PagosSection taller={taller} />
          <FotoSection taller={taller} />
          <ContenidoSection taller={taller} />
          <PreciosSection taller={taller} />
          <InscripcionesSection
            taller={taller}
            inscripciones={inscripciones}
            loading={loadingIns}
          />
          <EdicionesSection taller={taller} onNuevaDuplica={() => handleNuevaDuplica(taller)} />
        </>
      )}

      {/* Dialogs */}
      <NuevoTallerDialog
        open={nuevoOpen}
        onClose={() => {
          setNuevoOpen(false);
          setDuplicaTemplate(undefined);
          setDuplicaFromId(null);
        }}
        onSuccess={handleNuevoSuccess}
        template={duplicaTemplate}
      />
    </div>
  );
}
