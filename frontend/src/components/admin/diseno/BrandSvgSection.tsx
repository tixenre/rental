/**
 * BrandSvgSection — subir los SVG master de marca (wordmark + isologo) y derivar
 * los assets raster que consume el sistema.
 *
 * Subís el SVG vectorial una vez y el backend (motor `services/branding`, que
 * reusa el Chromium de los PDFs) rasteriza los derivados en los colores del
 * design system:
 *  - wordmark → logo del mail (blanco sobre transparente, para el header amber).
 *  - isologo  → favicon + ícono iOS + icon-512 (tile amber + isologo en ink).
 *
 * Las URLs derivadas se guardan en `app_settings` y las consume el mail (runtime)
 * y el favicon (swap del <link rel=icon> al cargar la app).
 */
import { useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload, Shapes, Type } from "lucide-react";
import { Spinner } from "@/design-system/ui/spinner";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { adminApi } from "@/lib/admin/api";

type Kind = "wordmark" | "isologo";

const META: Record<
  Kind,
  { title: string; icon: typeof Type; help: string; previewKey: string; previewBg: string }
> = {
  wordmark: {
    title: "Wordmark (SVG)",
    icon: Type,
    help: "El logotipo “rambla”. Deriva el logo blanco del header de los mails.",
    previewKey: "email_logo_url",
    previewBg: "#FAB428", // se previsualiza sobre amber (así va en el mail)
  },
  isologo: {
    title: "Isologo (SVG)",
    icon: Shapes,
    help: "El sello/ícono. Deriva el favicon, el ícono de iOS y la imagen para compartir.",
    previewKey: "favicon_url",
    previewBg: "transparent",
  },
};

function Uploader({ kind }: { kind: Kind }) {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const meta = META[kind];
  const Icon = meta.icon;

  const { data: settings } = useQuery({
    queryKey: ["admin", "settings"],
    queryFn: () => adminApi.listSettings(),
  });
  const masterUrl = settings?.items.find((s) => s.key === `${kind}_svg_url`)?.value ?? null;
  const previewUrl = settings?.items.find((s) => s.key === meta.previewKey)?.value ?? null;

  const mut = useMutation({
    mutationFn: (file: File) => adminApi.uploadBrandSvg(kind, file),
    onSuccess: () => {
      toast.success(`${meta.title} actualizado — assets regenerados`);
      qc.invalidateQueries({ queryKey: ["admin", "settings"] });
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function handleFile(file: File) {
    const isSvg = file.type.includes("svg") || file.name.toLowerCase().endsWith(".svg");
    if (!isSvg) {
      toast.error("Solo se admite SVG");
      return;
    }
    mut.mutate(file);
  }

  return (
    <div className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-muted-foreground" />
        <h3 className="font-display text-base text-ink">{meta.title}</h3>
      </div>
      <p className="text-xs text-muted-foreground">{meta.help}</p>
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div
          className="flex-shrink-0 w-32 h-16 rounded-md border hairline flex items-center justify-center overflow-hidden"
          style={{ background: meta.previewBg === "transparent" ? undefined : meta.previewBg }}
        >
          {previewUrl ? (
            <img
              loading="lazy"
              decoding="async"
              src={previewUrl}
              alt={`${kind} derivado`}
              className="object-contain w-full h-full p-2"
            />
          ) : masterUrl ? (
            <img
              loading="lazy"
              decoding="async"
              src={masterUrl}
              alt={kind}
              className="object-contain w-full h-full p-2"
            />
          ) : (
            <span className="text-xs text-muted-foreground">Sin {kind}</span>
          )}
        </div>
        <div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => inputRef.current?.click()}
            disabled={mut.isPending}
          >
            {mut.isPending ? (
              <Spinner size="sm" className="mr-2" />
            ) : (
              <Upload className="h-4 w-4 mr-2" />
            )}
            {mut.isPending ? "Procesando…" : masterUrl ? "Reemplazar SVG" : "Subir SVG"}
          </Button>
          {/* eslint-disable-next-line no-restricted-syntax -- input file: no hay componente DS */}
          <input
            ref={inputRef}
            type="file"
            accept=".svg,image/svg+xml"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
              e.target.value = "";
            }}
          />
        </div>
      </div>
    </div>
  );
}

export function BrandSvgSection() {
  return (
    <div className="rounded-lg border hairline bg-background p-4 space-y-4">
      <div>
        <h2 className="font-display text-lg text-ink">Marca (SVG)</h2>
        <p className="text-xs text-muted-foreground mt-1">
          Subí los SVG vectoriales y el sistema genera los assets (logo del mail, favicon, íconos)
          en los colores del design system. Una sola fuente → todo consistente.
        </p>
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        <Uploader kind="wordmark" />
        <Uploader kind="isologo" />
      </div>
    </div>
  );
}
