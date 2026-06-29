import { useEffect, useMemo, useRef, useState } from "react";
import {
  Copy,
  ExternalLink,
  ChevronDown,
  Image as ImageIcon,
  Upload,
  X,
} from "lucide-react";
import { Spinner } from "@/design-system/ui/spinner";
import { toast } from "sonner";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/design-system/ui/collapsible";
import { Input } from "@/design-system/ui/input";
import { Label } from "@/design-system/ui/label";
import { Button } from "@/design-system/ui/button";
import { Badge } from "@/design-system/ui/badge";
import { isHostedUrl } from "@/lib/equipment/photos";
import { normalizar } from "@/lib/search/normalize";
import type { CategoriaAdmin } from "@/lib/admin/api";

// ── Field ────────────────────────────────────────────────────────────────────

export function Field({
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

// ── CollapsibleSection ───────────────────────────────────────────────────────

export function CollapsibleSection({
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

// ── LinkInput ────────────────────────────────────────────────────────────────

export function LinkInput({
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

// ── PhotoCard ────────────────────────────────────────────────────────────────

export function PhotoCard({
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
            <img
              loading="lazy"
              decoding="async"
              src={url}
              alt=""
              className="h-full w-full object-contain"
            />
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
                <Badge variant="secondary" className="text-3xs">
                  Local — al guardar
                </Badge>
              )}
              {isHosted && (
                <Badge variant="default" className="text-3xs">
                  ✓ En R2
                </Badge>
              )}
              {isExternal && (
                <Badge variant="outline" className="text-3xs">
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
        {/* eslint-disable-next-line no-restricted-syntax -- input file: no hay componente DS */}
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
              <Spinner size="xs" className="mr-1" /> Subiendo…
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
                <Spinner size="xs" className="mr-1" /> Subiendo…
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

// ── CategoriasPicker ─────────────────────────────────────────────────────────

export function CategoriasPicker({
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

  const nq = normalizar(q.trim());
  const matchesName = (nombre: string) => !nq || normalizar(nombre).includes(nq);

  const visibleRoots = roots.filter((r) => {
    if (matchesName(r.nombre)) return true;
    return childrenOf(r.id).some((c) => matchesName(c.nombre));
  });

  return (
    <div className="space-y-2 mt-1">
      <div className="relative">
        <Input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar categoría…"
          className="w-full pr-7"
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
                        className="cursor-pointer text-2xs"
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

// ── TipoGlosario ─────────────────────────────────────────────────────────────

const TIPO_INFO: Record<
  "simple" | "kit" | "combo",
  { titulo: string; stock: string; precio: string; web: string; extra?: string }
> = {
  simple: {
    titulo: "Equipo",
    stock: "Propio",
    precio: "Propio (manual)",
    web: "Su categoría",
    extra: "Puede tener contenido de caja (reflector, cables…) solo informativo.",
  },
  kit: {
    titulo: "Kit",
    stock: "Propio + pools compartidos de accesorios (kit_componentes)",
    precio: "Manual (bundle cerrado; los componentes no suman)",
    web: "Su categoría — el cliente no sabe que es Kit",
    extra:
      "Diferencia con Equipo: consume accesorios de un pool compartido. El precio es el del bundle.",
  },
  combo: {
    titulo: "Combo",
    stock: "Derivado: mín. de los componentes esenciales",
    precio: "Σ (componente × cant × (1 − descuento_línea)), dinámico",
    web: "Categoría Combos",
    extra:
      "Esencial falta → no disponible. Best-effort falta → parcialmente disponible, mismo precio.",
  },
};

export function TipoGlosario({ tipo }: { tipo: "simple" | "kit" | "combo" }) {
  const info = TIPO_INFO[tipo];
  return (
    <div className="rounded-md border border-border/60 bg-muted/40 px-3 py-2 text-xs space-y-1">
      <p className="font-medium text-ink/90">{info.titulo}</p>
      <div className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 text-muted-foreground">
        <span className="font-medium">Stock</span>
        <span>{info.stock}</span>
        <span className="font-medium">Precio</span>
        <span>{info.precio}</span>
        <span className="font-medium">Web</span>
        <span>{info.web}</span>
      </div>
      {info.extra && <p className="text-muted-foreground/80 italic pt-0.5">{info.extra}</p>}
    </div>
  );
}
