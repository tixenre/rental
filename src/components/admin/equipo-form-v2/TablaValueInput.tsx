/**
 * Editor para specs tipo `tabla`. El value se serializa como JSON array
 * de rows: `[{key1: v1, key2: v2}, ...]`. Cada columna define key + tipo
 * (string/number/enum/bool) y se renderiza el input correspondiente.
 *
 * Caso de uso típico: spec Lúmenes con columnas (temperatura, valor) →
 * el dueño carga una fila por temperatura (5700K, 3200K, etc.) y el
 * sistema queda comparable entre luces.
 */

import { useEffect, useRef, useState } from "react";
import { Plus, Trash2, ClipboardPaste } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import type { SpecTablaColumna } from "@/lib/admin/api";

/** Para columnas tipo `valor_unidad`, cada celda guarda un objeto con
 *  número + unidad. El resto de tipos guarda un escalar (string/number/bool). */
type ValorUnidad = { valor: number | string; unidad: string };
type CellValue = string | number | boolean | ValorUnidad;
type TablaRow = Record<string, CellValue>;

function isValorUnidad(v: unknown): v is ValorUnidad {
  return typeof v === "object" && v !== null && "valor" in v && "unidad" in v;
}

function parseValue(value: string): TablaRow[] {
  if (!value?.trim()) return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function filterEmptyRows(rows: TablaRow[], columnas: SpecTablaColumna[]): TablaRow[] {
  return rows
    .map((r) => {
      const out: TablaRow = {};
      for (const c of columnas) {
        const v = r[c.key];
        if (v === undefined || v === null || v === "") continue;
        if (isValorUnidad(v)) {
          const valOk = v.valor !== "" && v.valor !== undefined;
          const uniOk = !!(v.unidad ?? "").toString().trim();
          if (valOk || uniOk) out[c.key] = v;
        } else {
          out[c.key] = v;
        }
      }
      return out;
    })
    .filter((r) => Object.keys(r).length > 0);
}

export function TablaValueInput({
  value,
  columnas,
  onChange,
  disabled,
}: {
  value: string;
  columnas: SpecTablaColumna[];
  onChange: (next: string) => void;
  disabled?: boolean;
}) {
  // State local: incluye rows en blanco recién agregadas. Solo serializa al
  // padre las rows que tienen al menos un valor (vía filterEmptyRows).
  // El bug anterior era que `addRow` agregaba `{}` y el filtro lo descartaba,
  // así que la fila vacía nunca volvía del padre → no se renderizaba.
  const [localRows, setLocalRows] = useState<TablaRow[]>(() => parseValue(value));
  // Para evitar loop: el último value que emitimos al padre. Si el value
  // que llega coincide, no resync.
  const lastEmittedRef = useRef<string>(value ?? "");

  useEffect(() => {
    // Si el padre cambió el value externamente (no por nuestro onChange),
    // resincronizar. La comparación es contra el último que emitimos.
    if ((value ?? "") !== lastEmittedRef.current) {
      setLocalRows(parseValue(value));
      lastEmittedRef.current = value ?? "";
    }
  }, [value]);

  function commit(nextRows: TablaRow[]) {
    setLocalRows(nextRows);
    const cleaned = filterEmptyRows(nextRows, columnas);
    const serialized = cleaned.length ? JSON.stringify(cleaned) : "";
    lastEmittedRef.current = serialized;
    onChange(serialized);
  }

  function setCell(rowIdx: number, key: string, v: CellValue) {
    commit(localRows.map((r, i) => (i === rowIdx ? { ...r, [key]: v } : r)));
  }

  function addRow() {
    commit([...localRows, {}]);
  }

  function removeRow(idx: number) {
    commit(localRows.filter((_, i) => i !== idx));
  }

  /** Paste-from-CSV: parsea texto multilínea con separadores `,` / tab / `;`
   *  y agrega N filas mapeando columnas en orden. Útil para meter una tabla
   *  copiada de B&H / Excel sin clickear celda por celda. */
  function pasteCsv(text: string) {
    const lines = text
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean);
    if (lines.length === 0) return 0;
    const newRows: TablaRow[] = [];
    for (const line of lines) {
      // Separador: tab si lo hay (paste de Excel/Sheets), si no `,` o `;`.
      const hasTab = line.includes("\t");
      const parts = hasTab ? line.split("\t") : line.split(/[,;]/).map((p) => p.trim());
      const row: TablaRow = {};
      for (let i = 0; i < columnas.length && i < parts.length; i++) {
        const c = columnas[i];
        const raw = (parts[i] ?? "").trim();
        if (!raw) continue;
        if (c.tipo === "number") {
          const n = Number(raw);
          row[c.key] = Number.isFinite(n) ? n : raw;
        } else if (c.tipo === "bool") {
          row[c.key] = ["true", "1", "yes", "sí", "si"].includes(raw.toLowerCase());
        } else if (c.tipo === "valor_unidad") {
          // Acepta "10000 lm" o "10000". Si la columna tiene una sola unidad
          // permitida, la usa; sino, intenta partir por espacio.
          const m = raw.match(/^([\d.]+)\s*(.*)$/);
          if (m) {
            const valor = Number.isFinite(Number(m[1])) ? Number(m[1]) : m[1];
            const opts = c.unidades_opciones ?? [];
            const unidad = m[2].trim()
              || (opts.length === 1 ? opts[0] : "");
            row[c.key] = { valor, unidad };
          } else {
            const opts = c.unidades_opciones ?? [];
            row[c.key] = { valor: raw, unidad: opts.length === 1 ? opts[0] : "" };
          }
        } else {
          row[c.key] = raw;
        }
      }
      if (Object.keys(row).length > 0) newRows.push(row);
    }
    if (newRows.length === 0) return 0;
    commit([...localRows, ...newRows]);
    return newRows.length;
  }

  const rows = localRows;

  if (!columnas?.length) {
    return (
      <div className="text-xs text-muted-foreground italic">
        Spec tipo tabla sin columnas definidas — configurá en /admin/specs/definitions.
      </div>
    );
  }

  // Construye un grid template que intercala columnas con sus conectores.
  // Ej. 2 columnas, col[1].prefijo="a" → "1fr auto 1fr auto" (col, sep, col, btn).
  const colsWithConnectors: ("col" | "sep")[] = [];
  for (let i = 0; i < columnas.length; i++) {
    if (i > 0 && columnas[i].prefijo) colsWithConnectors.push("sep");
    colsWithConnectors.push("col");
  }
  const gridTemplate = [
    ...colsWithConnectors.map((k) => (k === "col" ? "1fr" : "auto")),
    "auto",
  ].join(" ");

  return (
    <div className="space-y-1.5">
      <PasteCsvSection columnas={columnas} onPaste={pasteCsv} disabled={disabled} />

      {/* Header. Si valor_unidad tiene UNA sola unidad fija (definida en la
          spec), la pegamos al label como sufijo y la celda solo pide número. */}
      <div className="grid gap-1.5 px-1 text-[10px] font-mono uppercase tracking-wider text-muted-foreground"
           style={{ gridTemplateColumns: gridTemplate }}>
        {columnas.map((c, i) => {
          const opts = c.unidades_opciones ?? [];
          const onlyOneUnit = c.tipo === "valor_unidad" && opts.length === 1;
          const fixedUnit = onlyOneUnit ? opts[0] : (c.tipo !== "valor_unidad" ? c.unidad : null);
          const showSubHeaders = c.tipo === "valor_unidad" && !onlyOneUnit;
          return (
            <>
              {i > 0 && c.prefijo && <div key={`sep-h-${i}`} aria-hidden />}
              <div key={c.key} className="space-y-0.5">
                <div>
                  {c.label}
                  {fixedUnit ? <span className="opacity-60"> · {fixedUnit}</span> : null}
                </div>
                {showSubHeaders && (
                  <div className="grid grid-cols-2 gap-1 normal-case text-[9px] tracking-normal opacity-70">
                    <span>número</span>
                    <span>unidad</span>
                  </div>
                )}
              </div>
            </>
          );
        })}
        <div className="w-7" />
      </div>

      {/* Rows */}
      {rows.length === 0 && (
        <div className="text-xs text-muted-foreground italic py-1">
          Sin filas. Agregá una para empezar.
        </div>
      )}
      {rows.map((row, idx) => (
        <div
          key={idx}
          className="grid gap-1.5 items-center"
          style={{ gridTemplateColumns: gridTemplate }}
        >
          {columnas.map((c, i) => (
            <>
              {i > 0 && c.prefijo && (
                <div
                  key={`sep-${idx}-${i}`}
                  className="text-xs text-muted-foreground italic px-1 select-none"
                  aria-hidden
                >
                  {c.prefijo}
                </div>
              )}
              <CellInput
                key={c.key}
                col={c}
                value={row[c.key]}
                disabled={disabled}
                onChange={(v) => setCell(idx, c.key, v)}
              />
            </>
          ))}
          <button
            type="button"
            disabled={disabled}
            onClick={() => removeRow(idx)}
            className="h-8 w-7 inline-flex items-center justify-center text-muted-foreground hover:text-destructive disabled:opacity-40"
            title="Borrar fila"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}

      {/* Add row */}
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={addRow}
        disabled={disabled}
        className="h-7 px-2 text-xs gap-1"
      >
        <Plus className="h-3 w-3" /> Agregar fila
      </Button>
    </div>
  );
}

function PasteCsvSection({
  columnas,
  onPaste,
  disabled,
}: {
  columnas: SpecTablaColumna[];
  onPaste: (text: string) => number;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const colsExample = columnas
    .slice(0, 4)
    .map((c) => c.label)
    .join(" / ");
  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        disabled={disabled}
        className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-muted-foreground hover:text-ink disabled:opacity-40"
      >
        <ClipboardPaste className="h-3 w-3" />
        Pegar CSV
      </button>
    );
  }
  return (
    <div className="rounded-md border hairline bg-muted/10 p-2 space-y-1">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
          Pegar CSV ({colsExample})
        </span>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="text-[10px] text-muted-foreground hover:text-ink"
        >
          cerrar
        </button>
      </div>
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={
          "Pega filas separadas por línea, celdas por coma/tab.\n"
          + "Ej: 10000, 5700\n     8000, 3200"
        }
        rows={3}
        className="font-mono text-xs"
      />
      <div className="flex justify-end gap-1">
        <Button
          size="sm"
          variant="outline"
          onClick={() => setText("")}
          disabled={!text || disabled}
          className="h-6 px-2 text-[10px]"
        >
          Limpiar
        </Button>
        <Button
          size="sm"
          onClick={() => {
            const n = onPaste(text);
            if (n > 0) {
              setText("");
              setOpen(false);
            }
          }}
          disabled={!text.trim() || disabled}
          className="h-6 px-2 text-[10px]"
        >
          Agregar filas
        </Button>
      </div>
    </div>
  );
}


function CellInput({
  col,
  value,
  onChange,
  disabled,
}: {
  col: SpecTablaColumna;
  value: CellValue | undefined;
  onChange: (v: CellValue) => void;
  disabled?: boolean;
}) {
  if (col.tipo === "valor_unidad") {
    const opciones = col.unidades_opciones ?? [];
    const onlyOneUnit = opciones.length === 1;
    // Si solo hay una unidad permitida, la unidad ya está implícita: no
    // pedimos al usuario que la elija, la seteamos sola al cambiar el número.
    const baseUnidad = isValorUnidad(value) ? value.unidad : "";
    const vu: ValorUnidad = isValorUnidad(value)
      ? value
      : { valor: "", unidad: onlyOneUnit ? opciones[0] : "" };

    const updateValor = (raw: string) => {
      const valor = raw === "" ? "" : (Number.isFinite(Number(raw)) ? Number(raw) : raw);
      const unidad = onlyOneUnit ? opciones[0] : baseUnidad;
      onChange({ valor, unidad });
    };

    if (onlyOneUnit) {
      // Solo input numérico. La unidad va en el header.
      return (
        <Input
          type="number"
          value={vu.valor === "" ? "" : String(vu.valor)}
          onChange={(e) => updateValor(e.target.value)}
          disabled={disabled}
          className="h-8 text-xs"
          placeholder="número"
        />
      );
    }
    // 2+ opciones → dropdown. 0 opciones → input libre.
    const hasOpts = opciones.length > 1;
    return (
      <div className="grid grid-cols-2 gap-1">
        <Input
          type="number"
          value={vu.valor === "" ? "" : String(vu.valor)}
          onChange={(e) => updateValor(e.target.value)}
          disabled={disabled}
          className="h-8 text-xs"
          placeholder="número"
        />
        {hasOpts ? (
          <Select
            value={(vu.unidad ?? "") || "__empty"}
            onValueChange={(next) =>
              onChange({ ...vu, unidad: next === "__empty" ? "" : next })
            }
            disabled={disabled}
          >
            <SelectTrigger className="h-8 text-xs">
              <SelectValue placeholder="unidad" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__empty">—</SelectItem>
              {opciones.map((opt) => (
                <SelectItem key={opt} value={opt}>{opt}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <Input
            type="text"
            value={vu.unidad ?? ""}
            onChange={(e) => onChange({ ...vu, unidad: e.target.value })}
            disabled={disabled}
            className="h-8 text-xs"
            placeholder="unidad"
          />
        )}
      </div>
    );
  }
  const v = (isValorUnidad(value) ? "" : value) ?? "";
  if (col.tipo === "enum") {
    return (
      <Select
        value={String(v) || "__empty"}
        onValueChange={(next) => onChange(next === "__empty" ? "" : next)}
        disabled={disabled}
      >
        <SelectTrigger className="h-8 text-xs">
          <SelectValue placeholder={col.label} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="__empty">—</SelectItem>
          {(col.options ?? []).map((opt) => (
            <SelectItem key={opt} value={opt}>{opt}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }
  if (col.tipo === "bool") {
    const isYes = v === true || v === "true" || v === "1";
    return (
      <div className="flex gap-1">
        <Button
          type="button"
          size="sm"
          variant={isYes ? "default" : "outline"}
          onClick={() => onChange(true)}
          disabled={disabled}
          className="h-8 flex-1 text-xs"
        >Sí</Button>
        <Button
          type="button"
          size="sm"
          variant={!isYes && v !== "" ? "default" : "outline"}
          onClick={() => onChange(false)}
          disabled={disabled}
          className="h-8 flex-1 text-xs"
        >No</Button>
      </div>
    );
  }
  if (col.tipo === "number") {
    return (
      <Input
        type="number"
        value={v === "" ? "" : String(v)}
        onChange={(e) => {
          const raw = e.target.value;
          if (raw === "") {
            onChange("");
            return;
          }
          const num = Number(raw);
          onChange(Number.isFinite(num) ? num : raw);
        }}
        disabled={disabled}
        className="h-8 text-xs"
        placeholder={col.unidad ? `valor ${col.unidad}` : "valor"}
      />
    );
  }
  return (
    <Input
      type="text"
      value={String(v)}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      className="h-8 text-xs"
      placeholder={col.label}
    />
  );
}
