import { useEffect, useState } from "react";
import { Sparkles, ExternalLink, Loader2, Check, X, Plus, Bug, Image as ImageIcon, FileText, Link as LinkIcon } from "lucide-react";
import { toast } from "sonner";

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";

import { adminApi, type Equipo } from "@/lib/admin/api";
import { authedJson, authedFetch } from "@/lib/authedFetch";
import { isBucketUrl } from "@/lib/equipment/photos";

type DiagStep = { label: string; status: "pending" | "ok" | "fail" | "skip"; detail?: string };

export type EnriquecerResult = {
  marca: string | null;
  modelo: string | null;
  nombre_normalizado: string;
  descripcion: string;
  specs: { label: string; value: string }[];
  keywords: string[];
  foto_url: string | null;
  /** Todas las URLs de foto que pasaron la validación. La primera es la elegida por defecto. */
  foto_candidates?: string[];
  // Ficha extendida (cualquiera puede ser null si no se encontró)
  peso?: string | null;
  dimensiones?: string | null;
  montura?: string | null;
  formato?: string | null;
  resolucion?: string | null;
  alimentacion?: string | null;
  incluye?: string[];
  conectividad?: string[];
  compatible_con?: string[];
  video_url?: string | null;
  precio_bh_usd?: number | null;
  categoria_sugerida?: string | null;
  // Trazabilidad
  fuente_url: string;
  fuente_titulo: string;
  fuente_foto_url?: string | null;
  foto_motivo?: string | null;
  enriquecido_fuente?: string | null;
  raw?: Record<string, unknown>;
};

