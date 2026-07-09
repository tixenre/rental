import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi, type CategoriaAdmin, type Equipo } from "@/lib/admin/api";
import type { ContenidoIncluidoItem } from "@/data/equipment";
import {
  type Spec,
  uniq,
  withIds,
  newSpec,
  sameLabel,
  findTemplateMatch,
  upsertTemplateSpec,
} from "./spec-helpers";

/**
 * Centraliza la hidratación de `initial` que antes vivía desparramada en
 * ~12 `useState` + 9 `useEffect` de EquipoFormDialogV2.tsx, cada uno con su
 * propio parche de "race condition" (4 comentarios casi idénticos: un efecto
 * hidrata, otro lee un booleano derivado antes de que el primer `setState`
 * sea visible en el mismo commit de React, así que cada uno re-chequea
 * `initial.campo` a mano). Mismo patrón que `usePedidoDraft.ts` (pedido) —
 * ese hook resuelve el mismo problema de fondo para el editor de pedidos.
 *
 * Frontera deliberada (issue #1263 Fase 1): lo que necesita `form.watch`/
 * `form.setValue` de react-hook-form QUEDA en el componente (sentinel de
 * stock, auto-cálculo de precio, preview de auto-gen de nombre público) —
 * acá solo vive lo que se hidrata de `initial` + queries de referencia ya
 * resueltas por el caller. Los checks defensivos `initial?.campo` de los
 * efectos que SÍ quedan en el componente no se tocan: siguen siendo la
 * pieza que corta la race, centralizar la hidratación no cambia el
 * mecanismo de batching de efectos de React que la causa.
 */
