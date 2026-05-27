import { useState } from "react";
import { createLazyFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus, Trash2, Save, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { PhotoGallery, type GalleryFoto } from "@/components/common/PhotoGallery";
import { estudioAdminApi, type EstudioConfig, type FotoOrdenItem } from "@/lib/admin/api";
import { uploadStudioFile } from "@/lib/studio/photos";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/estudio/")({
  component: EstudioAdminPage,
});

// ── Schema ────────────────────────────────────────────────────────────────────

const featureSchema = z.object({
  label: z.string().min(1, "Requerido"),
  value: z.string().min(1, "Requerido"),
});

const faqSchema = z.object({
  q: z.string().min(1, "Requerido"),
  a: z.string().min(1, "Requerido"),
});

const schema = z.object({
  nombre: z.string().min(1, "Requerido"),
  tagline: z.string(),
  descripcion: z.string(),
  precio_hora: z.coerce.number().int().min(0),
  min_horas: z.coerce.number().int().min(1),
  open_hour: z.coerce.number().int().min(0).max(23),
  close_hour: z.coerce.number().int().min(1).max(24),
  buffer_horas: z.coerce.number().int().min(0),
  anticipacion_min_horas: z.coerce.number().int().min(0),
  pack_activo: z.boolean(),
  pack_nombre: z.string(),
  pack_descripcion: z.string(),
  pack_precio: z.coerce.number().int().min(0),
  features: z.array(featureSchema),
  faq: z.array(faqSchema),
});

type FormValues = z.infer<typeof schema>;

function configToForm(c: EstudioConfig): FormValues {
  return {
    nombre: c.nombre,
    tagline: c.tagline,
    descripcion: c.descripcion,
    precio_hora: c.precio_hora,
    min_horas: c.min_horas,
    open_hour: c.open_hour,
    close_hour: c.close_hour,
    buffer_horas: c.buffer_horas,
    anticipacion_min_horas: c.anticipacion_min_horas,
    pack_activo: c.pack_activo,
    pack_nombre: c.pack_nombre,
    pack_descripcion: c.pack_descripcion,
    pack_precio: c.pack_precio,
    features: c.features ?? [],
    faq: c.faq ?? [],
  };
}

// ── Page ──────────────────────────────────────────────────────────────────────

function EstudioAdminPage() {
  useDocumentTitle("Estudio · Back Office");
  const qc = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin", "estudio"],
    queryFn: () => estudioAdminApi.get(),
  });

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="px-4 py-8 text-center text-sm text-muted-foreground">
        Error cargando configuración del estudio.
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 md:px-6 py-6 space-y-8">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office
        </div>
        <h1 className="font-display text-3xl text-ink">Estudio</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Configuración del espacio, precios y galería de fotos.
        </p>
      </header>

      <ConfigForm
        config={data}
        onSaved={() => qc.invalidateQueries({ queryKey: ["admin", "estudio"] })}
      />

      <GaleriaSection
        fotos={data.fotos}
        onChanged={() => qc.invalidateQueries({ queryKey: ["admin", "estudio"] })}
      />
    </div>
  );
}

// ── Formulario de configuración ───────────────────────────────────────────────

