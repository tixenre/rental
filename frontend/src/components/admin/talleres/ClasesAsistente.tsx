import { useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";

import type { ClaseBody } from "@/lib/admin/api/types";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import { HoraSelect } from "./HoraSelect";

const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

function generarClasesSemanales(
  diaSemana: number,
  mesDesde: string,
  mesHasta: string,
  horaInicio: number,
  horaFin: number,
): ClaseBody[] {
  const [yD, mD] = mesDesde.split("-").map(Number);
  const [yH, mH] = mesHasta.split("-").map(Number);
  const end = new Date(yH, mH, 0);
  const jsDay = (diaSemana + 1) % 7;
  const cur = new Date(yD, mD - 1, 1);
  while (cur.getDay() !== jsDay) cur.setDate(cur.getDate() + 1);
  const result: ClaseBody[] = [];
  while (cur <= end) {
    result.push({
      fecha: cur.toISOString().slice(0, 10),
      hora_inicio: horaInicio,
      hora_fin: horaFin,
    });
    cur.setDate(cur.getDate() + 7);
  }
  return result;
}

export function ClasesAsistente({
  tipo,
  onTipoChange,
  clases,
  onChange,
}: {
  tipo: string;
  onTipoChange: (t: string) => void;
  clases: ClaseBody[];
  onChange: (s: ClaseBody[]) => void;
}) {
  const [newFecha, setNewFecha] = useState("");
  const [newIni, setNewIni] = useState(9);
  const [newFin, setNewFin] = useState(13);
  const [diaSemana, setDiaSemana] = useState(0);
  const [mesDesde, setMesDesde] = useState("");
  const [mesHasta, setMesHasta] = useState("");
  const [semIni, setSemIni] = useState(9);
  const [semFin, setSemFin] = useState(13);

  function addIntensivo() {
    if (!newFecha) {
      toast.error("Ingresá una fecha");
      return;
    }
    if (newIni >= newFin) {
      toast.error("Hora inicio debe ser menor a hora fin");
      return;
    }
    if (clases.find((s) => s.fecha === newFecha)) {
      toast.error("Esa fecha ya está en la lista");
      return;
    }
    onChange(
      [...clases, { fecha: newFecha, hora_inicio: newIni, hora_fin: newFin }].sort((a, b) =>
        a.fecha.localeCompare(b.fecha),
      ),
    );
    setNewFecha("");
  }

  function generateSemanal() {
    if (!mesDesde || !mesHasta) {
      toast.error("Ingresá ambos meses");
      return;
    }
    if (mesDesde > mesHasta) {
      toast.error("El mes desde debe ser anterior al hasta");
      return;
    }
    if (semIni >= semFin) {
      toast.error("Hora inicio debe ser menor a hora fin");
      return;
    }
    const generated = generarClasesSemanales(diaSemana, mesDesde, mesHasta, semIni, semFin);
    const existingDates = new Set(generated.map((g) => g.fecha));
    const kept = clases.filter((s) => !existingDates.has(s.fecha));
    onChange([...kept, ...generated].sort((a, b) => a.fecha.localeCompare(b.fecha)));
    toast.success(`${generated.length} clases generadas`);
  }

  function remove(fecha: string) {
    onChange(clases.filter((s) => s.fecha !== fecha));
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground shrink-0">
          Tipo
        </span>
        <Select value={tipo} onValueChange={onTipoChange}>
          <SelectTrigger className="w-[180px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="intensivo">Intensivo</SelectItem>
            <SelectItem value="semanal">Semanal</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {tipo === "intensivo" && (
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Fecha</label>
            <Input
              type="date"
              value={newFecha}
              onChange={(e) => setNewFecha(e.target.value)}
              className="w-[160px]"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Desde (h)</label>
            <HoraSelect value={newIni} onChange={setNewIni} min={0} max={23} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Hasta (h)</label>
            <HoraSelect value={newFin} onChange={setNewFin} min={1} max={24} />
          </div>
          <Button variant="outline" size="sm" onClick={addIntensivo} className="gap-1.5">
            <Plus className="h-3.5 w-3.5" />
            Agregar fecha
          </Button>
        </div>
      )}

      {tipo === "semanal" && (
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Día</label>
            <Select value={String(diaSemana)} onValueChange={(v) => setDiaSemana(Number(v))}>
              <SelectTrigger className="w-[130px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DIAS.map((d, i) => (
                  <SelectItem key={i} value={String(i)}>
                    {d}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Desde (mes)</label>
            <Input
              type="month"
              value={mesDesde}
              onChange={(e) => setMesDesde(e.target.value)}
              className="w-[140px]"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Hasta (mes)</label>
            <Input
              type="month"
              value={mesHasta}
              onChange={(e) => setMesHasta(e.target.value)}
              className="w-[140px]"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Desde (h)</label>
            <HoraSelect value={semIni} onChange={setSemIni} min={0} max={23} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Hasta (h)</label>
            <HoraSelect value={semFin} onChange={setSemFin} min={1} max={24} />
          </div>
          <Button variant="outline" size="sm" onClick={generateSemanal} className="gap-1.5">
            <Plus className="h-3.5 w-3.5" />
            Generar
          </Button>
        </div>
      )}

      {clases.length > 0 ? (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
            {clases.length} clase{clases.length !== 1 ? "s" : ""} · bloquean el estudio en esas
            franjas
          </p>
          <div className="flex flex-wrap gap-1.5">
            {clases.map((s) => (
              <span
                key={s.fecha}
                className="inline-flex items-center gap-1.5 rounded-full bg-muted/40 border border-border/50 px-3 py-1 text-xs"
              >
                {new Date(s.fecha + "T12:00:00").toLocaleDateString("es-AR", {
                  weekday: "short",
                  day: "numeric",
                  month: "short",
                })}
                <span className="text-muted-foreground">
                  {s.hora_inicio}–{s.hora_fin}h
                </span>
                <button
                  onClick={() => remove(s.fecha)}
                  className="ml-0.5 h-6 w-6 flex items-center justify-center text-muted-foreground/60 hover:text-destructive transition rounded"
                  aria-label="Quitar"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground/60 italic">
          Sin clases. Agregá al menos una para bloquear el estudio.
        </p>
      )}
    </div>
  );
}
