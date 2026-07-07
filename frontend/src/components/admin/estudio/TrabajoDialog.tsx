import { useEffect, useRef, useState } from "react";
import { Film, Image, Plus, Trash2, Upload, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { IconButton } from "@/design-system/ui/icon-button";
import { Input } from "@/design-system/ui/input";
import { Textarea } from "@/design-system/ui/textarea";
import { Spinner } from "@/design-system/ui/spinner";
import { ModalBackdrop } from "@/design-system/ui/modal-backdrop";
import { cn } from "@/lib/utils";
import { trabajosAdminApi, type EstudioTrabajo, type EstudioTrabajoInput } from "@/lib/admin/api";

// Clasifica un link externo para el ícono y el payload (el backend re-detecta).
function linkTipo(url: string): "youtube" | "instagram" | null {
  if (!url) return null;
  if (/youtu/.test(url)) return "youtube";
  if (/instagram\.com/.test(url)) return "instagram";
  return null;
}

// Ícono de Instagram (lucide no trae el glifo de marca).
function IgGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor">
      <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
    </svg>
  );
}

export type TrabajoDialogMode = { mode: "create" } | { mode: "edit"; trabajo: EstudioTrabajo };

export function TrabajoDialog({
  open,
  dialogMode,
  onClose,
  onSaved,
  availableCategorias,
}: {
  open: boolean;
  dialogMode: TrabajoDialogMode;
  onClose: () => void;
  onSaved: (t: EstudioTrabajo) => void;
  availableCategorias: string[];
}) {
  const isEdit = dialogMode.mode === "edit";
  const existing = isEdit ? dialogMode.trabajo : null;

  const [titulo, setTitulo] = useState(existing?.titulo ?? "");
  const [realizador, setRealizador] = useState(existing?.realizador ?? "");
  const [instagram, setInstagram] = useState(existing?.realizador_instagram ?? "");
  const [web, setWeb] = useState(existing?.realizador_web ?? "");
  const [categorias, setCategorias] = useState<string[]>(existing?.categorias ?? []);
  const [newTag, setNewTag] = useState("");
  const [draggingOver, setDraggingOver] = useState(false);
  const [descripcion, setDescripcion] = useState(existing?.descripcion ?? "");
  const [links, setLinks] = useState<string[]>(
    existing?.links?.length ? existing.links.map((l) => l.url) : [""],
  );
  const [thumbOverrides, setThumbOverrides] = useState<string[]>(
    existing?.links?.length ? existing.links.map(() => "") : [""],
  );
  const [activo, setActivo] = useState(existing?.activo ?? true);
  const [trabajoId, setTrabajoId] = useState<number | null>(existing?.id ?? null);
  const [fotos, setFotos] = useState(existing?.fotos ?? []);
  const [logoUrl, setLogoUrl] = useState(existing?.realizador_logo_url ?? null);
  const [uploadingFoto, setUploadingFoto] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [saving, setSaving] = useState(false);
  const [fetchingMeta, setFetchingMeta] = useState(false);
  const [showExtra, setShowExtra] = useState(false);

  const fotoInputRef = useRef<HTMLInputElement>(null);
  const logoInputRef = useRef<HTMLInputElement>(null);
  const fetchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function setLinkAt(idx: number, url: string) {
    setLinks((prev) => prev.map((l, i) => (i === idx ? url : l)));
    setThumbOverrides((prev) => prev.map((t, i) => (i === idx ? "" : t)));
  }
  function addLinkRow() {
    setLinks((prev) => [...prev, ""]);
    setThumbOverrides((prev) => [...prev, ""]);
  }
  function removeLinkRow(idx: number) {
    setLinks((prev) => {
      const next = prev.filter((_, i) => i !== idx);
      return next.length ? next : [""];
    });
    setThumbOverrides((prev) => {
      const next = prev.filter((_, i) => i !== idx);
      return next.length ? next : [""];
    });
  }
  function setThumbOverrideAt(idx: number, val: string) {
    setThumbOverrides((prev) => prev.map((t, i) => (i === idx ? val : t)));
  }

  function toggleCategoria(cat: string) {
    setCategorias((prev) =>
      prev.some((c) => c.toLowerCase() === cat.toLowerCase())
        ? prev.filter((c) => c.toLowerCase() !== cat.toLowerCase())
        : [...prev, cat],
    );
  }
  function addNewTag() {
    const t = newTag.trim();
    if (t && !categorias.some((c) => c.toLowerCase() === t.toLowerCase())) {
      setCategorias((prev) => [...prev, t]);
    }
    setNewTag("");
  }

  // Auto-fetch metadata al pegar un link reconocido (prefill de titulo/realizador).
  function handleLinkChange(idx: number, url: string) {
    setLinkAt(idx, url);
    if (fetchDebounceRef.current) clearTimeout(fetchDebounceRef.current);
    if (!linkTipo(url)) return;
    fetchDebounceRef.current = setTimeout(async () => {
      setFetchingMeta(true);
      try {
        const meta = await trabajosAdminApi.fetchMeta(url);
        if (meta.titulo && !titulo) setTitulo(meta.titulo);
        if (meta.realizador && !realizador) setRealizador(meta.realizador);
        // descripcion no se auto-rellena: el og:description de IG trae el caption
        // con likes/menciones/hashtags que no son útiles como descripción del trabajo.
      } catch {
        /* best-effort */
      } finally {
        setFetchingMeta(false);
      }
    }, 700);
  }

  // Reset cuando cambia el diálogo
  useEffect(() => {
    if (!open) return;
    const t = isEdit ? existing : null;
    setTitulo(t?.titulo ?? "");
    setRealizador(t?.realizador ?? "");
    setInstagram(t?.realizador_instagram ?? "");
    setWeb(t?.realizador_web ?? "");
    setCategorias(t?.categorias ?? []);
    setNewTag("");
    setDescripcion(t?.descripcion ?? "");
    setLinks(t?.links?.length ? t.links.map((l) => l.url) : [""]);
    setThumbOverrides(t?.links?.length ? t.links.map(() => "") : [""]);
    setActivo(t?.activo ?? true);
    setTrabajoId(t?.id ?? null);
    setFotos(t?.fotos ?? []);
    setLogoUrl(t?.realizador_logo_url ?? null);
    setShowExtra(false);
  }, [open, isEdit]); // eslint-disable-line react-hooks/exhaustive-deps

  const linksPayload = links
    .map((url, i) => ({
      url: url.trim(),
      tipo: linkTipo(url.trim()),
      thumbnail_url: (thumbOverrides[i] ?? "").trim() || undefined,
    }))
    .filter((l) => l.tipo !== null);

  function buildData(): EstudioTrabajoInput {
    return {
      titulo,
      realizador,
      realizador_instagram: instagram || null,
      realizador_web: web || null,
      categorias,
      descripcion,
      links: linksPayload,
      activo,
    };
  }

  async function ensureCreated(): Promise<number> {
    if (trabajoId) return trabajoId;
    const created = await trabajosAdminApi.create(buildData());
    setTrabajoId(created.id);
    return created.id;
  }

  async function handleSave() {
    setSaving(true);
    try {
      const data = buildData();
      let result: EstudioTrabajo;
      if (trabajoId) {
        result = await trabajosAdminApi.update(trabajoId, data);
      } else {
        result = await trabajosAdminApi.create(data);
        setTrabajoId(result.id);
      }
      onSaved(result);
      toast.success(isEdit ? "Trabajo actualizado" : "Trabajo creado");
    } catch (e) {
      toast.error("Error guardando", { description: (e as Error).message });
    } finally {
      setSaving(false);
    }
  }

  async function handleFotoUpload(files: FileList) {
    if (!files.length) return;
    setUploadingFoto(true);
    try {
      const id = await ensureCreated();
      let result: EstudioTrabajo = {} as EstudioTrabajo;
      for (const f of Array.from(files)) {
        result = await trabajosAdminApi.uploadFoto(id, f);
      }
      setFotos(result.fotos ?? []);
      toast.success("Foto subida");
    } catch (e) {
      toast.error("Error subiendo foto", { description: (e as Error).message });
    } finally {
      setUploadingFoto(false);
    }
  }

  async function handleDeleteFoto(idx: number) {
    if (!trabajoId) return;
    try {
      const result = await trabajosAdminApi.deleteFoto(trabajoId, idx);
      setFotos(result.fotos ?? []);
    } catch (e) {
      toast.error("Error eliminando foto", { description: (e as Error).message });
    }
  }

  async function handleLogoUpload(file: File) {
    setUploadingLogo(true);
    try {
      const id = await ensureCreated();
      const result = await trabajosAdminApi.uploadLogo(id, file);
      setLogoUrl(result.realizador_logo_url);
      toast.success("Logo subido");
    } catch (e) {
      toast.error("Error subiendo logo", { description: (e as Error).message });
    } finally {
      setUploadingLogo(false);
    }
  }

  if (!open) return null;

  return (
    <ModalBackdrop
      className="z-50 flex items-center justify-center bg-black/60 p-4"
      onClose={onClose}
    >
      <div className="relative bg-surface rounded-2xl border hairline shadow-xl w-full max-w-lg max-h-[90dvh] overflow-y-auto">
        <div className="sticky top-0 bg-surface border-b hairline px-5 py-4 flex items-center justify-between">
          <h2 className="font-display text-lg text-ink">
            {isEdit ? "Editar trabajo" : "Nuevo trabajo"}
          </h2>
          <IconButton
            aria-label="Cerrar"
            size="sm"
            onClick={onClose}
            className="rounded-full text-muted-foreground hover:bg-muted"
          >
            <X className="h-4 w-4" />
          </IconButton>
        </div>

        <div className="p-5 space-y-5">
          {/* Links — campo primario, auto-fetch en el primero. Varios links =
              varias diapositivas del carrusel público. */}
          <div className="space-y-2">
            <label className="t-eyebrow block">Links (YouTube / Instagram)</label>
            <div className="space-y-3">
              {links.map((url, idx) => {
                const tipo = linkTipo(url);
                return (
                  <div key={idx} className="space-y-1">
                    <div className="flex items-center gap-2">
                      {tipo === "youtube" ? (
                        <Film className="h-4 w-4 shrink-0 text-muted-foreground" />
                      ) : tipo === "instagram" ? (
                        <IgGlyph className="h-4 w-4 shrink-0 text-muted-foreground" />
                      ) : (
                        <Film className="h-4 w-4 shrink-0 text-muted-foreground/30" />
                      )}
                      <Input
                        value={url}
                        onChange={(e) => handleLinkChange(idx, e.target.value)}
                        placeholder="Pegá un link de YouTube o Instagram…"
                        autoFocus={!isEdit && idx === 0}
                      />
                      {(links.length > 1 || url) && (
                        <IconButton
                          aria-label="Quitar link"
                          size="sm"
                          onClick={() => removeLinkRow(idx)}
                          className="shrink-0 rounded-full text-muted-foreground/50 hover:text-foreground hover:bg-muted"
                        >
                          <X className="h-4 w-4" />
                        </IconButton>
                      )}
                    </div>
                    {tipo && (
                      <details className="ml-6">
                        <summary className="cursor-pointer text-2xs text-muted-foreground/40 hover:text-muted-foreground/70 select-none list-none">
                          miniatura alternativa
                        </summary>
                        <Input
                          className="mt-1 text-xs"
                          value={thumbOverrides[idx] ?? ""}
                          onChange={(e) => setThumbOverrideAt(idx, e.target.value)}
                          placeholder="URL de imagen (reemplaza la miniatura auto-detectada)"
                        />
                      </details>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={addLinkRow}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                <Plus className="h-3.5 w-3.5" />
                Agregar otro link
              </button>
              {fetchingMeta && (
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Spinner size="xs" />
                  Obteniendo info…
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground/50">
              Instagram funciona con reels, fotos y carruseles. Se muestran como un carrusel.
            </p>
          </div>

          {/* Título — auto-rellenado */}
          <div className="space-y-1">
            <label className="t-eyebrow">
              Título{" "}
              <span className="normal-case tracking-normal font-sans opacity-50">(opcional)</span>
            </label>
            <Input
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
              placeholder="Auto-rellenado desde el link, o escribí uno"
            />
          </div>

          {/* Realizador — auto-rellenado */}
          <div className="space-y-1">
            <label className="t-eyebrow">
              Realizador / Productora{" "}
              <span className="normal-case tracking-normal font-sans opacity-50">(opcional)</span>
            </label>
            <Input
              value={realizador}
              onChange={(e) => setRealizador(e.target.value)}
              placeholder="Auto-rellenado desde el link, o escribí uno"
            />
          </div>

          {/* Categorías (tags) — multi-select */}
          <div className="space-y-2">
            <label className="t-eyebrow">
              Categorías{" "}
              <span className="normal-case tracking-normal font-sans opacity-50">
                (opcional — podés elegir varias)
              </span>
            </label>
            {(() => {
              const all = [...new Set([...availableCategorias, ...categorias])];
              return all.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {all.map((cat) => {
                    const on = categorias.some((c) => c.toLowerCase() === cat.toLowerCase());
                    return (
                      <button
                        key={cat}
                        type="button"
                        onClick={() => toggleCategoria(cat)}
                        className={cn(
                          "inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-mono uppercase tracking-[0.1em] border transition-colors",
                          on
                            ? "bg-ink text-background border-ink"
                            : "border-hairline text-muted-foreground hover:border-ink/50 hover:text-foreground",
                        )}
                      >
                        {cat}
                        {on && <X className="h-3 w-3" />}
                      </button>
                    );
                  })}
                </div>
              ) : null;
            })()}
            <div className="flex items-center gap-2">
              <Input
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addNewTag();
                  }
                }}
                placeholder="Agregá un tag y Enter (ej: Moda, Editorial…)"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={addNewTag}
                disabled={!newTag.trim()}
              >
                <Plus className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>

          {/* Fotos */}
          <div className="space-y-2">
            <label className="t-eyebrow">
              Fotos{" "}
              {fotos.length > 0 ? (
                `(${fotos.length})`
              ) : (
                <span className="normal-case tracking-normal font-sans opacity-50">(opcional)</span>
              )}
            </label>
            {fotos.length > 0 && (
              <div className="grid grid-cols-3 gap-2">
                {fotos.map((f, idx) => (
                  <div
                    key={idx}
                    className="relative aspect-square rounded-lg overflow-hidden border hairline group"
                  >
                    <img src={f.url_sm ?? f.url} alt="" className="h-full w-full object-cover" />
                    <IconButton
                      aria-label="Eliminar foto"
                      size="xs"
                      onClick={() => handleDeleteFoto(idx)}
                      className="absolute top-1 right-1 rounded-full bg-black/70 text-white opacity-0 group-hover:opacity-100 hover:bg-black/90"
                    >
                      <Trash2 className="h-3 w-3" />
                    </IconButton>
                  </div>
                ))}
              </div>
            )}
            {/* eslint-disable-next-line no-restricted-syntax -- input file: no hay componente DS */}
            <input
              ref={fotoInputRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.length) handleFotoUpload(e.target.files);
                e.target.value = "";
              }}
            />
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDraggingOver(true);
              }}
              onDragEnter={(e) => {
                e.preventDefault();
                setDraggingOver(true);
              }}
              onDragLeave={() => setDraggingOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDraggingOver(false);
                if (e.dataTransfer.files?.length) handleFotoUpload(e.dataTransfer.files);
              }}
              onClick={() => !uploadingFoto && fotoInputRef.current?.click()}
              className={cn(
                "rounded-xl border-2 border-dashed p-5 text-center cursor-pointer transition-colors",
                draggingOver ? "border-ink bg-ink/5" : "border-hairline hover:border-ink/40",
                uploadingFoto && "opacity-60 cursor-not-allowed",
              )}
            >
              {uploadingFoto ? (
                <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                  <Spinner size="sm" />
                  Subiendo…
                </div>
              ) : (
                <>
                  <Upload className="h-5 w-5 mx-auto mb-1.5 text-muted-foreground/50" />
                  <p className="text-sm text-muted-foreground">
                    Arrastrá fotos acá o{" "}
                    <span className="text-foreground underline underline-offset-2">hacé click</span>
                  </p>
                  <p className="text-xs text-muted-foreground/50 mt-0.5">
                    Podés seleccionar varias a la vez
                  </p>
                </>
              )}
            </div>
          </div>

          {/* Más detalles — collapsible */}
          <div className="border-t hairline pt-4">
            <button
              type="button"
              onClick={() => setShowExtra(!showExtra)}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <svg
                viewBox="0 0 24 24"
                className={cn("h-3 w-3 transition-transform", showExtra && "rotate-90")}
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
              >
                <path d="M9 18l6-6-6-6" />
              </svg>
              Más detalles (descripción, redes del realizador, logo, visibilidad)
            </button>
            {showExtra && (
              <div className="space-y-4 mt-4">
                <div className="space-y-1">
                  <label className="t-eyebrow">Descripción breve</label>
                  <Textarea
                    value={descripcion}
                    onChange={(e) => setDescripcion(e.target.value)}
                    placeholder="Breve contexto del trabajo (opcional)"
                    rows={2}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="t-eyebrow">Instagram del realizador</label>
                    <Input
                      value={instagram}
                      onChange={(e) => setInstagram(e.target.value)}
                      placeholder="@usuario"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="t-eyebrow">Web</label>
                    <Input
                      value={web}
                      onChange={(e) => setWeb(e.target.value)}
                      placeholder="https://..."
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="t-eyebrow">Logo del realizador</label>
                  <div className="flex items-center gap-3">
                    {logoUrl ? (
                      <img
                        src={logoUrl}
                        alt="logo"
                        className="h-12 w-12 rounded-lg object-contain border hairline bg-muted/30"
                      />
                    ) : (
                      <div className="h-12 w-12 rounded-lg border-dashed border-2 border-muted-foreground/30 flex items-center justify-center">
                        <Image className="h-5 w-5 text-muted-foreground/40" />
                      </div>
                    )}
                    {/* eslint-disable-next-line no-restricted-syntax -- input file: no hay componente DS */}
                    <input
                      ref={logoInputRef}
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) handleLogoUpload(f);
                      }}
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => logoInputRef.current?.click()}
                      disabled={uploadingLogo}
                    >
                      {uploadingLogo ? <Spinner size="xs" className="mr-1.5" /> : null}
                      {logoUrl ? "Cambiar logo" : "Subir logo"}
                    </Button>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    role="switch"
                    aria-checked={activo}
                    onClick={() => setActivo(!activo)}
                    className={cn(
                      "relative h-5 w-9 rounded-full transition-colors",
                      activo ? "bg-ink" : "bg-muted",
                    )}
                  >
                    <span
                      className={cn(
                        "absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-background transition-transform",
                        activo ? "translate-x-4" : "translate-x-0",
                      )}
                    />
                  </button>
                  <span className="text-sm text-muted-foreground">
                    Visible en la página pública
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="sticky bottom-0 bg-surface border-t hairline px-5 py-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving || (!linksPayload.length && !titulo.trim() && !fotos.length)}
          >
            {saving ? <Spinner size="sm" className="mr-1.5" /> : null}
            {isEdit ? "Guardar cambios" : "Crear trabajo"}
          </Button>
        </div>
      </div>
    </ModalBackdrop>
  );
}