export function EnriquecerEquipoDialog({
  equipo,
  open,
  onOpenChange,
  onApplied,
}: {
  equipo: Equipo;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onApplied: () => void;
}) {
  const enriquecer = (input: { nombre?: string | null; marca?: string | null; modelo?: string | null; url?: string | null }) =>
    authedJson<EnriquecerResult>("/api/admin/equipos/enriquecer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<EnriquecerResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Campos editables del preview
  const [marca, setMarca] = useState("");
  const [modelo, setModelo] = useState("");
  const [fotoUrl, setFotoUrl] = useState("");
  const [bhUrl, setBhUrl] = useState("");

  // Toggles "aplicar"
  const [aplicarMarca, setAplicarMarca] = useState(true);
  const [aplicarModelo, setAplicarModelo] = useState(true);
  const [aplicarFoto, setAplicarFoto] = useState(true);
  const [aplicarBh, setAplicarBh] = useState(true);
  const [aplicarDescripcion, setAplicarDescripcion] = useState(true);
  const [aplicarSpecs, setAplicarSpecs] = useState(true);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [aplicarKeywords, setAplicarKeywords] = useState(true);
  // Ficha extendida (un solo toggle para todo el bloque)
  const [aplicarFichaExtendida, setAplicarFichaExtendida] = useState(true);

  const [keywordInput, setKeywordInput] = useState("");
  const [photoDiag, setPhotoDiag] = useState<DiagStep[] | null>(null);
  // Candidatos extra obtenidos por la búsqueda dedicada de fotos
  const [extraCands, setExtraCands] = useState<string[]>([]);
  const [searchingPhotos, setSearchingPhotos] = useState(false);
  // Modo: "info" = enriquecimiento completo (B&H + IA). "photos" = solo buscar fotos.
  const [mode, setMode] = useState<"info" | "photos" | null>(null);
  // URL manual opcional que guía la búsqueda (ej. página de B&H, sitio oficial)
  const [customUrl, setCustomUrl] = useState("");

  useEffect(() => {
    if (!open) {
      setResult(null);
      setError(null);
      setPhotoDiag(null);
      setExtraCands([]);
      setMode(null);
      setFotoUrl("");
      setCustomUrl("");
    }
  }, [open]);

  /** Modo "solo fotos": no llama a /enriquecer, solo a /buscar-fotos. */
  const buscarSoloFotos = async () => {
    setMode("photos");
    setLoading(true);
    setError(null);
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
          }),
        },
      );
      const cands = r.foto_candidates ?? [];
      setExtraCands(cands);
      if (cands.length === 0) {
        toast.info("No se encontraron fotos.");
      } else {
        // Pre-seleccionar la primera
        setFotoUrl(cands[0]);
        setAplicarFoto(true);
        toast.success(`${cands.length} fotos encontradas`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error buscando fotos");
    } finally {
      setLoading(false);
    }
  };

  /** Aplicar solo la foto seleccionada (modo "photos"). */
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
      const known = [
        ...(result?.foto_candidates ?? []),
        ...(fotoUrl ? [fotoUrl] : []),
        ...extraCands,
      ];
      const r = await authedJson<{ foto_candidates: string[] }>(
        "/api/admin/equipos/buscar-fotos",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            nombre: equipo.nombre,
            marca:  equipo.marca,
            modelo: equipo.modelo,
            exclude: known,
          }),
        },
      );
      const news = (r.foto_candidates ?? []).filter((u) => !known.includes(u));
      setExtraCands((prev) => [...prev, ...news]);
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
          body: JSON.stringify({ url: externalUrl }),
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

      update(1, {
        status: "ok",
        detail: res.size ? `${(res.size / 1024).toFixed(0)} KB` : "ok",
      });
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

  const run = async () => {
    setMode("info");
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await enriquecer({
        nombre: equipo.nombre,
        marca: equipo.marca,
        modelo: equipo.modelo,
        url: customUrl.trim() || null,
      });
      setResult(r);
      setMarca(r.marca ?? "");
      setModelo(r.modelo ?? "");
      setFotoUrl(r.foto_url ?? "");
      setBhUrl(r.fuente_url);
      setAplicarMarca(!equipo.marca && !!r.marca);
      setAplicarModelo(!equipo.modelo && !!r.modelo);
      setAplicarFoto(!equipo.foto_url && !!r.foto_url);
      setAplicarBh(!equipo.bh_url);
      setAplicarDescripcion(!!r.descripcion);
      setAplicarSpecs(r.specs.length > 0);
      setKeywords(r.keywords ?? []);
      setAplicarKeywords((r.keywords ?? []).length > 0);
      const tieneFichaExt = !!(
        r.peso || r.dimensiones || r.montura || r.formato ||
        r.resolucion || r.alimentacion || r.video_url ||
        typeof r.precio_bh_usd === "number" ||
        (r.incluye?.length ?? 0) > 0 ||
        (r.conectividad?.length ?? 0) > 0 ||
        (r.compatible_con?.length ?? 0) > 0
      );
      setAplicarFichaExtendida(tieneFichaExt);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  };

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

    // Construimos el body para el endpoint único.
    // Sólo incluimos lo que el usuario decidió aplicar — los campos no enviados
    // quedan como están en la DB (no se nullean).
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

    // Trazabilidad: siempre que se aplique algo, guardamos fuente y raw.
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
      // 1) Foto: si es externa, descargar via proxy y subir al bucket
      if (willApplyFoto) {
        try {
          const finalUrl = await uploadPhotoWithDiag(equipo.id, fotoUrl);
          body.foto_url = finalUrl;
        } catch (e) {
          fallidos.push(`foto (${e instanceof Error ? e.message : "error"})`);
        }
      }

      // 2) Single-call: graba equipo (marca/modelo/foto/bh_url) + ficha completa
      if (Object.keys(body).length > 0) {
        try {
          await adminApi.aplicarEnriquecimiento(equipo.id, body);
          if (body.marca) aplicados.push(`marca: ${body.marca as string}`);
          if (body.modelo) aplicados.push(`modelo: ${body.modelo as string}`);
          if (body.foto_url) aplicados.push("foto");
          if (body.bh_url) aplicados.push("link fuente");
          if (body.descripcion) aplicados.push("descripción");
          if (body.specs) aplicados.push(`${(body.specs as unknown[]).length} specs`);
          if (body.keywords) aplicados.push(`${(body.keywords as string[]).length} keywords`);
          if (aplicarFichaExtendida && fichaExtendidaTieneDatos) {
            aplicados.push("ficha técnica");
          }
        } catch (e) {
          fallidos.push(e instanceof Error ? e.message : "error al guardar");
        }
      }

      if (aplicados.length === 0 && fallidos.length > 0) {
        toast.error(`No se pudo guardar: ${fallidos.join(" · ")}`);
      } else if (fallidos.length > 0) {
        toast.warning(`Guardado parcial`, {
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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-amber" />
            Enriquecer con IA
          </DialogTitle>
          <DialogDescription>
            Buscamos en B&amp;H y sitios oficiales — la IA extrae specs, foto, ficha técnica
            y datos físicos. Revisá antes de aplicar.
          </DialogDescription>
        </DialogHeader>

        <div className="rounded-md border hairline p-3 bg-muted/30 text-sm">
          <div className="font-medium">{equipo.nombre}</div>
          <div className="text-muted-foreground text-xs">
            {[equipo.marca, equipo.modelo].filter(Boolean).join(" / ") || "Sin marca/modelo"}
          </div>
        </div>

        {!result && !loading && !error && mode !== "photos" && (
          <div className="py-4 space-y-4">
            {/* Input de URL opcional */}
            <div className="space-y-1.5">
              <label className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium uppercase tracking-wide">
                <LinkIcon className="h-3.5 w-3.5" />
                Link del producto (opcional)
              </label>
              <Input
                value={customUrl}
                onChange={(e) => setCustomUrl(e.target.value)}
                placeholder="https://www.bhphotovideo.com/… o sitio oficial"
                className="font-mono text-xs h-9"
              />
              <p className="text-[11px] text-muted-foreground">
                Si pegás un link, la IA va directo ahí en vez de buscar.
              </p>
            </div>

            <p className="text-xs text-muted-foreground text-center">¿Qué querés buscar?</p>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={buscarSoloFotos}
                className="rounded-md border hairline p-4 text-left transition hover:border-amber hover:bg-amber-soft/40"
              >
                <ImageIcon className="h-5 w-5 mb-2 text-amber" />
                <div className="font-medium text-sm">Solo fotos</div>
                <div className="text-[11px] text-muted-foreground mt-1">
                  Wikipedia, sitios oficiales y reviews. Rápido (~5s).
                </div>
              </button>
              <button
                type="button"
                onClick={run}
                className="rounded-md border hairline p-4 text-left transition hover:border-amber hover:bg-amber-soft/40"
              >
                <FileText className="h-5 w-5 mb-2 text-amber" />
                <div className="font-medium text-sm">
                  {customUrl.trim() ? "Buscar desde este link" : "Info técnica"}
                </div>
                <div className="text-[11px] text-muted-foreground mt-1">
                  {customUrl.trim()
                    ? `Scrapea ${(() => { try { return new URL(customUrl.trim()).hostname; } catch { return "el link"; } })()} con IA.`
                    : "B&H + IA: specs, peso, montura, precio. ~15s."
                  }
                </div>
              </button>
            </div>
          </div>
        )}

        {loading && (
          <div className="py-12 text-center text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin mx-auto mb-3" />
            {mode === "photos"
              ? "Buscando fotos en internet…"
              : "Buscando en B&H, scrapeando y extrayendo specs…"}
            <div className="text-xs mt-1">
              {mode === "photos" ? "Suele tardar 5-10 segundos." : "Suele tardar 10-20 segundos."}
            </div>
          </div>
        )}

        {/* Modo "solo fotos": grid de candidatos + botón aplicar */}
        {mode === "photos" && !loading && !error && (
          <div className="space-y-3">
            {extraCands.length === 0 ? (
              <div className="py-6 text-center text-sm text-muted-foreground">
                Sin resultados. Probá con la búsqueda completa o cargá una URL manual.
                <div className="mt-3">
                  <Button variant="outline" size="sm" onClick={buscarSoloFotos}>
                    Reintentar
                  </Button>
                </div>
              </div>
            ) : (
              <>
                {fotoUrl && (
                  <div className="rounded-md border hairline overflow-hidden bg-muted/30">
                    <img
                      src={fotoUrl}
                      alt="Preview"
                      className="w-full max-h-64 object-contain"
                      onError={(e) => { (e.target as HTMLImageElement).style.opacity = "0.3"; }}
                    />
                  </div>
                )}
                <div>
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
                      {extraCands.length} fotos — click para elegir
                    </span>
                    <Button
                      type="button" size="sm" variant="ghost" className="h-7 text-xs"
                      onClick={buscarMasFotos} disabled={searchingPhotos}
                    >
                      {searchingPhotos ? (
                        <><Loader2 className="h-3 w-3 mr-1 animate-spin" />Buscando…</>
                      ) : (
                        <><Sparkles className="h-3 w-3 mr-1 text-amber" />Buscar más</>
                      )}
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {extraCands.map((u) => {
                      const selected = u === fotoUrl;
                      return (
                        <button
                          type="button" key={u} onClick={() => setFotoUrl(u)} title={u}
                          className={
                            "relative h-16 w-16 overflow-hidden rounded border transition " +
                            (selected
                              ? "border-amber ring-2 ring-amber/40"
                              : "border-muted hover:border-ink/30")
                          }
                        >
                          <img
                            src={u} alt=""
                            className="h-full w-full object-cover"
                            onError={(e) => { (e.target as HTMLImageElement).style.opacity = "0.2"; }}
                          />
                          {selected && (
                            <span className="absolute right-0.5 top-0.5 rounded-full bg-amber p-0.5">
                              <Check className="h-2.5 w-2.5 text-ink" />
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
                {photoDiag && (
                  <div className="rounded-md border hairline bg-muted/30 p-3 text-xs">
                    <div className="flex items-center gap-1.5 mb-2 font-mono uppercase tracking-wide text-muted-foreground">
                      <Bug className="h-3.5 w-3.5" /> Subida de foto
                    </div>
                    <ul className="space-y-1">
                      {photoDiag.map((s, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <span className="mt-0.5">
                            {s.status === "ok" && <Check className="h-3.5 w-3.5 text-emerald-600" />}
                            {s.status === "fail" && <X className="h-3.5 w-3.5 text-destructive" />}
                            {s.status === "pending" && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
                            {s.status === "skip" && <span className="block h-3.5 w-3.5 rounded-full border" />}
                          </span>
                          <div className="flex-1 min-w-0">
                            <div className={s.status === "fail" ? "text-destructive font-medium" : ""}>{s.label}</div>
                            {s.detail && (
                              <div className="text-[10px] text-muted-foreground break-all">{s.detail}</div>
                            )}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {error && (
          <div className="rounded-md border hairline border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            {error}
            <div className="mt-2">
              <Button variant="outline" size="sm" onClick={run}>Reintentar</Button>
            </div>
          </div>
        )}

        {result && (
          <div className="space-y-4">
            <div className="flex flex-col gap-1">
              <a
                href={result.fuente_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-muted-foreground hover:text-ink inline-flex items-center gap-1"
              >
                <ExternalLink className="h-3 w-3" />
                Datos: {new URL(result.fuente_url).hostname}
              </a>
              {result.fuente_foto_url && result.fuente_foto_url !== result.fuente_url && (
                <a
                  href={result.fuente_foto_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-muted-foreground hover:text-ink inline-flex items-center gap-1"
                >
                  <ExternalLink className="h-3 w-3" />
                  Foto: {new URL(result.fuente_foto_url).hostname}
                </a>
              )}
            </div>

            {/* Foto preview + selector de candidatos */}
            {fotoUrl && (
              <div className="rounded-md border hairline overflow-hidden bg-muted/30">
                <img
                  src={fotoUrl}
                  alt="Preview"
                  className="w-full max-h-64 object-contain"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.opacity = "0.3";
                  }}
                />
              </div>
            )}

            {/* Selector de fotos: candidatos del enriquecedor + extras de buscar-fotos */}
            <div>
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  Otras opciones — click para elegir
                </span>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs"
                  onClick={buscarMasFotos}
                  disabled={searchingPhotos}
                >
                  {searchingPhotos ? (
                    <><Loader2 className="h-3 w-3 mr-1 animate-spin" />Buscando…</>
                  ) : (
                    <><Sparkles className="h-3 w-3 mr-1 text-amber" />Buscar más fotos</>
                  )}
                </Button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {[...(result.foto_candidates ?? []), ...extraCands].map((u, idx) => {
                  const isExtra = idx >= (result.foto_candidates?.length ?? 0);
                  const selected = u === fotoUrl;
                  return (
                    <button
                      type="button"
                      key={u}
                      onClick={() => setFotoUrl(u)}
                      title={u}
                      className={
                        "relative h-16 w-16 overflow-hidden rounded border transition " +
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
                      {selected && (
                        <span className="absolute right-0.5 top-0.5 rounded-full bg-amber p-0.5">
                          <Check className="h-2.5 w-2.5 text-ink" />
                        </span>
                      )}
                      {isExtra && !selected && (
                        <span className="absolute left-0.5 top-0.5 rounded-full bg-ink/70 px-1 py-px text-[8px] font-mono text-amber">
                          EXTRA
                        </span>
                      )}
                    </button>
                  );
                })}
                {(result.foto_candidates?.length ?? 0) === 0 && extraCands.length === 0 && (
                  <span className="text-[11px] text-muted-foreground italic py-2">
                    Sin candidatos. Click "Buscar más fotos" para intentar otros sitios.
                  </span>
                )}
              </div>
            </div>

            {!fotoUrl && result.foto_motivo && (
              <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                <strong>Sin foto válida:</strong> {result.foto_motivo}. Pegá una URL manualmente abajo o dejá el campo vacío.
              </div>
            )}

            <div className="flex items-center justify-between gap-2 -mb-1">
              <span className="text-xs uppercase tracking-wide text-muted-foreground">Campos</span>
              <div className="flex gap-1">
                <Button type="button" size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setAll(true)}>
                  Aplicar todos
                </Button>
                <Button type="button" size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setAll(false)}>
                  Ninguno
                </Button>
              </div>
            </div>

            <div className="space-y-3">
              <FieldRow
                label="Marca"
                value={marca}
                onChange={setMarca}
                checked={aplicarMarca}
                onCheckedChange={setAplicarMarca}
                current={equipo.marca}
              />
              <FieldRow
                label="Modelo"
                value={modelo}
                onChange={setModelo}
                checked={aplicarModelo}
                onCheckedChange={setAplicarModelo}
                current={equipo.modelo}
              />
              <FieldRow
                label="URL foto"
                value={fotoUrl}
                onChange={setFotoUrl}
                checked={aplicarFoto}
                onCheckedChange={setAplicarFoto}
                current={equipo.foto_url}
                mono
              />
              <FieldRow
                label="URL fuente (bh_url)"
                value={bhUrl}
                onChange={setBhUrl}
                checked={aplicarBh}
                onCheckedChange={setAplicarBh}
                current={equipo.bh_url}
                mono
              />
            </div>

            {result.descripcion && (
              <div>
                <div className="flex items-center justify-between gap-2">
                  <Label className="text-xs uppercase tracking-wide text-muted-foreground">
                    Descripción
                  </Label>
                  <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                    <Checkbox
                      checked={aplicarDescripcion}
                      onCheckedChange={(v) => setAplicarDescripcion(!!v)}
                    />
                    Aplicar
                  </label>
                </div>
                <Textarea value={result.descripcion} readOnly rows={3} className="mt-1 text-sm" />
              </div>
            )}

            {result.specs.length > 0 && (
              <div>
                <div className="flex items-center justify-between gap-2">
                  <Label className="text-xs uppercase tracking-wide text-muted-foreground">
                    Specs ({result.specs.length})
                  </Label>
                  <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                    <Checkbox
                      checked={aplicarSpecs}
                      onCheckedChange={(v) => setAplicarSpecs(!!v)}
                    />
                    Aplicar
                  </label>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-1.5 text-xs">
                  {result.specs.map((s, i) => (
                    <div key={i} className="rounded border hairline px-2 py-1">
                      <div className="text-muted-foreground">{s.label}</div>
                      <div className="font-medium truncate">{s.value}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Keywords editables */}
            <div>
              <div className="flex items-center justify-between gap-2">
                <Label className="text-xs uppercase tracking-wide text-muted-foreground">
                  Palabras clave ({keywords.length})
                </Label>
                <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                  <Checkbox
                    checked={aplicarKeywords}
                    onCheckedChange={(v) => setAplicarKeywords(!!v)}
                  />
                  Aplicar
                </label>
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground">
                Tags editoriales (ej. <em>bicolor</em>, <em>global shutter</em>). Aparecen como chips en el catálogo.
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
                      onClick={() => removeKeyword(k)}
                      className="hover:text-destructive"
                      aria-label={`Quitar ${k}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
                {keywords.length === 0 && (
                  <span className="text-[11px] text-muted-foreground italic">Sin keywords aún.</span>
                )}
              </div>
              <div className="mt-2 flex gap-1.5">
                <Input
                  value={keywordInput}
                  onChange={(e) => setKeywordInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") { e.preventDefault(); addKeyword(); }
                  }}
                  placeholder="Agregar palabra clave…"
                  className="h-8 text-xs"
                />
                <Button type="button" size="sm" variant="outline" onClick={addKeyword} className="h-8">
                  <Plus className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>

            {/* Ficha técnica extendida (peso, dimensiones, montura, etc.) */}
            {fichaExtendidaTieneDatos && (
              <div>
                <div className="flex items-center justify-between gap-2">
                  <Label className="text-xs uppercase tracking-wide text-muted-foreground">
                    Ficha técnica extendida
                  </Label>
                  <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                    <Checkbox
                      checked={aplicarFichaExtendida}
                      onCheckedChange={(v) => setAplicarFichaExtendida(!!v)}
                    />
                    Aplicar todo el bloque
                  </label>
                </div>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Datos físicos / técnicos detectados. Se guardan en la ficha y aparecen en el catálogo.
                </p>
                <div className="mt-2 grid grid-cols-2 gap-1.5 text-xs">
                  {result.peso && <FichaCell label="Peso" value={result.peso} />}
                  {result.dimensiones && <FichaCell label="Dimensiones" value={result.dimensiones} />}
                  {result.montura && <FichaCell label="Montura" value={result.montura} />}
                  {result.formato && <FichaCell label="Formato" value={result.formato} />}
                  {result.resolucion && <FichaCell label="Resolución" value={result.resolucion} />}
                  {result.alimentacion && <FichaCell label="Alimentación" value={result.alimentacion} />}
                  {typeof result.precio_bh_usd === "number" && (
                    <FichaCell label="Precio B&H (USD)" value={`$${result.precio_bh_usd.toLocaleString("en-US")}`} />
                  )}
                  {result.video_url && (
                    <FichaCell label="Video demo" value={new URL(result.video_url).hostname} />
                  )}
                </div>
                {(result.incluye?.length ?? 0) > 0 && (
                  <FichaList label="Incluye en la caja" items={result.incluye!} />
                )}
                {(result.conectividad?.length ?? 0) > 0 && (
                  <FichaList label="Conectividad" items={result.conectividad!} />
                )}
                {(result.compatible_con?.length ?? 0) > 0 && (
                  <FichaList label="Compatible con" items={result.compatible_con!} />
                )}
              </div>
            )}

            {/* Estado de subida de foto */}
            {photoDiag && (
              <div className="rounded-md border hairline bg-muted/30 p-3 text-xs">
                <div className="flex items-center gap-1.5 mb-2 font-mono uppercase tracking-wide text-muted-foreground">
                  <Bug className="h-3.5 w-3.5" /> Subida de foto
                </div>
                <ul className="space-y-1">
                  {photoDiag.map((s, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="mt-0.5">
                        {s.status === "ok" && <Check className="h-3.5 w-3.5 text-emerald-600" />}
                        {s.status === "fail" && <X className="h-3.5 w-3.5 text-destructive" />}
                        {s.status === "pending" && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
                        {s.status === "skip" && <span className="block h-3.5 w-3.5 rounded-full border" />}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className={s.status === "fail" ? "text-destructive font-medium" : ""}>{s.label}</div>
                        {s.detail && (
                          <div className="text-[10px] text-muted-foreground break-all">{s.detail}</div>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          {mode === "photos" && extraCands.length > 0 && !loading && (
            <Button onClick={aplicarSoloFoto} disabled={saving || !fotoUrl}>
              {saving ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Guardando…</>
              ) : (
                <><Check className="h-4 w-4 mr-2" /> Aplicar foto</>
              )}
            </Button>
          )}
          {result && (
            <>
              <Button variant="outline" onClick={run} disabled={loading || saving}>
                Re-buscar
              </Button>
              <Button onClick={aplicar} disabled={saving}>
                {saving ? (
                  <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Guardando…</>
                ) : (
                  <><Check className="h-4 w-4 mr-2" /> Aplicar al equipo</>
                )}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function FieldRow({
  label,
  value,
  onChange,
  checked,
  onCheckedChange,
  current,
  mono,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  current?: string | null;
  mono?: boolean;
}) {
  // Comparar normalizando: backend a veces devuelve null/undefined, el form
  // siempre tiene string. Trim también, así "FX3" no se marca como cambiado
  // si el actual es " FX3 ". Sin esto, casi todos los campos aparecen como
  // "cambia" aunque el valor sea idéntico — confunde al review.
  const changed = ((current ?? "") as string).trim() !== (value ?? "").trim();
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2">
        <Label className="text-xs uppercase tracking-wide text-muted-foreground">
          {label}
        </Label>
        <label className="flex items-center gap-1.5 text-xs cursor-pointer">
          <Checkbox checked={checked} onCheckedChange={(v) => onCheckedChange(!!v)} />
          Aplicar
          {changed && <Badge variant="secondary" className="text-[9px] px-1 py-0">cambia</Badge>}
        </label>
      </div>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={mono ? "font-mono text-xs" : ""}
      />
      {current && current !== value && (
        <div className="text-[11px] text-muted-foreground truncate">
          Actual: {current}
        </div>
      )}
    </div>
  );
}

function FichaCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border hairline px-2 py-1">
      <div className="text-muted-foreground">{label}</div>
      <div className="font-medium truncate">{value}</div>
    </div>
  );
}

function FichaList({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="mt-2">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground mb-1">
        {label}
      </div>
      <div className="flex flex-wrap gap-1">
        {items.map((item, i) => (
          <span
            key={`${label}-${i}`}
            className="inline-flex items-center rounded-full border hairline bg-muted/40 px-2 py-0.5 text-[11px]"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}
