import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Upload, Plus, Trash2, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { adminApi, type Equipo, type EquipoInput, type CategoriaAdmin, type KitComponente } from "@/lib/admin/api";
import { supabase } from "@/integrations/supabase/client";
import { EnriquecerEquipoDialog } from "./EnriquecerEquipoDialog";

const schema = z.object({
  nombre: z.string().min(1, "Nombre requerido"),
  marca: z.string().optional().nullable(),
  modelo: z.string().optional().nullable(),
  cantidad: z.coerce.number().int().min(0).default(1),
  precio_jornada: z.coerce.number().int().min(0).optional().nullable(),
  precio_usd: z.coerce.number().min(0).optional().nullable(),
  roi_pct: z.coerce.number().min(0).optional().nullable(),
  valor_reposicion: z.coerce.number().min(0).optional().nullable(),
  fecha_compra: z.string().optional().nullable(),
  serie: z.string().optional().nullable(),
  bh_url: z.string().optional().nullable(),
  foto_url: z.string().optional().nullable(),
  dueno: z.string().optional().nullable(),
  estado: z.enum(["operativo", "en_mantenimiento", "fuera_servicio"]).default("operativo"),
  visible_catalogo: z.boolean().default(true),
  etiquetas_csv: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;
type Spec = { label: string; value: string };

export function EquipoFormDialog({
  open,
  onOpenChange,
  initial,
  onSubmit,
  saving,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  initial?: Equipo | null;
  onSubmit: (data: EquipoInput, etiquetas: string[]) => void | Promise<void>;
  saving?: boolean;
}) {
  const isEdit = !!initial;
  const [enriching, setEnriching] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [tab, setTab] = useState("basicos");

  const form = useForm<FormValues>({
    resolver: zodResolver(schema) as never,
    defaultValues: {
      nombre: initial?.nombre ?? "",
      marca: initial?.marca ?? "",
      modelo: initial?.modelo ?? "",
      cantidad: initial?.cantidad ?? 1,
      precio_jornada: initial?.precio_jornada ?? undefined,
      precio_usd: initial?.precio_usd ?? undefined,
      roi_pct: initial?.roi_pct ?? undefined,
      valor_reposicion: initial?.valor_reposicion ?? undefined,
      fecha_compra: initial?.fecha_compra ?? "",
      serie: initial?.serie ?? "",
      bh_url: initial?.bh_url ?? "",
      foto_url: initial?.foto_url ?? "",
      dueno: initial?.dueno ?? "Rambla",
      estado: (initial?.estado as FormValues["estado"]) ?? "operativo",
      visible_catalogo: initial ? Boolean(initial.visible_catalogo) : true,
      etiquetas_csv: initial?.etiquetas?.join(", ") ?? "",
    },
  });

  // Ficha técnica (sólo en edición)
  const fichaQ = useQuery({
    queryKey: ["admin", "equipo-ficha", initial?.id],
    queryFn: () => adminApi.getFicha(initial!.id),
    enabled: !!initial?.id && open,
  });

  const [montura, setMontura] = useState("");
  const [formato, setFormato] = useState("");
  const [resolucion, setResolucion] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [notas, setNotas] = useState("");
  const [specs, setSpecs] = useState<Spec[]>([]);

  useEffect(() => {
    const f = fichaQ.data;
    if (f) {
      setMontura(f.montura ?? "");
      setFormato(f.formato ?? "");
      setResolucion(f.resolucion ?? "");
      setDescripcion(f.descripcion ?? "");
      setNotas(f.notas ?? "");
      try {
        const arr = f.specs_json ? JSON.parse(f.specs_json) : [];
        setSpecs(Array.isArray(arr) ? arr : []);
      } catch { setSpecs([]); }
    } else if (!initial) {
      setMontura(""); setFormato(""); setResolucion("");
      setDescripcion(""); setNotas(""); setSpecs([]);
    }
  }, [fichaQ.data, initial]);

  // Categorías (multi-select)
  const catsQ = useQuery({
    queryKey: ["admin", "categorias-list"],
    queryFn: () => adminApi.adminListCategorias(),
    enabled: open,
  });
  const [selectedCats, setSelectedCats] = useState<Set<number>>(new Set());
  useEffect(() => {
    if (initial?.categorias) {
      setSelectedCats(new Set(initial.categorias.map((c) => c.id)));
    } else {
      setSelectedCats(new Set());
    }
  }, [initial, open]);

  // Preview nombre público
  const tipoCat = useMemo(() => {
    if (!catsQ.data) return "";
    const first = [...selectedCats][0];
    if (!first) return "";
    return catsQ.data.find((c) => c.id === first)?.nombre ?? "";
  }, [catsQ.data, selectedCats]);

  const previewName = useMemo(() => {
    const parts = [
      tipoCat,
      form.watch("marca") ?? "",
      form.watch("modelo") ?? "",
      montura, formato, resolucion,
    ].map((s) => (s ?? "").trim()).filter(Boolean);
    if (parts.length === 0) return form.watch("nombre") || "—";
    const seen = new Set<string>();
    return parts.filter((p) => {
      const k = p.toLowerCase();
      if (seen.has(k)) return false;
      seen.add(k); return true;
    }).join(" ");
  }, [tipoCat, form, montura, formato, resolucion]);

  const submit = form.handleSubmit(async (values) => {
    const etiquetas = (values.etiquetas_csv ?? "")
      .split(",").map((s: string) => s.trim()).filter(Boolean);
    const { etiquetas_csv: _omit, visible_catalogo, ...rest } = values;
    void _omit;
    const payload: EquipoInput = {
      nombre: rest.nombre,
      cantidad: rest.cantidad,
      estado: rest.estado,
      marca: rest.marca || null,
      modelo: rest.modelo || null,
      serie: rest.serie || null,
      dueno: rest.dueno || null,
      bh_url: rest.bh_url || null,
      foto_url: rest.foto_url || null,
      fecha_compra: rest.fecha_compra || null,
      precio_jornada: rest.precio_jornada ?? null,
      precio_usd: rest.precio_usd ?? null,
      roi_pct: rest.roi_pct ?? null,
      valor_reposicion: rest.valor_reposicion ?? null,
      visible_catalogo: visible_catalogo ? 1 : 0,
    };
    await onSubmit(payload, etiquetas);

    // Si estamos editando, también guardar ficha y categorías
    if (isEdit && initial) {
      try {
        await Promise.all([
          adminApi.setFicha(initial.id, {
            descripcion: descripcion || null,
            notas: notas || null,
            specs_json: specs.length ? JSON.stringify(specs.filter((s) => s.label && s.value)) : null,
            montura: montura || null,
            formato: formato || null,
            resolucion: resolucion || null,
          }),
          adminApi.setCategorias(initial.id, [...selectedCats]),
        ]);
      } catch (e) {
        toast.error(`Datos básicos OK, pero falló ficha/categorías: ${e instanceof Error ? e.message : ""}`);
      }
    }
  });

  // Upload de foto a Supabase Storage
  const handleUpload = async (file: File) => {
    if (!file) return;
    setUploading(true);
    try {
      const ext = (file.name.split(".").pop() || "jpg").toLowerCase();
      const eqId = initial?.id ?? "nuevo";
      const path = `equipos/${eqId}/foto-${Date.now()}.${ext}`;
      const { error } = await supabase.storage
        .from("equipos-fotos")
        .upload(path, file, { contentType: file.type, upsert: false });
      if (error) throw error;
      const { data } = supabase.storage.from("equipos-fotos").getPublicUrl(path);
      form.setValue("foto_url", data.publicUrl, { shouldDirty: true });
      toast.success("Foto subida");
    } catch (e) {
      toast.error(`Error al subir: ${e instanceof Error ? e.message : ""}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex items-start justify-between gap-3">
              <DialogTitle className="font-display text-2xl">
                {isEdit ? "Editar equipo" : "Nuevo equipo"}
              </DialogTitle>
              {isEdit && initial && (
                <Button type="button" variant="outline" size="sm" onClick={() => setEnriching(true)}>
                  <Sparkles className="h-4 w-4 mr-1.5 text-amber" />
                  Enriquecer con IA
                </Button>
              )}
            </div>
            {isEdit && (
              <p className="text-xs text-muted-foreground">
                Se ve en la web como: <span className="text-ink font-medium italic">{previewName}</span>
              </p>
            )}
          </DialogHeader>

          <form onSubmit={submit} className="space-y-4">
            <Tabs value={tab} onValueChange={setTab}>
              <TabsList className="w-full">
                <TabsTrigger value="basicos" className="flex-1">Datos básicos</TabsTrigger>
                <TabsTrigger value="ficha" className="flex-1" disabled={!isEdit}>
                  Ficha técnica
                </TabsTrigger>
                <TabsTrigger value="cats" className="flex-1" disabled={!isEdit}>
                  Categorías
                </TabsTrigger>
                <TabsTrigger value="kit" className="flex-1" disabled={!isEdit}>
                  Kit
                </TabsTrigger>
              </TabsList>

              {/* ── Datos básicos ─────────────────────────────────────── */}
              <TabsContent value="basicos" className="space-y-4 mt-4">
                <Field label="Nombre interno" error={form.formState.errors.nombre?.message}>
                  <Input {...form.register("nombre")} placeholder="Ej: FX3 Cuerpo" />
                </Field>

                <div className="grid grid-cols-2 gap-3">
                  <Field label="Marca"><Input {...form.register("marca")} /></Field>
                  <Field label="Modelo"><Input {...form.register("modelo")} /></Field>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <Field label="Stock"><Input type="number" min={0} {...form.register("cantidad")} /></Field>
                  <Field label="Precio/día (ARS)"><Input type="number" min={0} {...form.register("precio_jornada")} /></Field>
                  <Field label="Valor (USD)"><Input type="number" min={0} step="0.01" {...form.register("precio_usd")} /></Field>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <Field label="ROI %"><Input type="number" min={0} step="0.01" {...form.register("roi_pct")} /></Field>
                  <Field label="Valor reposición (USD)"><Input type="number" min={0} step="0.01" {...form.register("valor_reposicion")} /></Field>
                  <Field label="Fecha de compra"><Input type="date" {...form.register("fecha_compra")} /></Field>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <Field label="N° Serie"><Input {...form.register("serie")} /></Field>
                  <Field label="Dueño"><Input {...form.register("dueno")} /></Field>
                </div>

                <Field label="Link de fuente (B&H, Adorama…)">
                  <Input {...form.register("bh_url")} className="font-mono text-xs" placeholder="https://..." />
                </Field>

                <Field label="Foto">
                  <div className="space-y-2">
                    <div className="flex gap-2">
                      <Input {...form.register("foto_url")} className="font-mono text-xs flex-1" placeholder="https://… o subí una" />
                      <label className="inline-flex">
                        <input
                          type="file" accept="image/*" className="hidden"
                          onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])}
                        />
                        <Button type="button" variant="outline" size="sm" disabled={uploading} asChild>
                          <span className="cursor-pointer">
                            {uploading
                              ? <><Loader2 className="h-4 w-4 mr-1 animate-spin" />Subiendo…</>
                              : <><Upload className="h-4 w-4 mr-1" />Subir</>}
                          </span>
                        </Button>
                      </label>
                    </div>
                    {form.watch("foto_url") && (
                      <img
                        src={form.watch("foto_url") ?? ""}
                        alt="Preview"
                        className="rounded-md border hairline max-h-40 object-contain bg-muted/30"
                        onError={(e) => { (e.target as HTMLImageElement).style.opacity = "0.3"; }}
                      />
                    )}
                  </div>
                </Field>

                <Field label="Etiquetas manuales (separadas por coma)">
                  <Input placeholder="Ej: vintage, kit boda" {...form.register("etiquetas_csv")} />
                </Field>

                <div className="grid grid-cols-2 gap-3 items-end">
                  <Field label="Estado">
                    <Select
                      value={form.watch("estado")}
                      onValueChange={(v) => form.setValue("estado", v as FormValues["estado"])}
                    >
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="operativo">Operativo</SelectItem>
                        <SelectItem value="en_mantenimiento">En mantenimiento</SelectItem>
                        <SelectItem value="fuera_servicio">Fuera de servicio</SelectItem>
                      </SelectContent>
                    </Select>
                  </Field>
                  <label className="flex items-center justify-between rounded-md border hairline px-3 py-2 text-sm">
                    <span>Visible en catálogo</span>
                    <Switch
                      checked={form.watch("visible_catalogo")}
                      onCheckedChange={(v) => form.setValue("visible_catalogo", v)}
                    />
                  </label>
                </div>
              </TabsContent>

              {/* ── Ficha técnica ─────────────────────────────────────── */}
              <TabsContent value="ficha" className="space-y-4 mt-4">
                <div className="rounded-md border hairline bg-muted/30 px-3 py-2 text-xs">
                  Estos campos arman el <strong>nombre público</strong> que se ve en el catálogo.
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <Field label="Montura">
                    <Input value={montura} onChange={(e) => setMontura(e.target.value)} placeholder="Ej: Montura E" />
                  </Field>
                  <Field label="Formato">
                    <Input value={formato} onChange={(e) => setFormato(e.target.value)} placeholder="Ej: Full Frame" />
                  </Field>
                  <Field label="Resolución">
                    <Input value={resolucion} onChange={(e) => setResolucion(e.target.value)} placeholder="Ej: 4K" />
                  </Field>
                </div>

                <Field label="Descripción (visible en el catálogo)">
                  <Textarea rows={3} value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
                </Field>

                <Field label="Notas internas (no se muestran)">
                  <Textarea rows={2} value={notas} onChange={(e) => setNotas(e.target.value)} />
                </Field>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs uppercase tracking-wide text-muted-foreground">
                      Specs ({specs.length})
                    </Label>
                    <Button type="button" size="sm" variant="ghost" onClick={() => setSpecs([...specs, { label: "", value: "" }])}>
                      <Plus className="h-3.5 w-3.5 mr-1" /> Agregar
                    </Button>
                  </div>
                  <div className="space-y-1.5">
                    {specs.map((s, i) => (
                      <div key={i} className="flex gap-2">
                        <Input
                          placeholder="Etiqueta (ej: Sensor)"
                          value={s.label}
                          onChange={(e) => setSpecs(specs.map((x, j) => j === i ? { ...x, label: e.target.value } : x))}
                          className="flex-[2]"
                        />
                        <Input
                          placeholder="Valor (ej: Full-frame 12MP)"
                          value={s.value}
                          onChange={(e) => setSpecs(specs.map((x, j) => j === i ? { ...x, value: e.target.value } : x))}
                          className="flex-[3]"
                        />
                        <Button type="button" size="icon" variant="ghost" onClick={() => setSpecs(specs.filter((_, j) => j !== i))}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                    {specs.length === 0 && (
                      <p className="text-xs text-muted-foreground italic">Sin specs.</p>
                    )}
                  </div>
                </div>
              </TabsContent>

              {/* ── Categorías ────────────────────────────────────────── */}
              <TabsContent value="cats" className="space-y-3 mt-4">
                <div className="rounded-md border hairline bg-muted/30 px-3 py-2 text-xs">
                  La <strong>primera categoría</strong> se usa como tipo en el nombre público.
                  Las etiquetas auto se regeneran solas.
                </div>
                {catsQ.isLoading ? (
                  <p className="text-sm text-muted-foreground">Cargando categorías…</p>
                ) : (
                  <CategoriasPicker
                    categorias={catsQ.data ?? []}
                    selected={selectedCats}
                    onChange={setSelectedCats}
                  />
                )}
              </TabsContent>
            </Tabs>

            <DialogFooter className="gap-2">
              <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancelar</Button>
              <Button type="submit" disabled={saving}>
                {saving ? "Guardando…" : isEdit ? "Guardar cambios" : "Crear equipo"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {enriching && initial && (
        <EnriquecerEquipoDialog
          equipo={initial}
          open={enriching}
          onOpenChange={setEnriching}
          onApplied={() => { setEnriching(false); fichaQ.refetch(); }}
        />
      )}
    </>
  );
}

function CategoriasPicker({
  categorias, selected, onChange,
}: {
  categorias: CategoriaAdmin[];
  selected: Set<number>;
  onChange: (s: Set<number>) => void;
}) {
  const toggle = (id: number) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    onChange(next);
  };
  // Agrupar por padre
  const roots = categorias.filter((c) => c.parent_id == null);
  const childrenOf = (pid: number) => categorias.filter((c) => c.parent_id === pid);

  return (
    <div className="space-y-3 max-h-72 overflow-y-auto rounded-md border hairline p-2">
      {roots.map((root) => (
        <div key={root.id}>
          <button
            type="button"
            onClick={() => toggle(root.id)}
            className="text-left"
          >
            <Badge variant={selected.has(root.id) ? "default" : "outline"} className="cursor-pointer">
              {root.nombre}
            </Badge>
          </button>
          <div className="flex flex-wrap gap-1 mt-1 ml-3">
            {childrenOf(root.id).map((c) => (
              <button key={c.id} type="button" onClick={() => toggle(c.id)}>
                <Badge variant={selected.has(c.id) ? "default" : "secondary"} className="cursor-pointer text-[10px]">
                  {c.nombre}
                </Badge>
              </button>
            ))}
          </div>
        </div>
      ))}
      {roots.length === 0 && (
        <p className="text-xs text-muted-foreground italic">No hay categorías. Creá algunas en /admin/settings.</p>
      )}
    </div>
  );
}

function Field({
  label, error, children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs uppercase tracking-wide text-muted-foreground">{label}</Label>
      {children}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
