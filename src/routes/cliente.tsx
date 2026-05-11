import { createFileRoute, Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { authedFetch } from "@/lib/authedFetch";

export const Route = createFileRoute("/cliente")({
  component: ClienteLayout,
});

type ClienteSession = { email?: string; name?: string; cliente_id?: number };

// Rutas dentro de /cliente que NO requieren auth
const PUBLIC_PATHS = ["/cliente/login", "/cliente/registro"];

function ClienteLayout() {
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  const [session, setSession] = useState<ClienteSession | null>(null);
  const [loading, setLoading] = useState(!isPublic);

  useEffect(() => {
    let alive = true;
    authedFetch("/api/cliente/me")
      .then(async (r) => {
        if (!alive) return;
        if (r.ok) {
          const data = (await r.json()) as ClienteSession;
          setSession(data);
          // Si estaba en login/registro y ya tiene sesión, mandarlo al portal
          if (isPublic) navigate({ to: "/cliente/portal" });
        } else if (!isPublic) {
          navigate({ to: "/cliente/login" });
        }
      })
      .catch(() => { if (alive && !isPublic) navigate({ to: "/cliente/login" }); })
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [navigate, isPublic]);

  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center text-sm text-muted-foreground">
        Cargando…
      </div>
    );
  }

  return <Outlet />;
}
