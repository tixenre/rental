import { useEffect, useState } from "react";
import { Sparkles, ExternalLink, Loader2, Check, X, Plus, Bug } from "lucide-react";
import { toast } from "sonner";

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";

import { adminApi, type Equipo } from "@/lib/admin/api";
import { authedFetch, authedJson } from "@/lib/authedFetch";
import { supabase } from "@/integrations/supabase/client";
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
  fuente_url: string;
  fuente_titulo: string;
  fuente_foto_url?: string | null;
  foto_motivo?: string | null;
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
  const enriquecer = (input: { nombre: string; marca?: string | null; modelo?: string | null }) =>
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

  const [keywordInput, setKeywordInput] = useState("");
  const [photoDiag, setPhotoDiag] = useState<DiagStep[] | null>(null);

  useEffect(() => {
    if (!open) {
      setResult(null);
      setError(null);
      setPhotoDiag(null);
    }
  }, [open]);

  const addKeyword = () => {
    const v = keywordInput.trim().toLowerCase();
    if (!v) return;
    if (keywords.includes(v)) { setKeywordInput(""); return; }
    setKeywords([...keywords, v]);
    setKeywordInput("");
  };
  const removeKeyword = (k: string) => setKeywords(keywords.filter((x) => x !== k));

  /** Sube la foto externa al bucket reportando cada paso al panel de diagnóstico. */
  const uploadPhotoWithDiag = async (equipoId: number, externalUrl: string): Promise<string> => {
    const steps: DiagStep[] = [
      { label: "1. Llamar /api/admin/proxy-image", status: "pending" },
      { label: "2. Recibir blob (tamaño + tipo)", status: "pending" },
      { label: "3. Subir a Supabase Storage (equipos-fotos)", status: "pending" },
      { label: "4. Obtener URL pública", status: "pending" },
    ];
    const update = (i: number, patch: Partial<DiagStep>) => {
      steps[i] = { ...steps[i], ...patch };
      setPhotoDiag([...steps]);
    };
    setPhotoDiag([...steps]);

    if (isBucketUrl(externalUrl)) {
      steps.forEach((_, i) => update(i, { status: "skip", detail: "ya es URL del bucket" }));
      return externalUrl;
    }

    const res = await authedFetch(`/api/admin/proxy-image?url=${encodeURIComponent(externalUrl)}`);
    if (!res.ok) {
      const txt = await res.text().catch(() => "");
      update(0, { status: "fail", detail: `HTTP ${res.status} ${txt.slice(0, 120)}` });
      throw new Error(`proxy-image → ${res.status}`);
    }
    update(0, { status: "ok", detail: `HTTP ${res.status}` });

    const blob = await res.blob();
    if (blob.size === 0) {
      update(1, { status: "fail", detail: "blob vacío (0 bytes)" });
      throw new Error("blob vacío");
    }
    update(1, { status: "ok", detail: `${(blob.size / 1024).toFixed(1)} KB · ${blob.type || "sin content-type"}` });

    const ct = blob.type || "image/jpeg";
    const ext = ct.includes("png") ? "png" : ct.includes("webp") ? "webp" : ct.includes("avif") ? "avif" : "jpg";
    const path = `equipos/${equipoId}/foto-${Date.now()}.${ext}`;

    // Verificar sesión Supabase antes de subir (RLS necesita rol authenticated)
    const { data: sess } = await supabase.auth.getSession();
    if (!sess?.session?.user?.id) {
      update(2, { status: "fail", detail: "Sin sesión Supabase (rol anon). Cerrá sesión y volvé a entrar." });
      throw new Error("Sin sesión Supabase");
    }

    const { error: upErr } = await supabase.storage
      .from("equipos-fotos")
      .upload(path, blob, { contentType: ct, upsert: false });
    if (upErr) {
      const userEmail = sess.session.user.email ?? "(sin email)";
      update(2, { status: "fail", detail: `${upErr.message} · user=${userEmail}` });
      throw upErr;
    }
    update(2, { status: "ok", detail: path });

    const { data } = supabase.storage.from("equipos-fotos").getPublicUrl(path);
    if (!data?.publicUrl) {
      update(3, { status: "fail", detail: "no devolvió publicUrl" });
      throw new Error("sin publicUrl");
    }
    update(3, { status: "ok", detail: data.publicUrl });
    return data.publicUrl;
  };

  const run = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await enriquecer({
        nombre: equipo.nombre,
        marca: equipo.marca,
        modelo: equipo.modelo,
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
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  };

  const setAll = (v: boolean) => {
    setAplicarMarca(v); setAplicarModelo(v); setAplicarFoto(v); setAplicarBh(v);
    setAplicarDescripcion(v); setAplicarSpecs(v); setAplicarKeywords(v);
  };

  const aplicar = async () => {
    if (!result) return;
    const patch: Record<string, unknown> = {};
    const aplicados: string[] = [];
    const fallidos: string[] = [];

    if (aplicarMarca && marca) { patch.marca = marca; }
    if (aplicarModelo && modelo) { patch.modelo = modelo; }
    if (aplicarBh && bhUrl) { patch.bh_url = bhUrl; }

    // Ficha (descripción + specs + keywords) — se persiste aparte
    const fichaPatch: { descripcion?: string | null; specs_json?: string | null; keywords_json?: string | null } = {};
    if (aplicarDescripcion && result.descripcion) {
      fichaPatch.descripcion = result.descripcion;
    }
    if (aplicarSpecs && result.specs.length > 0) {
      fichaPatch.specs_json = JSON.stringify(result.specs);
    }
    if (aplicarKeywords && keywords.length > 0) {
      fichaPatch.keywords_json = JSON.stringify(keywords);
    }

    const willApplyFoto = aplicarFoto && !!fotoUrl;

    if (
      Object.keys(patch).length === 0 &&
      Object.keys(fichaPatch).length === 0 &&
      !willApplyFoto
    ) {
      toast.info("No hay cambios para aplicar.");
      return;
    }

    setSaving(true);
    try {
      // 1) Foto: si es externa, descargar via proxy y subir al bucket (con diagnóstico)
      if (willApplyFoto) {
        try {
          const finalUrl = await uploadPhotoWithDiag(equipo.id, fotoUrl);
          patch.foto_url = finalUrl;
        } catch (e) {
          fallidos.push(`foto (${e instanceof Error ? e.message : "error"})`);
        }
      }

      // 2) Datos básicos del equipo
      if (Object.keys(patch).length > 0) {
        try {
          await adminApi.updateEquipo(equipo.id, patch as Partial<Equipo>);
          if (patch.marca) aplicados.push(`marca: ${patch.marca}`);
          if (patch.modelo) aplicados.push(`modelo: ${patch.modelo}`);
          if (patch.bh_url) aplicados.push("link fuente");
          if (patch.foto_url) aplicados.push("foto");
        } catch (e) {
          fallidos.push(`datos básicos (${e instanceof Error ? e.message : "error"})`);
        }
      }

      // 3) Ficha (descripción / specs)
      if (Object.keys(fichaPatch).length > 0) {
        try {
          await adminApi.setFicha(equipo.id, fichaPatch);
          if (fichaPatch.descripcion) aplicados.push("descripción");
          if (fichaPatch.specs_json) aplicados.push(`${result.specs.length} specs`);
          if (fichaPatch.keywords_json) aplicados.push(`${keywords.length} keywords`);
        } catch (e) {
          fallidos.push(`ficha (${e instanceof Error ? e.message : "error"})`);
        }
      }

      // 4) Verificar que la ficha quedó persistida releyéndola
      let verificada = true;
      if (Object.keys(fichaPatch).length > 0) {
        try {
          const f = await adminApi.getFicha(equipo.id);
          const okDesc = !fichaPatch.descripcion || (f.descripcion ?? "").length > 0;
          const okSpecs = !fichaPatch.specs_json || !!f.specs_json;
          verificada = okDesc && okSpecs;
        } catch {
          verificada = false;
        }
      }

      if (aplicados.length === 0 && fallidos.length > 0) {
        toast.error(`No se pudo guardar: ${fallidos.join(" · ")}`);
      } else if (fallidos.length > 0) {
        toast.warning(`Guardado parcial`, {
          description: `OK: ${aplicados.join(" · ")}. Falló: ${fallidos.join(" · ")}`,
          duration: 7000,
        });
      } else if (!verificada) {
        toast.warning("Guardado pero la ficha no se ve al releer. Refrescá y revisá.", {
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
            Buscamos en B&amp;H / Adorama y la IA extrae specs, foto y descripción.
            Revisá el resultado antes de aplicar.
          </DialogDescription>
        </DialogHeader>

        <div className="rounded-md border hairline p-3 bg-muted/30 text-sm">
          <div className="font-medium">{equipo.nombre}</div>
          <div className="text-muted-foreground text-xs">
            {[equipo.marca, equipo.modelo].filter(Boolean).join(" / ") || "Sin marca/modelo"}
          </div>
        </div>

        {!result && !loading && !error && (
          <div className="py-6 text-center">
            <Button onClick={run} size="lg">
              <Sparkles className="h-4 w-4 mr-2" />
              Buscar en internet
            </Button>
          </div>
        )}

        {loading && (
          <div className="py-12 text-center text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin mx-auto mb-3" />
            Buscando en B&amp;H, scrapeando y extrayendo specs…
            <div className="text-xs mt-1">Suele tardar 10-20 segundos.</div>
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

            {/* Foto preview */}
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

            {/* Diagnóstico de foto */}
            {photoDiag && (
              <div className="rounded-md border hairline bg-muted/30 p-3 text-xs">
                <div className="flex items-center gap-1.5 mb-2 font-mono uppercase tracking-wide text-muted-foreground">
                  <Bug className="h-3.5 w-3.5" /> Diagnóstico de foto
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
  const changed = (current ?? "") !== value;
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
