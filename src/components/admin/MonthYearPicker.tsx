/**
 * MonthYearPicker — selector simple de mes + año.
 *
 * Para campos donde el día no importa (ej: fecha de compra de un equipo —
 * issue #109). Almacena como string "YYYY-MM" para compatibilidad con
 * fecha ISO ordenable.
 *
 * Acepta también valores legacy "YYYY-MM-DD" (date input) y los parsea
 * para extraer mes/año.
 */

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const MESES_ES = [
  "Enero",
  "Febrero",
  "Marzo",
  "Abril",
  "Mayo",
  "Junio",
  "Julio",
  "Agosto",
  "Septiembre",
  "Octubre",
  "Noviembre",
  "Diciembre",
] as const;

function parseValue(v: string | null | undefined): { year: string; month: string } {
  if (!v) return { year: "", month: "" };
  // Acepta "YYYY-MM" o "YYYY-MM-DD"
  const m = v.match(/^(\d{4})-(\d{2})/);
  if (!m) return { year: "", month: "" };
  return { year: m[1], month: m[2] };
}

const CURRENT_YEAR = new Date().getFullYear();
const YEARS = Array.from({ length: 25 }, (_, i) => String(CURRENT_YEAR - i));

export function MonthYearPicker({
  value,
  onChange,
}: {
  value: string | null | undefined;
  onChange: (v: string) => void;
}) {
  const { year, month } = parseValue(value);

  const update = (newYear: string, newMonth: string) => {
    if (!newYear || !newMonth) {
      onChange("");
      return;
    }
    onChange(`${newYear}-${newMonth}`);
  };

  return (
    <div className="grid grid-cols-2 gap-1.5">
      <Select value={month} onValueChange={(v) => update(year || String(CURRENT_YEAR), v)}>
        <SelectTrigger>
          <SelectValue placeholder="Mes" />
        </SelectTrigger>
        <SelectContent>
          {MESES_ES.map((m, i) => {
            const monthValue = String(i + 1).padStart(2, "0");
            return (
              <SelectItem key={monthValue} value={monthValue}>
                {m}
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>
      <Select value={year} onValueChange={(v) => update(v, month || "01")}>
        <SelectTrigger>
          <SelectValue placeholder="Año" />
        </SelectTrigger>
        <SelectContent>
          {YEARS.map((y) => (
            <SelectItem key={y} value={y}>
              {y}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

/**
 * Display human-readable de un valor YYYY-MM. Ej: "2024-03" → "marzo 2024".
 */
export function formatMonthYear(value: string | null | undefined): string {
  const { year, month } = parseValue(value);
  if (!year || !month) return "—";
  const monthIdx = parseInt(month, 10) - 1;
  if (monthIdx < 0 || monthIdx > 11) return "—";
  return `${MESES_ES[monthIdx].toLowerCase()} ${year}`;
}
