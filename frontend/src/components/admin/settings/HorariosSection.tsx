/**
 * HorariosSection — TODOS los settings de horas del alquiler en una sola
 * card (antes repartidos en 3 secciones sin relación visible: ex-
 * `LeadTimeSection`, ex-`BufferSection` y esta misma): antelación mínima,
 * buffer entre alquileres, horarios habilitados por día, y el TEXTO de los
 * dos avisos que arma `services/fechas.py::disclaimers_retiro` (#1237) —
 * antes hardcodeado en Python, ahora editable para no tener que pedir un
 * cambio de código por una coma.
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { Textarea } from "@/design-system/ui/textarea";
import { Spinner } from "@/design-system/ui/spinner";

import { adminApi } from "@/lib/admin/api";

// ── Buffer entre alquileres (motor de reservas) ─────────────────────────────

function BufferBlock() {
  const qc = useQueryClient();
  const [valor, setValor] = useState("");

  const settingQ = useQuery({
    queryKey: ["settings", "buffer_horas_alquiler"],
    queryFn: () => adminApi.getSetting("buffer_horas_alquiler"),
    staleTime: 0,
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
    <div className="space-y-2">
      <div>
        <h3 className="text-sm font-semibold text-ink">Buffer entre alquileres</h3>
        <p className="text-xs text-muted-foreground mt-0.5">
          Horas de prep/revisión exigidas entre que un equipo vuelve y sale de nuevo. Con buffer
          &gt; 0, dos alquileres del mismo equipo no pueden quedar pegados (respeta la hora de
          retiro/devolución). Poné 0 para permitir alquileres consecutivos. Ej: 24 = un día.
        </p>
      </div>
      <div className="flex items-end gap-2">
        <div className="space-y-1">
          <div className="text-2xs uppercase tracking-wide text-muted-foreground">
            Horas de buffer
          </div>
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
    </div>
  );
}

// ── Antelación mínima (lead-time, #1126) ────────────────────────────────────

function LeadTimeBlock() {
  const qc = useQueryClient();
  const [valor, setValor] = useState("");

  const settingQ = useQuery({
    queryKey: ["settings", "antelacion_minima_horas"],
    queryFn: () => adminApi.getSetting("antelacion_minima_horas"),
    staleTime: 0,
  });

  useEffect(() => {
    if (settingQ.data && valor === "") setValor(settingQ.data.value ?? "0");
  }, [settingQ.data, valor]);

  const updateMut = useMutation({
    mutationFn: (v: string) => adminApi.updateSetting("antelacion_minima_horas", v),
    onSuccess: () => {
      toast.success("Antelación mínima actualizada");
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const actual = settingQ.data?.value ?? "0";
  const dirty = valor.trim() !== actual && valor.trim() !== "";

  return (
    <div className="space-y-2">
      <div>
        <h3 className="text-sm font-semibold text-ink">Antelación mínima</h3>
        <p className="text-xs text-muted-foreground mt-0.5">
          Horas mínimas entre el pedido y el retiro para reservar online. Dentro de esa ventana el
          cliente no puede confirmar por la web (ve el aviso de abajo). Poné 0 para desactivarlo. El
          admin nunca queda limitado.
        </p>
      </div>
      <div className="flex items-end gap-2">
        <div className="space-y-1">
          <div className="text-2xs uppercase tracking-wide text-muted-foreground">
            Horas de antelación
          </div>
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
    </div>
  );
}

// ── Horarios habilitados por día ─────────────────────────────────────────────

const DIAS_ORDEN: Array<[string, string]> = [
  ["lun", "Lunes"],
  ["mar", "Martes"],
  ["mie", "Miércoles"],
  ["jue", "Jueves"],
  ["vie", "Viernes"],
  ["sab", "Sábado"],
  ["dom", "Domingo"],
];
type DiaCfg = { abierto: boolean; desde: string; hasta: string };
const DEFAULT_DIA: DiaCfg = { abierto: true, desde: "09:00", hasta: "18:00" };

function HorariosGridBlock() {
  const qc = useQueryClient();
  const [cfg, setCfg] = useState<Record<string, DiaCfg> | null>(null);

  const settingQ = useQuery({
    queryKey: ["settings", "horarios_retiro"],
    queryFn: () => adminApi.getSetting("horarios_retiro"),
    retry: false,
    staleTime: 0,
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
        next[key] = f
          ? { abierto: true, desde: f.desde, hasta: f.hasta }
          : { ...DEFAULT_DIA, abierto: false };
      } else {
        // Sin config previa: plantilla L-V abierto 09-18, finde cerrado.
        next[key] =
          key === "sab" || key === "dom" ? { ...DEFAULT_DIA, abierto: false } : { ...DEFAULT_DIA };
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
        toast.error(
          `${DIAS_ORDEN.find(([k]) => k === key)?.[1]}: la apertura debe ser anterior al cierre`,
        );
        return;
      }
      payload[key] = d.abierto ? { desde: d.desde, hasta: d.hasta } : null;
    }
    updateMut.mutate(JSON.stringify(payload));
  };

  return (
    <div className="space-y-2">
      <div>
        <h3 className="text-sm font-semibold text-ink">Horarios de retiro y devolución</h3>
        <p className="text-xs text-muted-foreground mt-0.5">
          Franja horaria habilitada por día para que el cliente elija retiro y devolución (misma
          franja para ambos). Los días cerrados no se pueden seleccionar. Aplica al checkout del
          cliente — los pedidos cargados a mano en el back-office no se restringen.
        </p>
      </div>
      <div className="space-y-2">
        {cfg &&
          DIAS_ORDEN.map(([key, label]) => {
            const d = cfg[key];
            return (
              <div key={key} className="flex items-center gap-3">
                <label className="flex items-center gap-2 w-40 shrink-0 text-sm">
                  {/* eslint-disable-next-line no-restricted-syntax -- checkbox nativo: el DS Checkbox es Radix (otra API) */}
                  <input
                    type="checkbox"
                    checked={d.abierto}
                    onChange={(e) => setDia(key, { abierto: e.target.checked })}
                  />
                  <span className={d.abierto ? "text-ink" : "text-muted-foreground line-through"}>
                    {label}
                  </span>
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
    </div>
  );
}