function ConfigForm({ config, onSaved }: { config: EstudioConfig; onSaved: () => void }) {
  const {
    register,
    handleSubmit,
    control,
    watch,
    formState: { errors, isDirty },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: configToForm(config),
  });

  const featuresArr = useFieldArray({ control, name: "features" });
  const faqArr = useFieldArray({ control, name: "faq" });

  const packActivo = watch("pack_activo");

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      estudioAdminApi.update({
        ...values,
        features_json: JSON.stringify(values.features),
        faq_json: JSON.stringify(values.faq),
      }),
    onSuccess: () => {
      toast.success("Estudio guardado");
      onSaved();
    },
    onError: (e) => toast.error("Error guardando", { description: (e as Error).message }),
  });

  return (
    <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-8">
      {/* ── Datos generales ── */}
      <Section title="Datos generales">
        <Field label="Nombre" error={errors.nombre?.message}>
          <Input {...register("nombre")} placeholder="El Estudio" />
        </Field>
        <Field label="Tagline" error={errors.tagline?.message}>
          <Input {...register("tagline")} placeholder="Foto y video en Mar del Plata" />
        </Field>
        <Field label="Descripción" error={errors.descripcion?.message}>
          <Textarea {...register("descripcion")} rows={3} />
        </Field>
      </Section>

      {/* ── Precios y horarios ── */}
      <Section title="Precios y horarios">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Field label="Precio por hora ($)" error={errors.precio_hora?.message}>
            <Input type="number" min={0} {...register("precio_hora")} />
          </Field>
          <Field label="Mínimo de horas" error={errors.min_horas?.message}>
            <Input type="number" min={1} {...register("min_horas")} />
          </Field>
          <Field label="Buffer entre reservas (h)" error={errors.buffer_horas?.message}>
            <Input type="number" min={0} {...register("buffer_horas")} />
          </Field>
          <Field label="Anticipación mínima (h)" error={errors.anticipacion_min_horas?.message}>
            <Input type="number" min={0} {...register("anticipacion_min_horas")} />
          </Field>
          <Field label="Apertura (hora)" error={errors.open_hour?.message}>
            <Input type="number" min={0} max={23} {...register("open_hour")} />
          </Field>
          <Field label="Cierre (hora)" error={errors.close_hour?.message}>
            <Input type="number" min={1} max={24} {...register("close_hour")} />
          </Field>
        </div>
      </Section>

      {/* ── Pack ── */}
      <Section title="Pack Todo Incluido">
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" {...register("pack_activo")} className="h-4 w-4 rounded" />
          Pack activo (se muestra en la página pública)
        </label>
        {packActivo && (
          <div className="space-y-3 mt-3">
            <Field label="Nombre del pack" error={errors.pack_nombre?.message}>
              <Input {...register("pack_nombre")} />
            </Field>
            <Field label="Descripción del pack" error={errors.pack_descripcion?.message}>
              <Textarea {...register("pack_descripcion")} rows={2} />
            </Field>
            <Field label="Precio del pack ($)" error={errors.pack_precio?.message}>
              <Input type="number" min={0} {...register("pack_precio")} />
            </Field>
          </div>
        )}
      </Section>

      {/* ── Características ── */}
      <Section title="Características">
        <p className="text-xs text-muted-foreground mb-3">
          Aparecen en el grid de la página pública.
        </p>
        <div className="space-y-2">
          {featuresArr.fields.map((f, i) => (
            <div key={f.id} className="flex gap-2 items-start">
              <Input
                {...register(`features.${i}.label`)}
                placeholder="Superficie"
                className="w-36 shrink-0"
              />
              <Input {...register(`features.${i}.value`)} placeholder="— m²" />
              <button
                type="button"
                onClick={() => featuresArr.remove(i)}
                className="mt-2 text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-2"
          onClick={() => featuresArr.append({ label: "", value: "" })}
        >
          <Plus className="h-3.5 w-3.5 mr-1" /> Añadir característica
        </Button>
      </Section>

      {/* ── FAQ ── */}
      <Section title="Preguntas frecuentes">
        <div className="space-y-3">
          {faqArr.fields.map((f, i) => (
            <div key={f.id} className="rounded-xl border hairline p-3 space-y-2">
              <div className="flex items-start gap-2">
                <Input {...register(`faq.${i}.q`)} placeholder="Pregunta" className="flex-1" />
                <button
                  type="button"
                  onClick={() => faqArr.remove(i)}
                  className="mt-2 text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              <Textarea {...register(`faq.${i}.a`)} placeholder="Respuesta" rows={2} />
            </div>
          ))}
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-2"
          onClick={() => faqArr.append({ q: "", a: "" })}
        >
          <Plus className="h-3.5 w-3.5 mr-1" /> Añadir pregunta
        </Button>
      </Section>

      {/* ── Submit ── */}
      <div className="sticky bottom-0 bg-background border-t hairline -mx-4 md:-mx-6 px-4 md:px-6 py-3 flex justify-end gap-3">
        <Button
          type="submit"
          disabled={mutation.isPending || !isDirty}
          className="bg-foreground text-background hover:bg-amber hover:text-ink"
        >
          {mutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <Save className="h-4 w-4 mr-2" />
          )}
          Guardar
        </Button>
      </div>
    </form>
  );
}

// ── Galería ───────────────────────────────────────────────────────────────────

function GaleriaSection({
  fotos,
  onChanged,
}: {
  fotos: Array<{ id: number; url: string; orden: number; es_principal: boolean }>;
  onChanged: () => void;
}) {
  const qc = useQueryClient();
  const [uploading, setUploading] = useState(false);

  async function handleUpload(files: FileList) {
    setUploading(true);
    try {
      const uploads = Array.from(files).map((f) => uploadStudioFile(f));
      await Promise.all(uploads);
      toast.success(files.length === 1 ? "Foto subida" : `${files.length} fotos subidas`);
      onChanged();
    } catch (e) {
      toast.error("Error subiendo foto", { description: (e as Error).message });
    } finally {
      setUploading(false);
    }
  }

  const deleteMut = useMutation({
    mutationFn: (id: number) => estudioAdminApi.deleteFoto(id),
    onSuccess: () => {
      toast.success("Foto eliminada");
      onChanged();
    },
    onError: (e) => toast.error("Error eliminando", { description: (e as Error).message }),
  });

  const reorderMut = useMutation({
    mutationFn: (items: FotoOrdenItem[]) => estudioAdminApi.reorderFotos(items),
    onSuccess: (data) => {
      qc.setQueryData(["admin", "estudio"], (old: EstudioConfig | undefined) =>
        old ? { ...old, fotos: data.fotos } : old,
      );
    },
    onError: (e) => toast.error("Error reordenando", { description: (e as Error).message }),
  });

  function handleReorder(reordered: GalleryFoto[]) {
    reorderMut.mutate(
      reordered.map((f) => ({ id: f.id, orden: f.orden, es_principal: f.es_principal })),
    );
  }

  function handleSetPrincipal(id: number) {
    const updated = fotos.map((f) => ({ id: f.id, orden: f.orden, es_principal: f.id === id }));
    reorderMut.mutate(updated);
  }

  return (
    <Section title="Galería de fotos">
      <p className="text-xs text-muted-foreground mb-4">
        La primera foto marcada como principal aparece en el hero de la página pública.
      </p>
      <PhotoGallery
        fotos={fotos}
        onUpload={handleUpload}
        onDelete={(id) => deleteMut.mutate(id)}
        onReorder={handleReorder}
        onSetPrincipal={handleSetPrincipal}
        uploading={uploading}
        disabled={deleteMut.isPending || reorderMut.isPending}
      />
    </Section>
  );
}

// ── Helpers de UI ─────────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border hairline bg-surface p-5 space-y-4">
      <h2 className="font-display text-lg text-ink">{title}</h2>
      {children}
    </section>
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
    <div className="space-y-1">
      <label className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
        {label}
      </label>
      {children}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
