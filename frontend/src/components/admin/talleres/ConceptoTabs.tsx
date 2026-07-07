import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Save, Upload } from "lucide-react";
import { toast } from "sonner";

import { talleresAdminApi } from "@/lib/admin/api/talleres";
import type { TallerConcepto } from "@/lib/admin/api/types";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { Textarea } from "@/design-system/ui/textarea";
import { Spinner } from "@/design-system/ui/spinner";
import { updateConceptoInCache } from "./cache";

export function FotoSection({ concepto }: { concepto: TallerConcepto }) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);

  async function handleUpload(file: File) {
    setUploading(true);
    try {
      await talleresAdminApi.uploadFotoInstructor(concepto.id, file);
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
          {/* eslint-disable-next-line no-restricted-syntax -- input file: no hay componente DS */}
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

export function ContenidoSection({ concepto }: { concepto: TallerConcepto }) {
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
    mutationFn: (body: object) => talleresAdminApi.updateConcepto(concepto.id, body),
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
        <Textarea
          rows={opts?.rows}
          value={form[key] as string}
          onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
          className="resize-y"
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
