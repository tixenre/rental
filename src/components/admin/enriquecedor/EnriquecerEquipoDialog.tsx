import { Sparkles, ExternalLink, Loader2, Check, X, Plus, Image as ImageIcon, FileText, Link as LinkIcon, CloudUpload } from "lucide-react";

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";

import { type Equipo } from "@/lib/admin/api";
import { isHostedUrl } from "@/lib/equipment/photos";
import { useEnriquecedor } from "./useEnriquecedor";
import { PhotoGrid } from "./PhotoGrid";
import { PhotoDiag } from "./PhotoDiag";
import { FieldRow, FichaCell, FichaList } from "./FieldRow";

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
  const {
    loading, saving, result, error,
    marca, setMarca,
    modelo, setModelo,
    fotoUrl, setFotoUrl, uploadingFotoUrl, selectFoto,
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
    wantFotos, setWantFotos,
    wantSpecs, setWantSpecs,
    customUrl, setCustomUrl,
    fichaExtendidaTieneDatos,
    runSearch, aplicarSoloFoto, buscarMasFotos, addKeyword, removeKeyword, setAll, aplicar,
  } = useEnriquecedor({ equipo, open, onApplied, onOpenChange });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-full sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-amber" />
            Auto-completar info
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

        {!result && fotosResult.length === 0 && !loading && !error && (
          <div className="py-4 space-y-4">
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

            <p className="text-xs text-muted-foreground">¿Qué querés buscar?</p>
            <div className="grid grid-cols-2 gap-3">
              <label className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition ${wantFotos ? "border-amber bg-amber/10" : "border-border hover:border-ink/40"}`}>
                <Checkbox checked={wantFotos} onCheckedChange={(v) => setWantFotos(v === true)} className="mt-0.5" />
                <div className="flex-1 min-w-0">
                  <ImageIcon className="h-4 w-4 mb-1 text-amber" />
                  <div className="font-medium text-sm">Fotos</div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">
                    B&H, sitios oficiales. ~5s.
                  </div>
                </div>
              </label>
              <label className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition ${wantSpecs ? "border-amber bg-amber/10" : "border-border hover:border-ink/40"}`}>
                <Checkbox checked={wantSpecs} onCheckedChange={(v) => setWantSpecs(v === true)} className="mt-0.5" />
                <div className="flex-1 min-w-0">
                  <FileText className="h-4 w-4 mb-1 text-amber" />
                  <div className="font-medium text-sm">Specs</div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">
                    B&H + IA: ficha técnica. ~15s.
                  </div>
                </div>
              </label>
            </div>
            <Button
              onClick={runSearch}
              disabled={!wantFotos && !wantSpecs}
              className="w-full"
            >
              <Sparkles className="h-4 w-4 mr-2" />
              {customUrl.trim() ? "Buscar desde este link" : "Buscar"}
            </Button>
          </div>
        )}

        {loading && (
          <div className="py-12 text-center text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin mx-auto mb-3" />
            {wantFotos && !wantSpecs
              ? "Buscando fotos en internet…"
              : wantSpecs && !wantFotos
              ? "Buscando en B&H, scrapeando y extrayendo specs…"
              : "Buscando fotos y specs en paralelo…"}
            <div className="text-xs mt-1">
              {wantSpecs ? "Suele tardar 10-20 segundos." : "Suele tardar 5-10 segundos."}
            </div>
          </div>
        )}

        {fotosResult.length > 0 && !result && !loading && !error && (
          <div className="space-y-3">
            {fotoUrl && (
              <div className="rounded-md border hairline overflow-hidden bg-white relative">
                <img
                  src={fotoUrl}
                  alt="Preview"
                  className="w-full max-h-64 object-contain"
                  onError={(e) => { (e.target as HTMLImageElement).style.opacity = "0.3"; }}
                />
                <div className="absolute top-2 right-2">
                  {uploadingFotoUrl ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-background/90 border hairline px-2 py-0.5 text-[11px] text-muted-foreground">
                      <Loader2 className="h-3 w-3 animate-spin" /> Subiendo a R2…
                    </span>
                  ) : isHostedUrl(fotoUrl) ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[11px] text-emerald-700 font-medium">
                      <CloudUpload className="h-3 w-3" /> En R2
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-[11px] text-amber-700">
                      URL externa
                    </span>
                  )}
                </div>
              </div>
            )}
            <PhotoGrid
              candidates={fotosResult}
              selected={fotoUrl}
              onSelect={selectFoto}
              onBuscarMas={buscarMasFotos}
              searching={searchingPhotos}
              loadingUrl={uploadingFotoUrl}
            />
            {photoDiag && <PhotoDiag steps={photoDiag} />}
          </div>
        )}

        {error && (
          <div className="rounded-md border hairline border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            {error}
            <div className="mt-2">
              <Button variant="outline" size="sm" onClick={runSearch}>Reintentar</Button>
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

            {fotoUrl && (
              <div className="rounded-md border hairline overflow-hidden bg-muted/30 relative">
                <img
                  src={fotoUrl}
                  alt="Preview"
                  className="w-full max-h-64 object-contain"
                  onError={(e) => { (e.target as HTMLImageElement).style.opacity = "0.3"; }}
                />
                <div className="absolute top-2 right-2">
                  {uploadingFotoUrl ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-background/90 border hairline px-2 py-0.5 text-[11px] text-muted-foreground">
                      <Loader2 className="h-3 w-3 animate-spin" /> Subiendo a R2…
                    </span>
                  ) : isHostedUrl(fotoUrl) ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[11px] text-emerald-700 font-medium">
                      <CloudUpload className="h-3 w-3" /> En R2
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-[11px] text-amber-700">
                      URL externa
                    </span>
                  )}
                </div>
              </div>
            )}

            <PhotoGrid
              candidates={fotosResult}
              selected={fotoUrl}
              onSelect={selectFoto}
              onBuscarMas={buscarMasFotos}
              searching={searchingPhotos}
              loadingUrl={uploadingFotoUrl}
            />

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
              <FieldRow label="Marca" value={marca} onChange={setMarca} checked={aplicarMarca} onCheckedChange={setAplicarMarca} current={equipo.marca} />
              <FieldRow label="Modelo" value={modelo} onChange={setModelo} checked={aplicarModelo} onCheckedChange={setAplicarModelo} current={equipo.modelo} />
              <FieldRow label="URL foto" value={fotoUrl} onChange={setFotoUrl} checked={aplicarFoto} onCheckedChange={setAplicarFoto} current={equipo.foto_url} mono />
              <FieldRow label="URL fuente (bh_url)" value={bhUrl} onChange={setBhUrl} checked={aplicarBh} onCheckedChange={setAplicarBh} current={equipo.bh_url} mono />
            </div>

            {result.descripcion && (
              <div>
                <div className="flex items-center justify-between gap-2">
                  <Label className="text-xs uppercase tracking-wide text-muted-foreground">Descripción</Label>
                  <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                    <Checkbox checked={aplicarDescripcion} onCheckedChange={(v) => setAplicarDescripcion(!!v)} />
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
                    <Checkbox checked={aplicarSpecs} onCheckedChange={(v) => setAplicarSpecs(!!v)} />
                    Aplicar
                  </label>
                </div>
                <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-xs">
                  {result.specs.map((s, i) => (
                    <div key={i} className="rounded border hairline px-2 py-1">
                      <div className="text-muted-foreground">{s.label}</div>
                      <div className="font-medium truncate">{s.value}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div>
              <div className="flex items-center justify-between gap-2">
                <Label className="text-xs uppercase tracking-wide text-muted-foreground">
                  Palabras clave ({keywords.length})
                </Label>
                <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                  <Checkbox checked={aplicarKeywords} onCheckedChange={(v) => setAplicarKeywords(!!v)} />
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
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addKeyword(); } }}
                  placeholder="Agregar palabra clave…"
                  className="h-8 text-xs"
                />
                <Button type="button" size="sm" variant="outline" onClick={addKeyword} className="h-8">
                  <Plus className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>

            {fichaExtendidaTieneDatos && (
              <div>
                <div className="flex items-center justify-between gap-2">
                  <Label className="text-xs uppercase tracking-wide text-muted-foreground">
                    Ficha técnica extendida
                  </Label>
                  <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                    <Checkbox checked={aplicarFichaExtendida} onCheckedChange={(v) => setAplicarFichaExtendida(!!v)} />
                    Aplicar todo el bloque
                  </label>
                </div>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Datos físicos / técnicos detectados. Se guardan en la ficha y aparecen en el catálogo.
                </p>
                <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-xs">
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

            {photoDiag && <PhotoDiag steps={photoDiag} />}
          </div>
        )}

        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          {fotosResult.length > 0 && !result && !loading && (
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
              <Button variant="outline" onClick={runSearch} disabled={loading || saving}>
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