// ── Texto de los avisos del picker (#1237) ───────────────────────────────────
// Antes hardcodeado en `services/fechas.py::disclaimers_retiro` — ahora
// editable acá (vacío = vuelve al texto por defecto, misma convención que
// `ContactoSection`). El backend sigue siendo dueño de la REGLA (¿corresponde
// avisar?); esto solo cambia la redacción.

type DisclaimerField = {
  key: "disclaimer_antelacion_texto" | "disclaimer_horarios_finde_texto";
  label: string;
  placeholder: string;
  helper: string;
};

const DISCLAIMER_FIELDS: DisclaimerField[] = [
  {
    key: "disclaimer_antelacion_texto",
    label: "Aviso de antelación mínima",
    placeholder:
      "Reservás online con al menos {horas} h de anticipación, por eso no ves horas más cercanas a ahora.",
    helper:
      "Aparece cuando la antelación mínima de arriba está prendida. Usá {horas} para insertar el número configurado.",
  },
  {
    key: "disclaimer_horarios_finde_texto",
    label: "Aviso de horarios de fin de semana",
    placeholder: "Sábados y domingos tenemos horarios reducidos.",
    helper:
      "Aparece solo si el cliente elige un sábado o domingo con horario más corto que un día de semana.",
  },
];

function DisclaimerFieldRow({ field }: { field: DisclaimerField }) {
  const qc = useQueryClient();
  const settingQ = useQuery({
    queryKey: ["settings", field.key],
    queryFn: () => adminApi.getSetting(field.key),
    retry: false,
    staleTime: 0,
  });
  const [value, setValue] = useState("");
  useEffect(() => {
    if (settingQ.isFetched && value === "") setValue(settingQ.data?.value ?? "");
  }, [settingQ.isFetched, settingQ.data, value]);

  const mut = useMutation({
    mutationFn: (v: string) => adminApi.updateSetting(field.key, v),
    onSuccess: (data) => {
      toast.success(`${field.label} guardado`);
      qc.setQueryData(["settings", field.key], data);
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const trimmed = value.trim();
  const saved = (settingQ.data?.value ?? "").trim();
  const changed = trimmed !== saved;

  return (
    <div className="space-y-1.5">
      <div className="text-xs font-medium text-ink">{field.label}</div>
      <Textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={field.placeholder}
        rows={3}
        className="text-sm"
      />
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">{field.helper}</p>
        <Button
          type="button"
          size="sm"
          disabled={!changed || mut.isPending}
          onClick={() => mut.mutate(trimmed)}
        >
          {mut.isPending ? <Spinner size="sm" /> : <Check className="h-4 w-4" />}
        </Button>
      </div>
    </div>
  );
}

// ── Section ──────────────────────────────────────────────────────────────────

export function HorariosSection() {
  return (
    <section className="card p-4 space-y-5">
      <div>
        <h2 className="font-display text-lg text-ink">Horarios</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Todos los settings de horas del alquiler: espaciado entre alquileres del motor de
          reservas, cuánta antelación pedís y qué horarios habilitás en el selector de fechas del
          catálogo público, y qué texto ve el cliente en los avisos.
        </p>
      </div>

      <BufferBlock />

      <div className="border-t hairline pt-4">
        <LeadTimeBlock />
      </div>

      <div className="border-t hairline pt-4">
        <HorariosGridBlock />
      </div>

      <div className="border-t hairline pt-4 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-ink">Texto de los avisos</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Editá la redacción que ve el cliente en el picker. Vacío = vuelve al texto por defecto.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {DISCLAIMER_FIELDS.map((f) => (
            <DisclaimerFieldRow key={f.key} field={f} />
          ))}
        </div>
      </div>
    </section>
  );
}
