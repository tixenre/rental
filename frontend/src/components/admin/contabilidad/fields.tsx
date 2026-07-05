/**
 * fields.tsx — controles chicos compartidos entre los forms de contabilidad
 * (NuevoMovimientoForm, CambioDivisaForm). Extraídos para no duplicar
 * (una sola forma de cada cosa).
 */
import type { Cuenta } from "@/lib/admin/api";

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="space-y-1">
      <span className="block t-eyebrow">{label}</span>
      {children}
    </label>
  );
}

export function CuentaSelect({
  cuentas,
  value,
  onChange,
}: {
  cuentas: Cuenta[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-9 rounded-md border hairline bg-surface-elevated px-2 text-sm"
    >
      <option value="">Elegir…</option>
      {cuentas.map((c) => (
        <option key={c.id} value={c.id}>
          {c.nombre}
        </option>
      ))}
    </select>
  );
}
