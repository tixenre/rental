import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { authedFetch } from "@/lib/authedFetch";

export const Route = createFileRoute("/cliente/registro")({
  head: () => ({ meta: [{ title: "Completá tu registro — Rambla Rental" }] }),
  component: ClienteRegistroPage,
});

function ClienteRegistroPage() {
  const navigate = useNavigate();
  const [info, setInfo] = useState<{ email: string; name: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [form, setForm] = useState({
    nombre: "", apellido: "", telefono: "",
    direccion: "", cuit: "", perfil_impuestos: "consumidor_final",
  });

  const token = new URLSearchParams(window.location.search).get("t") ?? "";

  useEffect(() => {
    if (!token) { navigate({ to: "/cliente/login" }); return; }
    authedFetch(`/api/cliente/registro-info?t=${encodeURIComponent(token)}`)
      .then(async (r) => {
        if (r.ok) {
          const data = await r.json();
          setInfo(data);
          const parts = (data.name as string).split(" ");
          setForm((f) => ({ ...f, nombre: parts[0] ?? "", apellido: parts.slice(1).join(" ") }));
        } else {
          const d = await r.json().catch(() => ({}));
          setError(d.detail ?? "Token inválido o expirado. Volvé a iniciar sesión con Google.");
        }
      })
      .catch(() => setError("Error de red. Intentá de nuevo."));
  }, [token, navigate]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.nombre.trim() || !form.apellido.trim() || !form.telefono.trim()) {
      setError("Nombre, apellido y teléfono son obligatorios.");
      return;
    }
    setSending(true);
    setError(null);
    try {
      const r = await authedFetch("/api/cliente/registro", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, ...form }),
      });
      if (r.ok) {
        navigate({ to: "/cliente/portal" });
      } else {
        const d = await r.json().catch(() => ({}));
        setError(d.detail ?? "Error al registrarse. Intentá de nuevo.");
      }
    } catch {
      setError("Error de red. Intentá de nuevo.");
    } finally {
      setSending(false);
    }
  }

  if (!info && !error) {
    return (
      <div className="min-h-screen grid place-items-center text-sm text-muted-foreground">
        Verificando…
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background grid place-items-center px-4 py-12">
      <div className="w-full max-w-sm rounded-2xl border hairline bg-surface p-8 shadow-sm space-y-6">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Portal de clientes
          </div>
          <h1 className="mt-1 font-display text-2xl text-ink">Completá tu perfil</h1>
          {info && (
            <p className="mt-1 text-xs text-muted-foreground">
              Cuenta Google: <span className="font-medium text-ink">{info.email}</span>
            </p>
          )}
        </div>

        {error && (
          <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
            {error}
          </div>
        )}

        {info && (
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Nombre *" value={form.nombre}
                onChange={(v) => setForm((f) => ({ ...f, nombre: v }))} />
              <Field label="Apellido *" value={form.apellido}
                onChange={(v) => setForm((f) => ({ ...f, apellido: v }))} />
            </div>
            <Field label="Teléfono *" type="tel" value={form.telefono}
              onChange={(v) => setForm((f) => ({ ...f, telefono: v }))} />
            <Field label="Dirección" value={form.direccion}
              onChange={(v) => setForm((f) => ({ ...f, direccion: v }))} />
            <Field label="CUIT / DNI" value={form.cuit}
              onChange={(v) => setForm((f) => ({ ...f, cuit: v }))} />
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">
                Perfil impositivo
              </label>
              <select
                value={form.perfil_impuestos}
                onChange={(e) => setForm((f) => ({ ...f, perfil_impuestos: e.target.value }))}
                className="w-full rounded-md border hairline bg-background px-3 py-2 text-sm text-ink focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="consumidor_final">Consumidor final</option>
                <option value="responsable_inscripto">Responsable inscripto</option>
                <option value="monotributo">Monotributo</option>
                <option value="exento">Exento</option>
              </select>
            </div>
            <button
              type="submit"
              disabled={sending}
              className="w-full rounded-md bg-ink py-2.5 text-sm font-medium text-background transition hover:opacity-90 active:scale-[0.98] disabled:opacity-50"
            >
              {sending ? "Guardando…" : "Completar registro"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

function Field({
  label, value, onChange, type = "text",
}: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  return (
    <div>
      <label className="block text-xs font-medium text-muted-foreground mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border hairline bg-background px-3 py-2 text-sm text-ink focus:outline-none focus:ring-1 focus:ring-ring"
      />
    </div>
  );
}
