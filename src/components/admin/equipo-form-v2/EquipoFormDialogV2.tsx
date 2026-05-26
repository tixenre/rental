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
  Loader2,
  Upload,
  Plus,
  Trash2,
  Sparkles,
  Search,
  Link as LinkIcon,
  Image as ImageIcon,
  X,
  Copy,
  ExternalLink,
  ChevronDown,
} from "lucide-react";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DUENOS, isCanonicalDueno } from "@/lib/admin/duenos";
import { MonthYearPicker } from "@/components/admin/MonthYearPicker";

import { adminApi, type Equipo, type EquipoInput, type CategoriaAdmin } from "@/lib/admin/api";
import { uploadFileToBucket, uploadExternalUrlToBucket, isHostedUrl } from "@/lib/equipment/photos";
import { authedJson } from "@/lib/authedFetch";
import { useUsdRate, useRoiPctDefault, calcularPrecioJornada } from "@/hooks/useSettings";
import { KitEditor } from "./KitEditor";
import { SpecsDiffEditor } from "./SpecsDiffEditor";
import { type Spec, newSpec, withIds, sameLabel, findSpecValue, uniq } from "./spec-helpers";
import type { AutocompletarResult } from "../autocompletar";
import { generarNombrePublico, categoriaSoportaAutoGen } from "./nombre-publico";
import { renderNombrePublicoTemplate } from "@/lib/equipment/nombre-template";

// ════════════════════════════════════════════════════════════════════
// Schema
// ════════════════════════════════════════════════════════════════════

// Schema dinámico: en creación validamos campos mínimos obligatorios
// (#351). En edición todo queda opcional para no romper flujos de
// completado parcial — el dashboard de calidad ya visibiliza los huecos.
function buildSchema(isEdit: boolean) {
  const requiredStr = (name: string) =>
    isEdit ? z.string().optional().nullable() : z.string().min(1, `${name} requerido`);
  const requiredNum = (name: string) =>
    isEdit
      ? z.coerce.number().min(0).optional().nullable()
      : z.coerce.number().min(1, `${name} requerido`);

  return z.object({
    nombre: z.string().min(1, "Nombre requerido"),
    marca: requiredStr("Marca"),
    modelo: z.string().optional().nullable(),
    cantidad: z.coerce.number().int().min(1, "Cantidad requerida").default(1),
    precio_jornada: requiredNum("Precio/jornada"),
    precio_usd: z.coerce.number().min(0).optional().nullable(),
    roi_pct: z.coerce.number().min(0).optional().nullable(),
    valor_reposicion: z.coerce.number().min(0).optional().nullable(),
    fecha_compra: z.string().optional().nullable(),
    serie: z.string().optional().nullable(),
    bh_url: z.string().optional().nullable(),
    foto_url: z.string().optional().nullable(),
    dueno: requiredStr("Dueño"),
    estado: z.enum(["operativo", "en_mantenimiento", "fuera_servicio"]).default("operativo"),
    visible_catalogo: z.boolean().default(true),
    ficha_completa: z.boolean().default(false),
  });
}

type FormValues = z.infer<ReturnType<typeof buildSchema>>;

/** Campos "recomendados" para un equipo (#351). Después del create, si
 *  alguno está vacío, mostramos un toast con CTA para completar. */
const RECOMMENDED_FIELDS = ["foto", "descripcion", "serie", "valor_reposicion"] as const;
type RecommendedField = (typeof RECOMMENDED_FIELDS)[number];
const RECOMMENDED_LABELS: Record<RecommendedField, string> = {
  foto: "foto",
  descripcion: "descripción",
  serie: "número de serie",
  valor_reposicion: "valor de reposición",
};

// ════════════════════════════════════════════════════════════════════
// Componente principal
// ════════════════════════════════════════════════════════════════════

