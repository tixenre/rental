import { createFileRoute, Outlet, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { authedFetch } from "@/lib/authedFetch";

export const Route = createFileRoute("/cliente")({
  component: ClienteLayout,
});

type ClienteSession = { email?: string; name?: string; cliente_id?: number };

function ClienteLayout() {
  const navigate = useNavigate();
  const [session, setSession] = useState<ClienteSession | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    authedFetch("/api/cliente/me")
      .then(async (r) => {
        if (!alive) return;
        if (r.ok) {
          setSession(await r.json());
        } else {
          navigate({ to: "/cliente/login" });
        }
      })
      .catch(() => navigate({ to: "/cliente/login" }))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [navigate]);

  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center text-sm text-muted-foreground">
        Cargando…
      </div>
    );
  }
  if (!session) return <Outlet />;

  return <Outlet />;
}
