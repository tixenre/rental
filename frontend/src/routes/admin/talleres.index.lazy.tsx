import { useEffect, useRef, useState } from "react";
import { createLazyFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Users, ExternalLink, Clock, CheckCircle2, Upload, Loader2, Save } from "lucide-react";
import { toast } from "sonner";

import { authedFetch, authedJson } from "@/lib/authedFetch";
import { useDocumentTitle } from "@/lib/use-document-title";
import { AdminSection } from "@/components/admin/AdminSection";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { formatARS } from "@/lib/format";

export const Route = createLazyFileRoute("/admin/talleres/")({
  component: TalleresAdminPage,
});

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
  cupos_total: number;
  cupos_confirmados: number;
  cupos_disponibles: number;
  precio_total: number;
  activo: boolean;
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
  instructor_bio?: string;
  instructor_proyectos?: string;
  programa_teorica?: string[];
  programa_practica?: string[];
};

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
              {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
              {taller.instructor_foto_url ? "Cambiar foto" : "Subir foto"}
            </Button>
          </div>
        </div>
      </div>
    </AdminSection>
  );
}

function ContenidoSection({ taller }: { taller: TallerAdmin }) {
  const qc = useQueryClient();

  const [form, setForm] = useState({
    nombre: taller.nombre,
    subtitulo: taller.subtitulo,
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
      descripcion: taller.descripcion,
      publico_objetivo: taller.publico_objetivo,
      instructor_bio: taller.instructor_bio,
      instructor_proyectos: taller.instructor_proyectos,
      programa_teorica: (taller.programa_teorica ?? []).join("\n"),
      programa_practica: (taller.programa_practica ?? []).join("\n"),
    });
  }, [taller.id]);

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
    const body: UpdateBody = {
      nombre: form.nombre,
      subtitulo: form.subtitulo,
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
    };
    mut.mutate(body);
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
          value={form[key]}
          onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
        />
      ) : (
        <textarea
          rows={opts?.rows}
          value={form[key]}
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
        {field("Descripción", "descripcion", { rows: 4 })}
        {field("¿Para quiénes?", "publico_objetivo", {
          rows: 3,
          hint: "Texto que aparece en el box 'Orientado a'",
        })}
        {field("Bio de la instructora", "instructor_bio", { rows: 4 })}
        {field("Proyectos (separados por coma)", "instructor_proyectos", {
          rows: 3,
          hint: "Cada nombre separado por coma. Se muestran como pills.",
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

function TalleresAdminPage() {
  useDocumentTitle("Talleres — Admin");
  const [tallerSeleccionado, setTallerSeleccionado] = useState<number | null>(null);

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

  const taller = talleres.find((t) => t.id === tallerActivo);
  const confirmadas = inscripciones.filter((i) => !i.en_lista_espera);
  const espera = inscripciones.filter((i) => i.en_lista_espera);

  const fmtDate = (iso: string | null) => {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString("es-AR", {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <Users className="h-5 w-5 text-muted-foreground" />
        <h1 className="text-xl font-semibold text-ink">Talleres</h1>
      </div>

      {loadingTalleres && <p className="text-sm text-muted-foreground">Cargando talleres…</p>}

      {talleres.length > 1 && (
        <div className="flex flex-wrap gap-2">
          {talleres.map((t) => (
            <button
              key={t.id}
              onClick={() => setTallerSeleccionado(t.id)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
                t.id === tallerActivo
                  ? "bg-ink text-amber"
                  : "bg-muted/40 text-muted-foreground hover:text-ink"
              }`}
            >
              {t.nombre}
            </button>
          ))}
        </div>
      )}

      {taller && (
        <AdminSection storageKey="talleres:info" title={`${taller.nombre} ${taller.subtitulo}`}>
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-foreground">
            <span>
              <span className="text-ink font-medium">{taller.cupos_confirmados}</span>/
              {taller.cupos_total} cupos confirmados
            </span>
            {taller.cupos_disponibles > 0 ? (
              <span className="text-verde-ink">{taller.cupos_disponibles} disponibles</span>
            ) : (
              <span className="text-amber">Sin cupos — lista de espera activa</span>
            )}
            <span>Precio: {formatARS(taller.precio_total)}</span>
            <span>
              {new Date(taller.fecha_inicio + "T12:00:00").toLocaleDateString("es-AR", {
                day: "numeric",
                month: "long",
              })}
              {" y "}
              {new Date(taller.fecha_fin + "T12:00:00").toLocaleDateString("es-AR", {
                day: "numeric",
                month: "long",
              })}
            </span>
          </div>
        </AdminSection>
      )}

      {taller && <FotoSection taller={taller} />}
      {taller && <ContenidoSection taller={taller} />}

      {loadingIns && <p className="text-sm text-muted-foreground">Cargando inscripciones…</p>}

      {!loadingIns && inscripciones.length === 0 && tallerActivo && (
        <div className="rounded-xl border border-dashed border-border/60 py-12 text-center text-sm text-muted-foreground">
          No hay inscripciones todavía.
        </div>
      )}

      {confirmadas.length > 0 && (
        <AdminSection
          storageKey="talleres:confirmadas"
          title={`Inscripciones confirmadas (${confirmadas.length})`}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-xs text-muted-foreground border-b border-border/60">
                  <th className="pb-2 pr-4 font-medium">Nombre</th>
                  <th className="pb-2 pr-4 font-medium">Email</th>
                  <th className="pb-2 pr-4 font-medium">Teléfono</th>
                  <th className="pb-2 pr-4 font-medium hidden lg:table-cell">Experiencia</th>
                  <th className="pb-2 pr-4 font-medium">Comprobante</th>
                  <th className="pb-2 font-medium">Fecha</th>
                </tr>
              </thead>
              <tbody>
                {confirmadas.map((ins) => (
                  <tr
                    key={ins.id}
                    className="border-b border-border/40 hover:bg-muted/20 transition"
                  >
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
                        <span className="text-muted-foreground/50 text-xs">Sin adjunto</span>
                      )}
                    </td>
                    <td className="py-2.5 text-muted-foreground text-xs">
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {fmtDate(ins.created_at)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </AdminSection>
      )}

      {espera.length > 0 && (
        <AdminSection storageKey="talleres:espera" title={`Lista de espera (${espera.length})`}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-xs text-muted-foreground border-b border-border/60">
                  <th className="pb-2 pr-4 font-medium">Nombre</th>
                  <th className="pb-2 pr-4 font-medium">Email</th>
                  <th className="pb-2 pr-4 font-medium">Teléfono</th>
                  <th className="pb-2 font-medium">Fecha</th>
                </tr>
              </thead>
              <tbody>
                {espera.map((ins) => (
                  <tr
                    key={ins.id}
                    className="border-b border-border/40 hover:bg-muted/20 transition"
                  >
                    <td className="py-2.5 pr-4 font-medium text-ink">{ins.nombre}</td>
                    <td className="py-2.5 pr-4 text-muted-foreground">
                      <a href={`mailto:${ins.email}`} className="hover:text-ink transition">
                        {ins.email}
                      </a>
                    </td>
                    <td className="py-2.5 pr-4 text-muted-foreground">{ins.telefono}</td>
                    <td className="py-2.5 text-muted-foreground text-xs">
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {fmtDate(ins.created_at)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </AdminSection>
      )}
    </div>
  );
}
