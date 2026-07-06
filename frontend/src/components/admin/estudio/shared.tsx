import { AdminSection } from "@/components/admin/AdminSection";

function slugifyForStorage(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

// Section/Field locales — Fase 2 (C27/C30) los reemplaza por los composites
// del DS. Se mantienen acá, no en el DS, porque son un paso intermedio.
export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  // Cada sección es colapsable y persiste su estado por título (slug).
  // Antes era un scroll lineal de ~900 líneas; ahora el dueño abre lo que
  // necesita y deja el resto cerrado.
  return (
    <AdminSection title={title} storageKey={`estudio:${slugifyForStorage(title)}`}>
      <section className="rounded-2xl border hairline bg-surface p-5 space-y-4">{children}</section>
    </AdminSection>
  );
}

export function Field({
  label,
  error,
  hint,
  children,
}: {
  label: string;
  error?: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <label className="t-eyebrow">{label}</label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
