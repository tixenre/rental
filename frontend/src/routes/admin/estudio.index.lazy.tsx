import { useEffect, useRef, useState } from "react";
import { createLazyFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Plus,
  Trash2,
  Save,
  Loader2,
  Package,
  Search,
  GripVertical,
  Pencil,
  Eye,
  EyeOff,
  Film,
  Image,
  X,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { Button } from "@/design-system/ui/button";
import { Pill } from "@/design-system/kit/Pill";
import { Input } from "@/design-system/ui/input";
import { Textarea } from "@/design-system/ui/textarea";
import { cn } from "@/lib/utils";
import { formatARS } from "@/lib/format";
import { PhotoGallery, type GalleryFoto } from "@/components/common/PhotoGallery";
import {
  adminApi,
  estudioAdminApi,
  trabajosAdminApi,
  type EstudioConfig,
  type EstudioTrabajo,
  type EstudioTrabajoInput,
  type FotoOrdenItem,
  type EstudioSlotFijo,
} from "@/lib/admin/api";
import { uploadStudioFile } from "@/lib/studio/photos";
import { useDocumentTitle } from "@/lib/use-document-title";
import { AdminPage } from "@/components/admin/AdminPage";
import { AdminSection } from "@/components/admin/AdminSection";
import { useConfirm } from "@/components/admin/useConfirm";

export const Route = createLazyFileRoute("/admin/estudio/")({
  component: EstudioAdminPage,
});

// Clasifica un link externo para el ícono y el payload (el backend re-detecta).
function linkTipo(url: string): "youtube" | "instagram" | null {
  if (!url) return null;
  if (/youtu/.test(url)) return "youtube";
  if (/instagram\.com/.test(url)) return "instagram";
  return null;
}

// Ícono de Instagram (lucide no trae el glifo de marca).
function IgGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor">
      <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
    </svg>
  );
}

// ── Schema ────────────────────────────────────────────────────────────────────

// El value puede estar vacío: features con value en blanco se ocultan en
// público (filtro en /estudio.tsx) y quedan listadas en admin para que el
// dueño las complete cuando quiera. Si forzamos `min(1)` acá, el submit
// silenciosamente falla validación (button "Guardar" no dispara nada).
const featureSchema = z.object({
  label: z.string().min(1, "Requerido"),
  value: z.string(),
});

// FAQ y testimonios: schemas permisivos. Si el dueño hace "Añadir" y deja la
// fila vacía sin completar, NO bloqueamos el guardado — las filas totalmente
// vacías se filtran en el handler de submit (`stripEmpty`). El filtro defensivo
// también vive en `/estudio.tsx` (front público) por si llegara algo basura.
const faqSchema = z.object({
  q: z.string(),
  a: z.string(),
});

const testimonioSchema = z.object({
  autor: z.string(),
  texto: z.string(),
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
  direccion: z.string(),
  como_llegar: z.string(),
  mapa_url: z.string(),
  testimonios: z.array(testimonioSchema),
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
    direccion: c.direccion,
    como_llegar: c.como_llegar,
    mapa_url: c.mapa_url,
    testimonios: c.testimonios ?? [],
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
    <AdminPage
      title="Estudio"
      maxW="max-w-3xl"
      description="Configuración del espacio, precios y galería de fotos."
    >
      <div className="space-y-8">
        <ConfigForm
          config={data}
          onSaved={() => qc.invalidateQueries({ queryKey: ["admin", "estudio"] })}
        />

        <PackSection />

        <GaleriaSection
          fotos={data.fotos}
          onChanged={() => qc.invalidateQueries({ queryKey: ["admin", "estudio"] })}
        />

        <TrabajosSection
          trabajos={data.trabajos ?? []}
          onChanged={() => qc.invalidateQueries({ queryKey: ["admin", "estudio"] })}
        />

        <SlotsSection />
      </div>
    </AdminPage>
  );
}

// ── Pack curado (v2-C) ──────────────────────────────────────────────────────────

