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
 *  - HTML upload para extraer specs (determinístico, sin LLM).
 *  - Kit con drag-drop (igual que el viejo).
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Upload,
  Trash2,
  Search,
  Link as LinkIcon,
  Image as ImageIcon,
  FileCode,
  Printer,
} from "lucide-react";
import { Spinner } from "@/design-system/ui/spinner";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/design-system/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/design-system/ui/alert-dialog";
import { Input } from "@/design-system/ui/input";
import { Label } from "@/design-system/ui/label";
import { Button } from "@/design-system/ui/button";
import { Switch } from "@/design-system/ui/switch";
import { Textarea } from "@/design-system/ui/textarea";
import { Badge } from "@/design-system/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import { DUENOS, isCanonicalDueno } from "@/lib/admin/duenos";
import { MonthYearPicker } from "@/components/admin/MonthYearPicker";
import { useConfirm } from "@/components/admin/useConfirm";

import { adminApi, type Equipo, type EquipoInput } from "@/lib/admin/api";
import type { ContenidoIncluidoItem } from "@/data/equipment";
import { uploadFileToBucket, uploadExternalUrlToBucket, isHostedUrl } from "@/lib/equipment/photos";
import { uploadEquipoFotoFromUrl } from "@/lib/equipment/equipoFotos";
import { PhotoGallery } from "@/components/common/PhotoGallery";
import { authedJson } from "@/lib/authedFetch";
import { useUsdRate, useRoiPctDefault, calcularPrecioJornada } from "@/hooks/useSettings";
import { Monto, PrecioUnidad } from "@/components/admin/Monto";
import { KitEditor } from "./KitEditor";
import { ComboEditor } from "./ComboEditor";
import { ContenidoIncluidoEditor } from "./ContenidoIncluidoEditor";
import { SpecsDiffEditor } from "./SpecsDiffEditor";
import { type Spec, newSpec, withIds, sameLabel, uniq } from "./spec-helpers";
import { renderNombrePublicoTemplate } from "@/lib/equipment/nombre-template";
import {
  Field,
  CollapsibleSection,
  LinkInput,
  PhotoCard,
  CategoriasPicker,
  TipoGlosario,
} from "./form-helpers";
import {
  buildSchema,
  type FormValues,
  RECOMMENDED_FIELDS,
  type RecommendedField,
  RECOMMENDED_LABELS,
} from "./equipo-form-schema";
import { useEquipoFotos } from "./useEquipoFotos";

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
  onSubmit: (data: EquipoInput) => Promise<Equipo>;
  saving?: boolean;
  /** "dialog" (modal, default) o "page" (editor de página completa con
   *  2 columnas + aside + save bar fija, como el mock del handoff). */
  variant?: "dialog" | "page";
  /** Si el equipo se creó pero le faltan recomendados, el parent decide
   *  qué hacer (ej. reabrir el form en modo edit). #351 */
  onCreatedWithMissingRecommended?: (equipo: Equipo, missing: RecommendedField[]) => void;
}) {
  const isEdit = !!initial;
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { rate: usdRate } = useUsdRate();
  const roiDefault = useRoiPctDefault();

  // "Aplicar" (guardar sin cerrar) vs "Guardar" (cerrar al terminar). El
  // botón Aplicar setea este ref a false antes de disparar el submit; en el
  // success path consultamos el ref para decidir cerrar o quedarnos.
  const closeOnSuccessRef = useRef(true);

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
      tipo: (initial?.tipo as FormValues["tipo"]) ?? "simple",
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
  // B1 #635: contenido incluido (dim. 3)
  const [contenidoIncluido, setContenidoIncluido] = useState<ContenidoIncluidoItem[]>([]);
  // keywords_json ya no se edita a mano acá — se calcula solo desde las specs
  // (compute_keywords, ver services/nombre_builder.py). El form solo lo
  // carga y lo reenvía sin tocar (round-trip), para no pisarlo a null en
  // cada guardado — nunca se renderiza ni se muta desde la UI.
  const [tags, setTags] = useState<string[]>([]);

  // ── Nombre público ─────────────────────────────────────────────────
  // Input libre + toggle "generar automático desde categoría". El toggle
  // arranca ON: si la categoría de specs tiene un molde (nombre_publico_
  // template, seteado desde /admin/equipos/specs), el nombre se arma solo
  // desde los specs — es una fuente VIVA (services/nombre_service.py la lee
  // en cada guardado, no una copia). El usuario puede toggle OFF para
  // escribir a mano: eso se guarda como `nombre_publico_override`, que
  // gana SIEMPRE sobre el molde de categoría (así cambiar el molde no pisa
  // un nombre elegido a mano — ver services/nombre_builder.py, 2026-07).
  const [nombrePublico, setNombrePublico] = useState("");
  const [nombrePublicoAuto, setNombrePublicoAuto] = useState(true);
  // Carga inicial / reset: el override (equipos.nombre_publico_override) es
  // la ÚNICA fuente de "hay un nombre a mano" — separado del efecto de ficha
  // de abajo porque vive en otra tabla (equipos, no equipo_fichas).
  useEffect(() => {
    const override = initial?.nombre_publico_override?.trim() || "";
    if (override) {
      setNombrePublico(override);
      setNombrePublicoAuto(false);
    } else {
      // Sin override explícito: sembramos con el nombre EFECTIVO ya calculado
      // (equipos.nombre_publico) en vez de dejar el campo vacío. Sin esto, un
      // equipo cuyo nombre viene del ficha-template legado (texto YA
      // renderizado, sin placeholders — una foto vieja, no un molde vivo)
      // mostraba el campo en blanco mientras ese texto congelado seguía
      // siendo lo que ve el catálogo público: el admin no tenía forma de
      // verlo ni de saber que estaba ahí (bug real, encontrado en vivo —
      // equipo con specs editadas cuyo nombre nunca reaccionaba).
      // Si hay molde de categoría real, el efecto de auto-gen de abajo pisa
      // esto enseguida con el valor recién calculado (sin flicker: corre
      // antes de que el usuario interactúe). Si NO hay molde, este valor se
      // queda — y el próximo Guardar lo persiste como override real
      // (mismo criterio que "tipear apaga el auto-gen"), autocurando el
      // dato congelado equipo por equipo con el uso normal, sin necesitar
      // una migración aparte.
      setNombrePublico(initial?.nombre_publico?.trim() || "");
      setNombrePublicoAuto(true);
    }
  }, [initial?.id, initial?.nombre_publico_override, initial?.nombre_publico]);

  // Specs traídos del HTML upload: se guardan en una lista separada para
  // que el usuario los apruebe uno por uno (vs los specs actuales).
  const [specsPropuestos, setSpecsPropuestos] = useState<Spec[]>([]);

  // ── HTML source ────────────────────────────────────────────────────
  const [uploadingHtml, setUploadingHtml] = useState(false);
  const [reExtracting, setReExtracting] = useState(false);
  const [htmlSourceUrl, setHtmlSourceUrl] = useState(initial?.html_source_url ?? null);
  useEffect(() => {
    setHtmlSourceUrl(initial?.html_source_url ?? null);
  }, [initial?.html_source_url]);

  // ── Buscar fotos ───────────────────────────────────────────────────
  const [photoSearching, setPhotoSearching] = useState(false);
  const [photoCands, setPhotoCands] = useState<string[]>([]);
  const [pickingPhotoUrl, setPickingPhotoUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadingToR2, setUploadingToR2] = useState(false);

  // ── Galería multi-foto (edit mode) ────────────────────────────────
  // Concern decoupled del form → useEquipoFotos (query + mutaciones + handlers).
  const gallery = useEquipoFotos(initial, open);

  // CREATE mode: archivo local que se sube después de crear el equipo.
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [pendingFilePreview, setPendingFilePreview] = useState("");
  useEffect(
    () => () => {
      if (pendingFilePreview) URL.revokeObjectURL(pendingFilePreview);
    },
    [pendingFilePreview],
  );

  // ── Sentinel de stock para combos: cantidad = 9999 ─────────────────
  const watchedTipo = form.watch("tipo");
  useEffect(() => {
    if (watchedTipo === "combo") {
      form.setValue("cantidad", 9999, { shouldDirty: true });
    }
  }, [watchedTipo, form]);

  // ── Manual override del precio/día ─────────────────────────────────
  const [precioJornadaManual, setPrecioUnidadManual] = useState(false);
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
      // nombrePublico/nombrePublicoAuto: cargados por el efecto de arriba
      // desde `initial.nombre_publico_override` (equipos, no equipo_fichas).

      let kws: string[] = [];
      try {
        const arr = f.keywords_json ? JSON.parse(f.keywords_json) : [];
        kws = Array.isArray(arr) ? arr.filter((x) => typeof x === "string") : [];
      } catch {
        kws = [];
      }
      setTags(uniq(kws));

      // Contenido incluido (B1 #635)
      try {
        const arr = f.contenido_incluido_json ? JSON.parse(f.contenido_incluido_json) : [];
        setContenidoIncluido(
          Array.isArray(arr)
            ? arr.filter(
                (v): v is ContenidoIncluidoItem =>
                  v != null && typeof v === "object" && typeof v.nombre === "string",
              )
            : [],
        );
      } catch {
        setContenidoIncluido([]);
      }
    } else if (!initial) {
      setDescripcion("");
      setNotas("");
      setTags([]);
      setContenidoIncluido([]);
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
  const htmlInputRef = useRef<HTMLInputElement | null>(null);
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
  // Preview del molde de la categoría de specs (el mismo que lee el backend
  // en vivo — services.nombre_service._categoria_template_de). Sin molde de
  // categoría no hay auto-gen: ya no hay fallback hardcodeado por categoría
  // (existía en nombre-publico.ts, retirado — era exactamente el patrón que
  // el backend eliminó en #415 por dar nombres que "el back-end nunca iba a
  // producir": la preview tiene que mostrar SOLO lo que se va a guardar).
  const watchedMarca = form.watch("marca");
  const watchedModelo = form.watch("modelo");
  useEffect(() => {
    if (!nombrePublicoAuto) return;
    // Chequeo directo a `initial.nombre_publico_override` (no solo al estado
    // derivado `nombrePublicoAuto`): cuando `initial` llega async, el efecto
    // que carga el override y este pueden correr en el mismo commit — un
    // `setNombrePublicoAuto(false)` recién encolado en el otro efecto no se
    // refleja todavía en la clausura de ESTE efecto en el mismo pase (React
    // no re-lee estado recién encolado entre efectos del mismo commit), así
    // que sin este chequeo este efecto podía pisar el override recién
    // cargado con "" — confirmado en vivo (equipo con override guardado
    // abría con el campo vacío pese al toggle ya en OFF).
    if (initial?.nombre_publico_override?.trim()) return;
    // Sin molde de categoría no hay nada que auto-generar — bail ANTES de
    // tocar el input. `nombrePublicoAuto` arranca en `true` por default y el
    // toggle para apagarlo queda OCULTO cuando `autoGenDisponible` es falso
    // (no hay molde), así que sin este chequeo el efecto seguía disparando en
    // cada cambio de marca/modelo/specs y BORRABA silenciosamente el nombre
    // que el usuario tipeó a mano — confirmado en vivo (modo creación: tipear
    // el nombre público y después la marca lo vaciaba). No alcanza con que
    // el toggle esté oculto: el efecto mismo tiene que respetar la ausencia
    // de molde, no solo la UI.
    if (!categoriaTemplate) return;
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
    setNombrePublico(fromTemplate ?? "");
  }, [
    nombrePublicoAuto,
    categoriaRoot,
    categoriaTemplate,
    watchedMarca,
    watchedModelo,
    specs,
    initial?.nombre,
    initial?.nombre_publico_override,
    templateItems,
  ]);

  /** Hay auto-gen disponible? Solo si la categoría de specs tiene molde en DB. */
  const autoGenDisponible = !!categoriaTemplate;

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
      await uploadEquipoFotoFromUrl(initial.id, externalUrl);
      await qc.invalidateQueries({ queryKey: ["admin", "equipo-fotos", initial.id] });
      void qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
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
  // HTML source — sube el archivo, persiste en R2 y extrae specs. También
  // usado por re-extract (#1203): mismo resultado, sin volver a subir el
  // archivo — comparten `_aplicarSpecsExtraidos` (aplica al template o
  // manda a revisión), no hay 2 formas de procesar el mismo resultado.
  // ════════════════════════════════════════════════════════════════════
  const _aplicarSpecsExtraidos = (
    specsExtraidos: { label: string; value: string; spec_key?: string }[],
    tituloSinSpecs: string,
  ) => {
    const propuestos: Spec[] = withIds(specsExtraidos ?? []);
    if (propuestos.length === 0) {
      toast.success(tituloSinSpecs, { description: "No se extrajeron specs del archivo" });
      return;
    }
    const tmplByKey = new Map<string, import("@/lib/admin/api").SpecTemplate>();
    const tmplByLabel = new Map<string, import("@/lib/admin/api").SpecTemplate>();
    for (const t of templateItems ?? []) {
      if (t.spec_key) tmplByKey.set(t.spec_key, t);
      if (t.label?.trim()) tmplByLabel.set(t.label.trim().toLowerCase(), t);
    }
    const findTmpl = (p: Spec) =>
      (p.spec_key ? tmplByKey.get(p.spec_key) : undefined) ??
      tmplByLabel.get(p.label.trim().toLowerCase());

    const autoAplicables = propuestos.filter((p) => !!findTmpl(p));
    const requierenRevision = propuestos.filter((p) => !findTmpl(p));

    if (autoAplicables.length > 0) {
      setSpecs((prev) => {
        const next = [...prev];
        for (const p of autoAplicables) {
          const tmpl = findTmpl(p)!;
          const targetId = `spec-${tmpl.spec_def_id}`;
          const idx = next.findIndex(
            (x) =>
              x.id === targetId ||
              x.id === `tmpl-${tmpl.spec_def_id}` ||
              sameLabel(x.label, tmpl.label),
          );
          if (idx >= 0) {
            next[idx] = { ...next[idx], value: p.value };
          } else {
            next.push({
              id: targetId,
              label: tmpl.label,
              value: p.value,
              spec_key: p.spec_key,
            });
          }
        }
        return next;
      });
    }
    if (requierenRevision.length > 0) setSpecsPropuestos(requierenRevision);

    const parts: string[] = [];
    if (autoAplicables.length) parts.push(`${autoAplicables.length} aplicados al template`);
    if (requierenRevision.length) parts.push(`${requierenRevision.length} pendientes de revisar`);
    toast.success("HTML procesado", { description: parts.join(" · ") || "specs extraídos" });
  };

  const handleHtmlUpload = async (file: File) => {
    if (!initial?.id) return;
    setUploadingHtml(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await authedJson<{
        html_source_url: string;
        specs?: { label: string; value: string; spec_key?: string }[];
      }>(`/api/admin/equipos/${initial.id}/upload-html-source`, { method: "POST", body: fd });
      setHtmlSourceUrl(r.html_source_url);
      _aplicarSpecsExtraidos(r.specs ?? [], "HTML guardado");
    } catch (e) {
      toast.error(`Error al subir HTML: ${e instanceof Error ? e.message : ""}`);
    } finally {
      setUploadingHtml(false);
    }
  };

  const handleReExtractSpecs = async () => {
    if (!initial?.id) return;
    setReExtracting(true);
    try {
      const r = await adminApi.reExtractSpecs(initial.id);
      _aplicarSpecsExtraidos(r.specs ?? [], "HTML re-procesado");
    } catch (e) {
      toast.error(`Error al re-extraer specs: ${e instanceof Error ? e.message : ""}`);
    } finally {
      setReExtracting(false);
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
            const ok = await confirm({
              title: "¿Guardar con serie duplicada?",
              description: (
                <>
                  Ya hay otro equipo con la serie "{serieTrim}":
                  <br />• {dups[0].nombre}
                  {dups.length > 1 ? ` (+${dups.length - 1} más)` : ""}
                </>
              ),
              confirmLabel: "Guardar igual",
            });
            if (!ok) return;
          }
        } catch {
          // Si la búsqueda falla, no bloqueamos el save.
        }
      }

      const { visible_catalogo, ficha_completa, tipo, ...rest } = values;

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
        tipo,
      };

      const fallidos: string[] = [];
      let equipoId: number | undefined;

      try {
        const saved = await onSubmit(payload);
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

        // Ficha legacy: descripción + notas + keywords + contenido incluido.
        // El nombre público ya NO va acá — vive en equipos.nombre_publico_override
        // (ver más abajo). Las specs estructuradas tampoco — viven en equipo_specs
        // y se persisten vía putEquipoSpecs (más abajo).
        const tieneFicha = isEdit || !!descripcion || !!notas || tags.length > 0;
        if (tieneFicha) {
          try {
            const validos = contenidoIncluido.filter((ci) => ci.nombre.trim().length > 0);
            const fichaGuardada = await adminApi.setFicha(equipoId, {
              descripcion: descripcion || null,
              notas: notas || null,
              keywords_json: tags.length ? JSON.stringify(tags) : null,
              // B1 #635: contenido incluido — filtramos los ítems sin nombre
              // (el usuario puede tener una fila vacía sin completar; no la
              // enviamos para no fallar la validación del backend y perder
              // los ítems válidos en la misma operación).
              contenido_incluido_json: validos.length > 0 ? JSON.stringify(validos) : null,
            });
            // Actualizar el cache de ficha inmediatamente con la respuesta del
            // servidor. Sin esto, al usar "Aplicar" (no cierra el form), la
            // invalidación del equipo dispara el effect [fichaQ.data, initial]
            // con la ficha VIEJA (no invalidada) → setContenidoIncluido(viejos)
            // pisa lo recién guardado. Con setQueryData el effect re-corre con
            // la ficha fresca y el contenido queda correcto en pantalla.
            qc.setQueryData(["admin", "equipo-ficha", equipoId], fichaGuardada);
          } catch (e) {
            fallidos.push(`ficha (${e instanceof Error ? e.message : "error"})`);
          }
        }

        // Nombre público: override manual vía el endpoint dedicado — gana
        // SIEMPRE sobre el molde de categoría (ver services/nombre_builder.py).
        // "Auto ON + hay molde de categoría" → el backend ya lo arma en vivo,
        // no hay nada que guardar acá; si tenía un override viejo (volvió a
        // auto), lo soltamos para que el molde tome el control de nuevo.
        const usaMoldeDeCategoria = nombrePublicoAuto && !!categoriaTemplate;
        const texto = usaMoldeDeCategoria ? "" : nombrePublico.trim();
        const teniaOverride = !!initial?.nombre_publico_override?.trim();
        // Solo llamamos al endpoint si hay algo que CAMBIAR — nunca en cada
        // guardado sin condición. Si el campo está vacío y nunca hubo
        // override, no tocamos nada: un equipo que nadie re-guardó desde
        // antes del molde vivo puede tener un `nombre_publico` "fósil" de un
        // mecanismo viejo (auto-build hardcodeado, retirado) — limpiar el
        // override en ese caso dispara actualizar_nombres_de igual y lo
        // pisaría a vacío sin que el usuario haya tocado el nombre.
        if (texto) {
          try {
            await adminApi.aprobarNombre(equipoId, { override: texto, revisado: true });
          } catch (e) {
            fallidos.push(`nombre público (${e instanceof Error ? e.message : "error"})`);
          }
        } else if (teniaOverride) {
          try {
            await adminApi.aprobarNombre(equipoId, { override: null, revisado: false });
          } catch (e) {
            fallidos.push(`nombre público (${e instanceof Error ? e.message : "error"})`);
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

      // Invalidar las queries PÚBLICAS (catálogo + ficha de equipo) — el save
      // arriba ya invalida lo admin (vía saveMut.onSettled del route padre),
      // pero nombre público/specs/categorías se escriben acá con llamadas
      // directas que ese onSettled no cubre. Sin esto, el catálogo público
      // sigue mostrando el dato viejo hasta que su staleTime (30-60s) vence
      // solo — "tarda en reproducirse" no era timing raro, era que nadie le
      // avisaba. Prefix-match: no hace falta el slug/rango de fechas exacto.
      void qc.invalidateQueries({ queryKey: ["equipos"] });
      void qc.invalidateQueries({ queryKey: ["equipo"] });
      void qc.invalidateQueries({ queryKey: ["categorias"] });

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
        toast.success(
          isEdit
            ? closeOnSuccessRef.current
              ? "Equipo actualizado"
              : "Cambios aplicados"
            : "Equipo creado",
        );
      }
      if (closeOnSuccessRef.current) {
        onOpenChange(false);
      } else {
        // Aplicar: reseteamos el baseline de dirty para que las próximas
        // ediciones se detecten como nuevas y el confirm-close vuelva a
        // funcionar después de Aplicar.
        form.reset(form.getValues(), { keepValues: true });
      }
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
  // descripcion/notas/specs manuales sin tocar form fields.
  const [confirmCloseOpen, setConfirmCloseOpen] = useState(false);
  const hasUnsavedChanges =
    form.formState.isDirty || specsPropuestos.length > 0 || pendingFile !== null;

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
                <Spinner size="xs" className="mr-1" /> Buscando…
              </>
            ) : (
              <>
                <ImageIcon className="h-3.5 w-3.5 mr-1" /> Buscar foto (~5s)
              </>
            )}
          </Button>
          {isEdit && (
            <>
              {/* eslint-disable-next-line no-restricted-syntax -- input file: no hay componente DS */}
              <input
                ref={htmlInputRef}
                type="file"
                accept=".html,.htm"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void handleHtmlUpload(f);
                  e.target.value = "";
                }}
              />
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => htmlInputRef.current?.click()}
                disabled={uploadingHtml}
              >
                {uploadingHtml ? (
                  <>
                    <Spinner size="xs" className="mr-1" /> Subiendo…
                  </>
                ) : (
                  <>
                    <FileCode className="h-3.5 w-3.5 mr-1" />
                    {htmlSourceUrl ? "Reemplazar HTML" : "Subir HTML"}
                  </>
                )}
              </Button>
              {htmlSourceUrl && (
                <>
                  <span className="flex items-center gap-1 text-xs text-verde-ink font-medium">
                    <FileCode className="h-3 w-3" /> HTML guardado
                  </span>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => void handleReExtractSpecs()}
                    disabled={reExtracting || uploadingHtml}
                    title="Re-corre la extracción sobre el HTML ya guardado, sin resubirlo — útil después de agregar un spec nuevo al registry"
                  >
                    {reExtracting ? (
                      <>
                        <Spinner size="xs" className="mr-1" /> Buscando…
                      </>
                    ) : (
                      "Buscar valores actualizados"
                    )}
                  </Button>
                </>
              )}
            </>
          )}
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════════════
              IDENTIFICACIÓN — foto + nombres + marca/modelo
          ════════════════════════════════════════════════════════════════ */}
      <section className="space-y-3">
        <div className={`grid grid-cols-1 ${!isEdit ? "sm:grid-cols-[160px_1fr]" : ""} gap-3`}>
          {/* Foto card — solo en CREATE mode; en EDIT la galería toma el mando */}
          {!isEdit && (
            <div className="space-y-1">
              <PhotoCard
                url={fotoActual}
                pendingFile={pendingFile}
                hasInitial={false}
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
          )}

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
                  onChange={(e) => {
                    // Tipear a mano es la señal de "esto es mío" — apaga el
                    // auto-gen. Sin esto, `nombrePublicoAuto` (default true)
                    // queda armado en silencio mientras no hay molde (el
                    // toggle para verlo/apagarlo está oculto), y el texto
                    // tipeado se borra apenas se elige una categoría de specs
                    // que sí tiene molde — confirmado en vivo (Angulo 5).
                    setNombrePublico(e.target.value);
                    setNombrePublicoAuto(false);
                  }}
                  placeholder={
                    autoGenDisponible
                      ? "Generado automático según el molde de la categoría"
                      : "Ej: Cable HDMI 2.0 50cm"
                  }
                />
                {autoGenDisponible && (
                  <label className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Switch checked={nombrePublicoAuto} onCheckedChange={setNombrePublicoAuto} />
                    Generar automático desde el molde de {categoriaRoot}
                    {!nombrePublicoAuto && (
                      <span className="opacity-60">(off — se guarda como nombre fijo)</span>
                    )}
                  </label>
                )}
                {autoGenDisponible && nombrePublicoAuto && (
                  <p className="text-2xs text-muted-foreground italic">
                    Molde vivo de la categoría — si el dueño lo cambia desde /admin/equipos/specs,
                    este nombre se actualiza solo (toggle OFF para fijarlo a mano).
                  </p>
                )}
                {!nombrePublicoAuto && (
                  <p className="text-2xs text-muted-foreground italic">
                    Nombre fijo: gana siempre, aunque cambie el molde de la categoría.
                  </p>
                )}
                {!autoGenDisponible && categoriaRoot && (
                  <p className="text-xs text-muted-foreground italic">
                    "{categoriaRoot}" todavía no tiene molde configurado. Escribilo a mano — se
                    guarda como nombre fijo (o configurá el molde en /admin/equipos/specs).
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
                    <img
                      loading="lazy"
                      decoding="async"
                      src={u}
                      alt=""
                      className="h-full w-full object-contain"
                    />
                    {isPicking && (
                      <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                        <Spinner size="sm" className="text-white" />
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
              GALERÍA DE FOTOS — solo en edit mode
          ════════════════════════════════════════════════════════════════ */}
      {isEdit && (
        <section className="space-y-2 pt-2 border-t hairline">
          <p className="text-xs font-medium text-ink/80">Galería de fotos</p>
          <p className="text-xs text-muted-foreground">
            La foto marcada como principal aparece en la ficha pública y en el catálogo.
          </p>
          <PhotoGallery
            fotos={gallery.fotos}
            onUpload={gallery.handleGalleryUpload}
            onDelete={gallery.onDelete}
            onReorder={gallery.handleGalleryReorder}
            onSetPrincipal={gallery.handleGallerySetPrincipal}
            uploading={gallery.galleryUploading}
            disabled={gallery.mutating}
          />
        </section>
      )}

      {/* ════════════════════════════════════════════════════════════════
              PRECIO Y STOCK
          ════════════════════════════════════════════════════════════════ */}
      <section className="space-y-3 pt-2 border-t hairline">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <Field label="Stock">
            {form.watch("tipo") === "combo" ? (
              <div className="flex items-center h-9 px-3 rounded-md border hairline bg-muted/30 text-sm text-muted-foreground">
                Sentinel (9999) — derivado de componentes
              </div>
            ) : (
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
                <Input
                  type="number"
                  min={0}
                  className="text-center"
                  {...form.register("cantidad")}
                />
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
            )}
          </Field>
          <Field label="Valor USD">
            <Input type="number" step="0.01" {...form.register("precio_usd")} />
          </Field>
          <Field label="% día">
            <Input type="number" step="0.1" {...form.register("roi_pct")} />
          </Field>
          <Field label={precioJornadaManual ? "Precio/jornada (manual)" : "Precio/jornada (auto)"}>
            <div className="flex gap-1">
              <Input
                type="number"
                {...form.register("precio_jornada", {
                  onChange: () => setPrecioUnidadManual(true),
                })}
              />
              {precioJornadaManual && (
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  title="Recalcular automático"
                  onClick={() => setPrecioUnidadManual(false)}
                >
                  ↺
                </Button>
              )}
            </div>
          </Field>
        </div>

        <div className="space-y-2">
          <Field label="Tipo de producto">
            <Select
              value={form.watch("tipo")}
              onValueChange={(v) =>
                form.setValue("tipo", v as FormValues["tipo"], { shouldDirty: true })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="simple">Equipo</SelectItem>
                <SelectItem value="kit">Kit</SelectItem>
                <SelectItem value="combo">Combo</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <TipoGlosario tipo={form.watch("tipo")} />
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
                // Buscar template por spec_key primero, label como fallback.
                const byKey = new Map<string, import("@/lib/admin/api").SpecTemplate>(
                  (templateItems ?? []).filter((t) => t.spec_key).map((t) => [t.spec_key, t]),
                );
                const byLabel = new Map<string, import("@/lib/admin/api").SpecTemplate>(
                  (templateItems ?? [])
                    .filter((t) => t.label?.trim())
                    .map((t) => [t.label.trim().toLowerCase(), t]),
                );
                const tmpl =
                  (s.spec_key ? byKey.get(s.spec_key) : undefined) ??
                  byLabel.get(s.label.trim().toLowerCase());
                if (tmpl) {
                  const targetId = `spec-${tmpl.spec_def_id}`;
                  const next = [...prev];
                  const idx = next.findIndex(
                    (x) =>
                      x.id === targetId ||
                      x.id === `tmpl-${tmpl.spec_def_id}` ||
                      sameLabel(x.label, tmpl.label),
                  );
                  if (idx >= 0) {
                    next[idx] = { ...next[idx], value: s.value };
                  } else {
                    next.push({
                      id: targetId,
                      label: tmpl.label,
                      value: s.value,
                      spec_key: s.spec_key,
                    });
                  }
                  return next;
                }
                // Sin template match: spec custom con UUID id.
                const idx = prev.findIndex((x) => sameLabel(x.label, s.label));
                if (idx >= 0) {
                  const next = [...prev];
                  next[idx] = { ...next[idx], value: s.value };
                  return next;
                }
                return [...prev, newSpec(s.label, s.value, s.spec_key)];
              });
              setSpecsPropuestos((prev) => prev.filter((x) => x.id !== s.id));
            }}
            onDescartarPropuesto={(s) => {
              setSpecsPropuestos((prev) => prev.filter((x) => x.id !== s.id));
            }}
          />
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
        <CollapsibleSection
          title={
            form.watch("tipo") === "combo" ? "Componentes del combo" : "Kit (componentes incluidos)"
          }
        >
          {form.watch("tipo") === "combo" ? (
            <ComboEditor equipoId={initial.id} />
          ) : (
            <KitEditor equipoId={initial.id} />
          )}
        </CollapsibleSection>
      )}

      {/* ════════════════════════════════════════════════════════════════
              CONTENIDO INCLUIDO — B1 #635 (solo en EDIT)
          ════════════════════════════════════════════════════════════════ */}
      {isEdit && initial && (
        <CollapsibleSection title="Contenido de la caja" defaultOpen={contenidoIncluido.length > 0}>
          <div className="flex items-start justify-between mb-2 gap-2">
            <p className="text-xs text-muted-foreground">
              Qué viene en la caja (reflector, fuente, cables, estuche). Solo informativo — no
              afecta reservas ni stock.
            </p>
            {contenidoIncluido.length > 0 && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="shrink-0"
                onClick={() => {
                  const nombre = initial.nombre ?? "Equipo";
                  const marca = initial.marca ?? "";
                  const fotoUrl = initial.foto_url ?? "";
                  const fotoAbs =
                    fotoUrl.startsWith("http://") || fotoUrl.startsWith("https://") ? fotoUrl : "";
                  const fotoTag = fotoAbs
                    ? `<img src="${fotoAbs}" style="width:80px;height:80px;object-fit:cover;border-radius:6px;display:block;margin:0 0 16px">`
                    : "";
                  const itemsHtml = contenidoIncluido
                    .map((ci) => {
                      const ciNombre = ci.nombre.replace(/</g, "&lt;").replace(/>/g, "&gt;");
                      const ciFoto =
                        ci.foto_url &&
                        (ci.foto_url.startsWith("http://") || ci.foto_url.startsWith("https://"))
                          ? `<img src="${ci.foto_url}" style="width:40px;height:40px;object-fit:cover;border-radius:4px;vertical-align:middle;margin-right:8px">`
                          : `<span style="display:inline-block;width:40px;height:40px;background:#eee;border-radius:4px;vertical-align:middle;margin-right:8px"></span>`;
                      return `<tr>
                        <td style="padding:6px 8px">${ciFoto}</td>
                        <td style="padding:6px 8px;font-size:13px">${ciNombre}</td>
                        <td style="padding:6px 8px;text-align:center;font-weight:600">${ci.cantidad}</td>
                        <td style="padding:6px 8px;text-align:center"><span style="display:inline-block;width:18px;height:18px;border:1.5px solid #555;border-radius:3px"></span></td>
                      </tr>`;
                    })
                    .join("\n");
                  const html = `<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<title>Contenido: ${nombre.replace(/</g, "&lt;")}</title>
<style>
  body { font-family: -apple-system, Helvetica, sans-serif; color: #111; padding: 24px 32px; max-width: 600px; margin: 0 auto; }
  h2 { margin: 0 0 4px; font-size: 20px; }
  .marca { color: #666; font-size: 13px; margin-bottom: 16px; }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: #666; padding: 6px 8px; border-bottom: 2px solid #111; }
  td { border-bottom: 1px solid #eee; vertical-align: middle; }
  @media print { @page { margin: 16mm; } }
</style>
</head><body>
${fotoTag}
<h2>${nombre.replace(/</g, "&lt;")}</h2>
<div class="marca">${marca.replace(/</g, "&lt;")}</div>
<table>
<thead><tr><th></th><th>Ítem</th><th style="text-align:center">Cant.</th><th style="text-align:center">✓</th></tr></thead>
<tbody>${itemsHtml}</tbody>
</table>
<script>window.onload = function(){ window.print(); };</script>
</body></html>`;
                  const w = window.open("", "_blank", "width=700,height=600");
                  if (w) {
                    w.document.write(html);
                    w.document.close();
                  }
                }}
              >
                <Printer className="h-3 w-3 mr-1" />
                Imprimir contenido
              </Button>
            )}
          </div>
          <ContenidoIncluidoEditor
            equipoId={initial.id}
            items={contenidoIncluido}
            onChange={setContenidoIncluido}
          />
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

  // En edit: dos botones — "Aplicar" persiste sin cerrar (para iterar sin
  // perder posición), "Guardar" persiste y vuelve a la lista. En create solo
  // mostramos "Guardar" porque el flujo post-create necesita el handoff a
  // edit (missing-recommended) o la navegación.
  const triggerApply = () => {
    if (saving) return;
    closeOnSuccessRef.current = false;
    document.querySelector<HTMLFormElement>(`form[data-equipo-form-v2]`)?.requestSubmit();
  };
  const footerActions = (
    <>
      <Button type="button" variant="ghost" onClick={() => handleCloseRequest(false)}>
        Cancelar
      </Button>
      {isEdit && (
        <Button type="button" variant="outline" disabled={saving} onClick={triggerApply}>
          {saving ? (
            <>
              <Spinner size="sm" className="mr-1.5" /> Guardando…
            </>
          ) : (
            "Aplicar"
          )}
        </Button>
      )}
      <Button
        type="submit"
        variant="primary"
        form={formId}
        disabled={saving}
        onClick={() => {
          closeOnSuccessRef.current = true;
        }}
      >
        {saving ? (
          <>
            <Spinner size="sm" className="mr-1.5" /> Guardando…
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
            <div className="t-eyebrow">Inventario · Equipos</div>
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
                    <img
                      loading="lazy"
                      decoding="async"
                      src={fotoActual}
                      alt=""
                      className="max-h-full max-w-full object-contain"
                    />
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
                  <div className="t-eyebrow">$ / jornada</div>
                  <div className="font-display text-xl font-black text-ink tabular-nums mt-0.5">
                    <PrecioUnidad value={form.watch("precio_jornada")} />
                  </div>
                </div>
                <div className="rounded-lg border hairline bg-card px-3 py-2.5">
                  <div className="t-eyebrow">% día</div>
                  <div className="font-display text-xl font-black text-ink tabular-nums mt-0.5">
                    {kpiFmt(form.watch("roi_pct"))}%
                  </div>
                </div>
                <div className="rounded-lg border hairline bg-card px-3 py-2.5 col-span-2">
                  <div className="t-eyebrow">Valor reposición</div>
                  <div className="font-display text-xl font-black text-ink tabular-nums mt-0.5">
                    <Monto value={form.watch("valor_reposicion")} moneda="USD" />
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
