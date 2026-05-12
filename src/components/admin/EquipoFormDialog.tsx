import { useEffect, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Upload, Plus, Trash2, Sparkles, ChevronUp, ChevronDown, GripVertical, Search } from "lucide-react";
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
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
import { DUENOS, isCanonicalDueno } from "@/lib/admin/duenos";
import { MonthYearPicker } from "@/components/admin/MonthYearPicker";

import { adminApi, type Equipo, type EquipoInput, type CategoriaAdmin, type KitComponente } from "@/lib/admin/api";
import { uploadFileToBucket, uploadExternalUrlToBucket, isHostedUrl } from "@/lib/equipment/photos";
import { authedJson } from "@/lib/authedFetch";
import { useUsdRate, useRoiPctDefault, calcularPrecioJornada } from "@/hooks/useSettings";
import { AutocompletarEquipoDialog, type AutocompletarResult } from "./autocompletar";
import { Link as LinkIcon, Image as ImageIcon, Check as CheckIcon, X } from "lucide-react";

const TPL_TOKENS = ["tipo", "marca", "modelo", "nombre", "montura", "formato", "resolucion"] as const;

/** Render preview del template (mismas reglas que useEquipos.renderNameTemplate). */
function renderTplPreview(tpl: string, vars: Record<string, string>): string {
  const lower: Record<string, string> = {};
  for (const k of Object.keys(vars)) lower[k.toLowerCase()] = vars[k] ?? "";
  const SEP = "[\\s\\-–—,/|·]";
  let out = tpl.replace(
    new RegExp(`(${SEP}+)?\\{([a-zA-Z_]+)\\}(${SEP}+)?`, "g"),
    (_m, before: string | undefined, key: string, after: string | undefined) => {
      const k = key.toLowerCase();
      if (!(k in lower)) return _m;
      const val = lower[k].trim();
      if (val) return `${before ?? ""}${val}${after ?? ""}`;
      if (after) return before ?? "";
      if (before) return "";
      return "";
    },
  );
  out = out.replace(/\s+/g, " ").trim();
  out = out.replace(new RegExp(`^${SEP}+|${SEP}+$`, "g"), "").trim();
  out = out.replace(new RegExp(`(${SEP})\\s*\\1+`, "g"), "$1");
  if (!out || /^[\s\-–—,/|·]+$/.test(out)) return "";
  return out;
}

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
  /** Devuelve el Equipo guardado (para que el form pueda persistir ficha extendida si fue importada). */
  onSubmit: (data: EquipoInput, etiquetas: string[]) => Promise<Equipo>;
  saving?: boolean;
}) {
  const isEdit = !!initial;
  const [enriching, setEnriching] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadingToR2, setUploadingToR2] = useState(false);
  const [tab, setTab] = useState("basicos");

  // Settings globales: tipo de cambio + ROI default. Se usan para
  // calcular precio_jornada de forma reactiva.
  const { rate: usdRate, isLoading: usdLoading } = useUsdRate();
  const roiDefault = useRoiPctDefault();

  // Si el usuario edita precio_jornada manualmente, no queremos seguir
  // sobreescribiéndolo con el cálculo automático. Track de "manual override".
  const [precioJornadaManual, setPrecioJornadaManual] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema) as never,
    defaultValues: {
      nombre: initial?.nombre ?? "",
      marca: initial?.marca ?? "",
      modelo: initial?.modelo ?? "",
      cantidad: initial?.cantidad ?? 1,
      precio_jornada: initial?.precio_jornada ?? undefined,
      precio_usd: initial?.precio_usd ?? undefined,
      // Default ROI desde settings (3% por convención de Rambla).
      roi_pct: initial?.roi_pct ?? (initial ? undefined : roiDefault),
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

  // Recalcular precio_jornada cuando cambia precio_usd, roi_pct o usd_rate.
  // Sólo si el usuario NO lo overrideó manualmente. Esto le permite editar
  // un precio fijo (ej. equipos especiales) sin que se le pise.
  const watchedUsd = form.watch("precio_usd");
  const watchedRoi = form.watch("roi_pct");
  useEffect(() => {
    if (precioJornadaManual) return;
    const calculado = calcularPrecioJornada(
      watchedUsd ? Number(watchedUsd) : null,
      usdRate,
      watchedRoi ? Number(watchedRoi) : null,
    );
    if (calculado !== null) {
      form.setValue("precio_jornada", calculado, { shouldDirty: true });
    }
  }, [watchedUsd, watchedRoi, usdRate, precioJornadaManual, form]);

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
  const [keywords, setKeywords] = useState<string[]>([]);
  const [keywordInput, setKeywordInput] = useState("");
  const [nombreTpl, setNombreTpl] = useState("");
  const tplInputRef = useRef<HTMLInputElement | null>(null);

  // ── Import desde URL (B&H, sitio oficial, etc.) ─────────────────────────
  const [importUrl, setImportUrl] = useState("");
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  // Ficha extendida importada (se persiste vía aplicarEnriquecimiento al guardar)
  const [importedFichaExt, setImportedFichaExt] = useState<Partial<AutocompletarResult> | null>(null);
  const [importSummary, setImportSummary] = useState<string | null>(null);

  // ── Búsqueda dedicada de fotos ─────────────────────────────────────────
  const [photoSearching, setPhotoSearching] = useState(false);
  const [photoCands, setPhotoCands] = useState<string[]>([]);
  const [pickingPhotoUrl, setPickingPhotoUrl] = useState<string | null>(null);

  // ── Foto pendiente (para CREATE mode, no se puede subir sin id) ────────
  // Cuando el usuario elige un archivo local en el form de "Nuevo equipo",
  // todavía no existe el equipo en la DB, así que no podemos subirlo a R2
  // (R2 path requiere el id). Guardamos el File en memoria + un blob URL
  // para preview, y lo subimos después del create con el id real.
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [pendingFilePreview, setPendingFilePreview] = useState<string>("");

  // Liberar el objectURL al desmontar / al cambiar el preview, para no
  // perder memoria.
  useEffect(() => {
    return () => {
      if (pendingFilePreview) URL.revokeObjectURL(pendingFilePreview);
    };
  }, [pendingFilePreview]);

  const buscarFotos = async () => {
    setPhotoSearching(true);
    // Timeout 30s: si Firecrawl o el scraper backend cuelgan, abortamos
    // para que el botón no quede en "Buscando…" indefinidamente.
    const ctrl = new AbortController();
    const timeoutId = setTimeout(() => ctrl.abort(), 30_000);
    try {
      const r = await authedJson<{ foto_candidates: string[] }>(
        "/api/admin/equipos/buscar-fotos",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            nombre: form.getValues("nombre"),
            marca:  form.getValues("marca") || null,
            modelo: form.getValues("modelo") || null,
            exclude: photoCands,
          }),
          signal: ctrl.signal,
        },
      );
      const news = (r.foto_candidates ?? []).filter((u) => !photoCands.includes(u));
      setPhotoCands((prev) => [...prev, ...news]);
      if (news.length === 0) {
        toast.info("No se encontraron más fotos.");
      } else {
        toast.success(`${news.length} fotos encontradas`);
      }
    } catch (e) {
      if (e instanceof Error && e.name === "AbortError") {
        toast.error("La búsqueda tardó demasiado (timeout 30s)");
      } else {
        toast.error(e instanceof Error ? e.message : "Error buscando fotos");
      }
    } finally {
      clearTimeout(timeoutId);
      setPhotoSearching(false);
    }
  };

  /** Click en un candidato. En EDIT sube a R2 al toque (queda hosteado y
   *  el form ve la URL final). En CREATE solo dejamos la URL externa en el
   *  form: el submit() la subirá a R2 después de crear el equipo. */
  const elegirFoto = async (externalUrl: string) => {
    if (!initial?.id) {
      // CREATE mode: setear la URL externa en el form, el submit se ocupa.
      // También limpiamos cualquier archivo pendiente para no pisar.
      if (pendingFile) {
        setPendingFile(null);
        if (pendingFilePreview) URL.revokeObjectURL(pendingFilePreview);
        setPendingFilePreview("");
      }
      form.setValue("foto_url", externalUrl, { shouldDirty: true });
      toast.info("Foto elegida (se subirá al crear el equipo)");
      return;
    }
    setPickingPhotoUrl(externalUrl);
    try {
      const r2url = await uploadExternalUrlToBucket(initial.id, externalUrl);
      form.setValue("foto_url", r2url, { shouldDirty: true });
      toast.success("Foto seleccionada y subida");
    } catch (e) {
      toast.error(`No se pudo subir: ${e instanceof Error ? e.message : ""}`);
    } finally {
      setPickingPhotoUrl(null);
    }
  };

  useEffect(() => {
    const f = fichaQ.data;
    if (f) {
      setMontura(f.montura ?? "");
      setFormato(f.formato ?? "");
      setResolucion(f.resolucion ?? "");
      setDescripcion(f.descripcion ?? "");
      setNotas(f.notas ?? "");
      setNombreTpl(f.nombre_publico_template ?? "");
      try {
        const arr = f.specs_json ? JSON.parse(f.specs_json) : [];
        setSpecs(Array.isArray(arr) ? arr : []);
      } catch { setSpecs([]); }
      try {
        const arr = f.keywords_json ? JSON.parse(f.keywords_json) : [];
        setKeywords(Array.isArray(arr) ? arr.filter((x) => typeof x === "string") : []);
      } catch { setKeywords([]); }
    } else if (!initial) {
      setMontura(""); setFormato(""); setResolucion("");
      setDescripcion(""); setNotas(""); setSpecs([]); setKeywords([]); setNombreTpl("");
    }
  }, [fichaQ.data, initial]);

  const addKeyword = () => {
    const v = keywordInput.trim().toLowerCase();
    if (!v) return;
    if (keywords.includes(v)) { setKeywordInput(""); return; }
    setKeywords([...keywords, v]);
    setKeywordInput("");
  };

  const subirFotoUrlAR2 = async () => {
    if (!initial?.id) return;
    const url = form.getValues("foto_url");
    if (!url || isHostedUrl(url)) return;
    setUploadingToR2(true);
    try {
      const r2url = await uploadExternalUrlToBucket(initial.id, url);
      form.setValue("foto_url", r2url, { shouldDirty: true });
      toast.success("Foto subida a R2");
    } catch (e) {
      toast.error(`No se pudo subir a R2: ${e instanceof Error ? e.message : ""}`);
    } finally {
      setUploadingToR2(false);
    }
  };

  const importarDesdeUrl = async () => {
    const u = importUrl.trim();
    if (!u) return;
    // Validar que sea una URL válida HTTP(S) antes de mandarla al backend.
    // Sin esto, un string suelto ("asd") se manda igual y vuelve un error
    // feo del backend después de varios segundos.
    try {
      const parsed = new URL(u);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        throw new Error("URL debe empezar con http:// o https://");
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "URL inválida";
      setImportError(msg);
      toast.error(`URL inválida: ${msg}`);
      return;
    }
    setImporting(true);
    setImportError(null);
    setImportSummary(null);
    try {
      const r = await authedJson<AutocompletarResult>("/api/admin/equipos/enriquecer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: u }),
      });
      // ── Llenar campos básicos del form (sólo si vinieron datos)
      const sets = (k: keyof FormValues, v: string | number | null | undefined) => {
        if (v !== null && v !== undefined && v !== "") {
          form.setValue(k, v as never, { shouldDirty: true });
        }
      };
      // Si no había nombre, usar el normalizado de la IA
      if (!form.getValues("nombre")?.trim() && r.nombre_normalizado) {
        sets("nombre", r.nombre_normalizado);
      }
      sets("marca", r.marca ?? "");
      sets("modelo", r.modelo ?? "");
      if (r.foto_url) sets("foto_url", r.foto_url);
      sets("bh_url", r.fuente_url);
      if (typeof r.precio_bh_usd === "number") sets("precio_usd", r.precio_bh_usd);

      // ── Llenar ficha visible
      if (r.descripcion) setDescripcion(r.descripcion);
      if (r.specs?.length) setSpecs(r.specs);
      if (r.keywords?.length) setKeywords(r.keywords);
      if (r.montura)    setMontura(r.montura);
      if (r.formato)    setFormato(r.formato);
      if (r.resolucion) setResolucion(r.resolucion);

      // ── Guardar ficha extendida para persistir al submit
      setImportedFichaExt(r);

      // Resumen visible
      const parts: string[] = [];
      if (r.specs?.length) parts.push(`${r.specs.length} specs`);
      if (r.keywords?.length) parts.push(`${r.keywords.length} keywords`);
      if (r.descripcion) parts.push("descripción");
      if (r.peso || r.dimensiones || r.alimentacion) parts.push("datos físicos");
      if (r.incluye?.length) parts.push("contenido caja");
      if (r.video_url) parts.push("video demo");
      setImportSummary(parts.length ? parts.join(" · ") : "datos básicos");
      toast.success("Datos importados", { description: parts.join(" · ") });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Error desconocido";
      setImportError(msg);
      toast.error(`No se pudo importar: ${msg}`);
    } finally {
      setImporting(false);
    }
  };

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
    const marca = (form.watch("marca") ?? "").trim();
    const modelo = (form.watch("modelo") ?? "").trim();
    const nombre = (form.watch("nombre") ?? "").trim();
    const vars: Record<string, string> = {
      tipo: tipoCat, marca, modelo, nombre, montura, formato, resolucion,
    };
    const tpl = nombreTpl.trim();
    if (tpl) {
      const rendered = renderTplPreview(tpl, vars);
      if (rendered) return rendered;
    }
    const parts = [tipoCat, marca, modelo, montura, formato, resolucion]
      .map((s) => s.trim()).filter(Boolean);
    if (parts.length === 0) return nombre || "—";
    const seen = new Set<string>();
    return parts.filter((p) => {
      const k = p.toLowerCase();
      if (seen.has(k)) return false;
      seen.add(k); return true;
    }).join(" ");
  }, [tipoCat, form, montura, formato, resolucion, nombreTpl]);

  const submit = form.handleSubmit(async (values) => {
    const etiquetas = (values.etiquetas_csv ?? "")
      .split(",").map((s: string) => s.trim()).filter(Boolean);
    const { etiquetas_csv: _omit, visible_catalogo, ...rest } = values;
    void _omit;

    // Detectamos si la foto del form va a requerir un upload post-create.
    // Tres casos posibles:
    //   1. pendingFile      → archivo local elegido en CREATE mode
    //   2. URL externa      → URL del campo que NO está hosteada en R2
    //   3. URL R2 ya hosteada (o vacía) → no hay que subir nada
    const fotoUrlForm = rest.foto_url || null;
    const fotoExternaPendiente =
      !pendingFile && fotoUrlForm && !isHostedUrl(fotoUrlForm) ? fotoUrlForm : null;

    // Para el INSERT/UPDATE inicial:
    //   - Si hay pendingFile → mandamos null y completamos después.
    //   - Si hay URL externa → la mandamos provisional (después la pisamos con la R2).
    //   - Si ya es R2 → la mandamos directamente.
    const fotoUrlInicial = pendingFile ? null : fotoUrlForm;

    const payload: EquipoInput = {
      nombre: rest.nombre,
      cantidad: rest.cantidad,
      estado: rest.estado,
      marca: rest.marca || null,
      modelo: rest.modelo || null,
      serie: rest.serie || null,
      dueno: rest.dueno || null,
      bh_url: rest.bh_url || null,
      foto_url: fotoUrlInicial,
      fecha_compra: rest.fecha_compra || null,
      precio_jornada: rest.precio_jornada ?? null,
      precio_usd: rest.precio_usd ?? null,
      roi_pct: rest.roi_pct ?? null,
      valor_reposicion: rest.valor_reposicion ?? null,
      visible_catalogo: visible_catalogo ? 1 : 0,
    };

    // Acumulamos errores parciales para reportar en un solo toast al final.
    const fallidos: string[] = [];
    let equipoId: number | undefined;

    try {
      // 1) Crear o actualizar el equipo. Si esto falla, abortamos: sin equipo
      //    no tiene sentido seguir con foto/ficha/categorías.
      const saved = await onSubmit(payload, etiquetas);
      equipoId = saved?.id ?? initial?.id;
      if (!equipoId) {
        toast.error("No se pudo guardar el equipo");
        return;
      }

      // 2) Subir foto pendiente (archivo local) o externa, con el id real.
      //    Si falla, el equipo queda con la URL provisional (o null) y se avisa.
      if (pendingFile) {
        try {
          const r2url = await uploadFileToBucket(equipoId, pendingFile);
          await adminApi.updateEquipo(equipoId, { foto_url: r2url });
          form.setValue("foto_url", r2url, { shouldDirty: false });
          // Limpiamos el archivo pendiente y su preview.
          setPendingFile(null);
          if (pendingFilePreview) URL.revokeObjectURL(pendingFilePreview);
          setPendingFilePreview("");
        } catch (e) {
          fallidos.push(`foto (${e instanceof Error ? e.message : "error"})`);
        }
      } else if (fotoExternaPendiente) {
        try {
          const r2url = await uploadExternalUrlToBucket(equipoId, fotoExternaPendiente);
          await adminApi.updateEquipo(equipoId, { foto_url: r2url });
          form.setValue("foto_url", r2url, { shouldDirty: false });
        } catch (e) {
          // Foto queda como URL externa — no es ideal pero el equipo está OK.
          fallidos.push(`foto a R2 (${e instanceof Error ? e.message : "error"})`);
        }
      }

      // 3) Ficha base (visible). Se guarda siempre que estemos editando o
      //    cuando creamos y hay datos importados / cargados.
      const tieneDatosFicha = (
        isEdit ||
        !!descripcion || !!notas || specs.length > 0 || keywords.length > 0 ||
        !!montura || !!formato || !!resolucion || !!nombreTpl.trim() ||
        !!importedFichaExt
      );
      if (tieneDatosFicha) {
        try {
          await adminApi.setFicha(equipoId, {
            descripcion: descripcion || null,
            notas: notas || null,
            specs_json: specs.length ? JSON.stringify(specs.filter((s) => s.label && s.value)) : null,
            montura: montura || null,
            formato: formato || null,
            resolucion: resolucion || null,
            keywords_json: keywords.length ? JSON.stringify(keywords) : null,
            nombre_publico_template: nombreTpl.trim() || null,
          });
        } catch (e) {
          fallidos.push(`ficha (${e instanceof Error ? e.message : "error"})`);
        }
      }

      // 4) Ficha extendida (peso, dimensiones, incluye, etc.) — cuando se
      //    importó desde URL.
      if (importedFichaExt) {
        try {
          const r = importedFichaExt;
          const ext: Record<string, unknown> = {};
          if (r.peso) ext.peso = r.peso;
          if (r.dimensiones) ext.dimensiones = r.dimensiones;
          if (r.alimentacion) ext.alimentacion = r.alimentacion;
          if (r.video_url) ext.video_url = r.video_url;
          if (typeof r.precio_bh_usd === "number") ext.precio_bh_usd = r.precio_bh_usd;
          if (r.incluye?.length) ext.incluye = r.incluye;
          if (r.conectividad?.length) ext.conectividad = r.conectividad;
          if (r.compatible_con?.length) ext.compatible_con = r.compatible_con;
          if (r.fuente_url) ext.fuente_url = r.fuente_url;
          if (r.fuente_titulo) ext.fuente_titulo = r.fuente_titulo;
          if (r.enriquecido_fuente) ext.enriquecido_fuente = r.enriquecido_fuente;
          if (r.raw) ext.raw = r.raw;
          if (Object.keys(ext).length > 0) {
            await adminApi.aplicarEnriquecimiento(equipoId, ext);
          }
        } catch (e) {
          fallidos.push(`ficha extendida (${e instanceof Error ? e.message : "error"})`);
        }
      }

      // 5) Categorías: sólo cuando estamos editando (en create no hay UI).
      if (isEdit && initial) {
        try {
          await adminApi.setCategorias(initial.id, [...selectedCats]);
        } catch (e) {
          fallidos.push(`categorías (${e instanceof Error ? e.message : "error"})`);
        }
      }
    } catch (e) {
      // Falla en el create/update del equipo (1). El dialog queda abierto
      // para que el usuario reintente sin perder el form.
      toast.error(e instanceof Error ? e.message : "Error al guardar el equipo");
      return;
    }

    // 6) Notificación final al usuario y cierre del dialog.
    if (fallidos.length > 0) {
      toast.warning(isEdit ? "Equipo actualizado con avisos" : "Equipo creado con avisos", {
        description: `Falló: ${fallidos.join(" · ")}`,
        duration: 7000,
      });
    } else {
      toast.success(isEdit ? "Equipo actualizado" : "Equipo creado");
    }
    onOpenChange(false);
  });

  // Upload de foto al bucket equipos-fotos.
  // EDIT mode: sube directo al toque, queda en R2 con el id del equipo.
  // CREATE mode: guarda el File en memoria + preview local. El submit() lo
  //   sube cuando el equipo ya existe (no podemos subir a R2 sin id).
  const handleUpload = async (file: File) => {
    if (!file) return;
    if (!initial?.id) {
      // CREATE mode: pendingFile + blob URL para preview.
      setPendingFile(file);
      if (pendingFilePreview) URL.revokeObjectURL(pendingFilePreview);
      setPendingFilePreview(URL.createObjectURL(file));
      // Limpiamos cualquier URL externa que hubiera en el form: el upload
      // del File pendiente tiene precedencia sobre cualquier URL.
      form.setValue("foto_url", "", { shouldDirty: true });
      toast.info("Foto lista — se va a subir cuando crees el equipo");
      return;
    }
    setUploading(true);
    try {
      const publicUrl = await uploadFileToBucket(initial.id, file);
      form.setValue("foto_url", publicUrl, { shouldDirty: true });
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
        <DialogContent className="w-full sm:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <DialogTitle className="font-display text-2xl">
                {isEdit ? "Editar equipo" : "Nuevo equipo"}
              </DialogTitle>
              {isEdit && initial && (
                <Button type="button" variant="outline" size="sm" onClick={() => setEnriching(true)}>
                  <Sparkles className="h-4 w-4 mr-1.5 text-amber" />
                  Auto-completar
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
            {/* ── Importar desde URL ──────────────────────────────────── */}
            <div className="rounded-md border hairline bg-amber-soft/40 p-3 space-y-2">
              <div className="flex items-center gap-1.5 text-xs font-medium text-ink/80">
                <LinkIcon className="h-3.5 w-3.5" />
                {isEdit ? "Actualizar desde URL" : "Crear desde URL"}
                <span className="font-normal text-muted-foreground">
                  · pegá un link de B&amp;H, sitio oficial o Adorama
                </span>
              </div>
              <div className="flex gap-2">
                <Input
                  value={importUrl}
                  onChange={(e) => setImportUrl(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") { e.preventDefault(); importarDesdeUrl(); }
                  }}
                  placeholder="https://www.bhphotovideo.com/c/product/..."
                  className="font-mono text-xs"
                />
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={importarDesdeUrl}
                  disabled={importing || !importUrl.trim()}
                  className="shrink-0"
                >
                  {importing ? (
                    <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Importando…</>
                  ) : (
                    <><Sparkles className="h-3.5 w-3.5 mr-1.5 text-amber" />Importar</>
                  )}
                </Button>
              </div>
              {importError && (
                <div className="text-xs text-destructive">{importError}</div>
              )}
              {importSummary && !importError && (
                <div className="text-xs text-muted-foreground">
                  ✓ Importado: <span className="text-ink">{importSummary}</span>
                  {!isEdit && " (se guardará al crear el equipo)"}
                </div>
              )}
            </div>

            <Tabs value={tab} onValueChange={setTab}>
              <TabsList className="w-full">
                <TabsTrigger value="basicos" className="flex-1 text-xs sm:text-sm">Básicos</TabsTrigger>
                <TabsTrigger value="ficha" className="flex-1 text-xs sm:text-sm" disabled={!isEdit}>
                  Ficha
                </TabsTrigger>
                <TabsTrigger value="cats" className="flex-1 text-xs sm:text-sm" disabled={!isEdit}>
                  Cats
                </TabsTrigger>
                <TabsTrigger value="kit" className="flex-1 text-xs sm:text-sm" disabled={!isEdit}>
                  Kit
                </TabsTrigger>
              </TabsList>

              {/* ── Datos básicos ─────────────────────────────────────── */}
              <TabsContent value="basicos" className="space-y-4 mt-4">
                <Field label="Nombre interno" error={form.formState.errors.nombre?.message}>
                  <Input {...form.register("nombre")} placeholder="Ej: FX3 Cuerpo" />
                </Field>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Field label="Marca"><Input {...form.register("marca")} /></Field>
                  <Field label="Modelo"><Input {...form.register("modelo")} /></Field>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <Field label="Stock"><Input type="number" min={0} {...form.register("cantidad")} /></Field>
                  <Field label="Valor USD"><Input type="number" min={0} step="0.01" {...form.register("precio_usd")} /></Field>
                  <Field label="ROI %"><Input type="number" min={0} step="0.01" {...form.register("roi_pct")} /></Field>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs uppercase tracking-wide text-muted-foreground">
                        Precio/día (ARS)
                      </Label>
                      {precioJornadaManual ? (
                        <button
                          type="button"
                          onClick={() => setPrecioJornadaManual(false)}
                          className="text-[10px] text-amber hover:underline"
                          title="Volver al cálculo automático"
                        >
                          ↺ auto
                        </button>
                      ) : (
                        <span className="text-[10px] text-muted-foreground">auto</span>
                      )}
                    </div>
                    <Input
                      type="number" min={0}
                      {...form.register("precio_jornada", {
                        // Si el usuario tipea, lo marcamos como manual para
                        // que el efecto reactivo deje de pisarlo.
                        onChange: () => {
                          if (!precioJornadaManual) setPrecioJornadaManual(true);
                        },
                      })}
                    />
                    {!precioJornadaManual && form.watch("precio_usd") && form.watch("roi_pct") && (
                      <p className="text-[10px] text-muted-foreground font-mono">
                        {Number(form.watch("precio_usd")).toFixed(2)} × {usdLoading ? "…" : usdRate} × {Number(form.watch("roi_pct"))}%
                        {form.watch("precio_jornada") != null && (
                          <span className="text-ink"> = ${Number(form.watch("precio_jornada")).toLocaleString("es-AR", { maximumFractionDigits: 0 })}</span>
                        )}
                      </p>
                    )}
                  </div>
                  <Field label="Valor reposición (USD)">
                    <Input type="number" min={0} step="0.01" {...form.register("valor_reposicion")} />
                  </Field>
                  <Field label="Fecha de compra">
                    <MonthYearPicker
                      value={form.watch("fecha_compra")}
                      onChange={(v) => form.setValue("fecha_compra", v, { shouldDirty: true })}
                    />
                  </Field>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Field label="N° Serie">
                    <div className="flex items-center gap-1.5">
                      <Input
                        {...form.register("serie")}
                        placeholder="N° de serie"
                        className="flex-1"
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          form.setValue("serie", "N/A", { shouldDirty: true })
                        }
                        className="shrink-0 text-xs h-9"
                        title="Marcar como no aplica (ej. reflectores, cables sin serie)"
                      >
                        N/A
                      </Button>
                    </div>
                  </Field>
                  <Field label="Dueño">
                    {(() => {
                      const value = form.watch("dueno") ?? "Rambla";
                      const isLegacy = value && !isCanonicalDueno(value);
                      return (
                        <Select
                          value={isLegacy ? "" : value}
                          onValueChange={(v) => form.setValue("dueno", v, { shouldDirty: true })}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder={isLegacy ? `(legacy: ${value})` : "Elegir"} />
                          </SelectTrigger>
                          <SelectContent>
                            {DUENOS.map((d) => (
                              <SelectItem key={d} value={d}>{d}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      );
                    })()}
                  </Field>
                </div>

                <Field label="Link de fuente (B&H, Adorama…)">
                  <Input {...form.register("bh_url")} className="font-mono text-xs" placeholder="https://..." />
                </Field>

                <Field label="Foto">
                  <div className="space-y-2">
                    {/* Foto card: cuando hay foto elegida */}
                    {(pendingFilePreview || form.watch("foto_url")) ? (
                      <div className="rounded-lg border hairline bg-muted/20 overflow-hidden">
                        <div className="relative">
                          <img
                            src={pendingFilePreview || form.watch("foto_url") || ""}
                            alt="Foto"
                            className="w-full max-h-52 object-contain bg-white"
                            onError={(e) => { (e.target as HTMLImageElement).style.opacity = "0.3"; }}
                          />
                          {/* Badge estado */}
                          <div className="absolute top-2 left-2">
                            {pendingFile ? (
                              <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 border border-blue-200 px-2 py-0.5 text-[11px] text-blue-700">
                                Archivo local
                              </span>
                            ) : isHostedUrl(form.watch("foto_url")) ? (
                              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[11px] text-emerald-700 font-medium">
                                ✓ En R2
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-[11px] text-amber-700">
                                URL externa
                              </span>
                            )}
                          </div>
                          {/* Botón limpiar */}
                          <button
                            type="button"
                            className="absolute top-2 right-2 rounded-full bg-background/90 border hairline p-1 hover:bg-background"
                            onClick={() => {
                              form.setValue("foto_url", "", { shouldDirty: true });
                              setPendingFile(null);
                              if (pendingFilePreview) URL.revokeObjectURL(pendingFilePreview);
                              setPendingFilePreview("");
                            }}
                          >
                            <X className="h-3.5 w-3.5 text-muted-foreground" />
                          </button>
                        </div>
                        <div className="px-3 py-2 flex items-center gap-2 border-t hairline">
                          {!pendingFile && form.watch("foto_url") && !isHostedUrl(form.watch("foto_url")) && isEdit && (
                            <Button
                              type="button" variant="outline" size="sm"
                              className="h-7 text-xs shrink-0"
                              disabled={uploadingToR2}
                              onClick={subirFotoUrlAR2}
                            >
                              {uploadingToR2
                                ? <><Loader2 className="h-3 w-3 mr-1 animate-spin" />Subiendo…</>
                                : "Subir a R2"}
                            </Button>
                          )}
                          <p className="font-mono text-[10px] text-muted-foreground truncate min-w-0 flex-1">
                            {pendingFile ? pendingFile.name : form.watch("foto_url")}
                          </p>
                          <label className="inline-flex shrink-0">
                            <input type="file" accept="image/*" className="hidden"
                              onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])} />
                            <Button type="button" variant="ghost" size="sm" className="h-7 text-xs px-2" disabled={uploading} asChild>
                              <span className="cursor-pointer" title="Subir otra foto">
                                {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
                              </span>
                            </Button>
                          </label>
                        </div>
                      </div>
                    ) : (
                      /* Sin foto: input URL + botón Subir */
                      <div className="flex gap-2">
                        <Input {...form.register("foto_url")} className="font-mono text-xs flex-1" placeholder="https://… o subí una foto" />
                        <label className="inline-flex">
                          <input type="file" accept="image/*" className="hidden"
                            onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])} />
                          <Button type="button" variant="outline" size="sm" disabled={uploading} asChild>
                            <span className="cursor-pointer">
                              {uploading
                                ? <><Loader2 className="h-4 w-4 mr-1 animate-spin" />Subiendo…</>
                                : <><Upload className="h-4 w-4 mr-1" />Subir</>}
                            </span>
                          </Button>
                        </label>
                      </div>
                    )}

                    {/* Candidatos de buscar-fotos */}
                    {photoCands.length > 0 && (
                      <div>
                        <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">
                          {photoCands.length} candidatas — click para usar
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {photoCands.map((u) => {
                            const selected = form.watch("foto_url") === u;
                            const loading = pickingPhotoUrl === u;
                            return (
                              <button
                                type="button"
                                key={u}
                                onClick={() => elegirFoto(u)}
                                disabled={loading}
                                title={u}
                                className={
                                  "relative h-14 w-14 overflow-hidden rounded border transition " +
                                  (selected
                                    ? "border-amber ring-2 ring-amber/40"
                                    : "border-muted hover:border-ink/30")
                                }
                              >
                                <img
                                  src={u}
                                  alt=""
                                  className="h-full w-full object-cover"
                                  onError={(e) => {
                                    (e.target as HTMLImageElement).style.opacity = "0.2";
                                  }}
                                />
                                {loading && (
                                  <div className="absolute inset-0 grid place-items-center bg-background/80">
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                  </div>
                                )}
                                {selected && !loading && (
                                  <span className="absolute right-0.5 top-0.5 rounded-full bg-amber p-0.5">
                                    <CheckIcon className="h-2.5 w-2.5 text-ink" />
                                  </span>
                                )}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                </Field>

                <Field label="Etiquetas manuales (separadas por coma)">
                  <Input placeholder="Ej: vintage, kit boda" {...form.register("etiquetas_csv")} />
                </Field>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-end">
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

                <Field label="Nombre público (template)">
                  <Input
                    ref={tplInputRef}
                    value={nombreTpl}
                    onChange={(e) => setNombreTpl(e.target.value)}
                    placeholder="Vacío = automático. Ej: {marca} {modelo} — {montura}"
                    className="font-mono text-sm"
                  />
                  <div className="mt-2 flex flex-wrap gap-1">
                    {TPL_TOKENS.map((t) => (
                      <button
                        key={t}
                        type="button"
                        onClick={() => {
                          const token = `{${t}}`;
                          const el = tplInputRef.current;
                          if (!el) {
                            setNombreTpl((v) => (v ? `${v} ${token}` : token));
                            return;
                          }
                          const start = el.selectionStart ?? nombreTpl.length;
                          const end = el.selectionEnd ?? nombreTpl.length;
                          const next = nombreTpl.slice(0, start) + token + nombreTpl.slice(end);
                          setNombreTpl(next);
                          requestAnimationFrame(() => {
                            el.focus();
                            const pos = start + token.length;
                            el.setSelectionRange(pos, pos);
                          });
                        }}
                        className="rounded-full border hairline bg-background px-2 py-0.5 font-mono text-[10px] text-muted-foreground transition hover:border-ink hover:text-ink"
                      >
                        {`{${t}}`}
                      </button>
                    ))}
                    {nombreTpl && (
                      <button
                        type="button"
                        onClick={() => setNombreTpl("")}
                        className="ml-auto rounded-full border hairline bg-background px-2 py-0.5 font-mono text-[10px] text-muted-foreground transition hover:border-destructive hover:text-destructive"
                      >
                        Limpiar (usar automático)
                      </button>
                    )}
                  </div>
                  <p className="mt-2 text-[11px] text-muted-foreground">
                    Vista previa: <span className="font-medium text-ink">{previewName}</span>
                  </p>
                </Field>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
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
                    {specs.map((s, i) => {
                      const move = (dir: -1 | 1) => {
                        const j = i + dir;
                        if (j < 0 || j >= specs.length) return;
                        const next = [...specs];
                        [next[i], next[j]] = [next[j], next[i]];
                        setSpecs(next);
                      };
                      return (
                        <div
                          key={i}
                          className="flex gap-2 items-start group"
                          draggable
                          onDragStart={(e) => {
                            e.dataTransfer.effectAllowed = "move";
                            e.dataTransfer.setData("text/plain", String(i));
                          }}
                          onDragOver={(e) => {
                            e.preventDefault();
                            e.dataTransfer.dropEffect = "move";
                          }}
                          onDrop={(e) => {
                            e.preventDefault();
                            const from = Number(e.dataTransfer.getData("text/plain"));
                            if (Number.isNaN(from) || from === i) return;
                            const next = [...specs];
                            const [moved] = next.splice(from, 1);
                            next.splice(i, 0, moved);
                            setSpecs(next);
                          }}
                        >
                          <div className="flex flex-col items-center pt-1.5 text-muted-foreground">
                            <GripVertical className="h-4 w-4 cursor-grab opacity-40 group-hover:opacity-100" />
                          </div>
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
                          <div className="flex flex-col">
                            <Button type="button" size="icon" variant="ghost" className="h-5 w-7" disabled={i === 0} onClick={() => move(-1)} aria-label="Subir">
                              <ChevronUp className="h-3.5 w-3.5" />
                            </Button>
                            <Button type="button" size="icon" variant="ghost" className="h-5 w-7" disabled={i === specs.length - 1} onClick={() => move(1)} aria-label="Bajar">
                              <ChevronDown className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                          <Button type="button" size="icon" variant="ghost" onClick={() => setSpecs(specs.filter((_, j) => j !== i))}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      );
                    })}
                    {specs.length === 0 && (
                      <p className="text-xs text-muted-foreground italic">Sin specs.</p>
                    )}
                  </div>
                </div>

                <div>
                  <Label className="text-xs uppercase tracking-wide text-muted-foreground">
                    Palabras clave ({keywords.length})
                  </Label>
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    Tags editoriales propios del equipo (ej. <em>bicolor</em>, <em>CRI 96</em>, <em>global shutter</em>).
                    Aparecen como chips en el catálogo.
                  </p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {keywords.map((k) => (
                      <span
                        key={k}
                        className="inline-flex items-center gap-1 rounded-full bg-amber-soft px-2 py-0.5 text-[11px] font-mono uppercase tracking-wider text-ink/80"
                      >
                        {k}
                        <button
                          type="button"
                          onClick={() => setKeywords(keywords.filter((x) => x !== k))}
                          className="hover:text-destructive"
                          aria-label={`Quitar ${k}`}
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </span>
                    ))}
                    {keywords.length === 0 && (
                      <span className="text-[11px] text-muted-foreground italic">Sin keywords.</span>
                    )}
                  </div>
                  <div className="mt-2 flex gap-1.5">
                    <Input
                      value={keywordInput}
                      onChange={(e) => setKeywordInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") { e.preventDefault(); addKeyword(); }
                      }}
                      placeholder="Agregar palabra clave y Enter…"
                      className="h-8 text-xs"
                    />
                    <Button type="button" size="sm" variant="outline" onClick={addKeyword} className="h-8">
                      <Plus className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              </TabsContent>

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

              {/* ── Kit / sub-equipos ─────────────────────────────────── */}
              <TabsContent value="kit" className="space-y-3 mt-4">
                <div className="rounded-md border hairline bg-muted/30 px-3 py-2 text-xs">
                  Componentes que <strong>vienen incluidos</strong> al alquilar este equipo.
                  El stock de cada componente se descuenta automáticamente.
                </div>
                {isEdit && initial && (
                  <KitEditor equipoId={initial.id} />
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
        <AutocompletarEquipoDialog
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

// ── SortableKitItem ──────────────────────────────────────────────────────────

function SortableKitItem({
  item, busy, onUpdateQty, onRemove,
}: {
  item: KitComponente;
  busy: number | null;
  onUpdateQty: (id: number, qty: number) => void;
  onRemove: (id: number) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: item.componente_id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 rounded-md border hairline px-2 py-1.5 bg-background"
    >
      {/* drag handle */}
      <button
        type="button"
        className="cursor-grab active:cursor-grabbing text-muted-foreground/50 hover:text-muted-foreground touch-none"
        {...attributes}
        {...listeners}
        tabIndex={-1}
      >
        <GripVertical className="h-4 w-4" />
      </button>

      {item.foto_url
        ? <img src={item.foto_url} alt="" className="h-8 w-8 object-contain rounded bg-muted/30 shrink-0" />
        : <div className="h-8 w-8 rounded bg-muted/30 shrink-0" />
      }

      <div className="flex-1 min-w-0">
        <div className="text-sm truncate">{item.nombre}</div>
        {item.marca && <div className="text-[11px] text-muted-foreground">{item.marca}</div>}
      </div>

      <Input
        type="number" min={1}
        value={item.cantidad}
        className="w-16 h-8 text-center"
        onChange={(e) => onUpdateQty(item.componente_id, Math.max(1, parseInt(e.target.value || "1", 10)))}
        disabled={busy === item.componente_id}
      />
      <Button type="button" size="icon" variant="ghost"
        onClick={() => onRemove(item.componente_id)}
        disabled={busy === item.componente_id}>
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  );
}

// ── KitEditor ────────────────────────────────────────────────────────────────

function KitEditor({ equipoId }: { equipoId: number }) {
  const [items, setItems] = useState<KitComponente[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<Equipo[]>([]);
  const [searching, setSearching] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const load = async () => {
    setLoading(true);
    try {
      const k = await adminApi.getKit(equipoId);
      setItems(k);
    } catch (e) {
      toast.error(`Kit: ${e instanceof Error ? e.message : ""}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); /* eslint-disable-next-line */ }, [equipoId]);

  useEffect(() => {
    if (!search.trim() || search.trim().length < 2) { setResults([]); return; }
    const t = setTimeout(async () => {
      setSearching(true);
      try {
        const r = await adminApi.listEquipos({ q: search.trim(), per_page: 15 });
        setResults(r.items.filter((e) => e.id !== equipoId));
      } finally { setSearching(false); }
    }, 250);
    return () => clearTimeout(t);
  }, [search, equipoId]);

  const add = async (componente_id: number) => {
    setBusy(componente_id);
    try {
      await adminApi.addKitItem(equipoId, componente_id, 1);
      await load();
      setSearch("");
      setResults([]);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error");
    } finally { setBusy(null); }
  };

  const updateQty = async (componente_id: number, cantidad: number) => {
    if (cantidad < 1) return;
    setBusy(componente_id);
    try {
      await adminApi.addKitItem(equipoId, componente_id, cantidad);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error");
    } finally { setBusy(null); }
  };

  const remove = async (componente_id: number) => {
    setBusy(componente_id);
    try {
      await adminApi.removeKitItem(equipoId, componente_id);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error");
    } finally { setBusy(null); }
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = items.findIndex((i) => i.componente_id === active.id);
    const newIndex = items.findIndex((i) => i.componente_id === over.id);
    if (oldIndex === -1 || newIndex === -1) return;

    const reordered = arrayMove(items, oldIndex, newIndex);
    setItems(reordered); // optimistic update
    try {
      await adminApi.reorderKit(equipoId, reordered.map((i) => i.componente_id));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error al reordenar");
      await load(); // revert
    }
  };

  return (
    <div className="space-y-4">
      {/* ── Buscador (arriba) ── */}
      <div>
        <Label className="text-xs uppercase tracking-wide text-muted-foreground">Agregar componente</Label>
        <div className="relative mt-1">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por nombre, marca o modelo…"
            className="pl-8"
          />
          {searching && (
            <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 animate-spin text-muted-foreground" />
          )}
        </div>

        {results.length > 0 && (
          <div className="mt-1.5 max-h-56 overflow-y-auto rounded-md border hairline divide-y shadow-sm">
            {results.map((r) => (
              <button key={r.id} type="button"
                className="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-accent text-left disabled:opacity-50"
                onClick={() => add(r.id)}
                disabled={busy === r.id || items.some((i) => i.componente_id === r.id)}>
                {r.foto_url
                  ? <img src={r.foto_url} alt="" className="h-7 w-7 object-contain rounded bg-muted/30 shrink-0" />
                  : <div className="h-7 w-7 rounded bg-muted/30 shrink-0" />
                }
                <div className="flex-1 min-w-0">
                  <div className="text-sm truncate">{r.nombre}</div>
                  <div className="text-[11px] text-muted-foreground truncate">
                    {[r.marca, r.modelo].filter(Boolean).join(" / ")} · stock {r.cantidad}
                  </div>
                </div>
                {items.some((i) => i.componente_id === r.id)
                  ? <Badge variant="secondary" className="text-[10px]">en kit</Badge>
                  : <Plus className="h-4 w-4 text-muted-foreground shrink-0" />}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Lista de componentes con drag-and-drop ── */}
      <div>
        <Label className="text-xs uppercase tracking-wide text-muted-foreground">
          Componentes ({items.length})
          {items.length > 1 && (
            <span className="ml-1.5 normal-case font-normal text-muted-foreground/60">· arrastrá para reordenar</span>
          )}
        </Label>

        {loading ? (
          <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Cargando…
          </div>
        ) : items.length === 0 ? (
          <p className="text-xs text-muted-foreground italic mt-2">
            Sin componentes. Usá el buscador de arriba para agregar.
          </p>
        ) : (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext
              items={items.map((i) => i.componente_id)}
              strategy={verticalListSortingStrategy}
            >
              <div className="space-y-1.5 mt-2">
                {items.map((it) => (
                  <SortableKitItem
                    key={it.componente_id}
                    item={it}
                    busy={busy}
                    onUpdateQty={updateQty}
                    onRemove={remove}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </div>
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
