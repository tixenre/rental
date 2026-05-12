/**
 * Rediseño del form de equipos (V2).
 *
 * Cambios vs el original:
 *  - Sin tabs. Scroll lineal con secciones colapsables (Ficha, Kit, Avanzado).
 *  - Mismo flow CREATE / EDIT (sin tabs deshabilitados al crear).
 *  - Identificación: nombre interno + nombre público lado a lado, con toggle
 *    de auto-gen por categoría.
 *  - "Link de fuente" como primera cosa del form, con botones para abrir y
 *    copiar al clipboard.
 *  - "Buscar foto" + "Autocompletar todo" como dos botones del mismo widget.
 *  - Diff visual al traer specs del autocompletar.
 *  - Kit con drag-drop (igual que el viejo).
 *
 * El backend no cambia: usa los mismos endpoints (adminApi.createEquipo,
 * setFicha, setCategorias, aplicarEnriquecimiento, etc.).
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery } from "@tanstack/react-query";
import {
  Loader2, Upload, Plus, Trash2, Sparkles, Search, GripVertical,
  Link as LinkIcon, Image as ImageIcon, X, Copy, ExternalLink, ChevronDown,
} from "lucide-react";
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
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
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
import type { AutocompletarResult } from "../autocompletar";
import { generarNombrePublico, categoriaSoportaAutoGen } from "./nombre-publico";

// ════════════════════════════════════════════════════════════════════
// Schema
// ════════════════════════════════════════════════════════════════════

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
  ficha_completa: z.boolean().default(false),
});

type FormValues = z.infer<typeof schema>;
type Spec = { id: string; label: string; value: string };

const newSpec = (label = "", value = ""): Spec => ({
  id: crypto.randomUUID(),
  label,
  value,
});

const withIds = (raw: Array<{ label: string; value: string }>): Spec[] =>
  raw.map((s) => newSpec(s.label, s.value));

const sameLabel = (a: string, b: string) =>
  a.trim().toLowerCase() === b.trim().toLowerCase();

/** Une dos listas de specs por label (case-insensitive). Si ya existe, no pisa. */
const mergeSpecs = (existing: Spec[], extras: Spec[]): Spec[] => {
  const result = [...existing];
  for (const e of extras) {
    if (!e.value.trim()) continue;
    if (result.some((s) => sameLabel(s.label, e.label))) continue;
    result.push(e);
  }
  return result;
};

/** Devuelve el valor de un spec por label, o "". */
const findSpecValue = (specs: Spec[], label: string): string =>
  specs.find((s) => sameLabel(s.label, label))?.value ?? "";

const uniq = <T,>(arr: T[]): T[] => Array.from(new Set(arr));

// ════════════════════════════════════════════════════════════════════
// Componente principal
// ════════════════════════════════════════════════════════════════════