export function useEquipoFormDraft(
  initial: Equipo | null | undefined,
  open: boolean,
  refs: {
    categorias: CategoriaAdmin[] | undefined;
    specCategorias: { id: number; nombre: string }[] | undefined;
  },
) {
  // ── Estado de ficha (campos que no van en form-hook) ───────────────
  // Nota: montura/formato/resolucion ya no son inputs propios — viven como
  // specs. En load se migran a specs si los campos dedicados del backend
  // tienen valor, y en save se extraen de specs para escribir los campos
  // dedicados (que el catálogo público sigue leyendo).
  const [descripcion, setDescripcion] = useState("");
  const [notas, setNotas] = useState("");
  // B1 #635: contenido incluido (dim. 3)
  const [contenidoIncluido, setContenidoIncluido] = useState<ContenidoIncluidoItem[]>([]);
  // keywords_json ya no se edita a mano acá — se calcula solo desde las specs
  // (compute_keywords, ver services/nombre_builder.py). El form solo lo
  // carga y lo reenvía sin tocar (round-trip), para no pisarlo a null en
  // cada guardado — nunca se renderiza ni se muta desde la UI.
  const [tags, setTags] = useState<string[]>([]);

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
      // nombrePublico/nombrePublicoAuto: cargados por el efecto de abajo
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
  // de arriba porque vive en otra tabla (equipos, no equipo_fichas).
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
      // Si hay molde de categoría real, el efecto de auto-gen (en el
      // componente) pisa esto enseguida con el valor recién calculado (sin
      // flicker: corre antes de que el usuario interactúe). Si NO hay
      // molde, este valor se queda — y el próximo Guardar lo persiste como
      // override real (mismo criterio que "tipear apaga el auto-gen"),
      // autocurando el dato congelado equipo por equipo con el uso normal,
      // sin necesitar una migración aparte.
      setNombrePublico(initial?.nombre_publico?.trim() || "");
      setNombrePublicoAuto(true);
    }
  }, [initial?.id, initial?.nombre_publico_override, initial?.nombre_publico]);

  // ── HTML source ────────────────────────────────────────────────────
  const [htmlSourceUrl, setHtmlSourceUrl] = useState(initial?.html_source_url ?? null);
  useEffect(() => {
    setHtmlSourceUrl(initial?.html_source_url ?? null);
  }, [initial?.html_source_url]);

  // ── Manual override del precio/día (solo hidratación — el auto-cálculo
  //    que lee `form.watch` queda en el componente) ───────────────────
  // `precioJornadaManual` arrancaba SIEMPRE en `false`, sin sembrarse del
  // flag real `initial.precio_jornada_manual` — abrir un equipo que YA
  // tenía el precio fijado a mano disparaba igual el auto-cálculo, pisando
  // en silencio el precio manual con el de fórmula. Confirmado en vivo: el
  // label decía "(auto)" para un equipo marcado manual en la base.
  const [precioJornadaManual, setPrecioJornadaManual] = useState(false);
  useEffect(() => {
    setPrecioJornadaManual(initial?.precio_jornada_manual ?? false);
  }, [initial?.id, initial?.precio_jornada_manual]);

  // ── Categorías del catálogo ─────────────────────────────────────────
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
  const specsTouchedRef = useRef(false);
  const [categoriaSpecsRaw, setCategoriaSpecsRaw] = useState<string>("");
  useEffect(() => {
    setCategoriaSpecsRaw(initial?.categoria_specs ?? "");
    specsTouchedRef.current = false;
  }, [initial, open]);

  // Auto-default: si la categoría de specs quedó vacía (equipo viejo sin
  // backfill, o equipo nuevo recién categorizado) y el equipo está en una
  // categoría de catálogo cuyo root es una de las funcionales del registry,
  // la adoptamos. Mantiene specs como driver del nombre público sin obligar
  // al admin a elegirla a mano. El selector explícito gana (specsTouchedRef).
  useEffect(() => {
    if (specsTouchedRef.current) return;
    if (categoriaSpecsRaw) return;
    const categorias = refs.categorias;
    const specCategorias = refs.specCategorias ?? [];
    if (!categorias || selectedCats.size === 0 || specCategorias.length === 0) return;
    const funcNames = new Set(specCategorias.map((c) => c.nombre));
    const resolveRootName = (startId: number): string | null => {
      const seen = new Set<number>();
      let cur = categorias.find((x) => x.id === startId);
      while (cur) {
        if (cur.parent_id == null) return cur.nombre;
        if (seen.has(cur.id)) return null;
        seen.add(cur.id);
        cur = categorias.find((x) => x.id === cur!.parent_id);
      }
      return null;
    };
    for (const id of selectedCats) {
      const root = resolveRootName(id);
      if (root && funcNames.has(root)) {
        setCategoriaSpecsRaw(root);
        return;
      }
    }
  }, [categoriaSpecsRaw, refs.categorias, selectedCats, refs.specCategorias]);

  /** Setter público: tipear/elegir a mano marca `specsTouchedRef` para que
   *  el auto-default de arriba deje de pelear contra una elección explícita
   *  (incluida "Sin categoría de specs") — encapsulado acá, ya no hace falta
   *  que el componente conozca el ref. */
  const setCategoriaSpecs = (v: string) => {
    specsTouchedRef.current = true;
    setCategoriaSpecsRaw(v);
  };

  /** Nombre de la categoría de specs — drive de specs + nombre público. */
  const categoriaRoot = categoriaSpecsRaw || null;

  /** Id de la categoría de specs (en `categorias`), para fetchear el spec
   *  template. Resuelto contra la fuente canónica de specs (no el catálogo). */
  const categoriaRootId = useMemo(() => {
    if (!categoriaSpecsRaw) return null;
    const c = (refs.specCategorias ?? []).find((x) => x.nombre === categoriaSpecsRaw);
    return c?.id ?? null;
  }, [refs.specCategorias, categoriaSpecsRaw]);

  /** Template de nombre público de la categoría raíz (NULL si no hay). */
  const categoriaTemplate = useMemo(() => {
    if (!refs.categorias || categoriaRootId == null) return null;
    const cat = refs.categorias.find((x) => x.id === categoriaRootId);
    return cat?.nombre_publico_template ?? null;
  }, [refs.categorias, categoriaRootId]);

  /** Hay auto-gen disponible? Solo si la categoría de specs tiene molde en DB. */
  const autoGenDisponible = !!categoriaTemplate;

  // ── Specs estructuradas (equipo_specs) ────────────────────────────
  // Fuente única para el panel "Ficha técnica" del form. Devuelve:
  //  - specs: { [spec_def_id]: value } — lo que el equipo tiene cargado
  //  - template: lista de specs aplicables a las categorías del equipo
  //    (el backend hace WITH RECURSIVE para resolver ancestros, así que
  //    no hace falta calcular acá una "categoría raíz dominante").
  // Al guardar, vuelve por putEquipoSpecs (PUT al mismo endpoint).
  const [specs, setSpecs] = useState<Spec[]>([]);
  const equipoSpecsQ = useQuery({
    queryKey: ["admin", "equipo-specs", initial?.id],
    queryFn: () => adminApi.getEquipoSpecs(initial!.id),
    enabled: !!initial?.id && open,
  });
  useEffect(() => {
    if (!initial?.id) {
      setSpecs([]);
      return;
    }
    const data = equipoSpecsQ.data;
    if (!data) return;
    // Mapear { spec_def_id → value } a Spec[]. El id de cada Spec es
    // `spec-${spec_def_id}` para poder mapear de vuelta al guardar
    // (putEquipoSpecs). El label sale de `data.template` — el MISMO response
    // ya trae el template resuelto (WITH RECURSIVE por categorías del
    // equipo), así que no hace falta esperar a la query/efecto de
    // re-etiquetado de abajo (ese sigue existiendo para cuando el admin
    // cambia la categoría de specs EN VIVO dentro del form — acá cubrimos
    // el arranque). Antes sembraba con un fallback numérico ("spec 45")
    // hasta que el re-etiquetado corría; en esa ventana cualquier
    // consumidor que matchea specs por label (el preview de nombre público
    // auto-generado, ej.) no encontraba el spec y el placeholder quedaba
    // vacío — confirmado en vivo.
    const labelById = new Map(data.template.map((t) => [t.spec_def_id, t.label]));
    const next: Spec[] = [];
    for (const [defIdStr, value] of Object.entries(data.specs)) {
      const v = value == null ? "" : String(value);
      if (!v.trim()) continue;
      const label = labelById.get(Number(defIdStr)) ?? `spec ${defIdStr}`;
      next.push({ id: `spec-${defIdStr}`, label, value: v });
    }
    setSpecs(next);
    // `initial?.id` (no `initial` entero) a propósito: Aplicar/Guardar
    // invalida `["admin","equipo",id]` (route padre), que refetchea el
    // equipo y le da a `initial` una referencia NUEVA — con `initial`
    // completo en deps este efecto volvía a correr sobre el MISMO
    // `equipoSpecsQ.data` (nadie invalida `["admin","equipo-specs",id]`
    // en el save) y pisaba specs recién guardadas con la foto vieja
    // pre-edición: tipear algo en Ficha técnica + Aplicar/Guardar
    // revertía el campo a lo que tenía antes de tipear, aunque el POST
    // ya había persistido el valor nuevo (confirmado en vivo + DB). Solo
    // re-sembrar cuando cambia el EQUIPO (o entre vacío↔con-equipo), no
    // en cada refetch incidental de otros campos del mismo equipo.
  }, [equipoSpecsQ.data, initial?.id]);

  // Specs traídos del HTML upload: se guardan en una lista separada para
  // que el usuario los apruebe uno por uno (vs los specs actuales).
  const [specsPropuestos, setSpecsPropuestos] = useState<Spec[]>([]);

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

  // ════════════════════════════════════════════════════════════════════
  // HTML source — sube el archivo, persiste en R2 y extrae specs. También
  // usado por re-extract (#1203): mismo resultado, sin volver a subir el
  // archivo — comparten `aplicarSpecsExtraidos` (aplica al template o
  // manda a revisión), no hay 2 formas de procesar el mismo resultado.
  // ════════════════════════════════════════════════════════════════════
  const aplicarSpecsExtraidos = (
    specsExtraidos: { label: string; value: string; spec_key?: string }[],
    tituloSinSpecs: string,
  ) => {
    const propuestos: Spec[] = withIds(specsExtraidos ?? []);
    if (propuestos.length === 0) {
      toast.success(tituloSinSpecs, { description: "No se extrajeron specs del archivo" });
      return;
    }
    const autoAplicables = propuestos.filter((p) => !!findTemplateMatch(templateItems, p));
    const requierenRevision = propuestos.filter((p) => !findTemplateMatch(templateItems, p));

    if (autoAplicables.length > 0) {
      setSpecs((prev) => {
        let next = prev;
        for (const p of autoAplicables) {
          const tmpl = findTemplateMatch(templateItems, p)!;
          next = upsertTemplateSpec(next, tmpl, p.value, p.spec_key);
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

  const aceptarPropuesto = (s: Spec) => {
    setSpecs((prev) => {
      const tmpl = findTemplateMatch(templateItems, s);
      if (tmpl) return upsertTemplateSpec(prev, tmpl, s.value, s.spec_key);
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
  };

  const descartarPropuesto = (s: Spec) => {
    setSpecsPropuestos((prev) => prev.filter((x) => x.id !== s.id));
  };

  return {
    // ficha
    descripcion,
    setDescripcion,
    notas,
    setNotas,
    contenidoIncluido,
    setContenidoIncluido,
    tags,
    fichaQuery: fichaQ,

    // nombre público
    nombrePublico,
    setNombrePublico,
    nombrePublicoAuto,
    setNombrePublicoAuto,
    autoGenDisponible,
    categoriaRoot,
    categoriaTemplate,

    // specs
    specs,
    setSpecs,
    specsPropuestos,
    templateItems,
    equipoSpecsQuery: equipoSpecsQ,
    aplicarSpecsExtraidos,
    aceptarPropuesto,
    descartarPropuesto,

    // categoría de specs
    categoriaSpecs: categoriaSpecsRaw,
    setCategoriaSpecs,

    // categorías de catálogo
    selectedCats,
    setSelectedCats,

    // html source
    htmlSourceUrl,
    setHtmlSourceUrl,

    // precio manual (hidratación — el auto-cálculo queda en el componente)
    precioJornadaManual,
    setPrecioJornadaManual,
  };
}

export type EquipoFormDraft = ReturnType<typeof useEquipoFormDraft>;
