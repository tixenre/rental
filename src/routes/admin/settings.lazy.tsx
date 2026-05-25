import { useEffect, useMemo, useRef, useState } from "react";
import { createLazyFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown, ArrowUp, Upload, Loader2, Image as ImageIcon,
  TrendingUp, TrendingDown, Sparkles, Plus, Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import { adminApi, descuentosJornadaApi } from "@/lib/admin/api";
import { interpolarDescuento } from "@/lib/api";
import { FAQ_GROUPS, parseFaq, type FaqGroup } from "@/data/faq";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/settings")({
  component: SettingsPage,
});

function SettingsPage() {
  useDocumentTitle("Settings · Back Office");

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-4xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office
        </div>
        <h1 className="font-display text-3xl text-ink">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Configuración del sistema y herramientas de mantenimiento.
        </p>
      </header>

      <AparienciaSection />

      <DescuentosJornadaSection />

      <BufferSection />

      <HorariosSection />

      <FaqSection />

      <CambioYPreciosSection />

      <RankingSection />
    </div>
  );
}

// ── Descuentos por jornadas ─────────────────────────────────────────────────

function DescuentosJornadaSection() {
  const qc = useQueryClient();
  const [dias, setDias] = useState("");
  const [pct, setPct] = useState("");

  const { data: puntos = [], isLoading } = useQuery({
    queryKey: ["descuentos-jornada"],
    queryFn: descuentosJornadaApi.list,
    staleTime: 5 * 60 * 1000,
  });

  const crear = useMutation({
    mutationFn: () => descuentosJornadaApi.create({ jornadas: Number(dias), pct: Number(pct) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["descuentos-jornada"] }); setDias(""); setPct(""); },
    onError: () => toast.error("Error al guardar"),
  });

  const borrar = useMutation({
    mutationFn: (id: number) => descuentosJornadaApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["descuentos-jornada"] }),
    onError: () => toast.error("Error al eliminar"),
  });

  const sorted = [...puntos].sort((a, b) => a.jornadas - b.jornadas);

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-4">
      <div>
        <h2 className="font-display text-lg text-ink">Descuentos por jornadas</h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          Definí puntos ancla. Los valores intermedios se interpolan automáticamente.
        </p>
      </div>

      {/* Tabla de puntos */}
      {isLoading ? (
        <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
      ) : sorted.length === 0 ? (
        <p className="text-sm text-muted-foreground italic">Sin descuentos configurados. Todos los alquileres aplican 0%.</p>
      ) : (
        <div className="border hairline rounded-md overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/40">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">Jornadas</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">Descuento</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground text-xs">Ej. interpol.</th>
                <th className="px-3 py-2 w-10" />
              </tr>
            </thead>
            <tbody className="divide-y hairline">
              {sorted.map((p, i) => {
                const siguiente = sorted[i + 1];
                const medio = siguiente
                  ? Math.round((p.jornadas + siguiente.jornadas) / 2)
                  : null;
                const pctMedio = medio ? interpolarDescuento(sorted, medio) : null;
                return (
                  <tr key={p.id}>
                    <td className="px-3 py-2 tabular-nums font-medium">{p.jornadas} {p.jornadas === 1 ? "día" : "días"}</td>
                    <td className="px-3 py-2 tabular-nums text-emerald-600 font-medium">{p.pct}%</td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {pctMedio !== null ? `${medio} días → ${pctMedio}%` : "—"}
                    </td>
                    <td className="px-3 py-2">
                      <button
                        onClick={() => borrar.mutate(p.id)}
                        className="text-muted-foreground hover:text-destructive"
                        disabled={borrar.isPending}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Agregar punto */}
      <div className="flex items-end gap-2">
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Jornadas</label>
          <Input
            type="number" min="1" value={dias} onChange={(e) => setDias(e.target.value)}
            placeholder="7" className="w-24 h-8 text-sm"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Descuento %</label>
          <Input
            type="number" min="0" max="100" step="0.5" value={pct} onChange={(e) => setPct(e.target.value)}
            placeholder="10" className="w-24 h-8 text-sm"
          />
        </div>
        <Button
          size="sm" variant="outline"
          onClick={() => crear.mutate()}
          disabled={!dias || !pct || crear.isPending}
        >
          {crear.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
          Agregar
        </Button>
      </div>
    </section>
  );
}


// ── Buffer entre alquileres ─────────────────────────────────────────────────

function BufferSection() {
  const qc = useQueryClient();
  const [valor, setValor] = useState("");

  const settingQ = useQuery({
    queryKey: ["settings", "buffer_horas_alquiler"],
    queryFn: () => adminApi.getSetting("buffer_horas_alquiler"),
    staleTime: 60_000,
  });

  useEffect(() => {
    if (settingQ.data && valor === "") setValor(settingQ.data.value ?? "0");
  }, [settingQ.data, valor]);

  const updateMut = useMutation({
    mutationFn: (v: string) => adminApi.updateSetting("buffer_horas_alquiler", v),
    onSuccess: () => {
      toast.success("Buffer actualizado");
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const actual = settingQ.data?.value ?? "0";
  const dirty = valor.trim() !== actual && valor.trim() !== "";

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink">Buffer entre alquileres</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Horas de prep/revisión exigidas entre que un equipo vuelve y sale de nuevo.
          Con buffer &gt; 0, dos alquileres del mismo equipo no pueden quedar pegados
          (respeta la hora de retiro/devolución). Poné 0 para permitir alquileres
          consecutivos. Ej: 24 = un día.
        </p>
      </div>
      <div className="flex items-end gap-2 border-t hairline pt-3">
        <div className="space-y-1">
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Horas de buffer</div>
          <Input
            type="number"
            min={0}
            className="w-28"
            value={valor}
            onChange={(e) => setValor(e.target.value)}
          />
        </div>
        <Button
          size="sm"
          onClick={() => updateMut.mutate(String(Math.max(0, Math.floor(Number(valor) || 0))))}
          disabled={!dirty || updateMut.isPending}
        >
          {updateMut.isPending ? "Guardando…" : "Guardar"}
        </Button>
      </div>
    </section>
  );
}


// ── Horarios habilitados de retiro/devolución ───────────────────────────────

const DIAS_ORDEN: Array<[string, string]> = [
  ["lun", "Lunes"], ["mar", "Martes"], ["mie", "Miércoles"], ["jue", "Jueves"],
  ["vie", "Viernes"], ["sab", "Sábado"], ["dom", "Domingo"],
];
type DiaCfg = { abierto: boolean; desde: string; hasta: string };
const DEFAULT_DIA: DiaCfg = { abierto: true, desde: "09:00", hasta: "18:00" };

function HorariosSection() {
  const qc = useQueryClient();
  const [cfg, setCfg] = useState<Record<string, DiaCfg> | null>(null);

  const settingQ = useQuery({
    queryKey: ["settings", "horarios_retiro"],
    queryFn: () => adminApi.getSetting("horarios_retiro"),
    retry: false,
    staleTime: 60_000,
  });

  // Inicializa el estado desde el setting (o defaults: L-V abierto, finde
  // cerrado). Espera a que el fetch termine (isFetched) para no pisar el valor
  // guardado con los defaults.
  useEffect(() => {
    if (cfg !== null || !settingQ.isFetched) return;
    let parsed: Record<string, { desde: string; hasta: string } | null> = {};
    try {
      parsed = settingQ.data?.value ? JSON.parse(settingQ.data.value) : {};
    } catch {
      parsed = {};
    }
    const hasData = Object.keys(parsed).length > 0;
    const next: Record<string, DiaCfg> = {};
    for (const [key] of DIAS_ORDEN) {
      const f = parsed[key];
      if (hasData) {
        next[key] = f ? { abierto: true, desde: f.desde, hasta: f.hasta } : { ...DEFAULT_DIA, abierto: false };
      } else {
        // Sin config previa: plantilla L-V abierto 09-18, finde cerrado.
        next[key] = key === "sab" || key === "dom" ? { ...DEFAULT_DIA, abierto: false } : { ...DEFAULT_DIA };
      }
    }
    setCfg(next);
  }, [settingQ.data, settingQ.isFetched, cfg]);

  const updateMut = useMutation({
    mutationFn: (v: string) => adminApi.updateSetting("horarios_retiro", v),
    onSuccess: () => {
      toast.success("Horarios actualizados");
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const setDia = (key: string, patch: Partial<DiaCfg>) =>
    setCfg((prev) => (prev ? { ...prev, [key]: { ...prev[key], ...patch } } : prev));

  const save = () => {
    if (!cfg) return;
    const payload: Record<string, { desde: string; hasta: string } | null> = {};
    for (const [key] of DIAS_ORDEN) {
      const d = cfg[key];
      if (d.abierto && d.desde >= d.hasta) {
        toast.error(`${DIAS_ORDEN.find(([k]) => k === key)?.[1]}: la apertura debe ser anterior al cierre`);
        return;
      }
      payload[key] = d.abierto ? { desde: d.desde, hasta: d.hasta } : null;
    }
    updateMut.mutate(JSON.stringify(payload));
  };

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink">Horarios de retiro y devolución</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Franja horaria habilitada por día para que el cliente elija retiro y devolución
          (misma franja para ambos). Los días cerrados no se pueden seleccionar. Aplica al
          checkout del cliente — los pedidos cargados a mano en el back-office no se restringen.
        </p>
      </div>
      <div className="border-t hairline pt-3 space-y-2">
        {cfg && DIAS_ORDEN.map(([key, label]) => {
          const d = cfg[key];
          return (
            <div key={key} className="flex items-center gap-3">
              <label className="flex items-center gap-2 w-40 shrink-0 text-sm">
                <input
                  type="checkbox"
                  checked={d.abierto}
                  onChange={(e) => setDia(key, { abierto: e.target.checked })}
                />
                <span className={d.abierto ? "text-ink" : "text-muted-foreground line-through"}>{label}</span>
              </label>
              {d.abierto ? (
                <div className="flex items-center gap-1.5 text-sm">
                  <Input
                    type="time"
                    step={1800}
                    value={d.desde}
                    onChange={(e) => setDia(key, { desde: e.target.value })}
                    className="w-28"
                  />
                  <span className="text-muted-foreground">–</span>
                  <Input
                    type="time"
                    step={1800}
                    value={d.hasta}
                    onChange={(e) => setDia(key, { hasta: e.target.value })}
                    className="w-28"
                  />
                </div>
              ) : (
                <span className="text-xs text-muted-foreground italic">Cerrado</span>
              )}
            </div>
          );
        })}
        <div className="pt-2">
          <Button size="sm" onClick={save} disabled={!cfg || updateMut.isPending}>
            {updateMut.isPending ? "Guardando…" : "Guardar horarios"}
          </Button>
        </div>
      </div>
    </section>
  );
}


// ── Preguntas frecuentes (editables) ────────────────────────────────────────

function FaqSection() {
  const qc = useQueryClient();
  const [groups, setGroups] = useState<FaqGroup[] | null>(null);

  const settingQ = useQuery({
    queryKey: ["settings", "faq_json"],
    queryFn: () => adminApi.getSetting("faq_json"),
    retry: false,
    staleTime: 60_000,
  });

  // Arranca del setting guardado, o de las FAQ por defecto (hardcodeadas).
  useEffect(() => {
    if (groups !== null || !settingQ.isFetched) return;
    const parsed = parseFaq(settingQ.data?.value);
    // Clonamos para no mutar el default importado.
    setGroups(parsed ?? FAQ_GROUPS.map((g) => ({ title: g.title, items: g.items.map((i) => ({ ...i })) })));
  }, [settingQ.data, settingQ.isFetched, groups]);

  const updateMut = useMutation({
    mutationFn: (v: string) => adminApi.updateSetting("faq_json", v),
    onSuccess: () => {
      toast.success("Preguntas frecuentes actualizadas");
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const setGroup = (gi: number, patch: Partial<FaqGroup>) =>
    setGroups((prev) => prev && prev.map((g, i) => (i === gi ? { ...g, ...patch } : g)));
  const setItem = (gi: number, ii: number, patch: Partial<{ q: string; a: string }>) =>
    setGroups((prev) =>
      prev && prev.map((g, i) =>
        i === gi ? { ...g, items: g.items.map((it, j) => (j === ii ? { ...it, ...patch } : it)) } : g,
      ),
    );
  const addItem = (gi: number) =>
    setGroups((prev) => prev && prev.map((g, i) => (i === gi ? { ...g, items: [...g.items, { q: "", a: "" }] } : g)));
  const removeItem = (gi: number, ii: number) =>
    setGroups((prev) => prev && prev.map((g, i) => (i === gi ? { ...g, items: g.items.filter((_, j) => j !== ii) } : g)));
  const addGroup = () => setGroups((prev) => [...(prev ?? []), { title: "Nueva sección", items: [] }]);
  const removeGroup = (gi: number) => setGroups((prev) => prev && prev.filter((_, i) => i !== gi));

  const save = () => {
    if (!groups) return;
    const clean = groups
      .map((g) => ({
        title: g.title.trim(),
        items: g.items
          .map((it) => ({ q: it.q.trim(), a: it.a.trim() }))
          .filter((it) => it.q && it.a),
      }))
      .filter((g) => g.title && g.items.length > 0);
    updateMut.mutate(JSON.stringify(clean));
  };

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink">Preguntas frecuentes</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Las que ve el cliente en <code className="text-ink">/preguntas-frecuentes</code>.
          Organizadas en secciones. Las preguntas o secciones vacías se descartan al guardar.
        </p>
      </div>

      <div className="border-t hairline pt-3 space-y-4">
        {groups?.map((g, gi) => (
          <div key={gi} className="rounded-md border hairline p-3 space-y-2">
            <div className="flex items-center gap-2">
              <Input
                value={g.title}
                onChange={(e) => setGroup(gi, { title: e.target.value })}
                placeholder="Título de la sección (ej. Reservas)"
                className="font-medium"
              />
              <Button
                type="button" size="icon" variant="ghost"
                onClick={() => removeGroup(gi)}
                title="Eliminar sección"
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </div>

            {g.items.map((it, ii) => (
              <div key={ii} className="flex items-start gap-2 pl-3 border-l-2 border-muted">
                <div className="flex-1 space-y-1">
                  <Input
                    value={it.q}
                    onChange={(e) => setItem(gi, ii, { q: e.target.value })}
                    placeholder="Pregunta"
                    className="text-sm"
                  />
                  <Textarea
                    value={it.a}
                    onChange={(e) => setItem(gi, ii, { a: e.target.value })}
                    placeholder="Respuesta"
                    rows={2}
                    className="text-sm"
                  />
                </div>
                <Button
                  type="button" size="icon" variant="ghost"
                  onClick={() => removeItem(gi, ii)}
                  title="Eliminar pregunta"
                >
                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                </Button>
              </div>
            ))}

            <Button type="button" size="sm" variant="outline" onClick={() => addItem(gi)}>
              <Plus className="h-3.5 w-3.5 mr-1" /> Pregunta
            </Button>
          </div>
        ))}

        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" onClick={addGroup}>
            <Plus className="h-4 w-4 mr-1" /> Sección
          </Button>
          <Button onClick={save} disabled={!groups || updateMut.isPending}>
            {updateMut.isPending ? "Guardando…" : "Guardar FAQ"}
          </Button>
        </div>
      </div>
    </section>
  );
}


// ── Apariencia (logo del sitio) ─────────────────────────────────────────────

function AparienciaSection() {
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
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <h2 className="font-display text-lg text-ink flex items-center gap-2">
        <ImageIcon className="h-4 w-4 text-muted-foreground" />
        Apariencia
      </h2>

      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex-shrink-0 w-32 h-16 rounded-md border hairline bg-muted flex items-center justify-center overflow-hidden">
          {logoUrl ? (
            <img src={logoUrl} alt="Logo actual" className="object-contain w-full h-full p-2" />
          ) : (
            <span className="text-xs text-muted-foreground">Sin logo</span>
          )}
        </div>

        <div className="space-y-1.5">
          <p className="text-sm text-muted-foreground">
            PNG, SVG o WebP recomendado. Máx 5 MB. Se optimiza automáticamente.
          </p>
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
            {uploadMut.isPending ? "Subiendo…" : "Subir logo"}
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
    </section>
  );
}

// ── Ranking automático de equipos ───────────────────────────────────────────

function RankingSection() {
  const qc = useQueryClient();
  const [reporte, setReporte] = useState<Awaited<ReturnType<typeof adminApi.recalcularRanking>> | null>(null);

  const recalcMut = useMutation({
    mutationFn: (dry_run: boolean) =>
      adminApi.recalcularRanking({ dry_run, ventana_dias: 180 }),
    onSuccess: (data) => {
      setReporte(data);
      if (!data.dry_run) {
        toast.success(`Ranking recalculado · ${data.cambios.length} equipos actualizados`);
        qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
        qc.invalidateQueries({ queryKey: ["equipos"] });
      } else {
        toast.message(`Preview: ${data.cambios.length} equipos cambiarían (dry-run)`);
      }
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-amber" /> Ranking automático
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Calcula la prioridad de cada equipo en el catálogo basándose en
          el histórico de pedidos e ingresos de los últimos 180 días.
          Normalizado por categoría (los equipos compiten contra sus pares,
          no contra todo el inventario).
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-2 pt-2">
        <Button
          variant="outline"
          onClick={() => recalcMut.mutate(true)}
          disabled={recalcMut.isPending}
        >
          {recalcMut.isPending && recalcMut.variables ? (
            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
          ) : null}
          Ver preview (dry-run)
        </Button>
        <Button
          onClick={() => recalcMut.mutate(false)}
          disabled={recalcMut.isPending}
        >
          {recalcMut.isPending && !recalcMut.variables ? (
            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
          ) : null}
          Recalcular y aplicar
        </Button>
      </div>

      {reporte && (
        <div className="mt-3 space-y-2 rounded-md border hairline bg-muted/30 p-3">
          <div className="text-xs">
            <span className="font-medium text-ink">
              {reporte.dry_run ? "Preview (dry-run): " : "Aplicado: "}
            </span>
            <span className="text-muted-foreground">
              {reporte.cambios.length} equipos {reporte.dry_run ? "cambiarían" : "actualizados"},
              {" "}{reporte.sin_cambios} sin cambios. Ventana: {reporte.ventana_dias} días.
            </span>
          </div>
          {reporte.cambios.length > 0 && (
            <div className="space-y-1 max-h-80 overflow-y-auto">
              {reporte.cambios
                .slice()
                .sort((a, b) => (b.despues.score - b.antes.score) - (a.despues.score - a.antes.score))
                .slice(0, 20)
                .map((c) => {
                  const delta = c.despues.score - c.antes.score;
                  return (
                    <div key={c.id} className="flex items-center justify-between gap-2 text-xs py-1 border-b hairline last:border-0">
                      <span className="text-ink truncate flex-1">{c.nombre}</span>
                      <span className="text-muted-foreground tabular shrink-0">
                        {c.antes.score} → {c.despues.score}
                      </span>
                      <span className={`tabular shrink-0 inline-flex items-center gap-0.5 ${delta > 0 ? "text-green-600" : delta < 0 ? "text-destructive" : "text-muted-foreground"}`}>
                        {delta > 0 ? <TrendingUp className="h-3 w-3" /> : delta < 0 ? <TrendingDown className="h-3 w-3" /> : null}
                        {delta > 0 ? "+" : ""}{delta}
                      </span>
                    </div>
                  );
                })}
              {reporte.cambios.length > 20 && (
                <div className="text-xs text-muted-foreground pt-1">
                  …y {reporte.cambios.length - 20} más.
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

// ── Cambio (USD/ARS) y recálculo masivo de precios ─────────────────────────

type RecalcMode = "missing" | "auto" | "all" | "ids";

function CambioYPreciosSection() {
  const qc = useQueryClient();
  const [valor, setValor] = useState("");
  const [confirmRecalc, setConfirmRecalc] = useState<{
    mode: RecalcMode;
    ids?: number[];
    preview: { total_cambios: number; total_evaluados: number };
  } | null>(null);

  const settingQ = useQuery({
    queryKey: ["settings", "usd_rate"],
    queryFn: () => adminApi.getSetting("usd_rate"),
    staleTime: 60_000,
  });

  // Cargar el valor actual cuando llega de la red.
  useEffect(() => {
    if (settingQ.data && !valor) setValor(settingQ.data.value);
  }, [settingQ.data, valor]);

  const updateMut = useMutation({
    mutationFn: (v: string) => adminApi.updateSetting("usd_rate", v),
    onSuccess: () => {
      toast.success("Tipo de cambio actualizado");
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const dryRunMut = useMutation({
    mutationFn: (args: { mode: RecalcMode; ids?: number[] }) =>
      adminApi.recalcularPrecios({ dry_run: true, ...args }).then((r) => ({ ...r, ...args })),
    onSuccess: (r) => {
      if (r.total_cambios === 0) {
        toast.info("Nada para recalcular — todos los precios ya están en sincro.");
        return;
      }
      setConfirmRecalc({
        mode: r.mode,
        ids: r.ids,
        preview: { total_cambios: r.total_cambios, total_evaluados: r.total_evaluados },
      });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const applyMut = useMutation({
    mutationFn: (args: { mode: RecalcMode; ids?: number[] }) =>
      adminApi.recalcularPrecios({ dry_run: false, ...args }),
    onSuccess: (r) => {
      toast.success(`${r.total_cambios} precios actualizados`);
      qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
      qc.invalidateQueries({ queryKey: ["equipos"] });
      qc.invalidateQueries({ queryKey: ["admin", "precios-manuales"] });
      setConfirmRecalc(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const dirty = valor.trim() !== (settingQ.data?.value ?? "");
  const fmtFecha = (s: string | null) => {
    if (!s) return "—";
    try {
      return new Date(s).toLocaleString("es-AR", {
        dateStyle: "medium", timeStyle: "short",
      });
    } catch {
      return s;
    }
  };
  const modeLabel = (m: RecalcMode) => ({
    missing: "Sólo equipos sin precio",
    auto: "Sólo precios automáticos",
    all: "Todos (incluye manuales)",
    ids: "Selección personalizada",
  }[m]);

  return (
    <>
      <section className="rounded-lg border hairline bg-background p-4 space-y-3">
        <header>
          <h2 className="font-display text-lg text-ink">Tipo de cambio &amp; precios</h2>
          <p className="text-sm text-muted-foreground">
            Cotización del dólar usada para calcular el precio de jornada en pesos.
            Actualizalo a fin de mes y después aplicá el recálculo masivo.
          </p>
        </header>

        <div className="flex flex-col sm:flex-row sm:items-end gap-3 border-t hairline pt-3">
          <div className="flex-1">
            <label className="text-xs uppercase tracking-wide text-muted-foreground">
              ARS por 1 USD
            </label>
            <Input
              type="number"
              min={0}
              step="0.01"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              placeholder="1200"
              className="mt-1"
            />
            <p className="mt-1 text-[11px] text-muted-foreground">
              Última actualización: {fmtFecha(settingQ.data?.updated_at ?? null)}
              {settingQ.data?.updated_by && ` · ${settingQ.data.updated_by}`}
            </p>
          </div>
          <Button
            onClick={() => updateMut.mutate(valor)}
            disabled={!dirty || updateMut.isPending || !valor.trim()}
          >
            {updateMut.isPending ? "Guardando…" : "Guardar"}
          </Button>
        </div>

        <div className="border-t hairline pt-3 space-y-2">
          <div>
            <div className="text-ink font-medium">Recalcular precios</div>
            <p className="text-xs text-muted-foreground">
              <code className="font-mono text-[11px] bg-muted/50 px-1 py-0.5 rounded">
                precio_jornada = precio_usd × usd_rate × (roi_pct / 100)
              </code>
              {" "}— redondeado al múltiplo de 100 más cercano.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline" size="sm"
              onClick={() => dryRunMut.mutate({ mode: "auto" })}
              disabled={dryRunMut.isPending}
              title="Respeta los precios marcados como manuales"
            >
              {dryRunMut.isPending ? (
                <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Calculando…</>
              ) : (
                "Sólo automáticos (recomendado)"
              )}
            </Button>
            <Button
              variant="ghost" size="sm"
              onClick={() => dryRunMut.mutate({ mode: "missing" })}
              disabled={dryRunMut.isPending}
              title="Sólo equipos que aún no tienen precio cargado"
            >
              Sólo sin precio
            </Button>
            <Button
              variant="ghost" size="sm"
              onClick={() => dryRunMut.mutate({ mode: "all" })}
              disabled={dryRunMut.isPending}
              title="Pisa los precios manuales también — usar con cuidado"
              className="text-destructive hover:text-destructive"
            >
              Todos (pisa manuales)
            </Button>
          </div>
        </div>

        <PreciosManualesPanel
          onRecalcSelected={(ids) => dryRunMut.mutate({ mode: "ids", ids })}
        />
      </section>

      <AlertDialog open={!!confirmRecalc} onOpenChange={(v) => { if (!v) setConfirmRecalc(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              ¿Aplicar recálculo a {confirmRecalc?.preview.total_cambios} equipos?
            </AlertDialogTitle>
            <AlertDialogDescription>
              Modo: <strong>{confirmRecalc && modeLabel(confirmRecalc.mode)}</strong>.
              {" "}De {confirmRecalc?.preview.total_evaluados} equipos evaluados,
              {" "}{confirmRecalc?.preview.total_cambios} cambiarían su precio en pesos.
              {confirmRecalc?.mode === "all" && (
                <span className="block mt-2 text-destructive">
                  ⚠️ Vas a pisar también los precios marcados como manuales.
                </span>
              )}
              {" "}Esta acción no se puede deshacer automáticamente.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                confirmRecalc && applyMut.mutate({
                  mode: confirmRecalc.mode,
                  ids: confirmRecalc.ids,
                })
              }
              disabled={applyMut.isPending}
            >
              {applyMut.isPending ? "Aplicando…" : "Sí, aplicar"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}


/** Lista los equipos con precio_jornada_manual=TRUE y muestra qué precio
 *  daría la fórmula con el USD rate actual. Permite seleccionar manualmente
 *  cuáles recalcular (los demás conservan su precio fijado). */
function PreciosManualesPanel({
  onRecalcSelected,
}: {
  onRecalcSelected: (ids: number[]) => void;
}) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [expanded, setExpanded] = useState(false);

  const manualesQ = useQuery({
    queryKey: ["admin", "precios-manuales"],
    queryFn: () => adminApi.listarPreciosManuales(),
    staleTime: 30_000,
  });

  const items = manualesQ.data?.items ?? [];
  const conDelta = items.filter((i) => i.delta != null && i.delta !== 0);

  if (manualesQ.isLoading) {
    return (
      <div className="border-t hairline pt-3 text-xs text-muted-foreground">
        Cargando precios manuales…
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="border-t hairline pt-3 text-xs text-muted-foreground">
        No hay equipos con precio fijado manualmente.
      </div>
    );
  }

  const toggleAll = () => {
    if (selected.size === conDelta.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(conDelta.map((i) => i.id)));
    }
  };

  const toggleOne = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const fmtPrecio = (n: number | null) =>
    n == null ? "—" : `$${Math.round(n).toLocaleString("es-AR", { maximumFractionDigits: 0 })}`;

  return (
    <div className="border-t hairline pt-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-ink font-medium text-sm">
            Precios manuales — revisión equipo por equipo
          </div>
          <p className="text-xs text-muted-foreground">
            {items.length} equipos con precio fijado a mano.{" "}
            {conDelta.length > 0
              ? `${conDelta.length} cambiarían con el USD actual.`
              : "Todos coinciden con la fórmula actual."}
          </p>
        </div>
        <Button
          variant="ghost" size="sm"
          onClick={() => setExpanded((e) => !e)}
          className="shrink-0 h-7 text-xs"
        >
          {expanded ? "Ocultar" : "Revisar"}
        </Button>
      </div>

      {expanded && (
        <div className="rounded-md border hairline bg-muted/20 max-h-96 overflow-y-auto">
          {conDelta.length > 0 && (
            <div className="sticky top-0 z-10 flex items-center justify-between gap-2 px-3 py-2 border-b hairline bg-background/95 backdrop-blur">
              <button
                type="button"
                onClick={toggleAll}
                className="text-[11px] underline hover:text-ink"
              >
                {selected.size === conDelta.length ? "Deseleccionar todos" : "Seleccionar todos los que cambian"}
              </button>
              <Button
                size="sm" className="h-7 text-xs"
                disabled={selected.size === 0}
                onClick={() => onRecalcSelected([...selected])}
              >
                Recalcular {selected.size > 0 ? `(${selected.size})` : ""}
              </Button>
            </div>
          )}
          <table className="w-full text-xs">
            <thead className="text-[10px] uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="text-left px-3 py-1.5 w-8"></th>
                <th className="text-left px-3 py-1.5">Equipo</th>
                <th className="text-right px-3 py-1.5">Actual</th>
                <th className="text-right px-3 py-1.5">Si recalcula</th>
                <th className="text-right px-3 py-1.5">Δ</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => {
                const cambia = it.delta != null && it.delta !== 0;
                return (
                  <tr key={it.id} className="border-t hairline">
                    <td className="px-3 py-1.5">
                      <input
                        type="checkbox"
                        checked={selected.has(it.id)}
                        disabled={!cambia}
                        onChange={() => toggleOne(it.id)}
                        className="cursor-pointer"
                      />
                    </td>
                    <td className="px-3 py-1.5 text-ink">
                      {it.nombre}
                      {(it.marca || it.modelo) && (
                        <span className="text-muted-foreground">
                          {" "}— {[it.marca, it.modelo].filter(Boolean).join(" / ")}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums">
                      {fmtPrecio(it.precio_actual)}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">
                      {fmtPrecio(it.precio_calculado)}
                    </td>
                    <td className={
                      "px-3 py-1.5 text-right tabular-nums " +
                      (cambia ? (it.delta! > 0 ? "text-emerald-600" : "text-destructive") : "text-muted-foreground")
                    }>
                      {cambia
                        ? `${it.delta! > 0 ? "+" : ""}${fmtPrecio(it.delta).slice(1)}`
                        : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

