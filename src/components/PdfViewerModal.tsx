/**
 * PdfViewerModal — overlay con iframe para previsualizar un PDF
 * sin forzar la descarga. Incluye botón "Descargar" con filename custom.
 *
 * Backend complementario: los endpoints PDF deben servir con
 * `Content-Disposition: inline` (no `attachment`) para que el iframe los muestre.
 */

import { useEffect } from "react";
import { authedFetch } from "@/lib/authedFetch";

type Props = {
  url: string;
  filename: string;
  titulo: string;
  onClose: () => void;
};

export function PdfViewerModal({ url, filename, titulo, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose]);

  async function handleDownload() {
    try {
      const res = await authedFetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const objUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(objUrl);
    } catch {
      window.open(url, "_blank");
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 flex flex-col"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={titulo}
    >
      <div
        className="flex items-center justify-between gap-2 bg-background border-b hairline px-3 py-2"
        onClick={(e) => e.stopPropagation()}
      >
        <span className="text-sm font-medium text-ink truncate">{titulo}</span>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={handleDownload}
            className="inline-flex items-center gap-1.5 rounded-md border hairline bg-background px-3 py-1.5 text-xs font-medium text-ink hover:bg-muted/50 transition"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3" />
            </svg>
            Descargar
          </button>
          <button
            onClick={onClose}
            aria-label="Cerrar"
            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted/50 hover:text-ink transition"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
      <iframe
        src={url}
        title={titulo}
        className="flex-1 w-full bg-white"
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  );
}
