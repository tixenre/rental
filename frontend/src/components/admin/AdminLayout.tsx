/**
 * AdminLayout — extracted from src/routes/admin.tsx para permitir
 * React.lazy() y chunkar todo el subtree admin fuera del bundle inicial.
 *
 * Visitors del catálogo público nunca lo descargan.
 */

import { Outlet, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Menu } from "lucide-react";

import { authedFetch } from "@/lib/authedFetch";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { SidebarProvider, SidebarTrigger } from "@/design-system/ui/sidebar";

type Session = { email?: string; name?: string; is_admin?: boolean };

export function AdminLayout() {
  const navigate = useNavigate();
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    authedFetch("/auth/me")
      .then(async (r) => {
        if (!alive) return;
        if (r.ok) {
          const data = (await r.json()) as Session;
          if (!data.is_admin) {
            // El usuario está logueado en Google pero su email no tiene
            // permiso de administración. Redirect al login con flag
            // `denied` para mostrarle el mensaje correspondiente.
            navigate({ to: "/admin/login", search: { denied: "1" } });
            return;
          }
          setSession(data);
        } else {
          navigate({ to: "/admin/login" });
        }
      })
      .catch(() => navigate({ to: "/admin/login" }))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [navigate]);

  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center text-sm text-muted-foreground">
        Cargando…
      </div>
    );
  }
  if (!session) return <Outlet />;

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full bg-background">
        <AdminSidebar email={session.email ?? ""} />
        <div className="flex-1 flex flex-col min-w-0">
          <header className="h-12 flex items-center gap-2 border-b hairline px-3 md:px-4 bg-background sticky top-0 z-10">
            <SidebarTrigger aria-label="Alternar sidebar">
              <Menu className="h-4 w-4" />
            </SidebarTrigger>
          </header>
          <main className="flex-1 min-w-0">
            <Outlet />
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}
