/**
 * AutocompletarBarSection — "Link del producto" + Buscar foto / Subir HTML /
 * Pegar HTML / Buscar valores actualizados.
 *
 * Extraído verbatim de `EquipoFormDialog.tsx` (split de god-module, Frente E
 * del skill `mantenimiento`, F2a #1263). Cero cambio de comportamiento — las
 * mutaciones quedan en el padre (comparten `photoCands`/specs con
 * `IdentificacionSection`); acá solo llegan los triggers + `isPending`.
 */
import type { RefObject } from "react";
import { Link as LinkIcon, Image as ImageIcon, FileCode, ClipboardPaste } from "lucide-react";
import { Spinner } from "@/design-system/ui/spinner";
import { Button } from "@/design-system/ui/button";
import { LinkInput } from "./form-helpers";

export function AutocompletarBarSection({
  isEdit,
  bhUrl,
  onBhUrlChange,
  htmlInputRef,
  htmlSourceUrl,
  onBuscarFotos,
  buscarFotosPending,
  onHtmlFileSelected,
  uploadingHtmlPending,
  onPegarHtmlClick,
  onReExtractSpecs,
  reExtractPending,
}: {
  isEdit: boolean;
  bhUrl: string;
  onBhUrlChange: (v: string) => void;
  htmlInputRef: RefObject<HTMLInputElement | null>;
  htmlSourceUrl: string | null;
  onBuscarFotos: () => void;
  buscarFotosPending: boolean;
  onHtmlFileSelected: (file: File) => void;
  uploadingHtmlPending: boolean;
  onPegarHtmlClick: () => void;
  onReExtractSpecs: () => void;
  reExtractPending: boolean;
}) {
  return (
    <section className="rounded-md border hairline bg-amber-soft/40 p-3 space-y-2">
      <div className="flex items-center gap-1.5 text-xs font-medium text-ink/80">
        <LinkIcon className="h-3.5 w-3.5" />
        Link del producto (B&amp;H, Adorama, sitio oficial)
      </div>
      <LinkInput
        value={bhUrl}
        onChange={onBhUrlChange}
        placeholder="https://www.bhphotovideo.com/c/product/..."
      />
      <div className="flex flex-wrap gap-1.5">
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onBuscarFotos}
          disabled={buscarFotosPending}
        >
          {buscarFotosPending ? (
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
                if (f) onHtmlFileSelected(f);
                e.target.value = "";
              }}
            />
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => htmlInputRef.current?.click()}
              disabled={uploadingHtmlPending}
            >
              {uploadingHtmlPending ? (
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
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={onPegarHtmlClick}
              title="Pegá el HTML de la página del producto (ej. copiado con Chrome MCP) sin subir un archivo"
            >
              <ClipboardPaste className="h-3.5 w-3.5 mr-1" />
              Pegar HTML
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
                  onClick={onReExtractSpecs}
                  disabled={reExtractPending || uploadingHtmlPending}
                  title="Re-corre la extracción sobre el HTML ya guardado, sin resubirlo — útil después de agregar un spec nuevo al registry"
                >
                  {reExtractPending ? (
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
  );
}