export function EquipoFormDialogV2({
  open,
  onOpenChange,
  initial,
  onSubmit,
  saving,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  initial?: Equipo | null;
  onSubmit: (data: EquipoInput, etiquetas: string[]) => Promise<Equipo>;
  saving?: boolean;
}) {
  const isEdit = !!initial;
  const { rate: usdRate } = useUsdRate();
  const roiDefault = useRoiPctDefault();

  // ── Estado del form (react-hook-form) ──────────────────────────────
  const form = useForm<FormValues>({
    resolver: zodResolver(schema) as never,
    defaultValues: {
      nombre: initial?.nombre ?? "",
      marca: initial?.marca ?? "",
      modelo: initial?.modelo ?? "",
      cantidad: initial?.cantidad ?? 1,
      precio_jornada: initial?.precio_jornada ?? undefined,
      precio_usd: initial?.precio_usd ?? undefined,
      roi_pct: initial?.roi_pct ?? (initial ? undefined : roiDefault),
      valor_reposicion: initial?.valor_reposicion ?? undefined,
      fecha_compra: initial?.fecha_compra ?? "",
      serie: initial?.serie ?? "",
      bh_url: initial?.bh_url ?? "",
      foto_url: initial?.foto_url ?? "",
      dueno: initial?.dueno ?? "Rambla",
      estado: (initial?.estado as FormValues["estado"]) ?? "operativo",
      visible_catalogo: initial ? Boolean(initial.visible_catalogo) : true,
      ficha_completa: initial ? Boolean(initial.ficha_completa) : false,
    },
  });

  // ── Estado de ficha (campos que no van en form-hook) ───────────────
  // Nota: montura/formato/resolucion ya no son inputs propios — viven como
  // specs. En load se migran a specs si los campos dedicados del backend
  // tienen valor, y en save se extraen de specs para escribir los campos
  // dedicados (que el catálogo público sigue leyendo).
  const [descripcion, setDescripcion] = useState("");
  const [notas, setNotas] = useState("");
  const [specs, setSpecs] = useState<Spec[]>([]);
  // Etiquetas unificadas: en V2 keywords y etiquetas son lo mismo. En save se
  // envían a los dos backends (etiquetas vía onSubmit, keywords_json vía setFicha).
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");

  // ── Nombre público ─────────────────────────────────────────────────
  // Input libre + toggle "generar automático desde categoría" (ver nombre-publico.ts).
  const [nombrePublico, setNombrePublico] = useState("");
  const [nombrePublicoAuto, setNombrePublicoAuto] = useState(false);

  // ── Autocompletar (URL importer) ───────────────────────────────────
  const [autocompletarUrl, setAutocompletarUrl] = useState("");
  const [autocompletando, setAutocompletando] = useState(false);
  const [importedFichaExt, setImportedFichaExt] = useState<Partial<AutocompletarResult> | null>(null);

  // Cache del scrape: se carga desde ficha.raw_json al editar y se actualiza
  // cuando se hace autocompletar. Habilita los botones ✨ por sección para
  // re-aplicar campos sin volver a scrapear.
  const [cachedScrape, setCachedScrape] = useState<Partial<AutocompletarResult> | null>(null);

  // Specs traídos del autocompletar: se guardan en una lista separada para
  // que el usuario los apruebe uno por uno (vs los specs actuales).
  const [specsPropuestos, setSpecsPropuestos] = useState<Spec[]>([]);

  // ── Buscar fotos ───────────────────────────────────────────────────
  const [photoSearching, setPhotoSearching] = useState(false);
  const [photoCands, setPhotoCands] = useState<string[]>([]);
  const [pickingPhotoUrl, setPickingPhotoUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadingToR2, setUploadingToR2] = useState(false);

  // CREATE mode: archivo local que se sube después de crear el equipo.
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [pendingFilePreview, setPendingFilePreview] = useState("");
  useEffect(() => () => {
    if (pendingFilePreview) URL.revokeObjectURL(pendingFilePreview);
  }, [pendingFilePreview]);

  // ── Manual override del precio/día ─────────────────────────────────
  const [precioJornadaManual, setPrecioJornadaManual] = useState(false);
  const watchedUsd = form.watch("precio_usd");
  const watchedRoi = form.watch("roi_pct");
  useEffect(() => {
    if (precioJornadaManual) return;
    const calc = calcularPrecioJornada(
      watchedUsd ? Number(watchedUsd) : null,
      usdRate,
      watchedRoi ? Number(watchedRoi) : null,
    );
    if (calc !== null) form.setValue("precio_jornada", calc, { shouldDirty: true });
  }, [watchedUsd, watchedRoi, usdRate, precioJornadaManual, form]);

  // ── Cargar ficha cuando estamos editando ──────────────────────────
  const fichaQ = useQuery({
    queryKey: ["admin", "equipo-ficha", initial?.id],
    queryFn: () => adminApi.getFicha(initial!.id),
    enabled: !!initial?.id && open,
  });
  useEffect(() => {
    const f = fichaQ.data;
    if (f) {
      setDescripcion(f.descripcion ?? "");
      setNotas(f.notas ?? "");
      // Si el nombre público guardado no tiene tokens, lo usamos como literal.
      // Si tiene tokens ({...}), lo dejamos vacío — el usuario regenera con auto.
      const tpl = (f.nombre_publico_template ?? "").trim();
      setNombrePublico(/\{[^}]+\}/.test(tpl) ? "" : tpl);

      let parsedSpecs: Spec[] = [];
      try {
        const raw = f.specs_json ? JSON.parse(f.specs_json) : [];
        parsedSpecs = withIds(Array.isArray(raw) ? raw : []);
      } catch { parsedSpecs = []; }

      // Migrar montura/formato/resolucion dedicados → specs (si todavía no están).
      const dedicated: Spec[] = [];
      if (f.montura?.trim()) dedicated.push(newSpec("Montura", f.montura.trim()));
      if (f.formato?.trim()) dedicated.push(newSpec("Formato", f.formato.trim()));
      if (f.resolucion?.trim()) dedicated.push(newSpec("Resolución", f.resolucion.trim()));
      setSpecs(mergeSpecs(parsedSpecs, dedicated));

      // Unificar keywords_json (ficha) + etiquetas (equipo top-level).
      let kws: string[] = [];
      try {
        const arr = f.keywords_json ? JSON.parse(f.keywords_json) : [];
        kws = Array.isArray(arr) ? arr.filter((x) => typeof x === "string") : [];
      } catch { kws = []; }
      setTags(uniq([...(initial?.etiquetas ?? []), ...kws]));

      // Cargar cache del scrape (raw_json) para los botones ✨ por sección.
      if (f.raw_json) {
        try { setCachedScrape(JSON.parse(f.raw_json)); }
        catch { setCachedScrape(null); }
      } else {
        setCachedScrape(null);
      }
    } else if (!initial) {
      setDescripcion(""); setNotas(""); setSpecs([]); setTags([]);
      setNombrePublico(""); setCachedScrape(null);
    }
  }, [fichaQ.data, initial]);

  // ── Categorías ─────────────────────────────────────────────────────
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

  /** Categoría raíz dominante = la primera asignada que NO tiene parent. */
  const categoriaRoot = useMemo(() => {
    if (!catsQ.data) return null;
    const cats = catsQ.data;
    for (const id of selectedCats) {
      const c = cats.find((x) => x.id === id);
      if (!c) continue;
      if (c.parent_id == null) return c.nombre;
      // si es hijo, devolver el padre
      const parent = cats.find((x) => x.id === c.parent_id);
      if (parent) return parent.nombre;
    }
    return null;
  }, [catsQ.data, selectedCats]);

  // ── Auto-generación del nombre público ────────────────────────────
  // Cuando el toggle está ON y la categoría tiene template, regenera al
  // tocar cualquier campo relevante. Montura/Formato/Resolución se leen
  // de los specs por label (ya no son inputs dedicados).
  const watchedMarca = form.watch("marca");
  const watchedModelo = form.watch("modelo");
  useEffect(() => {
    if (!nombrePublicoAuto) return;
    const gen = generarNombrePublico(categoriaRoot, {
      marca: watchedMarca ?? "",
      modelo: watchedModelo ?? "",
      montura: findSpecValue(specs, "Montura"),
      formato: findSpecValue(specs, "Formato"),
      resolucion: findSpecValue(specs, "Resolución"),
    });
    if (gen) setNombrePublico(gen);
  }, [nombrePublicoAuto, categoriaRoot, watchedMarca, watchedModelo, specs]);

  const autoGenDisponible = categoriaSoportaAutoGen(categoriaRoot);

  // ════════════════════════════════════════════════════════════════════
  // Autocompletar — llama al backend con la URL y rellena el form.
  // Specs van a una lista de "propuestos" para que el usuario los apruebe.
  // ════════════════════════════════════════════════════════════════════
  const autocompletar = async () => {
    const u = autocompletarUrl.trim();
    if (!u) {
      toast.error("Pegá un link primero");
      return;
    }
    try {
      const parsed = new URL(u);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        throw new Error("URL debe empezar con http:// o https://");
      }
    } catch (e) {
      toast.error(`URL inválida: ${e instanceof Error ? e.message : ""}`);
      return;
    }
    setAutocompletando(true);
    try {
      const r = await authedJson<AutocompletarResult>("/api/admin/equipos/enriquecer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: u }),
      });
      const sets = (k: keyof FormValues, v: string | number | null | undefined) => {
        if (v !== null && v !== undefined && v !== "") {
          form.setValue(k, v as never, { shouldDirty: true });
        }
      };
      if (!form.getValues("nombre")?.trim() && r.nombre_normalizado) {
        sets("nombre", r.nombre_normalizado);
      }
      sets("marca", r.marca ?? "");
      sets("modelo", r.modelo ?? "");
      if (r.foto_url) sets("foto_url", r.foto_url);
      sets("bh_url", r.fuente_url);
      if (typeof r.precio_bh_usd === "number") sets("precio_usd", r.precio_bh_usd);

      if (r.descripcion) setDescripcion(r.descripcion);
      if (r.keywords?.length) setTags((prev) => uniq([...prev, ...r.keywords!]));

      // Specs propuestos = los que vienen del autocompletar + montura/formato/resolucion
      // (que en V2 ya no son inputs dedicados — viven como specs).
      const propuestos: Spec[] = withIds(r.specs ?? []);
      if (r.montura) propuestos.unshift(newSpec("Montura", r.montura));
      if (r.formato) propuestos.unshift(newSpec("Formato", r.formato));
      if (r.resolucion) propuestos.unshift(newSpec("Resolución", r.resolucion));
      if (propuestos.length) setSpecsPropuestos(propuestos);

      setImportedFichaExt(r);
      // Actualizar cache del scrape: habilita los botones ✨ por sección
      // para re-aplicar después sin volver a scrapear.
      setCachedScrape(r);

      const parts: string[] = [];
      if (propuestos.length) parts.push(`${propuestos.length} specs propuestos`);
      if (r.keywords?.length) parts.push(`${r.keywords.length} etiquetas`);
      if (r.descripcion) parts.push("descripción");
      toast.success("Datos importados", { description: parts.join(" · ") || "datos básicos" });
    } catch (e) {
      toast.error(`No se pudo importar: ${e instanceof Error ? e.message : ""}`);
    } finally {
      setAutocompletando(false);
    }
  };

  // ════════════════════════════════════════════════════════════════════
  // Buscar fotos (solo foto, ~5s)
  // ════════════════════════════════════════════════════════════════════
  const buscarFotos = async () => {
    const u = autocompletarUrl.trim();
    setPhotoSearching(true);
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
            marca: form.getValues("marca") || null,
            modelo: form.getValues("modelo") || null,
            // Si hay URL en el autocompletar bar, usarla como fuente directa.
            ...(u ? { url: u } : {}),
            exclude: photoCands,
          }),
          signal: ctrl.signal,
        },
      );
      const news = (r.foto_candidates ?? []).filter((x) => !photoCands.includes(x));
      setPhotoCands((prev) => [...prev, ...news]);
      if (news.length === 0) toast.info("No se encontraron más fotos");
      else toast.success(`${news.length} fotos encontradas`);
    } catch (e) {
      if (e instanceof Error && e.name === "AbortError") toast.error("Timeout (30s)");
      else toast.error(e instanceof Error ? e.message : "Error buscando fotos");
    } finally {
      clearTimeout(timeoutId);
      setPhotoSearching(false);
    }
  };

  const elegirFoto = async (externalUrl: string) => {
    if (!initial?.id) {
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

  const handleUpload = async (file: File) => {
    if (!file) return;
    if (!initial?.id) {
      setPendingFile(file);
      if (pendingFilePreview) URL.revokeObjectURL(pendingFilePreview);
      setPendingFilePreview(URL.createObjectURL(file));
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

  // ════════════════════════════════════════════════════════════════════
  // Tags (etiquetas + keywords unificadas)
  // ════════════════════════════════════════════════════════════════════
  const addTag = () => {
    const v = tagInput.trim().toLowerCase();
    if (!v) return;
    if (tags.includes(v)) { setTagInput(""); return; }
    setTags([...tags, v]);
    setTagInput("");
  };

  // ════════════════════════════════════════════════════════════════════
  // Re-aplicar desde cache (botones ✨ por sección)
  // ════════════════════════════════════════════════════════════════════
  type CacheSection = "identificacion" | "foto" | "descripcion" | "ficha" | "etiquetas";

  const cacheHas = (s: CacheSection): boolean => {
    const r = cachedScrape;
    if (!r) return false;
    switch (s) {
      case "identificacion": return !!(r.marca || r.modelo || r.nombre_normalizado);
      case "foto":           return !!r.foto_url;
      case "descripcion":    return !!r.descripcion;
      case "ficha":          return !!(r.specs?.length || r.montura || r.formato || r.resolucion);
      case "etiquetas":      return !!r.keywords?.length;
    }
  };

  const applyFromCache = (s: CacheSection) => {
    const r = cachedScrape;
    if (!r) return;
    switch (s) {
      case "identificacion": {
        if (r.marca) form.setValue("marca", r.marca, { shouldDirty: true });
        if (r.modelo) form.setValue("modelo", r.modelo, { shouldDirty: true });
        if (r.nombre_normalizado && !form.getValues("nombre")?.trim()) {
          form.setValue("nombre", r.nombre_normalizado, { shouldDirty: true });
        }
        toast.success("Identificación recargada desde cache");
        break;
      }
      case "foto": {
        if (r.foto_url) {
          // Limpiar pendingFile (si había una foto local pendiente de subir) —
          // sino quedaría en estado inconsistente: URL del cache + archivo local
          // que ya no aplica, y al guardar se subirían los dos.
          if (pendingFile) {
            setPendingFile(null);
            if (pendingFilePreview) URL.revokeObjectURL(pendingFilePreview);
            setPendingFilePreview("");
          }
          form.setValue("foto_url", r.foto_url, { shouldDirty: true });
        }
        toast.success("Foto recargada desde cache");
        break;
      }
      case "descripcion": {
        if (r.descripcion) setDescripcion(r.descripcion);
        toast.success("Descripción recargada desde cache");
        break;
      }
      case "ficha": {
        const propuestos: Spec[] = withIds(r.specs ?? []);
        if (r.montura) propuestos.unshift(newSpec("Montura", r.montura));
        if (r.formato) propuestos.unshift(newSpec("Formato", r.formato));
        if (r.resolucion) propuestos.unshift(newSpec("Resolución", r.resolucion));
        setSpecsPropuestos(propuestos);
        toast.success(`${propuestos.length} specs propuestos desde cache`);
        break;
      }
      case "etiquetas": {
        if (r.keywords?.length) setTags((prev) => uniq([...prev, ...r.keywords!]));
        toast.success("Etiquetas mergeadas desde cache");
        break;
      }
    }
  };

  // ════════════════════════════════════════════════════════════════════
  // Submit — mismo flow que el viejo (delegamos en adminApi).
  // ════════════════════════════════════════════════════════════════════
  // Keyboard shortcut: Cmd/Ctrl+S guarda el form (Esc lo maneja el Dialog).
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (saving) return;
        const formEl = document.querySelector<HTMLFormElement>("form[data-equipo-form-v2]");
        formEl?.requestSubmit();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, saving]);

  const submit = form.handleSubmit(async (values) => {
    // Pre-flight: validación de duplicados por serie. La serie es lo más
    // único; si ya hay otro equipo con la misma, le pedimos confirmación al
    // user antes de seguir (puede ser legítimo en kits, pero conviene avisar).
    const serieTrim = values.serie?.trim();
    if (serieTrim) {
      try {
        const r = await adminApi.listEquipos({ q: serieTrim });
        const dups = r.items.filter(
          (e) => e.id !== initial?.id &&
                 (e.serie ?? "").trim().toLowerCase() === serieTrim.toLowerCase(),
        );
        if (dups.length > 0) {
          const ok = window.confirm(
            `Ya hay otro equipo con la serie "${serieTrim}":\n  • ${dups[0].nombre}` +
            (dups.length > 1 ? ` (+${dups.length - 1} más)` : "") +
            `\n\n¿Guardar igual?`,
          );
          if (!ok) return;
        }
      } catch {
        // Si la búsqueda falla, no bloqueamos el save.
      }
    }

    // Tags unificadas (chip UI) → se envían a ambos backends: etiquetas (top-level
    // equipo, para filtros/categorización) y keywords_json (ficha, para chips públicos).
    const etiquetas = uniq(tags.map((t) => t.trim()).filter(Boolean));
    const { visible_catalogo, ficha_completa, ...rest } = values;

    const fotoUrlForm = rest.foto_url || null;
    const fotoExternaPendiente =
      !pendingFile && fotoUrlForm && !isHostedUrl(fotoUrlForm) ? fotoUrlForm : null;
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
      ficha_completa: ficha_completa,
    };

    const fallidos: string[] = [];
    let equipoId: number | undefined;

    try {
      const saved = await onSubmit(payload, etiquetas);
      equipoId = saved?.id ?? initial?.id;
      if (!equipoId) {
        toast.error("No se pudo guardar el equipo");
        return;
      }

      // Foto pendiente o externa
      if (pendingFile) {
        try {
          const r2url = await uploadFileToBucket(equipoId, pendingFile);
          await adminApi.updateEquipo(equipoId, { foto_url: r2url });
          form.setValue("foto_url", r2url, { shouldDirty: false });
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
          fallidos.push(`foto a R2 (${e instanceof Error ? e.message : "error"})`);
        }
      }

      // Ficha — montura/formato/resolución se extraen de specs por label (V2
      // los maneja como specs); el catálogo público sigue leyendo los campos
      // dedicados, así que los seguimos guardando.
      const monturaSpec = findSpecValue(specs, "Montura") || null;
      const formatoSpec = findSpecValue(specs, "Formato") || null;
      const resolucionSpec = findSpecValue(specs, "Resolución") || null;
      const specsCleaned = specs
        .filter((s) => s.label.trim() && s.value.trim())
        .map(({ label, value }) => ({ label, value }));

      const tieneFicha = (
        isEdit ||
        !!descripcion || !!notas || specsCleaned.length > 0 || tags.length > 0 ||
        !!monturaSpec || !!formatoSpec || !!resolucionSpec ||
        !!nombrePublico.trim() || !!importedFichaExt
      );
      if (tieneFicha) {
        try {
          await adminApi.setFicha(equipoId, {
            descripcion: descripcion || null,
            notas: notas || null,
            specs_json: specsCleaned.length ? JSON.stringify(specsCleaned) : null,
            montura: monturaSpec,
            formato: formatoSpec,
            resolucion: resolucionSpec,
            keywords_json: tags.length ? JSON.stringify(tags) : null,
            // En V2 ya no hay template con tokens — el nombre público es literal.
            nombre_publico_template: nombrePublico.trim() || null,
          });
        } catch (e) {
          fallidos.push(`ficha (${e instanceof Error ? e.message : "error"})`);
        }
      }

      // Ficha extendida (peso, dimensiones, etc.) si vino del autocompletar
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

      // Categorías (en V2 las habilitamos también en CREATE)
      try {
        await adminApi.setCategorias(equipoId, [...selectedCats]);
      } catch (e) {
        fallidos.push(`categorías (${e instanceof Error ? e.message : "error"})`);
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error al guardar");
      return;
    }

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

  // ════════════════════════════════════════════════════════════════════
  // Render
  // ════════════════════════════════════════════════════════════════════
  const fotoActual = pendingFilePreview || form.watch("foto_url");
  const bhUrl = form.watch("bh_url");

  /** Botón ✨ que re-aplica una sección desde el scrape cacheado. */
  const CacheBtn = ({ section, label = "cache" }: { section: CacheSection; label?: string }) => {
    if (!cacheHas(section)) return null;
    return (
      <button
        type="button"
        onClick={() => applyFromCache(section)}
        title="Re-aplicar desde scrape guardado"
        className="text-[10px] text-muted-foreground hover:text-ink inline-flex items-center gap-0.5 shrink-0"
      >
        <Sparkles className="h-3 w-3" /> {label}
      </button>
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-full sm:max-w-3xl max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">
            {isEdit ? "Editar equipo" : "Nuevo equipo"}
          </DialogTitle>
          {nombrePublico && (
            <p className="text-xs text-muted-foreground">
              Se ve en la web como: <span className="text-ink font-medium italic">{nombrePublico}</span>
            </p>
          )}
        </DialogHeader>

        <form onSubmit={submit} className="space-y-5" data-equipo-form-v2>

          {/* ════════════════════════════════════════════════════════════════
              STATUS STRIP — switches de estado (visible + ficha completa)
          ════════════════════════════════════════════════════════════════ */}
          <div className="flex flex-wrap items-center gap-4 text-xs pb-2 border-b hairline">
            <label className="flex items-center gap-1.5 cursor-pointer">
              <Switch
                checked={form.watch("visible_catalogo")}
                onCheckedChange={(v) => form.setValue("visible_catalogo", v, { shouldDirty: true })}
              />
              <span className={form.watch("visible_catalogo") ? "text-ink" : "text-muted-foreground"}>
                {form.watch("visible_catalogo") ? "Visible en catálogo" : "Oculto del catálogo"}
              </span>
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer">
              <Switch
                checked={form.watch("ficha_completa")}
                onCheckedChange={(v) => form.setValue("ficha_completa", v, { shouldDirty: true })}
              />
              <span className={form.watch("ficha_completa") ? "text-ink" : "text-muted-foreground"}>
                {form.watch("ficha_completa") ? "Ficha completa" : "Ficha pendiente"}
              </span>
            </label>
          </div>

          {/* ════════════════════════════════════════════════════════════════
              AUTOCOMPLETAR BAR — sticky en mobile para no perderla al scrollear
          ════════════════════════════════════════════════════════════════ */}
          <section className="rounded-md border hairline bg-amber-soft/40 p-3 space-y-2 sticky top-0 z-10 sm:static">
            <div className="flex items-center gap-1.5 text-xs font-medium text-ink/80">
              <LinkIcon className="h-3.5 w-3.5" />
              Link del producto (B&amp;H, Adorama, sitio oficial)
            </div>
            <div className="flex gap-1.5">
              <Input
                value={autocompletarUrl}
                onChange={(e) => setAutocompletarUrl(e.target.value)}
                placeholder="https://www.bhphotovideo.com/c/product/..."
                className="font-mono text-xs"
              />
            </div>
            <div className="flex flex-wrap gap-1.5">
              <Button
                type="button" size="sm" variant="outline"
                onClick={buscarFotos}
                disabled={photoSearching}
              >
                {photoSearching
                  ? <><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> Buscando…</>
                  : <><ImageIcon className="h-3.5 w-3.5 mr-1" /> Buscar foto (~5s)</>}
              </Button>
              <Button
                type="button" size="sm"
                onClick={autocompletar}
                disabled={autocompletando}
              >
                {autocompletando
                  ? <><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> Importando…</>
                  : <><Sparkles className="h-3.5 w-3.5 mr-1" /> Autocompletar todo (~15s)</>}
              </Button>
            </div>
          </section>

          {/* ════════════════════════════════════════════════════════════════
              IDENTIFICACIÓN — foto + nombres + marca/modelo
          ════════════════════════════════════════════════════════════════ */}
          <section className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-[160px_1fr] gap-3">
              {/* Foto card */}
              <div className="space-y-1">
                {cacheHas("foto") && (
                  <div className="flex justify-end">
                    <CacheBtn section="foto" />
                  </div>
                )}
                <PhotoCard
                url={fotoActual}
                pendingFile={pendingFile}
                hasInitial={!!initial?.id}
                onClear={() => {
                  setPendingFile(null);
                  if (pendingFilePreview) URL.revokeObjectURL(pendingFilePreview);
                  setPendingFilePreview("");
                  form.setValue("foto_url", "", { shouldDirty: true });
                }}
                onUpload={handleUpload}
                onSubirAR2={subirFotoUrlAR2}
                uploading={uploading}
                uploadingToR2={uploadingToR2}
              />
              </div>

              <div className="space-y-3">
                <Field
                  label="Nombre interno (técnico, para vos)"
                  error={form.formState.errors.nombre?.message}
                  actions={<CacheBtn section="identificacion" label="cache id." />}
                >
                  <Input
                    {...form.register("nombre")}
                    placeholder="Ej: Sony ILME-FX30B Cuerpo"
                    autoFocus
                  />
                </Field>

                <Field label="Nombre público (cómo se ve en el catálogo)">
                  <div className="space-y-1.5">
                    <Input
                      value={nombrePublico}
                      onChange={(e) => {
                        setNombrePublico(e.target.value);
                        if (nombrePublicoAuto) setNombrePublicoAuto(false);
                      }}
                      placeholder={autoGenDisponible ? "Generado automático según la categoría" : "Ej: Cable HDMI 2.0 50cm"}
                    />
                    {autoGenDisponible && (
                      <label className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Switch
                          checked={nombrePublicoAuto}
                          onCheckedChange={setNombrePublicoAuto}
                        />
                        Generar automático desde {categoriaRoot?.toLowerCase()}
                        {!nombrePublicoAuto && <span className="opacity-60">(off)</span>}
                      </label>
                    )}
                    {!autoGenDisponible && categoriaRoot && (
                      <p className="text-[11px] text-muted-foreground italic">
                        Sin template auto para "{categoriaRoot}". Escribilo a mano.
                      </p>
                    )}
                  </div>
                </Field>

                <div className="grid grid-cols-2 gap-2">
                  <Field label="Marca">
                    <Input {...form.register("marca")} placeholder="Sony" />
                  </Field>
                  <Field label="Modelo">
                    <Input {...form.register("modelo")} placeholder="FX30" />
                  </Field>
                </div>
              </div>
            </div>

            {/* Candidatos de foto (si hay) */}
            {photoCands.length > 0 && (
              <div>
                <Label className="text-xs uppercase tracking-wide text-muted-foreground">
                  Fotos encontradas ({photoCands.length}) · click para elegir
                </Label>
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {photoCands.map((u) => {
                    const isPicking = pickingPhotoUrl === u;
                    const isSelected = form.watch("foto_url") === u;
                    return (
                      <button
                        key={u} type="button"
                        onClick={() => elegirFoto(u)}
                        disabled={isPicking}
                        className={`relative h-14 w-14 rounded border bg-background overflow-hidden ${isSelected ? "ring-2 ring-amber" : ""}`}
                      >
                        <img src={u} alt="" className="h-full w-full object-contain" />
                        {isPicking && (
                          <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                            <Loader2 className="h-4 w-4 animate-spin text-white" />
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </section>

          {/* ════════════════════════════════════════════════════════════════
              PRECIO Y STOCK
          ════════════════════════════════════════════════════════════════ */}
          <section className="space-y-3 pt-2 border-t hairline">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <Field label="Stock">
                <div className="flex gap-1">
                  <Button
                    type="button" size="icon" variant="outline"
                    className="h-9 w-9 shrink-0"
                    onClick={() => {
                      const raw = Number(form.getValues("cantidad") ?? 0);
                      const current = Number.isFinite(raw) ? raw : 0;
                      form.setValue("cantidad", Math.max(0, current - 1), { shouldDirty: true });
                    }}
                    aria-label="Restar 1 al stock"
                  >−</Button>
                  <Input type="number" min={0} className="text-center" {...form.register("cantidad")} />
                  <Button
                    type="button" size="icon" variant="outline"
                    className="h-9 w-9 shrink-0"
                    onClick={() => {
                      const raw = Number(form.getValues("cantidad") ?? 0);
                      const current = Number.isFinite(raw) ? raw : 0;
                      form.setValue("cantidad", current + 1, { shouldDirty: true });
                    }}
                    aria-label="Sumar 1 al stock"
                  >+</Button>
                </div>
              </Field>
              <Field label="Valor USD">
                <Input type="number" step="0.01" {...form.register("precio_usd")} />
              </Field>
              <Field label="ROI %">
                <Input type="number" step="0.1" {...form.register("roi_pct")} />
              </Field>
              <Field label={precioJornadaManual ? "Precio/día (manual)" : "Precio/día (auto)"}>
                <div className="flex gap-1">
                  <Input
                    type="number"
                    {...form.register("precio_jornada", {
                      onChange: () => setPrecioJornadaManual(true),
                    })}
                  />
                  {precioJornadaManual && (
                    <Button
                      type="button" size="icon" variant="ghost"
                      title="Recalcular automático"
                      onClick={() => setPrecioJornadaManual(false)}
                    >
                      ↺
                    </Button>
                  )}
                </div>
              </Field>
            </div>

            <Field label="Dueño">
              <Select
                value={form.watch("dueno") ?? ""}
                onValueChange={(v) => form.setValue("dueno", v, { shouldDirty: true })}
              >
                <SelectTrigger><SelectValue placeholder="Seleccionar…" /></SelectTrigger>
                <SelectContent>
                  {DUENOS.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
                  {form.watch("dueno") && !isCanonicalDueno(form.watch("dueno") ?? "") && (
                    <SelectItem value={form.watch("dueno") ?? ""}>{form.watch("dueno")} (custom)</SelectItem>
                  )}
                </SelectContent>
              </Select>
            </Field>
          </section>

          {/* ════════════════════════════════════════════════════════════════
              LINK DE FUENTE — copiable + clickeable
          ════════════════════════════════════════════════════════════════ */}
          <section className="pt-2 border-t hairline">
            <Field label="Link de fuente (B&H, sitio oficial — para referencia interna)">
              <LinkInput
                value={bhUrl ?? ""}
                onChange={(v) => form.setValue("bh_url", v, { shouldDirty: true })}
                placeholder="https://www.bhphotovideo.com/c/product/..."
              />
            </Field>
          </section>

          {/* ════════════════════════════════════════════════════════════════
              CATEGORÍAS
          ════════════════════════════════════════════════════════════════ */}
          <section className="pt-2 border-t hairline">
            <Label className="text-xs uppercase tracking-wide text-muted-foreground">
              Categorías {categoriaRoot && <span className="ml-1 normal-case text-ink/70">· primera = "{categoriaRoot}"</span>}
            </Label>
            <CategoriasPicker
              categorias={catsQ.data ?? []}
              selected={selectedCats}
              onChange={setSelectedCats}
            />
          </section>

          {/* ════════════════════════════════════════════════════════════════
              FICHA TÉCNICA — colapsable
          ════════════════════════════════════════════════════════════════ */}
          <CollapsibleSection
            title="Ficha técnica"
            defaultOpen={specsPropuestos.length > 0 || specs.length > 0}
            actions={<CacheBtn section="ficha" />}
          >
            <div className="space-y-3">
              <Field
                label="Descripción (visible en el catálogo)"
                actions={<CacheBtn section="descripcion" />}
              >
                <Textarea
                  rows={3}
                  value={descripcion}
                  onChange={(e) => setDescripcion(e.target.value)}
                />
              </Field>

              <SpecsDiffEditor
                specs={specs}
                propuestos={specsPropuestos}
                onChange={setSpecs}
                onAceptarPropuesto={(s) => {
                  setSpecs((prev) => {
                    const idx = prev.findIndex((x) => sameLabel(x.label, s.label));
                    if (idx >= 0) {
                      const next = [...prev];
                      next[idx] = { ...next[idx], value: s.value };
                      return next;
                    }
                    return [...prev, newSpec(s.label, s.value)];
                  });
                  setSpecsPropuestos((prev) => prev.filter((x) => x.id !== s.id));
                }}
                onDescartarPropuesto={(s) => {
                  setSpecsPropuestos((prev) => prev.filter((x) => x.id !== s.id));
                }}
              />

              <Field label="Etiquetas" actions={<CacheBtn section="etiquetas" />}>
                <div className="space-y-1.5">
                  <div className="flex flex-wrap gap-1">
                    {tags.map((t) => (
                      <Badge key={t} variant="secondary" className="text-[10px] gap-1">
                        {t}
                        <button type="button" onClick={() => setTags(tags.filter((x) => x !== t))}>
                          <X className="h-3 w-3" />
                        </button>
                      </Badge>
                    ))}
                    {tags.length === 0 && (
                      <span className="text-xs text-muted-foreground italic">Sin etiquetas</span>
                    )}
                  </div>
                  <div className="flex gap-1">
                    <Input
                      value={tagInput}
                      onChange={(e) => setTagInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") { e.preventDefault(); addTag(); }
                      }}
                      placeholder="Etiqueta y Enter… (ej. 4K, full frame, cinema)"
                    />
                    <Button type="button" size="icon" variant="outline" onClick={addTag}>
                      <Plus className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    Se usan para búsqueda, filtros del catálogo y chips visibles en la ficha pública.
                  </p>
                </div>
              </Field>
            </div>
          </CollapsibleSection>

          {/* ════════════════════════════════════════════════════════════════
              KIT — colapsable, solo en EDIT (necesita id del equipo)
          ════════════════════════════════════════════════════════════════ */}
          {isEdit && initial && (
            <CollapsibleSection title="Kit (componentes incluidos)">
              <KitEditor equipoId={initial.id} />
            </CollapsibleSection>
          )}

          {/* ════════════════════════════════════════════════════════════════
              AVANZADO — colapsable
          ════════════════════════════════════════════════════════════════ */}
          <CollapsibleSection title="Avanzado">
            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <Field label="Estado">
                  <Select
                    value={form.watch("estado")}
                    onValueChange={(v) => form.setValue("estado", v as FormValues["estado"], { shouldDirty: true })}
                  >
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="operativo">Operativo</SelectItem>
                      <SelectItem value="en_mantenimiento">En mantenimiento</SelectItem>
                      <SelectItem value="fuera_servicio">Fuera de servicio</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <Field label="Valor reposición (USD)">
                  <Input type="number" step="0.01" {...form.register("valor_reposicion")} />
                </Field>
                <Field label="Fecha de compra">
                  <MonthYearPicker
                    value={form.watch("fecha_compra") ?? ""}
                    onChange={(v) => form.setValue("fecha_compra", v, { shouldDirty: true })}
                  />
                </Field>
                <Field label="N° de serie">
                  <Input {...form.register("serie")} />
                </Field>
              </div>

              <Field label="Notas internas (no se muestran al cliente)">
                <Textarea rows={2} value={notas} onChange={(e) => setNotas(e.target.value)} />
              </Field>
            </div>
          </CollapsibleSection>

          {/* ════════════════════════════════════════════════════════════════
              FOOTER
          ════════════════════════════════════════════════════════════════ */}
          <DialogFooter className="pt-2 border-t hairline">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? <><Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> Guardando…</> : "Guardar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ════════════════════════════════════════════════════════════════════
// Sub-componentes
// ════════════════════════════════════════════════════════════════════

function Field({
  label, error, children, actions,
}: { label: string; error?: string; children: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2">
        <Label className="text-xs uppercase tracking-wide text-muted-foreground">{label}</Label>
        {actions}
      </div>
      {children}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

function CollapsibleSection({
  title, defaultOpen = false, children, actions,
}: { title: string; defaultOpen?: boolean; children: React.ReactNode; actions?: React.ReactNode }) {
  const [open, setOpen] = useState(defaultOpen);
  // Re-abre la sección si defaultOpen transiciona false→true (ej. llegaron
  // specs propuestos por cache). No fuerza cerrar si transiciona al revés —
  // respeta el toggle manual del user.
  const prevDefaultOpen = useRef(defaultOpen);
  useEffect(() => {
    if (defaultOpen && !prevDefaultOpen.current) setOpen(true);
    prevDefaultOpen.current = defaultOpen;
  }, [defaultOpen]);
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="border-t hairline pt-2">
      <div className="flex items-center gap-2">
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex items-center flex-1 text-left gap-1.5 py-1 text-sm font-medium hover:text-ink/70"
          >
            <ChevronDown className={`h-4 w-4 transition-transform ${open ? "" : "-rotate-90"}`} />
            {title}
          </button>
        </CollapsibleTrigger>
        {actions}
      </div>
      <CollapsibleContent className="pt-2">
        {children}
      </CollapsibleContent>
    </Collapsible>
  );
}

function LinkInput({
  value, onChange, placeholder,
}: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  const valid = useMemo(() => {
    if (!value.trim()) return false;
    try {
      const u = new URL(value);
      return u.protocol === "http:" || u.protocol === "https:";
    } catch { return false; }
  }, [value]);

  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success("Link copiado");
    } catch {
      toast.error("No se pudo copiar");
    }
  };

  return (
    <div className="flex gap-1">
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="font-mono text-xs"
      />
      {valid && (
        <>
          <Button
            type="button" size="icon" variant="outline"
            title="Copiar al portapapeles"
            onClick={copiar}
          >
            <Copy className="h-3.5 w-3.5" />
          </Button>
          <Button
            type="button" size="icon" variant="outline"
            title="Abrir en nueva pestaña"
            asChild
          >
            <a href={value} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </Button>
        </>
      )}
    </div>
  );
}

function PhotoCard({
  url, pendingFile, hasInitial, onClear, onUpload, onSubirAR2, uploading, uploadingToR2,
}: {
  url?: string | null;
  pendingFile: File | null;
  hasInitial: boolean;
  onClear: () => void;
  onUpload: (f: File) => void;
  onSubirAR2: () => void;
  uploading: boolean;
  uploadingToR2: boolean;
}) {
  const fileRef = useRef<HTMLInputElement | null>(null);
  const isExternal = !!url && !pendingFile && !isHostedUrl(url);
  const isHosted = !!url && !pendingFile && isHostedUrl(url);

  return (
    <div className="space-y-1.5">
      <div className="relative aspect-square rounded-md border hairline bg-muted/20 overflow-hidden">
        {url ? (
          <>
            <img src={url} alt="" className="h-full w-full object-contain" />
            <button
              type="button"
              onClick={onClear}
              className="absolute top-1 right-1 h-6 w-6 rounded-full bg-background/80 hover:bg-background flex items-center justify-center"
              title="Quitar foto"
            >
              <X className="h-3 w-3" />
            </button>
            <div className="absolute bottom-1 left-1">
              {pendingFile && <Badge variant="secondary" className="text-[9px]">Local — al guardar</Badge>}
              {isHosted && <Badge variant="default" className="text-[9px]">✓ En R2</Badge>}
              {isExternal && <Badge variant="outline" className="text-[9px]">URL externa</Badge>}
            </div>
          </>
        ) : (
          <div className="h-full w-full flex flex-col items-center justify-center text-muted-foreground text-xs">
            <ImageIcon className="h-6 w-6 mb-1 opacity-50" />
            Sin foto
          </div>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUpload(f);
            e.target.value = "";
          }}
        />
        <Button
          type="button" size="sm" variant="outline"
          className="text-xs"
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
        >
          {uploading
            ? <><Loader2 className="h-3 w-3 mr-1 animate-spin" /> Subiendo…</>
            : <><Upload className="h-3 w-3 mr-1" /> Subir foto</>}
        </Button>
        {isExternal && hasInitial && (
          <Button
            type="button" size="sm" variant="outline"
            className="text-xs"
            onClick={onSubirAR2}
            disabled={uploadingToR2}
          >
            {uploadingToR2
              ? <><Loader2 className="h-3 w-3 mr-1 animate-spin" /> Subiendo…</>
              : "Subir a R2"}
          </Button>
        )}
      </div>
    </div>
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
  const roots = categorias.filter((c) => c.parent_id == null);
  const childrenOf = (pid: number) => categorias.filter((c) => c.parent_id === pid);

  return (
    <div className="space-y-2 max-h-60 overflow-y-auto rounded-md border hairline p-2 mt-1">
      {roots.map((root) => (
        <div key={root.id}>
          <button type="button" onClick={() => toggle(root.id)}>
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
        <p className="text-xs text-muted-foreground italic">Sin categorías. Creá algunas en /admin/settings.</p>
      )}
    </div>
  );
}

/**
 * Specs editor con diff visual cuando hay propuestos del autocompletar.
 *
 * - Propuestos = vienen del autocompletar, esperan aprobación.
 * - Actuales = ya están guardados en la ficha, soportan drag-and-drop.
 *
 * El usuario puede aceptar uno por uno (reemplaza o agrega), descartar o editar.
 */
function SpecsDiffEditor({
  specs, propuestos, onChange, onAceptarPropuesto, onDescartarPropuesto,
}: {
  specs: Spec[];
  propuestos: Spec[];
  onChange: (s: Spec[]) => void;
  onAceptarPropuesto: (s: Spec) => void;
  onDescartarPropuesto: (s: Spec) => void;
}) {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const updateSpec = (id: string, patch: Partial<Spec>) => {
    onChange(specs.map((s) => s.id === id ? { ...s, ...patch } : s));
  };
  const removeSpec = (id: string) => onChange(specs.filter((s) => s.id !== id));
  const addSpec = () => onChange([...specs, newSpec()]);

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = specs.findIndex((s) => s.id === active.id);
    const newIdx = specs.findIndex((s) => s.id === over.id);
    if (oldIdx === -1 || newIdx === -1) return;
    onChange(arrayMove(specs, oldIdx, newIdx));
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {specs.length > 0 && (
            <>
              {specs.length} {specs.length === 1 ? "ítem" : "ítems"}
              {specs.length > 1 && (
                <span className="ml-1.5 opacity-60">· arrastrá para reordenar</span>
              )}
            </>
          )}
        </span>
        <Button type="button" size="sm" variant="ghost" onClick={addSpec}>
          <Plus className="h-3 w-3 mr-1" /> Agregar
        </Button>
      </div>

      {/* Propuestos (del autocompletar) */}
      {propuestos.length > 0 && (
        <div className="rounded-md border hairline bg-amber-soft/30 p-2 space-y-1.5">
          <p className="text-[11px] text-ink/70 font-medium">
            ✨ {propuestos.length} {propuestos.length === 1 ? "ítem propuesto" : "ítems propuestos"} del autocompletar
          </p>
          {propuestos.map((s) => {
            const existing = specs.find((x) => sameLabel(x.label, s.label));
            return (
              <div key={s.id} className="flex items-center gap-1.5 text-xs">
                <div className="flex-1 min-w-0">
                  <span className="font-medium">{s.label}:</span>{" "}
                  <span>{s.value}</span>
                  {existing && existing.value !== s.value && (
                    <span className="ml-1 text-muted-foreground line-through">{existing.value}</span>
                  )}
                </div>
                <Button type="button" size="sm" variant="default" className="h-6 px-1.5 text-[10px]"
                  onClick={() => onAceptarPropuesto(s)}>
                  ✓
                </Button>
                <Button type="button" size="sm" variant="outline" className="h-6 px-1.5 text-[10px]"
                  onClick={() => onDescartarPropuesto(s)}>
                  ✗
                </Button>
              </div>
            );
          })}
        </div>
      )}

      {/* Specs actuales con drag-and-drop */}
      {specs.length > 0 ? (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={specs.map((s) => s.id)} strategy={verticalListSortingStrategy}>
            <div className="space-y-1">
              {specs.map((s) => (
                <SortableSpec
                  key={s.id}
                  spec={s}
                  onUpdate={(patch) => updateSpec(s.id, patch)}
                  onRemove={() => removeSpec(s.id)}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      ) : (
        propuestos.length === 0 && (
          <p className="text-xs text-muted-foreground italic">Sin ítems.</p>
        )
      )}
    </div>
  );
}

function SortableSpec({
  spec, onUpdate, onRemove,
}: {
  spec: Spec;
  onUpdate: (patch: Partial<Spec>) => void;
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: spec.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} className="flex gap-1 items-center bg-background">
      <button
        type="button"
        className="cursor-grab active:cursor-grabbing text-muted-foreground/40 hover:text-muted-foreground touch-none px-0.5"
        {...attributes}
        {...listeners}
        tabIndex={-1}
      >
        <GripVertical className="h-3.5 w-3.5" />
      </button>
      <Input
        value={spec.label}
        onChange={(e) => onUpdate({ label: e.target.value })}
        placeholder="Spec"
        className="text-xs"
      />
      <Input
        value={spec.value}
        onChange={(e) => onUpdate({ value: e.target.value })}
        placeholder="Valor"
        className="text-xs"
      />
      <Button type="button" size="icon" variant="ghost" onClick={onRemove}>
        <Trash2 className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════
// Kit editor — copiado del viejo con drag-drop
// ════════════════════════════════════════════════════════════════════

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
    try { setItems(await adminApi.getKit(equipoId)); }
    catch (e) { toast.error(`Kit: ${e instanceof Error ? e.message : ""}`); }
    finally { setLoading(false); }
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
    try { await adminApi.addKitItem(equipoId, componente_id, 1); await load(); setSearch(""); setResults([]); }
    catch (e) { toast.error(e instanceof Error ? e.message : "Error"); }
    finally { setBusy(null); }
  };
  const updateQty = async (cid: number, cantidad: number) => {
    if (cantidad < 1) return;
    setBusy(cid);
    try { await adminApi.addKitItem(equipoId, cid, cantidad); await load(); }
    catch (e) { toast.error(e instanceof Error ? e.message : "Error"); }
    finally { setBusy(null); }
  };
  const remove = async (cid: number) => {
    setBusy(cid);
    try { await adminApi.removeKitItem(equipoId, cid); await load(); }
    catch (e) { toast.error(e instanceof Error ? e.message : "Error"); }
    finally { setBusy(null); }
  };
  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = items.findIndex((i) => i.componente_id === active.id);
    const newIdx = items.findIndex((i) => i.componente_id === over.id);
    if (oldIdx === -1 || newIdx === -1) return;
    const reordered = arrayMove(items, oldIdx, newIdx);
    setItems(reordered);
    try { await adminApi.reorderKit(equipoId, reordered.map((i) => i.componente_id)); }
    catch (e) { toast.error(e instanceof Error ? e.message : "Error al reordenar"); await load(); }
  };

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar componente por nombre, marca o modelo…"
          className="pl-8"
        />
        {searching && (
          <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 animate-spin text-muted-foreground" />
        )}
      </div>

      {results.length > 0 && (
        <div className="max-h-56 overflow-y-auto rounded-md border hairline divide-y shadow-sm">
          {results.map((r) => (
            <button
              key={r.id} type="button"
              className="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-accent text-left disabled:opacity-50"
              onClick={() => add(r.id)}
              disabled={busy === r.id || items.some((i) => i.componente_id === r.id)}
            >
              {r.foto_url
                ? <img src={r.foto_url} alt="" className="h-7 w-7 object-contain rounded bg-muted/30 shrink-0" />
                : <div className="h-7 w-7 rounded bg-muted/30 shrink-0" />}
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

      <div>
        <Label className="text-xs uppercase tracking-wide text-muted-foreground">
          Componentes ({items.length})
          {items.length > 1 && (
            <span className="ml-1.5 normal-case font-normal text-muted-foreground/60">
              · arrastrá para reordenar
            </span>
          )}
        </Label>

        {loading ? (
          <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Cargando…
          </div>
        ) : items.length === 0 ? (
          <p className="text-xs text-muted-foreground italic mt-2">
            Sin componentes. Usá el buscador de arriba.
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
        : <div className="h-8 w-8 rounded bg-muted/30 shrink-0" />}

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
