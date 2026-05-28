/**
 * LogoSection — upload del logo del sitio.
 *
 * Vivía en /admin/settings → "Apariencia". Se movió a /admin/diseno como
 * parte de la consolidación "Diseño y marca". El endpoint y el setting key
 * (`logo_url`) no cambian — sólo cambia la ubicación en el back-office.
 */
import { useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Image as ImageIcon, Loader2, Upload } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { adminApi } from "@/lib/admin/api";

export function LogoSection() {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: settings } = useQuery({
    queryKey: ["admin", "settings"],
    queryFn: () => adminApi.listSettings(),
  });

  const logoUrl = settings?.items.find((s) => s.key === "logo_url")?.value ?? null;

  const uploadMut = useMutation({
    mutationFn: (file: File) => adminApi.uploadLogo(file),
    onSuccess: () => {
      toast.success("Logo actualizado");
      qc.invalidateQueries({ queryKey: ["admin", "settings"] });
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function handleFile(file: File) {
    if (!file.type.startsWith("image/")) {
      toast.error("Solo se admiten imágenes");
      return;
    }
    uploadMut.mutate(file);
  }

  return (
    <div className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div className="flex items-center gap-2">
        <ImageIcon className="h-4 w-4 text-muted-foreground" />
        <h2 className="font-display text-lg text-ink">Logo del sitio</h2>
      </div>
      <p className="text-xs text-muted-foreground">
        Aparece en el top bar del catálogo público y del back-office. PNG, SVG o WebP. Máx 5 MB. Se
        optimiza automáticamente.
      </p>
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex-shrink-0 w-32 h-16 rounded-md border hairline bg-muted flex items-center justify-center overflow-hidden">
          {logoUrl ? (
            <img src={logoUrl} alt="Logo actual" className="object-contain w-full h-full p-2" />
          ) : (
            <span className="text-xs text-muted-foreground">Sin logo</span>
          )}
        </div>
        <div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => inputRef.current?.click()}
            disabled={uploadMut.isPending}
          >
            {uploadMut.isPending ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Upload className="h-4 w-4 mr-2" />
            )}
            {uploadMut.isPending ? "Subiendo…" : logoUrl ? "Reemplazar logo" : "Subir logo"}
          </Button>
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
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
