/**
 * AdminLayout — extracted from src/routes/admin.tsx para permitir
 * React.lazy() y chunkar todo el subtree admin fuera del bundle inicial.
 *
 * Visitors del catálogo público nunca lo descargan.
 */

import { Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Search } from "lucide-react";

import { authedFetch } from "@/lib/authedFetch";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { AdminCommandPalette } from "@/components/admin/AdminCommandPalette";
import { ConfirmProvider } from "@/components/admin/useConfirm";
import { SidebarProvider, SidebarTrigger } from "@/design-system/ui/sidebar";
import { EnrolarPasskeyGate } from "@/components/admin/EnrolarPasskeyGate";

type Session = { email?: string; name?: string; is_admin?: boolean };

export function AdminLayout() {
  const navigate = useNavigate();
  // /admin/login es hija de esta ruta (layout), pero maneja su PROPIO flujo de
  // auth (incluido "sin sesión todavía" mientras espera el 2º factor con
  // passkey, `?paso=passkey`). Sin este chequeo, el `navigate({to:"/admin/login"})`
  // de abajo pisaba ese query param en cada 401 — mandaba siempre a la pantalla
  // por defecto en vez de la de confirmar/registrar passkey.
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const isLoginPage = pathname === "/admin/login";
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(isLoginPage ? false : true);

  useEffect(() => {
    if (isLoginPage) return;
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
  }, [navigate, isLoginPage]);

  if (isLoginPage) return <Outlet />;

  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center text-sm text-muted-foreground">
        Cargando…
      </div>
    );
  }
  if (!session) return <Outlet />;

  // 2º factor obligatorio para admin: sin ninguna passkey enrolada todavía, se
  // fuerza el enrolamiento on-the-fly antes de dejar entrar al resto del back-office
  // (criterio del dueño). El modo dev-bypass (ADMIN_BYPASS_AUTH, nunca en prod) lo
  // saltea para no meterle fricción a la iteración local.
  if (session.email !== "bypass@local") {
    return (
      <EnrolarPasskeyGate>
        <AdminShell session={session} />
      </EnrolarPasskeyGate>
    );
  }

  return <AdminShell session={session} />;
}

function AdminShell({ session }: { session: Session }) {
  return (
    <ConfirmProvider>
      <SidebarProvider>
        <div className="min-h-screen flex w-full bg-background">
          <AdminSidebar email={session.email ?? ""} />
          <div className="flex-1 flex flex-col min-w-0">
            {/* En mobile el sidebar está oculto, así que los triggers viven acá */}
            <header className="md:hidden h-12 flex items-center justify-between border-b hairline px-3 bg-background sticky top-0 z-10">
              <SidebarTrigger aria-label="Abrir menú" />
              <button
                type="button"
                onClick={() => window.dispatchEvent(new Event("admin:cmdk"))}
                className="flex h-11 w-11 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-ink"
                aria-label="Buscar"
              >
                <Search className="h-4 w-4" />
              </button>
            </header>
            <main className="flex-1 min-w-0">
              <Outlet />
            </main>
          </div>
        </div>
        <AdminCommandPalette />
      </SidebarProvider>
    </ConfirmProvider>
  );
}
