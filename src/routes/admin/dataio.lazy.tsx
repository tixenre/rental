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
import { useRef, useState } from "react";
import {
  AlertTriangle,
  Database,
  Download,
  FileArchive,
  FileJson,
  FileSpreadsheet,
  Loader2,
  Trash2,
  Upload,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { authedFetch } from "@/lib/authedFetch";
import { useDocumentTitle } from "@/lib/use-document-title";

const RESET_CONFIRMATION = "BORRAR TODO";

export const Route = createLazyFileRoute("/admin/dataio")({
  component: DataIoPage,
});

const CATALOG_ENTITIES = [
  { key: "marcas", label: "Marcas", desc: "Sony, Canon, Aputure, …" },
  { key: "categorias", label: "Categorías", desc: "Árbol jerárquico (Cámaras > Foto, Video, …)" },
  { key: "etiquetas", label: "Etiquetas", desc: "Tags libres asignados a equipos" },
  {
    key: "spec_definitions",
    label: "Specs (definiciones)",
    desc: "Plantilla de specs por categoría raíz",
  },
  {
    key: "categoria_spec_templates",
    label: "Specs (asignaciones)",
    desc: "Qué specs aplican a cada categoría",
  },
  {
    key: "equipos",
    label: "Equipos",
    desc: "Catálogo completo de equipos con M2M categorías/etiquetas",
  },
  {
    key: "equipo_specs",
    label: "Equipo · valores de specs",
    desc: "Sensor, montura, formato, etc. por equipo",
  },
  {
    key: "equipo_fichas",
    label: "Equipo · fichas extendidas",
    desc: "Descripción, peso, conectividad, etc.",
  },
] as const;

const OPERATIONAL_ENTITIES = [
  { key: "clientes", label: "Clientes", desc: "Datos personales y fiscales. Clave: email." },
  {
    key: "alquileres",
    label: "Alquileres",
    desc: "Pedidos con items y pagos embebidos. Clave: numero_pedido.",
  },
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
  const [importBusy, setImportBusy] = useState(false);
  const [lastImport, setLastImport] = useState<ImportResult | null>(null);
  const importInputRef = useRef<HTMLInputElement>(null);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetConfirm, setResetConfirm] = useState("");
  const [resetBusy, setResetBusy] = useState(false);

  const handleResetOperacional = async () => {
    setResetBusy(true);
    try {
      const res = await authedFetch("/api/admin/dataio/reset-operacional", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: RESET_CONFIRMATION }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json.detail ?? `${res.status} ${res.statusText}`);
      toast.success(
        `Borrado: ${json.deleted?.clientes ?? 0} clientes, ${json.deleted?.alquileres ?? 0} alquileres`,
      );
      setLastImport(null);
      setResetOpen(false);
      setResetConfirm("");
    } catch (e) {
      toast.error(`Reset falló: ${(e as Error).message}`);
    } finally {
      setResetBusy(false);
    }
  };

  const handleDownload = async (entity: string, label: string) => {
    setBusy(entity);
    try {
      const fallback =
        entity.includes("-all") || entity === "full"
          ? `${entity}.zip`
          : entity.endsWith("-csv")
            ? `${entity.slice(0, -4)}.csv`
            : `${entity}.json`;
      await downloadFile(`/api/admin/dataio/export?entity=${entity}`, fallback);
      toast.success(`Descargado: ${label}`);
    } catch (e) {
      toast.error(`Falló la descarga de ${label}: ${(e as Error).message}`);
    } finally {
      setBusy(null);
    }
  };

  const handleImportOperacional = async (file: File, dryRun: boolean) => {
    setImportBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const url = `/api/admin/dataio/import?scope=operacional${dryRun ? "&dry_run=true" : ""}`;
      const res = await authedFetch(url, { method: "POST", body: fd });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json.detail ?? `${res.status} ${res.statusText}`);
      setLastImport(json as ImportResult);
      toast.success(
        `Import ${dryRun ? "(simulado)" : "OK"}: +${json.total_inserted ?? 0} ins, ~${json.total_updated ?? 0} upd`,
      );
    } catch (e) {
      toast.error(`Import falló: ${(e as Error).message}`);
    } finally {
      setImportBusy(false);
    }
  };

  return (
    <div className="px-4 md:px-6 py-6 space-y-8 max-w-4xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office
        </div>
        <h1 className="font-display text-3xl text-ink">Export / Import de datos</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Catálogo (versionado en el repo) y datos operacionales (clientes/pedidos, ad-hoc).
        </p>
      </header>

      {/* ─── CATÁLOGO ─── */}
      <section className="rounded-lg border bg-card p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <h2 className="font-display text-lg flex items-center gap-2">
              <FileArchive className="size-4" />
              Catálogo completo
            </h2>
            <p className="text-sm text-muted-foreground">
              ZIP con los 8 JSONs del catálogo. Si los commiteás a{" "}
              <code className="text-xs">data/catalog/</code>, pasan a ser la baseline oficial que se
              importa al startup.
            </p>
          </div>
          <Button
            onClick={() => handleDownload("catalog-all", "Catálogo completo")}
            disabled={busy !== null}
            className="shrink-0"
          >
            {busy === "catalog-all" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Download className="size-4" />
            )}
            Descargar ZIP
          </Button>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="font-display text-lg">Catálogo · por entidad</h2>
        <div className="rounded-lg border bg-card divide-y">
          {CATALOG_ENTITIES.map((e) => (
            <EntityRow key={e.key} entity={e} busy={busy} onDownload={handleDownload} />
          ))}
        </div>
      </section>

      {/* ─── PLANILLAS CSV ─── */}
      <section className="rounded-lg border bg-card p-5 space-y-3">
        <div className="space-y-1">
          <h2 className="font-display text-lg flex items-center gap-2">
            <FileSpreadsheet className="size-4" />
            Exportar a planilla (CSV)
          </h2>
          <p className="text-sm text-muted-foreground">
            Una sola hoja por entidad, lista para abrir en Excel/Sheets. Hace los JOINs por vos
            (marca, categorías y specs ya vienen en columnas). Alquileres y clientes incluyen datos
            privados — <strong className="text-foreground">no commitear al repo.</strong>
          </p>
        </div>
        <div className="flex flex-wrap gap-2 pt-1">
          <Button
            variant="outline"
            onClick={() => handleDownload("equipos-csv", "Equipos (CSV)")}
            disabled={busy !== null}
          >
            {busy === "equipos-csv" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Download className="size-4" />
            )}
            Equipos
          </Button>
          <Button
            variant="outline"
            onClick={() => handleDownload("alquileres-csv", "Alquileres (CSV)")}
            disabled={busy !== null}
          >
            {busy === "alquileres-csv" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Download className="size-4" />
            )}
            Alquileres
          </Button>
          <Button
            variant="outline"
            onClick={() => handleDownload("clientes-csv", "Clientes (CSV)")}
            disabled={busy !== null}
          >
            {busy === "clientes-csv" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Download className="size-4" />
            )}
            Clientes
          </Button>
          <Button
            onClick={() => handleDownload("csv-all", "Planillas (ZIP)")}
            disabled={busy !== null}
          >
            {busy === "csv-all" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <FileArchive className="size-4" />
            )}
            Todo (ZIP)
          </Button>
        </div>
      </section>

      {/* ─── OPERACIONAL ─── */}
      <section className="rounded-lg border border-amber-500/30 bg-amber-50/40 dark:bg-amber-950/10 p-5 space-y-3">
        <div className="flex items-start gap-3">
          <AlertTriangle className="size-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h2 className="font-display text-lg flex items-center gap-2">
              <Users className="size-4" />
              Datos operacionales (privados)
            </h2>
            <p className="text-sm text-muted-foreground">
              Clientes y pedidos contienen datos personales (email, teléfono, CUIT, montos).
              <strong className="text-foreground"> Nunca commitear al repo.</strong> Sirve para
              backups o migrar entre ambientes.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 pt-2">
          <Button
            onClick={() => handleDownload("operacional-all", "Operacional (clientes + alquileres)")}
            disabled={busy !== null}
          >
            {busy === "operacional-all" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Download className="size-4" />
            )}
            Descargar ZIP (operacional)
          </Button>
          <Button
            variant="outline"
            onClick={() => handleDownload("full", "Backup completo")}
            disabled={busy !== null}
          >
            {busy === "full" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <FileArchive className="size-4" />
            )}
            Backup full (catálogo + operacional)
          </Button>
        </div>

        <div className="rounded-md border bg-card divide-y">
          {OPERATIONAL_ENTITIES.map((e) => (
            <EntityRow key={e.key} entity={e} busy={busy} onDownload={handleDownload} />
          ))}
        </div>

        {/* Import operacional */}
        <div className="border-t border-amber-500/20 pt-4 space-y-3">
          <div className="space-y-1">
            <h3 className="font-medium text-sm flex items-center gap-2">
              <Database className="size-4" />
              Importar datos operacionales
            </h3>
            <p className="text-xs text-muted-foreground">
              Subí un ZIP con <code>clientes.json</code> y/o <code>alquileres.json</code>. Upsert
              por email (clientes) y numero_pedido (alquileres). Probá con <strong>dry-run</strong>{" "}
              primero — no toca la DB pero reporta el delta esperado.
            </p>
          </div>
          <input
            ref={importInputRef}
            type="file"
            accept=".zip"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              const dryRun = e.target.dataset.dryRun === "true";
              handleImportOperacional(f, dryRun);
              e.target.value = "";
              delete e.target.dataset.dryRun;
            }}
          />
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (importInputRef.current) {
                  importInputRef.current.dataset.dryRun = "true";
                  importInputRef.current.click();
                }
              }}
              disabled={importBusy}
            >
              {importBusy ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Upload className="size-4" />
              )}
              Subir ZIP · dry-run
            </Button>
            <Button
              size="sm"
              onClick={() => {
                if (importInputRef.current) {
                  importInputRef.current.dataset.dryRun = "false";
                  importInputRef.current.click();
                }
              }}
              disabled={importBusy}
            >
              {importBusy ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Upload className="size-4" />
              )}
              Subir ZIP · aplicar
            </Button>
          </div>

          {lastImport && (
            <div className="text-xs font-mono bg-background border rounded px-3 py-2 space-y-1">
              <div>
                {lastImport.dry_run ? "[DRY-RUN] " : ""}
                Total: +{lastImport.total_inserted} ins, ~{lastImport.total_updated} upd
              </div>
              {Object.entries(lastImport.stats).map(([entity, s]) => (
                <div key={entity} className="text-muted-foreground">
                  {entity}: +{s.inserted ?? 0} ins, ~{s.updated ?? 0} upd
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Zona destructiva: wipe clientes + alquileres */}
        <div className="border-t border-destructive/30 pt-4 mt-2 space-y-2">
          <div className="space-y-1">
            <h3 className="font-medium text-sm flex items-center gap-2 text-destructive">
              <Trash2 className="size-4" />
              Borrar todo (clientes + alquileres)
            </h3>
            <p className="text-xs text-muted-foreground">
              Elimina <strong>todos los clientes y alquileres</strong> (incluyendo items, pagos y
              solicitudes de modificación via cascade). Útil para hacer un wipe-and-reimport limpio.{" "}
              <strong className="text-destructive">No es reversible</strong> — hacé un backup antes
              (botón "Descargar ZIP" más arriba).
            </p>
          </div>
          <AlertDialog
            open={resetOpen}
            onOpenChange={(open) => {
              setResetOpen(open);
              if (!open) setResetConfirm("");
            }}
          >
            <AlertDialogTrigger asChild>
              <Button variant="destructive" size="sm">
                <Trash2 className="size-4" />
                Borrar clientes y alquileres
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>¿Borrar TODOS los datos operacionales?</AlertDialogTitle>
                <AlertDialogDescription>
                  Esta acción elimina permanentemente todos los clientes, alquileres, items, pagos y
                  solicitudes de modificación de la base de datos. El catálogo (equipos, marcas,
                  etc.) no se toca.
                  <br />
                  <br />
                  Para confirmar, escribí{" "}
                  <code className="font-mono font-bold">{RESET_CONFIRMATION}</code> abajo:
                </AlertDialogDescription>
              </AlertDialogHeader>
              <Input
                autoFocus
                value={resetConfirm}
                onChange={(e) => setResetConfirm(e.target.value)}
                placeholder={RESET_CONFIRMATION}
                className="font-mono"
              />
              <AlertDialogFooter>
                <AlertDialogCancel disabled={resetBusy}>Cancelar</AlertDialogCancel>
                <AlertDialogAction
                  disabled={resetConfirm !== RESET_CONFIRMATION || resetBusy}
                  onClick={(e) => {
                    e.preventDefault();
                    handleResetOperacional();
                  }}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  {resetBusy ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Trash2 className="size-4" />
                  )}
                  Borrar definitivamente
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </section>

      {/* ─── CLI HINT ─── */}
      <section className="rounded-lg border border-dashed bg-muted/30 p-5 space-y-2">
        <h3 className="font-medium text-sm">CLI equivalente</h3>
        <pre className="text-xs bg-background border rounded px-3 py-2 overflow-x-auto">
          {`# Catálogo (default — JSONs versionados)
python -m backend.dataio.cli export
python -m backend.dataio.cli import --dry-run
python -m backend.dataio.cli import
python -m backend.dataio.cli diff           # DB vs JSON

# Operacional (ad-hoc, NO commitear)
python -m backend.dataio.cli export --scope operacional --out /tmp/backup/
python -m backend.dataio.cli import --scope operacional --in /tmp/backup/ --dry-run

# Backup full
python -m backend.dataio.cli export --scope all --out /tmp/full-backup/`}
        </pre>
      </section>
    </div>
  );
}

type ImportResult = {
  ok: boolean;
  dry_run: boolean;
  stats: Record<string, { inserted?: number; updated?: number; skipped?: number }>;
  total_inserted: number;
  total_updated: number;
};

function EntityRow({
  entity,
  busy,
  onDownload,
}: {
  entity: { key: string; label: string; desc: string };
  busy: string | null;
  onDownload: (key: string, label: string) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 px-5 py-4">
      <div className="space-y-0.5 min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <FileJson className="size-4 text-muted-foreground shrink-0" />
          <span className="font-medium truncate">{entity.label}</span>
        </div>
        <p className="text-xs text-muted-foreground pl-6">{entity.desc}</p>
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={() => onDownload(entity.key, entity.label)}
        disabled={busy !== null}
        className="shrink-0"
      >
        {busy === entity.key ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Download className="size-4" />
        )}
        JSON
      </Button>
    </div>
  );
}
