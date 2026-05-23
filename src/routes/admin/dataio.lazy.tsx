/**
 * Página de export del catálogo.
 *
 * Permite descargar JSONs versionables del catálogo (marcas, categorías,
 * equipos, specs, etc.) para commitear al repo. La importación se hace
 * vía CLI (`python -m backend.dataio.cli import`) — no por UI.
 *
 * El catálogo "oficial" vive en /data/catalog/ del repo. Si descargás
 * un JSON desde acá y lo commiteás, esa pasa a ser la nueva baseline.
 */

import { createLazyFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Download, FileArchive, FileJson, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { authedFetch } from "@/lib/authedFetch";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/dataio")({
  component: DataIoPage,
});

const ENTITIES = [
  { key: "marcas", label: "Marcas", desc: "Sony, Canon, Aputure, …" },
  { key: "categorias", label: "Categorías", desc: "Árbol jerárquico (Cámaras > Foto, Video, …)" },
  { key: "etiquetas", label: "Etiquetas", desc: "Tags libres asignados a equipos" },
  { key: "spec_definitions", label: "Specs (definiciones)", desc: "Plantilla de specs por categoría raíz" },
  { key: "categoria_spec_templates", label: "Specs (asignaciones)", desc: "Qué specs aplican a cada categoría" },
  { key: "equipos", label: "Equipos", desc: "Catálogo completo de equipos con M2M categorías/etiquetas" },
  { key: "equipo_specs", label: "Equipo · valores de specs", desc: "Sensor, montura, formato, etc. por equipo" },
  { key: "equipo_fichas", label: "Equipo · fichas extendidas", desc: "Descripción, peso, conectividad, etc." },
] as const;

async function downloadFile(path: string, fallbackName: string) {
  const res = await authedFetch(path);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `${res.status} ${res.statusText}`);
  }
  const blob = await res.blob();
  // Extraer filename del Content-Disposition si está
  const cd = res.headers.get("Content-Disposition") || "";
  const match = cd.match(/filename="?([^";]+)"?/i);
  const filename = match?.[1] ?? fallbackName;

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function DataIoPage() {
  useDocumentTitle("Export catálogo · Back Office");
  const [busy, setBusy] = useState<string | null>(null);

  const handleDownload = async (entity: string, label: string) => {
    setBusy(entity);
    try {
      const fallback = entity === "all" ? "catalogo.zip" : `${entity}.json`;
      await downloadFile(`/api/admin/dataio/export?entity=${entity}`, fallback);
      toast.success(`Descargado: ${label}`);
    } catch (e) {
      toast.error(`Falló la descarga de ${label}: ${(e as Error).message}`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="px-4 md:px-6 py-6 space-y-8 max-w-4xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office
        </div>
        <h1 className="font-display text-3xl text-ink">Export del catálogo</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Descargá los JSONs del catálogo para versionarlos en el repo. Si commiteás un JSON
          descargado a <code className="text-xs">data/catalog/</code>, esa pasa a ser la nueva
          baseline oficial.
        </p>
      </header>

      <section className="rounded-lg border bg-card p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <h2 className="font-display text-lg flex items-center gap-2">
              <FileArchive className="size-4" />
              Catálogo completo
            </h2>
            <p className="text-sm text-muted-foreground">
              ZIP con los 8 JSONs (marcas, categorías, equipos, specs, fichas, etc.).
            </p>
          </div>
          <Button
            onClick={() => handleDownload("all", "Catálogo completo")}
            disabled={busy !== null}
            className="shrink-0"
          >
            {busy === "all" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Download className="size-4" />
            )}
            Descargar ZIP
          </Button>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="font-display text-lg">Por entidad</h2>
        <div className="rounded-lg border bg-card divide-y">
          {ENTITIES.map((e) => (
            <div
              key={e.key}
              className="flex items-center justify-between gap-4 px-5 py-4"
            >
              <div className="space-y-0.5 min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <FileJson className="size-4 text-muted-foreground shrink-0" />
                  <span className="font-medium truncate">{e.label}</span>
                </div>
                <p className="text-xs text-muted-foreground pl-6">{e.desc}</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleDownload(e.key, e.label)}
                disabled={busy !== null}
                className="shrink-0"
              >
                {busy === e.key ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Download className="size-4" />
                )}
                JSON
              </Button>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-dashed bg-muted/30 p-5 space-y-2">
        <h3 className="font-medium text-sm">Para importar</h3>
        <p className="text-sm text-muted-foreground">
          El import se hace desde la línea de comandos (servidor):
        </p>
        <pre className="text-xs bg-background border rounded px-3 py-2 overflow-x-auto">
{`# Validar JSONs sin tocar la DB
python -m backend.dataio.cli validate

# Dry-run: simula el upsert
python -m backend.dataio.cli import --dry-run

# Aplicar
python -m backend.dataio.cli import

# Ver qué hay en la DB que no esté en el repo
python -m backend.dataio.cli diff`}
        </pre>
      </section>
    </div>
  );
}
