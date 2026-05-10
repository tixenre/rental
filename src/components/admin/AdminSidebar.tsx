import { useState } from "react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { toast } from "sonner";
import {
  LayoutDashboard,
  Package,
  ClipboardList,
  Users,
  CalendarDays,
  BarChart3,
  Settings,
  LogOut,
} from "lucide-react";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { authedFetch } from "@/lib/authedFetch";

const items = [
  { title: "Dashboard", url: "/admin", icon: LayoutDashboard, exact: true },
  { title: "Equipos", url: "/admin/equipos", icon: Package },
  { title: "Pedidos", url: "/admin/pedidos", icon: ClipboardList },
  { title: "Clientes", url: "/admin/clientes", icon: Users },
  { title: "Calendario", url: "/admin/calendario", icon: CalendarDays },
  { title: "Estadísticas", url: "/admin/estadisticas", icon: BarChart3 },
  { title: "Settings", url: "/admin/settings", icon: Settings },
] as const;

export function AdminSidebar({ email }: { email: string }) {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const currentPath = useRouterState({
    select: (router) => router.location.pathname,
  });
  const navigate = useNavigate();
  const [isSigningOut, setIsSigningOut] = useState(false);

  const handleSignOut = async () => {
    if (isSigningOut) return;
    setIsSigningOut(true);
    try {
      await authedFetch("/auth/logout", { method: "POST" });
      navigate({ to: "/admin/login" });
    } catch (e) {
      toast.error("No se pudo cerrar sesión", {
        description: e instanceof Error ? e.message : String(e),
      });
      setIsSigningOut(false);
    }
  };

  const isActive = (url: string, exact?: boolean) =>
    exact ? currentPath === url : currentPath === url || currentPath.startsWith(url + "/");

  return (
    <Sidebar collapsible="icon" className="border-r hairline">
      <SidebarHeader className="border-b hairline">
        <Link
          to="/admin"
          className="flex items-center gap-2 px-2 py-3 group/header"
          aria-label="Rambla Rental — back-office"
        >
          <div className="grid place-items-center h-8 w-8 rounded-md bg-amber text-ink shrink-0 font-display text-sm">
            R
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="font-display text-sm leading-tight text-ink truncate">
                Rambla Rental
              </div>
              <div className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground">
                Back-office
              </div>
            </div>
          )}
        </Link>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          {!collapsed && (
            <SidebarGroupLabel className="font-mono text-[9px] uppercase tracking-[0.25em]">
              General
            </SidebarGroupLabel>
          )}
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => (
                <SidebarMenuItem key={item.url}>
                  <SidebarMenuButton
                    asChild
                    isActive={isActive(item.url, item.exact)}
                    tooltip={collapsed ? item.title : undefined}
                  >
                    <Link to={item.url} className="flex items-center gap-2">
                      <item.icon className="h-4 w-4 shrink-0" />
                      {!collapsed && <span>{item.title}</span>}
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t hairline">
        {!collapsed && email && (
          <div className="px-2 py-1.5 min-w-0">
            <div className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground">
              Sesión
            </div>
            <div className="text-xs text-ink truncate" title={email}>
              {email}
            </div>
          </div>
        )}
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              onClick={handleSignOut}
              disabled={isSigningOut}
              tooltip={collapsed ? "Cerrar sesión" : undefined}
            >
              <LogOut className="h-4 w-4 shrink-0" />
              {!collapsed && <span>{isSigningOut ? "Cerrando…" : "Cerrar sesión"}</span>}
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
