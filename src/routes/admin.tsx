import { createFileRoute, Outlet, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { Menu } from "lucide-react";

import { useAuth } from "@/hooks/use-auth";
import { isAdminEmail } from "@/lib/admin-emails";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";

export const Route = createFileRoute("/admin")({
  head: () => ({
    meta: [
      { title: "Back-office — Rambla Rental" },
      { name: "robots", content: "noindex, nofollow" },
    ],
  }),
  component: AdminLayout,
});

function AdminLayout() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      navigate({ to: "/login", search: { redirect: "/admin" } });
    }
  }, [user, loading, navigate]);

  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center text-sm text-muted-foreground">
        Cargando…
      </div>
    );
  }
  if (!user) return null;
  if (!isAdminEmail(user.email)) {
    return <NoAutorizado email={user.email ?? ""} />;
  }

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full bg-background">
        <AdminSidebar />
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

function NoAutorizado({ email }: { email: string }) {
  return (
    <div className="min-h-screen bg-background grid place-items-center px-4">
      <div className="max-w-md w-full text-center space-y-4">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Sin permisos
        </div>
        <h1 className="font-display text-3xl text-ink">Acceso no autorizado</h1>
        <p className="text-sm text-muted-foreground">
          La cuenta <span className="text-ink">{email}</span> no figura como administradora.
        </p>
        <a
          href="/"
          className="inline-flex items-center justify-center rounded-md border hairline px-4 py-2 text-sm text-ink hover:bg-accent/30"
        >
          Volver al catálogo
        </a>
      </div>
    </div>
  );
}