export function EquipoFormDialogV2({
  open,
  onOpenChange,
  initial,
  onSubmit,
  saving,
  onCreatedWithMissingRecommended,
  variant = "dialog",
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  initial?: Equipo | null;
  onSubmit: (data: EquipoInput, etiquetas: string[]) => Promise<Equipo>;
  saving?: boolean;
  /** "dialog" (modal, default) o "page" (editor de página completa con
   *  2 columnas + aside + save bar fija, como el mock del handoff). */
  variant?: "dialog" | "page";
  /** Si el equipo se creó pero le faltan recomendados, el parent decide
   *  qué hacer (ej. reabrir el form en modo edit). #351 */
  onCreatedWithMissingRecommended?: (equipo: Equipo, missing: RecommendedField[]) => void;
}) {
  const isEdit = !!initial;
  const { rate: usdRate } = useUsdRate();
  const roiDefault = useRoiPctDefault();

  // ── Estado del form (react-hook-form) ──────────────────────────────
  const schema = useMemo(() => buildSchema(isEdit), [isEdit]);
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
      // Default "N/A" en CREATE — equipos sin serie real comparten este
      // placeholder y el preflight de duplicados lo ignora.
      serie: initial ? (initial.serie ?? "") : "N/A",
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
  // El toggle arranca ON: si la categoría tiene template, el form regenera el
  // nombre desde los specs. El usuario puede toggle OFF para editar a mano,
  // pero por design queda enganchado al template — si el dueño modifica el
  // template en /admin/equipos/specs, la próxima vez que abra el equipo el
  // nombre se actualiza automáticamente (#calidad-datos).
  const [nombrePublico, setNombrePublico] = useState("");
  const [nombrePublicoAuto, setNombrePublicoAuto] = useState(true);

  // ── Autocompletar (URL importer) ───────────────────────────────────
  // El URL del autocompletar es el mismo bh_url del form — un único link
  // para todo (autocompletar, buscar fotos, referencia, copiar/abrir).
  const [autocompletando, setAutocompletando] = useState(false);
  const [importedFichaExt, setImportedFichaExt] = useState<Partial<AutocompletarResult> | null>(
    null,
  );

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
  useEffect(
    () => () => {
      if (pendingFilePreview) URL.revokeObjectURL(pendingFilePreview);
    },
    [pendingFilePreview],
  );

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
  // Ficha legacy = solo descripción, notas, nombre público template y
  // keywords. Las specs estructuradas viven en `equipo_specs` y se
  // cargan vía `equipoSpecsQ` (más abajo). Los campos legacy
  // `specs_json`, `montura`, `formato`, `resolucion` y `raw_json` ya no
  // se leen desde este form — quedan en BD como deuda hasta que se
  // borren del backend.
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
      const hasTokens = /\{[^}]+\}/.test(tpl);
      setNombrePublico(hasTokens ? "" : tpl);
      // Detectar override manual: si hay texto literal sin tokens, asumimos
      // que el dueño puso un nombre a mano y no queremos que auto-gen lo
      // pise al abrir (issue de auditoría). toggle OFF en ese caso.
      if (tpl && !hasTokens) {
        setNombrePublicoAuto(false);
      } else {
        setNombrePublicoAuto(true);
      }

      // Unificar keywords_json (ficha) + etiquetas (equipo top-level).
      let kws: string[] = [];
      try {
        const arr = f.keywords_json ? JSON.parse(f.keywords_json) : [];
        kws = Array.isArray(arr) ? arr.filter((x) => typeof x === "string") : [];
      } catch {
        kws = [];
      }
      setTags(uniq([...(initial?.etiquetas ?? []), ...kws]));
    } else if (!initial) {
      setDescripcion("");
      setNotas("");
      setTags([]);
      setNombrePublico("");
    }
  }, [fichaQ.data, initial]);

  // ── Specs estructuradas (equipo_specs) ────────────────────────────
  // Fuente única para el panel "Ficha técnica" del form. Devuelve:
  //  - specs: { [spec_def_id]: value } — lo que el equipo tiene cargado
  //  - template: lista de specs aplicables a las categorías del equipo
  //    (el backend hace WITH RECURSIVE para resolver ancestros, así que
  //    no hace falta calcular acá una "categoría raíz dominante").
  // Al guardar, vuelve por putEquipoSpecs (PUT al mismo endpoint).
  const equipoSpecsQ = useQuery({
    queryKey: ["admin", "equipo-specs", initial?.id],
    queryFn: () => adminApi.getEquipoSpecs(initial!.id),
    enabled: !!initial?.id && open,
  });
  useEffect(() => {
    if (!initial) {
      setSpecs([]);
      return;
    }
    const data = equipoSpecsQ.data;
    if (!data) return;
    // Mapear { spec_def_id → value } a Spec[]. El id de cada Spec es
    // `spec-${spec_def_id}` para poder mapear de vuelta al guardar
    // (putEquipoSpecs). El label se resuelve contra el template EN VIVO de la
    // categoría seleccionada en el efecto de re-etiquetado de abajo; acá
    // arrancamos con un fallback hasta que el template cargue.
    const next: Spec[] = [];
    for (const [defIdStr, value] of Object.entries(data.specs)) {
      const v = value == null ? "" : String(value);
      if (!v.trim()) continue;
      next.push({ id: `spec-${defIdStr}`, label: `spec ${defIdStr}`, value: v });
    }
    setSpecs(next);
  }, [equipoSpecsQ.data, initial]);

  // ── Categorías ─────────────────────────────────────────────────────
  const catsQ = useQuery({
    queryKey: ["admin", "categorias-list"],
    queryFn: () => adminApi.adminListCategorias(),
    enabled: open,
  });
  // Lista de marcas para el dropdown del campo Marca. Source-of-truth:
  // tabla `marcas`. El admin elige una existente o escribe una nueva
  // (autocomplete via <datalist>, free text permitido).
  const marcasQ = useQuery({
    queryKey: ["admin", "marcas-list"],
    queryFn: () => adminApi.adminListMarcas(),
    enabled: open,
  });
  const marcasOptions = useMemo(
    () => [...(marcasQ.data?.items ?? [])].sort((a, b) => a.nombre.localeCompare(b.nombre)),
    [marcasQ.data],
  );
  const [selectedCats, setSelectedCats] = useState<Set<number>>(new Set());
  useEffect(() => {
    if (initial?.categorias) {
      setSelectedCats(new Set(initial.categorias.map((c) => c.id)));
    } else {
      setSelectedCats(new Set());
    }
  }, [initial, open]);

  // ── Categoría de SPECS ─────────────────────────────────────────────
  // Define qué specs aplican (1 de las 5 del registry) Y la generación del
  // nombre público. Es independiente del árbol de catálogo (`selectedCats`),
  // que es solo agrupación para el front-office. El template de specs lo
  // resuelve el backend (`getEquipoSpecs`) desde `categoria_specs`.
  const specCatsQ = useQuery({
    queryKey: ["admin", "spec-categorias"],
    queryFn: () => adminApi.listSpecCategorias(),
    enabled: open,
  });
  const specCatOptions = useMemo(() => specCatsQ.data?.categorias ?? [], [specCatsQ.data]);
  const [categoriaSpecs, setCategoriaSpecs] = useState<string>("");
  // Se vuelve true en cuanto el admin toca el selector. Mientras sea false,
  // dejamos que el auto-default (abajo) complete la categoría de specs desde
  // el catálogo. Así no peleamos contra una elección explícita de "Sin
  // categoría de specs".
  const specsTouchedRef = useRef(false);
  useEffect(() => {
    setCategoriaSpecs(initial?.categoria_specs ?? "");
    specsTouchedRef.current = false;
  }, [initial, open]);

  // Auto-default: si la categoría de specs quedó vacía (equipo viejo sin
  // backfill, o equipo nuevo recién categorizado) y el equipo está en una
  // categoría de catálogo cuyo root es una de las funcionales del registry,
  // la adoptamos. Mantiene specs como driver del nombre público sin obligar
  // al admin a elegirla a mano. El selector explícito gana (specsTouchedRef).
  useEffect(() => {
    if (specsTouchedRef.current) return;
    if (categoriaSpecs) return;
    if (!catsQ.data || selectedCats.size === 0 || specCatOptions.length === 0) return;
    const funcNames = new Set(specCatOptions.map((c) => c.nombre));
    const resolveRootName = (startId: number): string | null => {
      const seen = new Set<number>();
      let cur = catsQ.data!.find((x) => x.id === startId);
      while (cur) {
        if (cur.parent_id == null) return cur.nombre;
        if (seen.has(cur.id)) return null;
        seen.add(cur.id);
        cur = catsQ.data!.find((x) => x.id === cur!.parent_id);
      }
      return null;
    };
    for (const id of selectedCats) {
      const root = resolveRootName(id);
      if (root && funcNames.has(root)) {
        setCategoriaSpecs(root);
        return;
      }
    }
  }, [categoriaSpecs, catsQ.data, selectedCats, specCatOptions]);

  /** Nombre de la categoría de specs — drive de specs + nombre público. */
  const categoriaRoot = categoriaSpecs || null;

  /** Id de la categoría de specs (en `categorias`), para fetchear el spec
   *  template. Resuelto contra la fuente canónica de specs (no el catálogo). */
  const categoriaRootId = useMemo(() => {
    if (!categoriaSpecs) return null;
    const c = specCatOptions.find((x) => x.nombre === categoriaSpecs);
    return c?.id ?? null;
  }, [specCatOptions, categoriaSpecs]);

  /** Template de nombre público de la categoría raíz (NULL si no hay). */
  const categoriaTemplate = useMemo(() => {
    if (!catsQ.data || categoriaRootId == null) return null;
    const cat = catsQ.data.find((x) => x.id === categoriaRootId);
    return cat?.nombre_publico_template ?? null;
  }, [catsQ.data, categoriaRootId]);

  // Template de specs de la categoría SELECCIONADA (en vivo, no la guardada).
  // Lee de spec_definitions por categoria_raiz_id (mismo criterio que
  // obtener_specs_equipo). Esto hace que al elegir "Categoría de specs" en el
  // form aparezcan los specs al instante, sin necesidad de guardar primero.
  const specTemplateQ = useQuery({
    queryKey: ["admin", "spec-template", categoriaRootId],
    queryFn: () => adminApi.listSpecTemplates(categoriaRootId!),
    enabled: open && categoriaRootId != null,
  });
  /** Items del template de specs de la categoría seleccionada, ordenados por
   *  prioridad ASC. SpecsDiffEditor matchea por label vs `specs`; los
   *  faltantes los renderiza como ghosts (input vacío). */
  const templateItems = useMemo(() => specTemplateQ.data?.items ?? [], [specTemplateQ.data]);

  // Re-etiquetado: cuando llega/cambia el template de la categoría
  // seleccionada, resolvemos el label de cada spec guardado (id
  // `spec-${spec_def_id}`) contra el template. Solo toca el label —preserva
  // los valores y ediciones en curso—, así un spec canónico cae en la sección
  // "Del template" y deja de verse como "spec N".
  useEffect(() => {
    if (templateItems.length === 0) return;
    const labelById = new Map(templateItems.map((t) => [t.spec_def_id, t.label]));
    setSpecs((prev) => {
      let changed = false;
      const next = prev.map((s) => {
        const m = /^spec-(\d+)$/.exec(s.id);
        if (!m) return s;
        const label = labelById.get(Number(m[1]));
        if (label && label !== s.label) {
          changed = true;
          return { ...s, label };
        }
        return s;
      });
      return changed ? next : prev;
    });
    // `equipoSpecsQ.data` en deps: cuando el efecto de carga reconstruye
    // `specs` (con labels fallback), re-etiquetamos aunque el template ya
    // estuviera cargado de antes (evita quedar pegado en "spec N").
  }, [templateItems, equipoSpecsQ.data]);

  // ── Auto-generación del nombre público ────────────────────────────
  // Cuando el toggle está ON y la categoría tiene template, regenera al
  // tocar cualquier campo relevante. Montura/Formato/Resolución se leen
  // de los specs por label (ya no son inputs dedicados).
  const watchedMarca = form.watch("marca");
  const watchedModelo = form.watch("modelo");
  useEffect(() => {
    if (!nombrePublicoAuto) return;
    // Prioridad 1: template definido por el admin en la categoría (DB).
    // Buscar el output_config de cada spec en el template (las definiciones
    // viven en templateItems con tipo + output_config; los valores en specs).
    const tmplByLabel = new Map(
      (templateItems ?? []).map((t) => [t.label.trim().toLowerCase(), t] as const),
    );
    const fromTemplate = renderNombrePublicoTemplate(categoriaTemplate, {
      marca: watchedMarca ?? "",
      modelo: watchedModelo ?? "",
      tipo: categoriaRoot ?? "",
      nombre: initial?.nombre ?? "",
      specs: specs.map((s) => {
        const tmpl = tmplByLabel.get(s.label.trim().toLowerCase());
        const isTabla = tmpl?.tipo === "tabla";
        return {
          label: s.label,
          value: s.value,
          ...(isTabla && s.value ? { value_raw: s.value } : {}),
          output_config: tmpl?.output_config ?? null,
        };
      }),
    });
    if (fromTemplate) {
      setNombrePublico(fromTemplate);
      return;
    }
    // Prioridad 2: template hardcoded (nombre-publico.ts) por categoría conocida.
    const gen = generarNombrePublico(categoriaRoot, {
      marca: watchedMarca ?? "",
      modelo: watchedModelo ?? "",
      montura: findSpecValue(specs, "Montura"),
      formato: findSpecValue(specs, "Formato"),
      resolucion: findSpecValue(specs, "Resolución"),
    });
    if (gen) setNombrePublico(gen);
  }, [
    nombrePublicoAuto,
    categoriaRoot,
    categoriaTemplate,
    watchedMarca,
    watchedModelo,
    specs,
    initial?.nombre,
    templateItems,
  ]);

  /** Hay alguna fuente de auto-gen disponible? Template DB o hardcoded. */
  const autoGenDisponible = !!categoriaTemplate || categoriaSoportaAutoGen(categoriaRoot);

  // ════════════════════════════════════════════════════════════════════
  // Autocompletar — llama al backend con la URL y rellena el form.
  // Specs van a una lista de "propuestos" para que el usuario los apruebe.
  // ════════════════════════════════════════════════════════════════════
  const autocompletar = async () => {
    const u = (form.getValues("bh_url") ?? "").trim();
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
      const r = await authedJson<AutocompletarResult>("/api/admin/equipos/autocompletar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // Pasamos las categorías ya seleccionadas para que el LLM use los
        // labels canónicos del template de esa categoría. Si todavía no
        // se eligió ninguna, el backend cae a guía general.
        body: JSON.stringify({
          url: u,
          categoria_ids: selectedCats.size > 0 ? [...selectedCats] : undefined,
        }),
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
      // Foto NO se toca acá — para fotos está el botón "Buscar foto" aparte.
      // Mantenemos el bh_url (fuente) para que se pueda re-usar.
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

      // Auto-aplicar los propuestos que matchean con el template del equipo
      // (label normalizado): el usuario no debería tener que clickear ✓ uno
      // por uno cuando ya hay un campo definido para ese spec. Solo quedan
      // como "propuestos pendientes" los que NO matchean — esos sí necesitan
      // decisión (¿agregar al catálogo? ¿ignorar?). El backend obliga al
      // LLM a usar el label canónico del template via enum en el JSON
      // schema, así el match acá es por igualdad simple.
      const tmplLabels = new Set((templateItems ?? []).map((t) => t.label.trim().toLowerCase()));
      const autoAplicables = propuestos.filter((p) => tmplLabels.has(p.label.trim().toLowerCase()));
      const requierenRevision = propuestos.filter(
        (p) => !tmplLabels.has(p.label.trim().toLowerCase()),
      );
      if (autoAplicables.length > 0) {
        setSpecs((prev) => {
          const next = [...prev];
          for (const p of autoAplicables) {
            const idx = next.findIndex((x) => sameLabel(x.label, p.label));
            if (idx >= 0) next[idx] = { ...next[idx], value: p.value };
            else next.push(newSpec(p.label, p.value));
          }
          return next;
        });
      }
      if (requierenRevision.length > 0) setSpecsPropuestos(requierenRevision);

      setImportedFichaExt(r);

      const parts: string[] = [];
      if (autoAplicables.length) parts.push(`${autoAplicables.length} aplicados al template`);
      if (requierenRevision.length) parts.push(`${requierenRevision.length} pendientes de revisar`);
      if (r.keywords?.length) parts.push(`${r.keywords.length} etiquetas`);
      if (r.descripcion) parts.push("descripción");
      toast.success("Specs importados", { description: parts.join(" · ") || "datos básicos" });
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
    const u = (form.getValues("bh_url") ?? "").trim();
    setPhotoSearching(true);
    const ctrl = new AbortController();
    const timeoutId = setTimeout(() => ctrl.abort(), 30_000);
    try {
      const r = await authedJson<{ foto_candidates: string[] }>("/api/admin/equipos/buscar-fotos", {
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
      });
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
    if (tags.includes(v)) {
      setTagInput("");
      return;
    }
    setTags([...tags, v]);
    setTagInput("");
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

  const submit = form.handleSubmit(
    async (values) => {
      // Validación de creación: al menos una categoría seleccionada (#351).
      // Las categorías viven en estado separado del schema zod, así que las
      // chequeamos acá. En edit dejamos pasar por compat con equipos legacy.
      if (!isEdit && selectedCats.size === 0) {
        toast.error("Categoría requerida", {
          description: "Elegí al menos una categoría antes de guardar.",
        });
        return;
      }

      // Pre-flight: validación de duplicados por serie. La serie es lo más
      // único; si ya hay otro equipo con la misma, le pedimos confirmación al
      // user antes de seguir (puede ser legítimo en kits, pero conviene avisar).
      // EXCEPCIÓN: "N/A" es un placeholder común — los equipos sin serie real
      // comparten ese valor por design, así que no avisamos.
      const serieTrim = values.serie?.trim();
      const isPlaceholderSerie = !!serieTrim && /^(n\/?a|n\/?d|sin\s*serie|-+)$/i.test(serieTrim);
      if (serieTrim && !isPlaceholderSerie) {
        try {
          const r = await adminApi.listEquipos({ q: serieTrim });
          const dups = r.items.filter(
            (e) =>
              e.id !== initial?.id &&
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
        categoria_specs: categoriaSpecs || null,
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

        // Ficha legacy: descripción + notas + keywords + nombre público.
        // Las specs estructuradas ya NO van acá — viven en equipo_specs y
        // se persisten vía putEquipoSpecs (más abajo).
        const tieneFicha =
          isEdit ||
          !!descripcion ||
          !!notas ||
          tags.length > 0 ||
          !!nombrePublico.trim() ||
          !!importedFichaExt;
        if (tieneFicha) {
          try {
            await adminApi.setFicha(equipoId, {
              descripcion: descripcion || null,
              notas: notas || null,
              keywords_json: tags.length ? JSON.stringify(tags) : null,
              // Si el toggle "auto" está ON y tenemos un template de categoría,
              // persistimos el TEMPLATE con tokens ("{marca} {modelo} ...").
              // Al re-abrir el form, hasTokens detectará tokens → toggle queda ON.
              // Cuando está OFF, guardamos el literal escrito por el dueño
              // (override fijo, no se regenera).
              nombre_publico_template:
                nombrePublicoAuto && categoriaTemplate
                  ? categoriaTemplate
                  : nombrePublico.trim() || null,
            });
          } catch (e) {
            fallidos.push(`ficha (${e instanceof Error ? e.message : "error"})`);
          }
        }

        // Specs estructuradas → PUT a equipo_specs (SoT única). El id de cada
        // spec codifica su spec_def_id (`spec-${id}` para guardados, `tmpl-${id}`
        // para los del template materializados), así que mapeamos directo sin
        // round-trip por label —que se rompía cuando el label todavía no estaba
        // resuelto contra el template. Los specs custom (id uuid, sin
        // spec_def_id) no van a equipo_specs: se gestionan en /admin/equipos/specs.
        if (isEdit && equipoSpecsQ.data) {
          try {
            const specsDict: Record<string, string> = {};
            for (const s of specs) {
              const value = s.value.trim();
              if (!value) continue;
              const m = /^(?:spec|tmpl)-(\d+)$/.exec(s.id);
              if (!m) continue;
              specsDict[m[1]] = value;
            }
            await adminApi.putEquipoSpecs(equipoId, specsDict);
          } catch (e) {
            fallidos.push(`specs (${e instanceof Error ? e.message : "error"})`);
          }
        }

        // Ficha extendida (peso, dimensiones, etc.) si vino del autocompletar
        if (importedFichaExt) {
          try {
            const r = importedFichaExt;
            // Specs físicas (peso/dimensiones/montura/formato/resolucion/
            // alimentacion) las consolida el backend en equipo_specs vía
            // _matchear_y_persistir_specs (post-Fase F). Mandamos los
            // campos planos del scrape — el backend hace el mapping a
            // spec_key correspondiente.
            const ext: Record<string, unknown> = {};
            if (r.peso) ext.peso = r.peso;
            if (r.dimensiones) ext.dimensiones = r.dimensiones;
            if (r.alimentacion) ext.alimentacion = r.alimentacion;
            if (r.montura) ext.montura = r.montura;
            if (r.formato) ext.formato = r.formato;
            if (r.resolucion) ext.resolucion = r.resolucion;
            // Listas y multimedia (no son specs estructuradas)
            if (r.video_url) ext.video_url = r.video_url;
            if (typeof r.precio_bh_usd === "number") ext.precio_bh_usd = r.precio_bh_usd;
            if (r.incluye?.length) ext.incluye = r.incluye;
            if (r.conectividad?.length) ext.conectividad = r.conectividad;
            if (r.compatible_con?.length) ext.compatible_con = r.compatible_con;
            if (r.fuente_url) ext.fuente_url = r.fuente_url;
            if (r.fuente_titulo) ext.fuente_titulo = r.fuente_titulo;
            if (r.enriquecido_fuente) ext.enriquecido_fuente = r.enriquecido_fuente;
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
        // En creación, si faltan campos recomendados, ofrecemos completarlos
        // ahora antes de cerrar — el equipo ya está creado, esto es opcional. #351
        if (!isEdit && equipoId) {
          // Para foto consideramos tanto foto_url ya seteada como pendingFile
          // recién subido (que ya se aplicó arriba con setValue).
          const missing: RecommendedField[] = [];
          const fotoTras = form.getValues("foto_url") || pendingFile;
          if (!fotoTras) missing.push("foto");
          if (!descripcion?.trim()) missing.push("descripcion");
          const serieClean = values.serie?.trim();
          if (!serieClean) missing.push("serie");
          if (!values.valor_reposicion || values.valor_reposicion === 0)
            missing.push("valor_reposicion");

          if (missing.length > 0 && onCreatedWithMissingRecommended) {
            const labels = missing.map((m) => RECOMMENDED_LABELS[m]).join(", ");
            toast.success("Equipo creado", {
              description: `Faltan datos recomendados: ${labels}`,
              action: {
                label: "Completar →",
                onClick: () => {
                  // Reabrimos el form en edit mode con el equipo recién creado.
                  // El form vuelve a abrirse con todos los datos cargados y los
                  // campos faltantes resaltados implícitamente vía el dashboard
                  // de calidad (#349).
                  const savedEquipo = { ...(initial ?? {}), ...payload, id: equipoId } as Equipo;
                  onCreatedWithMissingRecommended(savedEquipo, missing);
                },
              },
              duration: 12000,
            });
            onOpenChange(false);
            return;
          }
        }
        toast.success(isEdit ? "Equipo actualizado" : "Equipo creado");
      }
      onOpenChange(false);
    },
    (errors) => {
      // Fallaba silencioso cuando había errores de validación zod (ej. nombre
      // vacío, número negativo). Acá los surfaceamos como toast con el primer
      // campo problemático para que el usuario sepa qué corregir.
      const FIELD_LABELS: Record<string, string> = {
        nombre: "Nombre",
        marca: "Marca",
        modelo: "Modelo",
        cantidad: "Cantidad",
        precio_jornada: "Precio jornada",
        precio_usd: "Precio USD",
        roi_pct: "% día",
        valor_reposicion: "Valor reposición",
        fecha_compra: "Fecha de compra",
        serie: "Serie",
        bh_url: "Link de fuente",
        foto_url: "Foto",
        dueno: "Dueño",
        estado: "Estado",
      };
      const entries = Object.entries(errors);
      if (entries.length === 0) {
        toast.error("Hay errores en el formulario, revisalos.");
        return;
      }
      const [field, error] = entries[0];
      const label = FIELD_LABELS[field] ?? field;
      const msg = (error as { message?: string } | undefined)?.message ?? "valor inválido";
      toast.error(`${label}: ${msg}`, {
        description:
          entries.length > 1 ? `Y ${entries.length - 1} campo(s) más con errores.` : undefined,
      });
    },
  );

  // ════════════════════════════════════════════════════════════════════
  // Render
  // ════════════════════════════════════════════════════════════════════
  const fotoActual = pendingFilePreview || form.watch("foto_url");

  // ── Confirmación al cerrar con cambios sin guardar (#232) ──────────
  // Detectamos cambios desde 4 fuentes: form fields (react-hook-form),
  // specs propuestos del autocompletar, ficha externa importada, archivo
  // de foto pendiente de upload. Cubre los casos típicos de pérdida de
  // datos en silencio. Falsos negativos posibles: cambios SOLO en
  // descripcion/notas/tags/specs manuales sin tocar form fields.
  const [confirmCloseOpen, setConfirmCloseOpen] = useState(false);
  const hasUnsavedChanges =
    form.formState.isDirty ||
    specsPropuestos.length > 0 ||
    importedFichaExt !== null ||
    pendingFile !== null;

  const handleCloseRequest = (next: boolean) => {
    if (!next && hasUnsavedChanges) {
      setConfirmCloseOpen(true);
      return;
    }
    onOpenChange(next);
  };

  const formSections = (
    <>
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
        <LinkInput
          value={form.watch("bh_url") ?? ""}
          onChange={(v) => form.setValue("bh_url", v, { shouldDirty: true })}
          placeholder="https://www.bhphotovideo.com/c/product/..."
        />
        <div className="flex flex-wrap gap-1.5">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={buscarFotos}
            disabled={photoSearching}
          >
            {photoSearching ? (
              <>
                <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> Buscando…
              </>
            ) : (
              <>
                <ImageIcon className="h-3.5 w-3.5 mr-1" /> Buscar foto (~5s)
              </>
            )}
          </Button>
          <Button type="button" size="sm" onClick={autocompletar} disabled={autocompletando}>
            {autocompletando ? (
              <>
                <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> Buscando…
              </>
            ) : (
              <>
                <Sparkles className="h-3.5 w-3.5 mr-1" /> Buscar specs (~15s)
              </>
            )}
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
                  onChange={(e) => setNombrePublico(e.target.value)}
                  placeholder={
                    autoGenDisponible
                      ? "Generado automático según la categoría"
                      : "Ej: Cable HDMI 2.0 50cm"
                  }
                />
                {autoGenDisponible && (
                  <label className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Switch checked={nombrePublicoAuto} onCheckedChange={setNombrePublicoAuto} />
                    Generar automático desde {categoriaRoot?.toLowerCase()}
                    {!nombrePublicoAuto && (
                      <span className="opacity-60">
                        (off — el valor escrito se guarda como override fijo)
                      </span>
                    )}
                  </label>
                )}
                {autoGenDisponible && nombrePublicoAuto && (
                  <p className="text-[10px] text-muted-foreground italic">
                    Tu edición se mantiene en esta sesión. Si cambia el template o los specs, el
                    campo se regenera (toggle OFF para fijarlo).
                  </p>
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
                <Input
                  {...form.register("marca")}
                  placeholder="Sony"
                  list="marca-options"
                  autoComplete="off"
                />
                <datalist id="marca-options">
                  {marcasOptions.map((m) => (
                    <option key={m.id} value={m.nombre} />
                  ))}
                </datalist>
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
                    key={u}
                    type="button"
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
                type="button"
                size="icon"
                variant="outline"
                className="h-9 w-9 shrink-0"
                onClick={() => {
                  const raw = Number(form.getValues("cantidad") ?? 0);
                  const current = Number.isFinite(raw) ? raw : 0;
                  form.setValue("cantidad", Math.max(0, current - 1), { shouldDirty: true });
                }}
                aria-label="Restar 1 al stock"
              >
                −
              </Button>
              <Input type="number" min={0} className="text-center" {...form.register("cantidad")} />
              <Button
                type="button"
                size="icon"
                variant="outline"
                className="h-9 w-9 shrink-0"
                onClick={() => {
                  const raw = Number(form.getValues("cantidad") ?? 0);
                  const current = Number.isFinite(raw) ? raw : 0;
                  form.setValue("cantidad", current + 1, { shouldDirty: true });
                }}
                aria-label="Sumar 1 al stock"
              >
                +
              </Button>
            </div>
          </Field>
          <Field label="Valor USD">
            <Input type="number" step="0.01" {...form.register("precio_usd")} />
          </Field>
          <Field label="% día">
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
                  type="button"
                  size="icon"
                  variant="ghost"
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
            <SelectTrigger>
              <SelectValue placeholder="Seleccionar…" />
            </SelectTrigger>
            <SelectContent>
              {DUENOS.map((d) => (
                <SelectItem key={d} value={d}>
                  {d}
                </SelectItem>
              ))}
              {form.watch("dueno") && !isCanonicalDueno(form.watch("dueno") ?? "") && (
                <SelectItem value={form.watch("dueno") ?? ""}>
                  {form.watch("dueno")} (custom)
                </SelectItem>
              )}
            </SelectContent>
          </Select>
        </Field>
      </section>

      {/* ════════════════════════════════════════════════════════════════
              DESCRIPCIÓN — campo de marketing/catálogo, separado de la
              ficha técnica. Va en una sección propia para evitar confusión
              con specs.
          ════════════════════════════════════════════════════════════════ */}
      <CollapsibleSection title="Descripción (catálogo público)" defaultOpen={!!descripcion}>
        <Field label="Texto descriptivo">
          <Textarea
            rows={3}
            value={descripcion}
            onChange={(e) => setDescripcion(e.target.value)}
            placeholder="Texto de marketing visible en la ficha del catálogo. Ej: ventajas, casos de uso típicos, diferenciales."
          />
        </Field>
      </CollapsibleSection>

      {/* ════════════════════════════════════════════════════════════════
              FICHA TÉCNICA — colapsable. Solo specs estructuradas (template
              + custom). La descripción está separada en su propia sección.
          ════════════════════════════════════════════════════════════════ */}
      <CollapsibleSection
        title="Ficha técnica"
        defaultOpen={specsPropuestos.length > 0 || specs.length > 0 || !!categoriaSpecs}
      >
        <div className="space-y-3">
          <Field label="Categoría de specs">
            <Select
              value={categoriaSpecs || "__none__"}
              onValueChange={(v) => {
                specsTouchedRef.current = true;
                setCategoriaSpecs(v === "__none__" ? "" : v);
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Sin categoría de specs" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">Sin categoría de specs</SelectItem>
                {specCatOptions.map((c) => (
                  <SelectItem key={c.id} value={c.nombre}>
                    {c.nombre}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Define qué specs técnicas aplican y el nombre público. Al elegirla aparecen los specs
              abajo. Independiente del catálogo.
            </p>
          </Field>

          <SpecsDiffEditor
            specs={specs}
            propuestos={specsPropuestos}
            templateItems={templateItems}
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

          <Field label="Etiquetas">
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
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addTag();
                    }
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
              CATEGORÍAS DEL CATÁLOGO — agrupación para el front-office, separada
              de la categoría de specs (que vive en Ficha técnica).
          ════════════════════════════════════════════════════════════════ */}
      <section className="pt-2 border-t hairline space-y-3">
        <div>
          <Label className="text-xs uppercase tracking-wide text-muted-foreground">
            Categorías del catálogo
          </Label>
          <CategoriaSugeridaChip
            categoriaSugerida={importedFichaExt?.categoria_sugerida ?? null}
            categorias={catsQ.data ?? []}
            selected={selectedCats}
            onApply={(id) => setSelectedCats(new Set([...selectedCats, id]))}
          />
          <CategoriasPicker
            categorias={catsQ.data ?? []}
            selected={selectedCats}
            onChange={setSelectedCats}
          />
        </div>
      </section>

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
                onValueChange={(v) =>
                  form.setValue("estado", v as FormValues["estado"], { shouldDirty: true })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
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
              <Input {...form.register("serie")} placeholder="N/A si no tenés" />
            </Field>
          </div>

          <Field label="Notas internas (no se muestran al cliente)">
            <Textarea rows={2} value={notas} onChange={(e) => setNotas(e.target.value)} />
          </Field>
        </div>
      </CollapsibleSection>
    </>
  );

  const titleText = isEdit ? "Editar equipo" : "Nuevo equipo";
  const formId = "equipo-form-v2";

  const publicHint = nombrePublico ? (
    <p className="text-xs text-muted-foreground">
      Se ve en la web como: <span className="text-ink font-medium italic">{nombrePublico}</span>
    </p>
  ) : null;

  const footerActions = (
    <>
      <Button type="button" variant="ghost" onClick={() => handleCloseRequest(false)}>
        Cancelar
      </Button>
      <Button type="submit" form={formId} disabled={saving}>
        {saving ? (
          <>
            <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> Guardando…
          </>
        ) : (
          "Guardar"
        )}
      </Button>
    </>
  );

  const confirmCloseDialog = (
    <AlertDialog open={confirmCloseOpen} onOpenChange={setConfirmCloseOpen}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Tenés cambios sin guardar</AlertDialogTitle>
          <AlertDialogDescription>
            Si salís ahora, los cambios que hiciste en este equipo se pierden. ¿Querés salir igual?
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Volver al form</AlertDialogCancel>
          <AlertDialogAction
            onClick={() => {
              setConfirmCloseOpen(false);
              onOpenChange(false);
            }}
          >
            Salir sin guardar
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );

  // ── Variant "page": editor de página completa (mock del handoff) ──────
  if (variant === "page") {
    const kpiFmt = (n: unknown) =>
      typeof n === "number" && !Number.isNaN(n) ? n.toLocaleString("es-AR") : "—";
    return (
      <>
        <div className="px-4 md:px-6 py-6 pb-28 max-w-6xl mx-auto">
          <header className="mb-6">
            <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Inventario · Equipos
            </div>
            <h1 className="font-display text-3xl text-ink">{titleText}</h1>
            {publicHint}
          </header>
          <div className="grid lg:[grid-template-columns:minmax(0,1fr)_320px] gap-6 items-start">
            <form id={formId} onSubmit={submit} className="space-y-5 min-w-0" data-equipo-form-v2>
              {formSections}
            </form>
            <aside className="space-y-3 lg:sticky lg:top-6">
              <div className="rounded-lg border hairline bg-card overflow-hidden">
                <div className="aspect-square bg-white grid place-items-center p-4">
                  {fotoActual ? (
                    <img src={fotoActual} alt="" className="max-h-full max-w-full object-contain" />
                  ) : (
                    <ImageIcon className="h-10 w-10 text-muted-foreground/30" />
                  )}
                </div>
                <div className="p-3 border-t hairline">
                  <div className="font-medium text-ink text-sm leading-tight">
                    {form.watch("nombre") || "Equipo sin nombre"}
                  </div>
                  {nombrePublico && (
                    <div className="text-xs text-muted-foreground italic mt-0.5">
                      {nombrePublico}
                    </div>
                  )}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-lg border hairline bg-card px-3 py-2.5">
                  <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
                    $ / jornada
                  </div>
                  <div className="font-display text-xl font-black text-ink tabular-nums mt-0.5">
                    ${kpiFmt(form.watch("precio_jornada"))}
                  </div>
                </div>
                <div className="rounded-lg border hairline bg-card px-3 py-2.5">
                  <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
                    % día
                  </div>
                  <div className="font-display text-xl font-black text-ink tabular-nums mt-0.5">
                    {kpiFmt(form.watch("roi_pct"))}%
                  </div>
                </div>
                <div className="rounded-lg border hairline bg-card px-3 py-2.5 col-span-2">
                  <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
                    Valor reposición
                  </div>
                  <div className="font-display text-xl font-black text-ink tabular-nums mt-0.5">
                    ${kpiFmt(form.watch("valor_reposicion"))}
                  </div>
                </div>
              </div>
            </aside>
          </div>
        </div>
        <div className="sticky bottom-0 z-20 border-t hairline bg-background/95 backdrop-blur px-4 md:px-6 py-3 flex justify-end gap-2">
          {footerActions}
        </div>
        {confirmCloseDialog}
      </>
    );
  }

  return (
    <>
      <Dialog open={open} onOpenChange={handleCloseRequest}>
        <DialogContent className="w-full sm:max-w-3xl max-h-[92vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-display text-2xl">{titleText}</DialogTitle>
            {publicHint}
          </DialogHeader>
          <form id={formId} onSubmit={submit} className="space-y-5" data-equipo-form-v2>
            {formSections}
            <DialogFooter className="pt-2 border-t hairline">{footerActions}</DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      {confirmCloseDialog}
    </>
  );
}

// ════════════════════════════════════════════════════════════════════
// Sub-componentes
// ════════════════════════════════════════════════════════════════════

function Field({
  label,
  error,
  children,
  actions,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}) {
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
  title,
  defaultOpen = false,
  children,
  actions,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
  actions?: React.ReactNode;
}) {
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
      <CollapsibleContent className="pt-2">{children}</CollapsibleContent>
    </Collapsible>
  );
}

function LinkInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const valid = useMemo(() => {
    if (!value.trim()) return false;
    try {
      const u = new URL(value);
      return u.protocol === "http:" || u.protocol === "https:";
    } catch {
      return false;
    }
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
            type="button"
            size="icon"
            variant="outline"
            title="Copiar al portapapeles"
            onClick={copiar}
          >
            <Copy className="h-3.5 w-3.5" />
          </Button>
          <Button
            type="button"
            size="icon"
            variant="outline"
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
  url,
  pendingFile,
  hasInitial,
  onClear,
  onUpload,
  onSubirAR2,
  uploading,
  uploadingToR2,
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
              {pendingFile && (
                <Badge variant="secondary" className="text-[9px]">
                  Local — al guardar
                </Badge>
              )}
              {isHosted && (
                <Badge variant="default" className="text-[9px]">
                  ✓ En R2
                </Badge>
              )}
              {isExternal && (
                <Badge variant="outline" className="text-[9px]">
                  URL externa
                </Badge>
              )}
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
          type="button"
          size="sm"
          variant="outline"
          className="text-xs"
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? (
            <>
              <Loader2 className="h-3 w-3 mr-1 animate-spin" /> Subiendo…
            </>
          ) : (
            <>
              <Upload className="h-3 w-3 mr-1" /> Subir foto
            </>
          )}
        </Button>
        {isExternal && hasInitial && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="text-xs"
            onClick={onSubirAR2}
            disabled={uploadingToR2}
          >
            {uploadingToR2 ? (
              <>
                <Loader2 className="h-3 w-3 mr-1 animate-spin" /> Subiendo…
              </>
            ) : (
              "Subir a R2"
            )}
          </Button>
        )}
      </div>
    </div>
  );
}

/**
 * Chip de "Categoría sugerida" que aparece arriba del CategoriasPicker
 * cuando el scrape devolvió un `categoria_sugerida`. Match case-insensitive
 * (sin acentos) contra la lista de categorías de DB. Click → aplica.
 *
 * El backend se encarga de auto-asignar la madre si la sugerencia es hija
 * (ver `_expand_to_ancestors` en backend/routes/equipos.py).
 */
function CategoriaSugeridaChip({
  categoriaSugerida,
  categorias,
  selected,
  onApply,
}: {
  categoriaSugerida: string | null | undefined;
  categorias: CategoriaAdmin[];
  selected: Set<number>;
  onApply: (id: number) => void;
}) {
  if (!categoriaSugerida) return null;

  const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").trim();
  const target = norm(categoriaSugerida);

  const match = categorias.find((c) => norm(c.nombre) === target);
  if (!match) return null;
  if (selected.has(match.id)) return null;

  return (
    <button
      type="button"
      onClick={() => onApply(match.id)}
      className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-amber-soft px-3 py-1 text-xs text-ink hover:bg-amber transition active:scale-95"
      title="Aplicar la categoría sugerida por el scrape"
    >
      <Sparkles className="h-3 w-3 text-amber-700" />
      <span className="text-muted-foreground">Sugerida:</span>
      <strong>{match.nombre}</strong>
      <span className="text-muted-foreground">· Aplicar</span>
    </button>
  );
}

function CategoriasPicker({
  categorias,
  selected,
  onChange,
}: {
  categorias: CategoriaAdmin[];
  selected: Set<number>;
  onChange: (s: Set<number>) => void;
}) {
  const [q, setQ] = useState("");
  const toggle = (id: number) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange(next);
  };
  const roots = categorias.filter((c) => c.parent_id == null);
  const childrenOf = (pid: number) => categorias.filter((c) => c.parent_id === pid);

  const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const nq = norm(q.trim());
  const matchesName = (nombre: string) => !nq || norm(nombre).includes(nq);

  const visibleRoots = roots.filter((r) => {
    if (matchesName(r.nombre)) return true;
    return childrenOf(r.id).some((c) => matchesName(c.nombre));
  });

  return (
    <div className="space-y-2 mt-1">
      <div className="relative">
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar categoría…"
          className="w-full text-sm rounded-md border hairline px-3 py-1.5 pr-7 outline-none focus:ring-1 focus:ring-ring bg-background"
        />
        {q && (
          <button
            type="button"
            onClick={() => setQ("")}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
      <div className="space-y-2 max-h-60 overflow-y-auto rounded-md border hairline p-2">
        {visibleRoots.map((root) => {
          const visibleChildren = childrenOf(root.id).filter(
            (c) => matchesName(c.nombre) || matchesName(root.nombre),
          );
          return (
            <div key={root.id}>
              <button type="button" onClick={() => toggle(root.id)}>
                <Badge
                  variant={selected.has(root.id) ? "default" : "outline"}
                  className="cursor-pointer"
                >
                  {root.nombre}
                </Badge>
              </button>
              {visibleChildren.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1 ml-3">
                  {visibleChildren.map((c) => (
                    <button key={c.id} type="button" onClick={() => toggle(c.id)}>
                      <Badge
                        variant={selected.has(c.id) ? "default" : "secondary"}
                        className="cursor-pointer text-[10px]"
                      >
                        {c.nombre}
                      </Badge>
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
        {visibleRoots.length === 0 && (
          <p className="text-xs text-muted-foreground italic">
            {q ? "Sin resultados." : "Sin categorías. Creá algunas en /admin/settings."}
          </p>
        )}
      </div>
    </div>
  );
}
