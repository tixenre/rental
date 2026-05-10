import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { authedFetch, authedPostJson } from "@/lib/authedFetch";

export const Route = createFileRoute("/admin/login")({
  head: () => ({
    meta: [
      { title: "Acceso admin — Rambla Rental" },
      { name: "robots", content: "noindex, nofollow" },
    ],
  }),
  component: AdminLoginPage,
});

function AdminLoginPage() {
  const navigate = useNavigate();
  const [setupNeeded, setSetupNeeded] = useState(false);
  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    authedFetch("/auth/config")
      .then((r) => r.json())
      .then((d) => setSetupNeeded(Boolean(d?.setup_needed)))
      .catch(() => undefined);

    // Si ya hay sesión, ir directo al admin.
    authedFetch("/auth/me").then((r) => {
      if (r.ok) navigate({ to: "/admin" });
    });
  }, [navigate]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      if (setupNeeded) {
        await authedPostJson("/auth/register", { nombre, email, password });
      } else {
        await authedPostJson("/auth/login-local", { email, password });
      }
      navigate({ to: "/admin" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesión");
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-background grid place-items-center px-4 py-12">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-2xl border hairline bg-surface p-8 shadow-sm space-y-4"
      >
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Back-office
          </div>
          <h1 className="mt-1 font-display text-2xl text-ink">
            {setupNeeded ? "Crear cuenta admin" : "Acceso admin"}
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            {setupNeeded
              ? "No hay usuarios todavía. Creá el primero."
              : "Ingresá con tu email y contraseña."}
          </p>
        </div>

        {setupNeeded && (
          <label className="block">
            <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Nombre
            </div>
            <input
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              required
              className="mt-1 w-full rounded-md border hairline bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber"
            />
          </label>
        )}

        <label className="block">
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            Email
          </div>
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="mt-1 w-full rounded-md border hairline bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber"
          />
        </label>

        <label className="block">
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            Contraseña
          </div>
          <input
            type="password"
            autoComplete={setupNeeded ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={setupNeeded ? 8 : undefined}
            className="mt-1 w-full rounded-md border hairline bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber"
          />
        </label>

        {error && (
          <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-md bg-amber py-2.5 text-sm font-medium uppercase tracking-widest text-ink transition hover:brightness-110 disabled:opacity-50"
        >
          {busy ? "..." : setupNeeded ? "Crear y entrar" : "Ingresar"}
        </button>
      </form>
    </div>
  );
}
