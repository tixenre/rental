/**
 * primitives.tsx — piezas chicas compartidas entre las secciones del portal
 * cliente: el bloque clasificado del perfil, el botón de guardar y el campo
 * de formulario con label + hint. El helper de PATCH vive aparte en
 * patchPerfil.ts (react-refresh no deja mezclar componentes con funciones
 * sueltas en el mismo .tsx).
 */
import { Spinner } from "@/design-system/ui/spinner";

// ── Bloque clasificado del perfil (separador + heading) ───────────────────────
// Una sola forma del bloque del perfil (DRY): identidad / contacto / facturación /
// métodos / sesiones comparten la misma cáscara.
export function Bloque({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-t hairline pt-6 mb-6">
      <h3 className="font-display text-lg font-black text-ink tracking-[-0.01em] mb-4">{title}</h3>
      {children}
    </div>
  );
}

// ── Botón guardar compartido (contacto + facturación) ─────────────────────────
export function SaveButton({ saving, disabled = false }: { saving: boolean; disabled?: boolean }) {
  return (
    <button
      type="submit"
      disabled={saving || disabled}
      className="w-full inline-flex items-center justify-center gap-2 rounded-[10px] bg-ink h-[46px] font-sans text-15 font-bold text-amber transition hover:bg-amber hover:text-ink disabled:opacity-50"
    >
      {saving ? (
        <>
          <Spinner size="sm" /> Guardando…
        </>
      ) : (
        "Guardar cambios"
      )}
    </button>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="block">
        <span className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
          {label}
        </span>
        {hint && <span className="block text-xs text-muted-foreground/80 mt-0.5">{hint}</span>}
      </label>
      {children}
    </div>
  );
}
