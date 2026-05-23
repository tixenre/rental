import { useEffect, useState } from "react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { toast } from "sonner";
import {
  LayoutDashboard,
  Package,
  ClipboardList,
  Users,
  BarChart3,
  Settings,
  LogOut,
  ChevronRight,
  List,
  FolderTree,
  Tag,
  Wrench,
  Sparkles,
  Building2,
  Palette,
  Ruler,
  ShieldCheck,
  Database,
  Mail,
  Inbox,
  HardDriveDownload,
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
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { authedFetch } from "@/lib/authedFetch";

type SubItem = { title: string; url: string; icon?: typeof LayoutDashboard };
type NavItem = {
  title: string;
  url: string;
  icon: typeof LayoutDashboard;
  exact?: boolean;
  children?: SubItem[];
};

const items: NavItem[] = [
  {
    title: "Dashboard",
    url: "/admin",
    icon: LayoutDashboard,
    exact: true,
  },
  {
    title: "Inventario",
    url: "/admin/equipos",
    icon: Package,
    children: [
      { title: "Equipos",             url: "/admin/equipos",            icon: List },
      { title: "Calidad",             url: "/admin/equipos/calidad",    icon: ShieldCheck },
      { title: "Categorías",          url: "/admin/equipos/categorias", icon: FolderTree },
      { title: "Marcas",              url: "/admin/equipos/marcas",     icon: Building2 },
      { title: "Specs",               url: "/admin/specs",              icon: Database },
      { title: "Unidades",            url: "/admin/unidades",           icon: Ruler },
    ],
  },
  { title: "Pedidos",     url: "/admin/pedidos",     icon: ClipboardList },
  { title: "Solicitudes", url: "/admin/solicitudes", icon: Inbox },
  { title: "Clientes",    url: "/admin/clientes",    icon: Users },
  { title: "Estadísticas", url: "/admin/estadisticas", icon: BarChart3 },
  { title: "Diseño",      url: "/admin/diseno",      icon: Palette },
  { title: "Novedades",   url: "/admin/novedades",   icon: Sparkles },
  { title: "Emails",      url: "/admin/email-templates", icon: Mail },
  { title: "Export catálogo", url: "/admin/dataio", icon: HardDriveDownload },
  { title: "Settings",    url: "/admin/settings",    icon: Settings },
];

export function AdminSidebar({ email }: { email: string }) {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const currentPath = useRouterState({
    select: (router) => router.location.pathname,
  });
  const navigate = useNavigate();
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() => ({
    "/admin/equipos": true, // empieza expandido si estoy en una sub-ruta
  }));

  // Cuando navego a una sub-ruta, auto-expandir el grupo padre
  useEffect(() => {
    for (const item of items) {
      if (item.children?.some((c) => isActive(c.url, false))) {
        setOpenGroups((s) => ({ ...s, [item.url]: true }));
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPath]);

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

  function isActive(url: string, exact?: boolean): boolean {
    if (exact) return currentPath === url;
    return currentPath === url || currentPath.startsWith(url + "/");
  }

  // Para items con children, el padre se considera "activo" si yo estoy
  // exactamente en su URL O en cualquiera de sus hijos.
  function isParentActive(item: NavItem): boolean {
    if (isActive(item.url, true)) return true;
    return !!item.children?.some((c) => isActive(c.url, false));
  }

  function toggleGroup(url: string) {
    setOpenGroups((s) => ({ ...s, [url]: !s[url] }));
  }

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
              {items.map((item) => {
                const hasChildren = !!item.children && item.children.length > 0;
                const isOpen = openGroups[item.url] ?? false;
                const active = hasChildren ? isParentActive(item) : isActive(item.url, item.exact);

                // Item con hijos
                if (hasChildren && !collapsed) {
                  return (
                    <SidebarMenuItem key={item.url}>
                      <SidebarMenuButton
                        onClick={() => toggleGroup(item.url)}
                        isActive={active && isActive(item.url, true)}
                        className="cursor-pointer"
                      >
                        <item.icon className="h-4 w-4 shrink-0" />
                        <span>{item.title}</span>
                        <ChevronRight
                          className={`ml-auto h-3.5 w-3.5 transition-transform ${isOpen ? "rotate-90" : ""}`}
                        />
                      </SidebarMenuButton>
                      {isOpen && (
                        <SidebarMenuSub>
                          {item.children!.map((child) => {
                            const childActive = child.url === item.url
                              ? isActive(child.url, true)
                              : isActive(child.url, false);
                            return (
                              <SidebarMenuSubItem key={child.url}>
                                <SidebarMenuSubButton asChild isActive={childActive}>
                                  <Link to={child.url} className="flex items-center gap-2">
                                    {child.icon && <child.icon className="h-3.5 w-3.5 shrink-0" />}
                                    <span>{child.title}</span>
                                  </Link>
                                </SidebarMenuSubButton>
                              </SidebarMenuSubItem>
                            );
                          })}
                        </SidebarMenuSub>
                      )}
                    </SidebarMenuItem>
                  );
                }

                // Item con hijos pero sidebar colapsada — link directo al padre
                // (los sub-items se acceden al expandir la sidebar)
                if (hasChildren && collapsed) {
                  return (
                    <SidebarMenuItem key={item.url}>
                      <SidebarMenuButton asChild isActive={active} tooltip={item.title}>
                        <Link to={item.url}>
                          <item.icon className="h-4 w-4 shrink-0" />
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                }

                // Item simple
                return (
                  <SidebarMenuItem key={item.url}>
                    <SidebarMenuButton
                      asChild
                      isActive={active}
                      tooltip={collapsed ? item.title : undefined}
                    >
                      <Link to={item.url} className="flex items-center gap-2">
                        <item.icon className="h-4 w-4 shrink-0" />
                        {!collapsed && <span>{item.title}</span>}
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
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