function PackSection() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<{ id: number; nombre: string; marca: string | null }[]>(
    [],
  );
  const [searching, setSearching] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "estudio", "pack"],
    queryFn: () => estudioAdminApi.listPack(),
  });

  const pack = data?.pack ?? [];
  const packIds = new Set(pack.map((p) => p.id));

  const addMut = useMutation({
    mutationFn: (id: number) => estudioAdminApi.addPackEquipo(id),
    onSuccess: (res) => {
      qc.setQueryData(["admin", "estudio", "pack"], res);
    },
    onError: (e) => toast.error("No se pudo agregar", { description: (e as Error).message }),
  });

  const removeMut = useMutation({
    mutationFn: (id: number) => estudioAdminApi.removePackEquipo(id),
    onSuccess: (res) => {
      qc.setQueryData(["admin", "estudio", "pack"], res);
    },
    onError: (e) => toast.error("No se pudo quitar", { description: (e as Error).message }),
  });

  useEffect(() => {
    const q = search.trim();
    if (q.length < 2) {
      setResults([]);
      return;
    }
    let cancelado = false;
    setSearching(true);
    const t = setTimeout(() => {
      adminApi
        .listEquipos({ q, per_page: 15 })
        .then((r) => {
          if (!cancelado)
            setResults(r.items.map((e) => ({ id: e.id, nombre: e.nombre, marca: e.marca })));
        })
        .catch(() => {
          if (!cancelado) setResults([]);
        })
        .finally(() => {
          if (!cancelado) setSearching(false);
        });
    }, 250);
    return () => {
      cancelado = true;
      clearTimeout(t);
    };
  }, [search]);

  return (
    <Section title="Pack (equipos incluidos)">
      <p className="-mt-2 mb-3 text-sm text-muted-foreground">
        Elegí a mano qué equipos integran el pack. En cada franja se ofrecen solo los que estén
        disponibles — un equipo ocupado no se ofrece, pero no bloquea la reserva.
      </p>

      {/* Buscador */}
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar equipo para agregar…"
          className="pl-9"
        />
      </div>
      {search.trim().length >= 2 && (
        <div className="mt-2 max-h-60 space-y-1 overflow-y-auto rounded-lg border hairline p-1">
          {searching && <div className="px-2 py-1.5 text-sm text-muted-foreground">Buscando…</div>}
          {!searching && results.length === 0 && (
            <div className="px-2 py-1.5 text-sm text-muted-foreground">Sin resultados.</div>
          )}
          {results.map((e) => {
            const yaEsta = packIds.has(e.id);
            return (
              <button
                key={e.id}
                type="button"
                disabled={yaEsta || addMut.isPending}
                onClick={() => addMut.mutate(e.id)}
                className="flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted disabled:opacity-50"
              >
                <span>
                  {e.marca && <span className="text-muted-foreground">{e.marca} · </span>}
                  {e.nombre}
                </span>
                {yaEsta ? (
                  <span className="text-xs text-muted-foreground">Ya está</span>
                ) : (
                  <Plus className="h-4 w-4 shrink-0" />
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Lista actual */}
      <div className="mt-4 space-y-2">
        {isLoading ? (
          <div className="text-sm text-muted-foreground">Cargando…</div>
        ) : pack.length === 0 ? (
          <p className="text-sm text-muted-foreground">Todavía no hay equipos en el pack.</p>
        ) : (
          pack.map((p) => (
            <div
              key={p.id}
              className="flex items-center gap-3 rounded-lg border hairline px-3 py-2 text-sm"
            >
              <div className="relative aspect-square w-10 shrink-0 overflow-hidden rounded bg-muted/40">
                {p.foto_url ? (
                  <img
                    loading="lazy"
                    decoding="async"
                    src={p.foto_url}
                    alt={p.nombre}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="grid h-full w-full place-items-center">
                    <Package className="h-4 w-4 text-muted-foreground" />
                  </div>
                )}
              </div>
              <div className="min-w-0 flex-1">
                {p.marca && <div className="t-eyebrow">{p.marca}</div>}
                <div className="truncate text-ink">{p.nombre}</div>
              </div>
              <button
                type="button"
                disabled={removeMut.isPending}
                onClick={() => removeMut.mutate(p.id)}
                className="text-muted-foreground hover:text-destructive disabled:opacity-50"
                aria-label={`Quitar ${p.nombre}`}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))
        )}
      </div>
    </Section>
  );
}

// ── Slots fijos recurrentes mensuales (E4) ──────────────────────────────────────

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

function SlotsSection() {
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
        <div className="py-4 text-sm text-muted-foreground">Cargando…</div>
      ) : (
        <div className="space-y-2">
          {slots.length === 0 && (
            <p className="text-sm text-muted-foreground">Todavía no hay slots fijos.</p>
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

function pad2(n: number) {
  return n.toString().padStart(2, "0");
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
        <input type="checkbox" {...register("activo")} className="h-4 w-4 rounded" />
        Activo
      </label>
      <div className="flex gap-2">
        <Button type="submit" disabled={mutation.isPending} size="sm">
          {mutation.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
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
  const testimoniosArr = useFieldArray({ control, name: "testimonios" });

  const packActivo = watch("pack_activo");

  const mutation = useMutation({
    mutationFn: (values: FormValues) => {
      // Filtramos filas totalmente vacías antes de guardar — si el dueño hizo
      // "Añadir" y dejó la fila sin completar (caso típico cuando se arrepiente
      // o se distrae), no la persistimos. Features tienen seed canónico con
      // value vacío a propósito (admin las muestra; público las filtra), así
      // que ahí solo dropeamos las que tienen el label vacío también.
      const faqLimpio = values.faq.filter((f) => f.q.trim() || f.a.trim());
      const testimoniosLimpio = values.testimonios.filter((t) => t.autor.trim() || t.texto.trim());
      const featuresLimpio = values.features.filter((f) => f.label.trim());
      return estudioAdminApi.update({
        ...values,
        features_json: JSON.stringify(featuresLimpio),
        faq_json: JSON.stringify(faqLimpio),
        testimonios_json: JSON.stringify(testimoniosLimpio),
      });
    },
    onSuccess: () => {
      toast.success("Estudio guardado");
      onSaved();
    },
    onError: (e) => toast.error("Error guardando", { description: (e as Error).message }),
  });

  // Si la validación falla, react-hook-form NO llama al success-handler — el
  // submit "no hace nada". Surfaciamos un toast para que no se sienta roto.
  const onInvalid = (errs: typeof errors) => {
    const fields = Object.keys(errs).join(", ");
    toast.error("Revisá los campos marcados", {
      description: fields ? `Campos con error: ${fields}` : undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit((v) => mutation.mutate(v), onInvalid)} className="space-y-8">
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

      {/* ── Ubicación ── */}
      <Section title="Ubicación">
        <p className="-mt-1 text-xs text-muted-foreground">
          Si pegás un link de Google Maps, mostramos un mapa en la página pública. Sin link y sin
          dirección, el bloque entero se oculta.
        </p>
        <Field
          label="Mapa de Google (link o código embed)"
          error={errors.mapa_url?.message}
          hint='Pegá el link que da "Compartir" en la app de Google Maps (ej. https://maps.app.goo.gl/...) o el código iframe de "Compartir → Insertar mapa". Dejalo vacío para no mostrar mapa.'
        >
          <Textarea {...register("mapa_url")} rows={2} placeholder="https://maps.app.goo.gl/..." />
        </Field>
        <Field label="Dirección (texto)" error={errors.direccion?.message}>
          <Input {...register("direccion")} placeholder="Av. Colón 1234, Mar del Plata" />
        </Field>
        <Field label="Cómo llegar / estacionamiento" error={errors.como_llegar?.message}>
          <Textarea
            {...register("como_llegar")}
            rows={2}
            placeholder="Entrada de autos por el frente, estacionamiento sobre la calle…"
          />
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

      {/* ── Testimonios / prueba social ── */}
      <Section title="Testimonios (prueba social)">
        <p className="text-xs text-muted-foreground mb-3">
          Aparecen en la página pública. Si no hay ninguno, la sección no se muestra.
        </p>
        <div className="space-y-3">
          {testimoniosArr.fields.map((f, i) => (
            <div key={f.id} className="rounded-xl border hairline p-3 space-y-2">
              <div className="flex items-start gap-2">
                <Input
                  {...register(`testimonios.${i}.autor`)}
                  placeholder="Autor (ej. Productora X)"
                  className="flex-1"
                />
                <button
                  type="button"
                  onClick={() => testimoniosArr.remove(i)}
                  className="mt-2 text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              <Textarea
                {...register(`testimonios.${i}.texto`)}
                placeholder="Lo que dijeron del estudio"
                rows={2}
              />
            </div>
          ))}
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-2"
          onClick={() => testimoniosArr.append({ autor: "", texto: "" })}
        >
          <Plus className="h-3.5 w-3.5 mr-1" /> Añadir testimonio
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

// ── Trabajos (galería "en acción") ────────────────────────────────────────────

type TrabajoDialogMode = { mode: "create" } | { mode: "edit"; trabajo: EstudioTrabajo };

function TrabajoDialog({
  open,
  dialogMode,
  onClose,
  onSaved,
  availableCategorias,
}: {
  open: boolean;
  dialogMode: TrabajoDialogMode;
  onClose: () => void;
  onSaved: (t: EstudioTrabajo) => void;
  availableCategorias: string[];
}) {
  const isEdit = dialogMode.mode === "edit";
  const existing = isEdit ? dialogMode.trabajo : null;

  const [titulo, setTitulo] = useState(existing?.titulo ?? "");
  const [realizador, setRealizador] = useState(existing?.realizador ?? "");
  const [instagram, setInstagram] = useState(existing?.realizador_instagram ?? "");
  const [web, setWeb] = useState(existing?.realizador_web ?? "");
  const [categorias, setCategorias] = useState<string[]>(existing?.categorias ?? []);
  const [newTag, setNewTag] = useState("");
  const [draggingOver, setDraggingOver] = useState(false);
  const [descripcion, setDescripcion] = useState(existing?.descripcion ?? "");
  const [links, setLinks] = useState<string[]>(
    existing?.links?.length ? existing.links.map((l) => l.url) : [""],
  );
  const [thumbOverrides, setThumbOverrides] = useState<string[]>(
    existing?.links?.length ? existing.links.map(() => "") : [""],
  );
  const [activo, setActivo] = useState(existing?.activo ?? true);
  const [trabajoId, setTrabajoId] = useState<number | null>(existing?.id ?? null);
  const [fotos, setFotos] = useState(existing?.fotos ?? []);
  const [logoUrl, setLogoUrl] = useState(existing?.realizador_logo_url ?? null);
  const [uploadingFoto, setUploadingFoto] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [saving, setSaving] = useState(false);
  const [fetchingMeta, setFetchingMeta] = useState(false);
  const [showExtra, setShowExtra] = useState(false);

  const fotoInputRef = useRef<HTMLInputElement>(null);
  const logoInputRef = useRef<HTMLInputElement>(null);
  const fetchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function setLinkAt(idx: number, url: string) {
    setLinks((prev) => prev.map((l, i) => (i === idx ? url : l)));
    setThumbOverrides((prev) => prev.map((t, i) => (i === idx ? "" : t)));
  }
  function addLinkRow() {
    setLinks((prev) => [...prev, ""]);
    setThumbOverrides((prev) => [...prev, ""]);
  }
  function removeLinkRow(idx: number) {
    setLinks((prev) => {
      const next = prev.filter((_, i) => i !== idx);
      return next.length ? next : [""];
    });
    setThumbOverrides((prev) => {
      const next = prev.filter((_, i) => i !== idx);
      return next.length ? next : [""];
    });
  }
  function setThumbOverrideAt(idx: number, val: string) {
    setThumbOverrides((prev) => prev.map((t, i) => (i === idx ? val : t)));
  }

  function toggleCategoria(cat: string) {
    setCategorias((prev) =>
      prev.some((c) => c.toLowerCase() === cat.toLowerCase())
        ? prev.filter((c) => c.toLowerCase() !== cat.toLowerCase())
        : [...prev, cat],
    );
  }
  function addNewTag() {
    const t = newTag.trim();
    if (t && !categorias.some((c) => c.toLowerCase() === t.toLowerCase())) {
      setCategorias((prev) => [...prev, t]);
    }
    setNewTag("");
  }

  // Auto-fetch metadata al pegar un link reconocido (prefill de titulo/realizador).
  function handleLinkChange(idx: number, url: string) {
    setLinkAt(idx, url);
    if (fetchDebounceRef.current) clearTimeout(fetchDebounceRef.current);
    if (!linkTipo(url)) return;
    fetchDebounceRef.current = setTimeout(async () => {
      setFetchingMeta(true);
      try {
        const meta = await trabajosAdminApi.fetchMeta(url);
        if (meta.titulo && !titulo) setTitulo(meta.titulo);
        if (meta.realizador && !realizador) setRealizador(meta.realizador);
        // descripcion no se auto-rellena: el og:description de IG trae el caption
        // con likes/menciones/hashtags que no son útiles como descripción del trabajo.
      } catch {
        /* best-effort */
      } finally {
        setFetchingMeta(false);
      }
    }, 700);
  }

  // Reset cuando cambia el diálogo
  useEffect(() => {
    if (!open) return;
    const t = isEdit ? existing : null;
    setTitulo(t?.titulo ?? "");
    setRealizador(t?.realizador ?? "");
    setInstagram(t?.realizador_instagram ?? "");
    setWeb(t?.realizador_web ?? "");
    setCategorias(t?.categorias ?? []);
    setNewTag("");
    setDescripcion(t?.descripcion ?? "");
    setLinks(t?.links?.length ? t.links.map((l) => l.url) : [""]);
    setThumbOverrides(t?.links?.length ? t.links.map(() => "") : [""]);
    setActivo(t?.activo ?? true);
    setTrabajoId(t?.id ?? null);
    setFotos(t?.fotos ?? []);
    setLogoUrl(t?.realizador_logo_url ?? null);
    setShowExtra(false);
  }, [open, isEdit]); // eslint-disable-line react-hooks/exhaustive-deps

  const linksPayload = links
    .map((url, i) => ({
      url: url.trim(),
      tipo: linkTipo(url.trim()),
      thumbnail_url: (thumbOverrides[i] ?? "").trim() || undefined,
    }))
    .filter((l) => l.tipo !== null);

  function buildData(): EstudioTrabajoInput {
    return {
      titulo,
      realizador,
      realizador_instagram: instagram || null,
      realizador_web: web || null,
      categorias,
      descripcion,
      links: linksPayload,
      activo,
    };
  }

  async function ensureCreated(): Promise<number> {
    if (trabajoId) return trabajoId;
    const created = await trabajosAdminApi.create(buildData());
    setTrabajoId(created.id);
    return created.id;
  }

  async function handleSave() {
    setSaving(true);
    try {
      const data = buildData();
      let result: EstudioTrabajo;
      if (trabajoId) {
        result = await trabajosAdminApi.update(trabajoId, data);
      } else {
        result = await trabajosAdminApi.create(data);
        setTrabajoId(result.id);
      }
      onSaved(result);
      toast.success(isEdit ? "Trabajo actualizado" : "Trabajo creado");
    } catch (e) {
      toast.error("Error guardando", { description: (e as Error).message });
    } finally {
      setSaving(false);
    }
  }

  async function handleFotoUpload(files: FileList) {
    if (!files.length) return;
    setUploadingFoto(true);
    try {
      const id = await ensureCreated();
      let result: EstudioTrabajo = {} as EstudioTrabajo;
      for (const f of Array.from(files)) {
        result = await trabajosAdminApi.uploadFoto(id, f);
      }
      setFotos(result.fotos ?? []);
      toast.success("Foto subida");
    } catch (e) {
      toast.error("Error subiendo foto", { description: (e as Error).message });
    } finally {
      setUploadingFoto(false);
    }
  }

  async function handleDeleteFoto(idx: number) {
    if (!trabajoId) return;
    try {
      const result = await trabajosAdminApi.deleteFoto(trabajoId, idx);
      setFotos(result.fotos ?? []);
    } catch (e) {
      toast.error("Error eliminando foto", { description: (e as Error).message });
    }
  }

  async function handleLogoUpload(file: File) {
    setUploadingLogo(true);
    try {
      const id = await ensureCreated();
      const result = await trabajosAdminApi.uploadLogo(id, file);
      setLogoUrl(result.realizador_logo_url);
      toast.success("Logo subido");
    } catch (e) {
      toast.error("Error subiendo logo", { description: (e as Error).message });
    } finally {
      setUploadingLogo(false);
    }
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="relative bg-surface rounded-2xl border hairline shadow-xl w-full max-w-lg max-h-[90dvh] overflow-y-auto">
        <div className="sticky top-0 bg-surface border-b hairline px-5 py-4 flex items-center justify-between">
          <h2 className="font-display text-lg text-ink">
            {isEdit ? "Editar trabajo" : "Nuevo trabajo"}
          </h2>
          <button
            onClick={onClose}
            className="rounded-full p-1.5 hover:bg-muted transition-colors"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Links — campo primario, auto-fetch en el primero. Varios links =
              varias diapositivas del carrusel público. */}
          <div className="space-y-2">
            <label className="t-eyebrow block">Links (YouTube / Instagram)</label>
            <div className="space-y-3">
              {links.map((url, idx) => {
                const tipo = linkTipo(url);
                return (
                  <div key={idx} className="space-y-1">
                    <div className="flex items-center gap-2">
                      {tipo === "youtube" ? (
                        <Film className="h-4 w-4 shrink-0 text-muted-foreground" />
                      ) : tipo === "instagram" ? (
                        <IgGlyph className="h-4 w-4 shrink-0 text-muted-foreground" />
                      ) : (
                        <Film className="h-4 w-4 shrink-0 text-muted-foreground/30" />
                      )}
                      <Input
                        value={url}
                        onChange={(e) => handleLinkChange(idx, e.target.value)}
                        placeholder="Pegá un link de YouTube o Instagram…"
                        autoFocus={!isEdit && idx === 0}
                      />
                      {(links.length > 1 || url) && (
                        <button
                          type="button"
                          onClick={() => removeLinkRow(idx)}
                          className="shrink-0 rounded-full p-1.5 text-muted-foreground/50 hover:text-foreground hover:bg-muted transition-colors"
                          aria-label="Quitar link"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                    {tipo && (
                      <details className="ml-6">
                        <summary className="cursor-pointer text-2xs text-muted-foreground/40 hover:text-muted-foreground/70 select-none list-none">
                          miniatura alternativa
                        </summary>
                        <Input
                          className="mt-1 text-xs"
                          value={thumbOverrides[idx] ?? ""}
                          onChange={(e) => setThumbOverrideAt(idx, e.target.value)}
                          placeholder="URL de imagen (reemplaza la miniatura auto-detectada)"
                        />
                      </details>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={addLinkRow}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                <Plus className="h-3.5 w-3.5" />
                Agregar otro link
              </button>
              {fetchingMeta && (
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Obteniendo info…
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground/50">
              Instagram funciona con reels, fotos y carruseles. Se muestran como un carrusel.
            </p>
          </div>

          {/* Título — auto-rellenado */}
          <div className="space-y-1">
            <label className="t-eyebrow">
              Título{" "}
              <span className="normal-case tracking-normal font-sans opacity-50">(opcional)</span>
            </label>
            <Input
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
              placeholder="Auto-rellenado desde el link, o escribí uno"
            />
          </div>

          {/* Realizador — auto-rellenado */}
          <div className="space-y-1">
            <label className="t-eyebrow">
              Realizador / Productora{" "}
              <span className="normal-case tracking-normal font-sans opacity-50">(opcional)</span>
            </label>
            <Input
              value={realizador}
              onChange={(e) => setRealizador(e.target.value)}
              placeholder="Auto-rellenado desde el link, o escribí uno"
            />
          </div>

          {/* Categorías (tags) — multi-select */}
          <div className="space-y-2">
            <label className="t-eyebrow">
              Categorías{" "}
              <span className="normal-case tracking-normal font-sans opacity-50">
                (opcional — podés elegir varias)
              </span>
            </label>
            {(() => {
              const all = [...new Set([...availableCategorias, ...categorias])];
              return all.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {all.map((cat) => {
                    const on = categorias.some((c) => c.toLowerCase() === cat.toLowerCase());
                    return (
                      <button
                        key={cat}
                        type="button"
                        onClick={() => toggleCategoria(cat)}
                        className={cn(
                          "inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-mono uppercase tracking-[0.1em] border transition-colors",
                          on
                            ? "bg-ink text-background border-ink"
                            : "border-hairline text-muted-foreground hover:border-ink/50 hover:text-foreground",
                        )}
                      >
                        {cat}
                        {on && <X className="h-3 w-3" />}
                      </button>
                    );
                  })}
                </div>
              ) : null;
            })()}
            <div className="flex items-center gap-2">
              <Input
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addNewTag();
                  }
                }}
                placeholder="Agregá un tag y Enter (ej: Moda, Editorial…)"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={addNewTag}
                disabled={!newTag.trim()}
              >
                <Plus className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>

          {/* Fotos */}
          <div className="space-y-2">
            <label className="t-eyebrow">
              Fotos{" "}
              {fotos.length > 0 ? (
                `(${fotos.length})`
              ) : (
                <span className="normal-case tracking-normal font-sans opacity-50">(opcional)</span>
              )}
            </label>
            {fotos.length > 0 && (
              <div className="grid grid-cols-3 gap-2">
                {fotos.map((f, idx) => (
                  <div
                    key={idx}
                    className="relative aspect-square rounded-lg overflow-hidden border hairline group"
                  >
                    <img src={f.url_sm ?? f.url} alt="" className="h-full w-full object-cover" />
                    <button
                      onClick={() => handleDeleteFoto(idx)}
                      className="absolute top-1 right-1 rounded-full bg-black/70 p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <Trash2 className="h-3 w-3 text-white" />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <input
              ref={fotoInputRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.length) handleFotoUpload(e.target.files);
                e.target.value = "";
              }}
            />
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDraggingOver(true);
              }}
              onDragEnter={(e) => {
                e.preventDefault();
                setDraggingOver(true);
              }}
              onDragLeave={() => setDraggingOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDraggingOver(false);
                if (e.dataTransfer.files?.length) handleFotoUpload(e.dataTransfer.files);
              }}
              onClick={() => !uploadingFoto && fotoInputRef.current?.click()}
              className={cn(
                "rounded-xl border-2 border-dashed p-5 text-center cursor-pointer transition-colors",
                draggingOver ? "border-ink bg-ink/5" : "border-hairline hover:border-ink/40",
                uploadingFoto && "opacity-60 cursor-not-allowed",
              )}
            >
              {uploadingFoto ? (
                <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Subiendo…
                </div>
              ) : (
                <>
                  <Upload className="h-5 w-5 mx-auto mb-1.5 text-muted-foreground/50" />
                  <p className="text-sm text-muted-foreground">
                    Arrastrá fotos acá o{" "}
                    <span className="text-foreground underline underline-offset-2">hacé click</span>
                  </p>
                  <p className="text-xs text-muted-foreground/50 mt-0.5">
                    Podés seleccionar varias a la vez
                  </p>
                </>
              )}
            </div>
          </div>

          {/* Más detalles — collapsible */}
          <div className="border-t hairline pt-4">
            <button
              type="button"
              onClick={() => setShowExtra(!showExtra)}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <svg
                viewBox="0 0 24 24"
                className={cn("h-3 w-3 transition-transform", showExtra && "rotate-90")}
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
              >
                <path d="M9 18l6-6-6-6" />
              </svg>
              Más detalles (descripción, redes del realizador, logo, visibilidad)
            </button>
            {showExtra && (
              <div className="space-y-4 mt-4">
                <div className="space-y-1">
                  <label className="t-eyebrow">Descripción breve</label>
                  <Textarea
                    value={descripcion}
                    onChange={(e) => setDescripcion(e.target.value)}
                    placeholder="Breve contexto del trabajo (opcional)"
                    rows={2}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="t-eyebrow">Instagram del realizador</label>
                    <Input
                      value={instagram}
                      onChange={(e) => setInstagram(e.target.value)}
                      placeholder="@usuario"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="t-eyebrow">Web</label>
                    <Input
                      value={web}
                      onChange={(e) => setWeb(e.target.value)}
                      placeholder="https://..."
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="t-eyebrow">Logo del realizador</label>
                  <div className="flex items-center gap-3">
                    {logoUrl ? (
                      <img
                        src={logoUrl}
                        alt="logo"
                        className="h-12 w-12 rounded-lg object-contain border hairline bg-muted/30"
                      />
                    ) : (
                      <div className="h-12 w-12 rounded-lg border-dashed border-2 border-muted-foreground/30 flex items-center justify-center">
                        <Image className="h-5 w-5 text-muted-foreground/40" />
                      </div>
                    )}
                    <input
                      ref={logoInputRef}
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) handleLogoUpload(f);
                      }}
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => logoInputRef.current?.click()}
                      disabled={uploadingLogo}
                    >
                      {uploadingLogo ? (
                        <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                      ) : null}
                      {logoUrl ? "Cambiar logo" : "Subir logo"}
                    </Button>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    role="switch"
                    aria-checked={activo}
                    onClick={() => setActivo(!activo)}
                    className={cn(
                      "relative h-5 w-9 rounded-full transition-colors",
                      activo ? "bg-ink" : "bg-muted",
                    )}
                  >
                    <span
                      className={cn(
                        "absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-background transition-transform",
                        activo ? "translate-x-4" : "translate-x-0",
                      )}
                    />
                  </button>
                  <span className="text-sm text-muted-foreground">
                    Visible en la página pública
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="sticky bottom-0 bg-surface border-t hairline px-5 py-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving || (!linksPayload.length && !titulo.trim() && !fotos.length)}
          >
            {saving ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : null}
            {isEdit ? "Guardar cambios" : "Crear trabajo"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function SortableTrabajoCard({
  trabajo,
  onEdit,
  onDelete,
  onToggleActivo,
}: {
  trabajo: EstudioTrabajo;
  onEdit: (t: EstudioTrabajo) => void;
  onDelete: (id: number) => void;
  onToggleActivo: (id: number, activo: boolean) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: trabajo.id,
  });
  const style = { transform: CSS.Transform.toString(transform), transition };

  // Thumbnail = primer medio del carrusel (link procesado o foto).
  const first = trabajo.media?.[0];
  const thumb = first
    ? first.kind === "foto"
      ? (first.url_sm ?? first.url ?? null)
      : (first.thumbnail ?? null)
    : null;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "flex items-center gap-3 rounded-xl border hairline bg-background p-3 transition-shadow",
        isDragging ? "shadow-lg opacity-80" : "",
      )}
    >
      {/* Drag handle */}
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab text-muted-foreground hover:text-ink p-1 touch-none"
        aria-label="Arrastrar"
      >
        <GripVertical className="h-4 w-4" />
      </button>

      {/* Thumbnail */}
      <div className="h-12 w-16 rounded-lg overflow-hidden border hairline bg-muted/30 shrink-0">
        {thumb ? (
          <img src={thumb} alt="" className="h-full w-full object-cover" />
        ) : (
          <div className="h-full w-full flex items-center justify-center">
            {trabajo.tipo === "video" ? (
              <Film className="h-5 w-5 text-muted-foreground/40" />
            ) : (
              <Image className="h-5 w-5 text-muted-foreground/40" />
            )}
          </div>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-ink truncate">
          {trabajo.titulo || <span className="text-muted-foreground italic">Sin título</span>}
        </p>
        <p className="text-xs text-muted-foreground truncate">{trabajo.realizador || "—"}</p>
      </div>

      {/* Cantidad de medios */}
      <Pill tone="neutral" className="font-mono uppercase tracking-[0.1em]">
        {trabajo.media.length} {trabajo.media.length === 1 ? "medio" : "medios"}
      </Pill>

      {/* Actions */}
      <div className="flex items-center gap-1 shrink-0">
        <button
          onClick={() => onToggleActivo(trabajo.id, !trabajo.activo)}
          className="p-1.5 rounded-lg hover:bg-muted transition-colors"
          title={trabajo.activo ? "Ocultar" : "Publicar"}
        >
          {trabajo.activo ? (
            <Eye className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <EyeOff className="h-3.5 w-3.5 text-muted-foreground/40" />
          )}
        </button>
        <button
          onClick={() => onEdit(trabajo)}
          className="p-1.5 rounded-lg hover:bg-muted transition-colors"
          title="Editar"
        >
          <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
        </button>
        <button
          onClick={() => onDelete(trabajo.id)}
          className="p-1.5 rounded-lg hover:bg-muted transition-colors"
          title="Eliminar"
        >
          <Trash2 className="h-3.5 w-3.5 text-destructive/70" />
        </button>
      </div>
    </div>
  );
}

function TrabajosSection({
  trabajos: initialTrabajos,
  onChanged,
}: {
  trabajos: EstudioTrabajo[];
  onChanged: () => void;
}) {
  const [trabajos, setTrabajos] = useState(initialTrabajos);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<TrabajoDialogMode>({ mode: "create" });

  useEffect(() => {
    setTrabajos(initialTrabajos);
  }, [initialTrabajos]);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const deleteMut = useMutation({
    mutationFn: (id: number) => trabajosAdminApi.delete(id),
    onSuccess: () => {
      toast.success("Trabajo eliminado");
      onChanged();
    },
    onError: (e) => toast.error("Error eliminando", { description: (e as Error).message }),
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, activo }: { id: number; activo: boolean }) =>
      trabajosAdminApi.update(id, { activo }),
    onSuccess: (updated) => {
      setTrabajos((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    },
    onError: (e) => toast.error("Error", { description: (e as Error).message }),
  });

  const reorderMut = useMutation({
    mutationFn: (items: { id: number; orden: number }[]) => trabajosAdminApi.reorder(items),
    onError: (e) => toast.error("Error reordenando", { description: (e as Error).message }),
  });

  function handleDragEnd(event: {
    active: { id: number | string };
    over: { id: number | string } | null;
  }) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setTrabajos((prev) => {
      const oldIdx = prev.findIndex((t) => t.id === active.id);
      const newIdx = prev.findIndex((t) => t.id === over.id);
      const reordered = arrayMove(prev, oldIdx, newIdx).map((t, i) => ({ ...t, orden: i }));
      reorderMut.mutate(reordered.map((t) => ({ id: t.id, orden: t.orden })));
      return reordered;
    });
  }

  function openCreate() {
    setDialogMode({ mode: "create" });
    setDialogOpen(true);
  }

  function openEdit(t: EstudioTrabajo) {
    setDialogMode({ mode: "edit", trabajo: t });
    setDialogOpen(true);
  }

  function handleSaved(t: EstudioTrabajo) {
    setTrabajos((prev) => {
      const idx = prev.findIndex((x) => x.id === t.id);
      return idx >= 0 ? prev.map((x) => (x.id === t.id ? t : x)) : [...prev, t];
    });
    onChanged();
  }

  return (
    <>
      <Section title="Trabajos">
        <p className="text-xs text-muted-foreground">
          Producciones que aparecen en la sección "en acción" del estudio. Arrastrá para reordenar.
        </p>

        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={trabajos.map((t) => t.id)} strategy={verticalListSortingStrategy}>
            <div className="space-y-2">
              {trabajos.map((t) => (
                <SortableTrabajoCard
                  key={t.id}
                  trabajo={t}
                  onEdit={openEdit}
                  onDelete={(id) => deleteMut.mutate(id)}
                  onToggleActivo={(id, activo) => toggleMut.mutate({ id, activo })}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>

        {trabajos.length === 0 && (
          <p className="text-sm text-center text-muted-foreground py-4">
            No hay trabajos cargados todavía.
          </p>
        )}

        <Button variant="outline" size="sm" onClick={openCreate}>
          <Plus className="h-3.5 w-3.5 mr-1.5" />
          Agregar trabajo
        </Button>
      </Section>

      <TrabajoDialog
        open={dialogOpen}
        dialogMode={dialogMode}
        onClose={() => setDialogOpen(false)}
        onSaved={(t) => {
          handleSaved(t);
          setDialogOpen(false);
        }}
        availableCategorias={[...new Set(trabajos.flatMap((t) => t.categorias ?? []))]}
      />
    </>
  );
}

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

function slugifyForStorage(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  // Cada sección es colapsable y persiste su estado por título (slug).
  // Antes era un scroll lineal de ~900 líneas; ahora el dueño abre lo que
  // necesita y deja el resto cerrado.
  return (
    <AdminSection title={title} storageKey={`estudio:${slugifyForStorage(title)}`}>
      <section className="rounded-2xl border hairline bg-surface p-5 space-y-4">{children}</section>
    </AdminSection>
  );
}

function Field({
  label,
  error,
  hint,
  children,
}: {
  label: string;
  error?: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <label className="t-eyebrow">{label}</label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
