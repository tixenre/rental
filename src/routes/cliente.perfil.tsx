import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { authedFetch } from "@/lib/authedFetch";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

export const Route = createFileRoute("/cliente/perfil")({
  head: () => ({ meta: [{ title: "Mi perfil — Rambla Rental" }] }),
  component: PerfilPage,
});

type Perfil = {
  id: number;
  nombre: string;
  apellido: string;
  email: string;
  telefono: string;
  direccion: string;
  cuit?: string | null;
};

function PerfilPage() {
  const navigate = useNavigate();
  const [perfil, setPerfil] = useState<Perfil | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<Partial<Perfil>>({});

  useEffect(() => {
    let alive = true;
    authedFetch("/api/cliente/me")
      .then(async (r) => {
        if (!alive) return;
        if (!r.ok) { navigate({ to: "/cliente/login" }); return; }
        const data = (await r.json()) as Perfil;
        setPerfil(data);
        setForm({
          nombre: data.nombre,
          apellido: data.apellido,
          telefono: data.telefono,
          direccion: data.direccion,
          cuit: data.cuit ?? "",
        });
      })
      .catch(() => navigate({ to: "/cliente/login" }))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [navigate]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (saving) return;
    setSaving(true);
    try {
      const res = await authedFetch("/api/cliente/me", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail ?? `Error ${res.status}`);
      }
      const updated = (await res.json()) as Perfil;
      setPerfil(updated);
      toast.success("Perfil actualizado");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error al guardar");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="min-h-screen grid place-items-center text-sm text-muted-foreground">Cargando…</div>;
  }
  if (!perfil) return null;

  return (
    <div className="min-h-screen bg-background">
      {/* Header con branding */}
      <header className="border-b hairline bg-background sticky top-0 z-10">
        <div className="max-w-xl mx-auto px-4 h-14 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2 group">
            <span className="wordmark text-2xl text-amber leading-none group-hover:brightness-110 transition">rambla</span>
            <span className="font-mono text-[9px] uppercase tracking-[0.3em] text-foreground/70 border-l hairline pl-2">
              Rental
            </span>
          </a>
          <a href="/cliente/portal" className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-ink transition">
            ← Mis pedidos
          </a>
        </div>
      </header>

      {/* Sub-header amarillo */}
      <div className="bg-amber border-b hairline">
        <div className="max-w-xl mx-auto px-4 py-5">
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-ink/70">
            Portal de clientes
          </div>
          <h1 className="font-display text-3xl text-ink mt-1">Mi perfil</h1>
        </div>
      </div>

      <main className="max-w-xl mx-auto px-4 py-8">
        <form onSubmit={handleSave} className="space-y-5">
          <Field label="Email" hint="No se puede modificar (es tu identidad de login)">
            <input
              type="email"
              value={perfil.email}
              disabled
              className="w-full rounded-md border hairline bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
            />
          </Field>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Nombre">
              <input
                type="text"
                value={form.nombre ?? ""}
                onChange={(e) => setForm({ ...form, nombre: e.target.value })}
                className="w-full rounded-md border hairline bg-background px-3 py-2 text-sm text-ink"
                required
              />
            </Field>
            <Field label="Apellido">
              <input
                type="text"
                value={form.apellido ?? ""}
                onChange={(e) => setForm({ ...form, apellido: e.target.value })}
                className="w-full rounded-md border hairline bg-background px-3 py-2 text-sm text-ink"
              />
            </Field>
          </div>

          <Field label="Teléfono">
            <input
              type="tel"
              value={form.telefono ?? ""}
              onChange={(e) => setForm({ ...form, telefono: e.target.value })}
              placeholder="+54 9 223 ..."
              className="w-full rounded-md border hairline bg-background px-3 py-2 text-sm text-ink"
            />
          </Field>

          <Field label="Dirección">
            <input
              type="text"
              value={form.direccion ?? ""}
              onChange={(e) => setForm({ ...form, direccion: e.target.value })}
              placeholder="Calle, número, ciudad"
              className="w-full rounded-md border hairline bg-background px-3 py-2 text-sm text-ink"
            />
          </Field>

          <Field label="CUIT/CUIL" hint="Opcional — para facturación">
            <input
              type="text"
              value={form.cuit ?? ""}
              onChange={(e) => setForm({ ...form, cuit: e.target.value })}
              placeholder="20-12345678-9"
              className="w-full rounded-md border hairline bg-background px-3 py-2 text-sm text-ink"
            />
          </Field>

          <div className="pt-3">
            <button
              type="submit"
              disabled={saving}
              className="w-full inline-flex items-center justify-center gap-2 rounded-md bg-ink py-3 text-sm font-medium uppercase tracking-widest text-amber transition hover:brightness-110 disabled:opacity-50"
            >
              {saving ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Guardando…</>
              ) : (
                "Guardar cambios"
              )}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}

function Field({
  label, hint, children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="block">
        <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          {label}
        </span>
        {hint && (
          <span className="block text-[11px] text-muted-foreground/80 mt-0.5">{hint}</span>
        )}
      </label>
      {children}
    </div>
  );
}
