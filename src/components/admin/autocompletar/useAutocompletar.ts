import { useEffect, useState } from "react";
import { toast } from "sonner";
import { adminApi, type Equipo } from "@/lib/admin/api";
import { authedJson, authedFetch } from "@/lib/authedFetch";
import { isBucketUrl, isHostedUrl, uploadExternalUrlToBucket } from "@/lib/equipment/photos";
import { type DiagStep, type AutocompletarResult } from "./types";

export function useAutocompletar({
  equipo,
  open,
  onApplied,
  onOpenChange,
}: {
  equipo: Equipo;
  open: boolean;
  onApplied: () => void;
  onOpenChange: (v: boolean) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [loadingFoto, setLoadingFoto] = useState(false);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<AutocompletarResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [marca, setMarca] = useState("");
  const [modelo, setModelo] = useState("");
  const [fotoUrl, setFotoUrl] = useState("");
  const [uploadingFotoUrl, setUploadingFotoUrl] = useState("");
  const [bhUrl, setBhUrl] = useState("");

  const [aplicarMarca, setAplicarMarca] = useState(true);
  const [aplicarModelo, setAplicarModelo] = useState(true);
  const [aplicarFoto, setAplicarFoto] = useState(true);
  const [aplicarBh, setAplicarBh] = useState(true);
  const [aplicarDescripcion, setAplicarDescripcion] = useState(true);
  const [aplicarSpecs, setAplicarSpecs] = useState(true);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [aplicarKeywords, setAplicarKeywords] = useState(true);
  const [aplicarFichaExtendida, setAplicarFichaExtendida] = useState(true);

  const [keywordInput, setKeywordInput] = useState("");
  const [photoDiag, setPhotoDiag] = useState<DiagStep[] | null>(null);
  const [fotosResult, setFotosResult] = useState<string[]>([]);
  const [searchingPhotos, setSearchingPhotos] = useState(false);
  const [customUrl, setCustomUrl] = useState("");

  useEffect(() => {
    if (open) {
      // Pre-cargar el link del equipo si lo tiene, sino quedar en blanco.
      setCustomUrl(equipo?.bh_url ?? "");
    } else {
      setResult(null);
      setError(null);
      setPhotoDiag(null);
      setFotosResult([]);
      setFotoUrl("");
      setUploadingFotoUrl("");
      setCustomUrl("");
    }
  }, [open, equipo?.bh_url]);

  const solicitarAutocompletado = (input: {
    nombre?: string | null;
    marca?: string | null;
    modelo?: string | null;
    url?: string | null;
  }) =>
    authedJson<AutocompletarResult>("/api/admin/equipos/autocompletar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // Pasamos las categorías del equipo para que el LLM use los labels
      // canónicos del template — más relevante que la guía global.
      body: JSON.stringify({
        ...input,
        categoria_ids: (equipo?.categorias ?? []).map((c) => c.id),
      }),
    });

  /** Auto-sube la foto a R2 en segundo plano y actualiza fotoUrl cuando termina. */
  const selectFoto = async (url: string) => {
    setFotoUrl(url);
    setAplicarFoto(true);
    if (isHostedUrl(url)) return;
    setUploadingFotoUrl(url);
    try {
      const r2url = await uploadExternalUrlToBucket(equipo.id, url);
      setFotoUrl(r2url);
    } catch {
      // Mantener URL externa — se reintentará al aplicar
    } finally {
      setUploadingFotoUrl("");
    }
  };

  /** Busca solo la foto del producto a partir del link pegado. */
  const buscarFoto = async () => {
    setLoadingFoto(true);
    setError(null);
    setFotosResult([]);
    setFotoUrl("");
    setUploadingFotoUrl("");
    try {
      const r = await authedJson<{ foto_candidates: string[] }>(
        "/api/admin/equipos/buscar-fotos",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            nombre: equipo.nombre,
            marca: equipo.marca,
            modelo: equipo.modelo,
            url: customUrl.trim() || null,
          }),
        },
      );
      const cands = r.foto_candidates ?? [];
      setFotosResult(cands);
      if (cands.length > 0) {
        void selectFoto(cands[0]);
      } else {
        toast.info("No se encontró foto. Probá con otro link.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error buscando foto");
    } finally {
      setLoadingFoto(false);
    }
  };

  /** Busca specs + foto en paralelo (proceso completo). */
  const runSearch = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setFotosResult([]);
    setFotoUrl("");
    setUploadingFotoUrl("");

    const urlToUse = customUrl.trim() || null;

    try {
      const [fotosSettled, specsSettled] = await Promise.allSettled([
        authedJson<{ foto_candidates: string[] }>("/api/admin/equipos/buscar-fotos", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            nombre: equipo.nombre,
            marca: equipo.marca,
            modelo: equipo.modelo,
            url: urlToUse,
          }),
        }),
        solicitarAutocompletado({
          nombre: equipo.nombre,
          marca: equipo.marca,
          modelo: equipo.modelo,
          url: urlToUse,
        }),
      ]);

      const allCands: string[] = [];

      if (fotosSettled.status === "fulfilled") {
        allCands.push(...(fotosSettled.value.foto_candidates ?? []));
      } else {
        toast.error("Error buscando fotos: " + ((fotosSettled.reason as Error)?.message ?? "desconocido"));
      }

      if (specsSettled.status === "fulfilled") {
        const r = specsSettled.value;
        setResult(r);
        setMarca(r.marca ?? "");
        setModelo(r.modelo ?? "");
        setBhUrl(r.fuente_url);
        setAplicarMarca(!equipo.marca && !!r.marca);
        setAplicarModelo(!equipo.modelo && !!r.modelo);
        setAplicarBh(!equipo.bh_url);
        setAplicarDescripcion(!!r.descripcion);
        setAplicarSpecs(r.specs.length > 0);
        setKeywords(r.keywords ?? []);
        setAplicarKeywords((r.keywords ?? []).length > 0);
        const tieneFichaExt = !!(
          r.peso || r.dimensiones || r.montura || r.formato || r.resolucion || r.alimentacion ||
          r.video_url || typeof r.precio_bh_usd === "number" ||
          (r.incluye?.length ?? 0) > 0 || (r.conectividad?.length ?? 0) > 0 ||
          (r.compatible_con?.length ?? 0) > 0
        );
        setAplicarFichaExtendida(tieneFichaExt);
        for (const u of (r.foto_candidates ?? [])) {
          if (!allCands.includes(u)) allCands.push(u);
        }
      } else {
        toast.error("Error buscando specs: " + ((specsSettled.reason as Error)?.message ?? "desconocido"));
      }

      setFotosResult(allCands);
      if (allCands.length > 0) {
        void selectFoto(allCands[0]);
        setAplicarFoto(!equipo.foto_url);
      } else {
        setAplicarFoto(false);
      }

      if (fotosSettled.status !== "fulfilled" && specsSettled.status !== "fulfilled") {
        setError("No se pudo completar ninguna búsqueda.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  };

  const uploadPhotoWithDiag = async (equipoId: number, externalUrl: string): Promise<string> => {
    const steps: DiagStep[] = [
      { label: "Validar URL", status: "pending" },
      { label: "Descargar imagen", status: "pending" },
      { label: "Subir al almacenamiento", status: "pending" },
    ];
    const update = (i: number, patch: Partial<DiagStep>) => {
      steps[i] = { ...steps[i], ...patch };
      setPhotoDiag([...steps]);
    };
    setPhotoDiag([...steps]);

    if (isBucketUrl(externalUrl)) {
      steps.forEach((_, i) => update(i, { status: "skip", detail: "ya guardada" }));
      return externalUrl;
    }

    try {
      update(0, { status: "ok", detail: new URL(externalUrl).hostname });
    } catch {
      update(0, { status: "fail", detail: "URL inválida" });
      throw new Error("URL inválida");
    }

    update(1, { status: "pending" });
    try {
      const response = await authedFetch(
        `/api/admin/equipos/${equipoId}/upload-foto-from-url`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: externalUrl, bypass_whitelist: true }),
        },
      );
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail?.detail ?? `upload → ${response.status}`);
      }
      const res = await response.json() as {
        public_url: string;
        path: string | null;
        size?: number;
        content_type?: string;
        skipped?: boolean;
      };
      update(1, { status: "ok", detail: res.size ? `${(res.size / 1024).toFixed(0)} KB` : "ok" });
      update(2, {
        status: res.skipped ? "skip" : "ok",
        detail: res.skipped ? "ya guardada" : (res.path ?? "ok"),
      });
      return res.public_url;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "error";
      if (steps[1].status !== "ok") update(1, { status: "fail", detail: msg });
      else update(2, { status: "fail", detail: msg });
      throw e;
    }
  };

  const aplicarSoloFoto = async () => {
    if (!fotoUrl) {
      toast.info("Elegí una foto primero.");
      return;
    }
    setSaving(true);
    try {
      const finalUrl = await uploadPhotoWithDiag(equipo.id, fotoUrl);
      await adminApi.updateEquipo(equipo.id, { foto_url: finalUrl });
      toast.success("Foto aplicada al equipo ✨");
      onApplied();
      onOpenChange(false);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error al aplicar foto");
    } finally {
      setSaving(false);
    }
  };

  const buscarMasFotos = async () => {
    setSearchingPhotos(true);
    try {
      const known = [...fotosResult, ...(fotoUrl && !fotosResult.includes(fotoUrl) ? [fotoUrl] : [])];
      const r = await authedJson<{ foto_candidates: string[] }>("/api/admin/equipos/buscar-fotos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre: equipo.nombre, marca: equipo.marca, modelo: equipo.modelo, exclude: known }),
      });
      const news = (r.foto_candidates ?? []).filter((u) => !known.includes(u));
      setFotosResult((prev) => [...prev, ...news]);
      if (news.length === 0) {
        toast.info("No se encontraron fotos nuevas.");
      } else {
        toast.success(`${news.length} fotos nuevas encontradas`);
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error buscando fotos");
    } finally {
      setSearchingPhotos(false);
    }
  };

  const addKeyword = () => {
    const v = keywordInput.trim().toLowerCase();
    if (!v) return;
    if (keywords.includes(v)) { setKeywordInput(""); return; }
    setKeywords([...keywords, v]);
    setKeywordInput("");
  };

  const removeKeyword = (k: string) => setKeywords(keywords.filter((x) => x !== k));

  const setAll = (v: boolean) => {
    setAplicarMarca(v); setAplicarModelo(v); setAplicarFoto(v); setAplicarBh(v);
    setAplicarDescripcion(v); setAplicarSpecs(v); setAplicarKeywords(v);
    setAplicarFichaExtendida(v);
  };

  const fichaExtendidaTieneDatos = !!result && (
    !!result.peso || !!result.dimensiones || !!result.montura || !!result.formato ||
    !!result.resolucion || !!result.alimentacion || !!result.video_url ||
    typeof result.precio_bh_usd === "number" ||
    (result.incluye?.length ?? 0) > 0 ||
    (result.conectividad?.length ?? 0) > 0 ||
    (result.compatible_con?.length ?? 0) > 0
  );

  const aplicar = async () => {
    if (!result) return;
    const aplicados: string[] = [];
    const fallidos: string[] = [];

    const body: Record<string, unknown> = {};

    if (aplicarMarca && marca) body.marca = marca;
    if (aplicarModelo && modelo) body.modelo = modelo;
    if (aplicarBh && bhUrl) body.bh_url = bhUrl;
    if (aplicarDescripcion && result.descripcion) body.descripcion = result.descripcion;
    if (aplicarSpecs && result.specs.length > 0) body.specs = result.specs;
    if (aplicarKeywords && keywords.length > 0) body.keywords = keywords;

    if (aplicarFichaExtendida && fichaExtendidaTieneDatos) {
      if (result.peso) body.peso = result.peso;
      if (result.dimensiones) body.dimensiones = result.dimensiones;
      if (result.montura) body.montura = result.montura;
      if (result.formato) body.formato = result.formato;
      if (result.resolucion) body.resolucion = result.resolucion;
      if (result.alimentacion) body.alimentacion = result.alimentacion;
      if (result.video_url) body.video_url = result.video_url;
      if (typeof result.precio_bh_usd === "number") body.precio_bh_usd = result.precio_bh_usd;
      if ((result.incluye?.length ?? 0) > 0) body.incluye = result.incluye;
      if ((result.conectividad?.length ?? 0) > 0) body.conectividad = result.conectividad;
      if ((result.compatible_con?.length ?? 0) > 0) body.compatible_con = result.compatible_con;
    }

    if (Object.keys(body).length > 0) {
      body.fuente_url = result.fuente_url;
      body.fuente_titulo = result.fuente_titulo;
      if (result.enriquecido_fuente) body.enriquecido_fuente = result.enriquecido_fuente;
      if (result.raw) body.raw = result.raw;
    }

    const willApplyFoto = aplicarFoto && !!fotoUrl;

    if (Object.keys(body).length === 0 && !willApplyFoto) {
      toast.info("No hay cambios para aplicar.");
      return;
    }

    setSaving(true);
    try {
      if (willApplyFoto) {
        try {
          const finalUrl = await uploadPhotoWithDiag(equipo.id, fotoUrl);
          body.foto_url = finalUrl;
        } catch (e) {
          fallidos.push(`foto (${e instanceof Error ? e.message : "error"})`);
        }
      }

      if (Object.keys(body).length > 0) {
        try {
          const resp = await adminApi.aplicarEnriquecimiento(equipo.id, body);
          if (body.marca) aplicados.push(`marca: ${body.marca as string}`);
          if (body.modelo) aplicados.push(`modelo: ${body.modelo as string}`);
          if (body.foto_url) aplicados.push("foto");
          if (body.bh_url) aplicados.push("link fuente");
          if (body.descripcion) aplicados.push("descripción");
          if (body.specs) {
            // Si el backend nos dio matching estructurado, reportarlo con detalle.
            const m = resp.specs_matching;
            if (m) {
              aplicados.push(`${m.aplicadas} specs cargadas`);
              if (m.propuestas_creadas > 0) {
                aplicados.push(`${m.propuestas_creadas} sugerencias en Gear Compatibility`);
              }
            } else {
              aplicados.push(`${(body.specs as unknown[]).length} specs`);
            }
          }
          if (body.keywords) aplicados.push(`${(body.keywords as string[]).length} keywords`);
          if (aplicarFichaExtendida && fichaExtendidaTieneDatos) aplicados.push("ficha técnica");
        } catch (e) {
          fallidos.push(e instanceof Error ? e.message : "error al guardar");
        }
      }

      if (aplicados.length === 0 && fallidos.length > 0) {
        toast.error(`No se pudo guardar: ${fallidos.join(" · ")}`);
      } else if (fallidos.length > 0) {
        toast.warning("Guardado parcial", {
          description: `OK: ${aplicados.join(" · ")}. Falló: ${fallidos.join(" · ")}`,
          duration: 7000,
        });
      } else {
        toast.success("Equipo actualizado ✨", {
          description: aplicados.join(" · "),
          duration: 5000,
        });
      }

      onApplied();
      if (fallidos.length === 0) onOpenChange(false);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error al guardar");
    } finally {
      setSaving(false);
    }
  };

  return {
    loading, loadingFoto, saving, result, error,
    marca, setMarca,
    modelo, setModelo,
    fotoUrl, setFotoUrl,
    uploadingFotoUrl, selectFoto,
    bhUrl, setBhUrl,
    aplicarMarca, setAplicarMarca,
    aplicarModelo, setAplicarModelo,
    aplicarFoto, setAplicarFoto,
    aplicarBh, setAplicarBh,
    aplicarDescripcion, setAplicarDescripcion,
    aplicarSpecs, setAplicarSpecs,
    keywords, keywordInput, setKeywordInput,
    aplicarKeywords, setAplicarKeywords,
    aplicarFichaExtendida, setAplicarFichaExtendida,
    photoDiag,
    fotosResult,
    searchingPhotos,
    customUrl, setCustomUrl,
    fichaExtendidaTieneDatos,
    buscarFoto, runSearch, aplicarSoloFoto, buscarMasFotos, addKeyword, removeKeyword, setAll, aplicar,
  };
}
