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
  Megaphone,
  Ruler,
  ShieldCheck,
  Database,
  HardDriveDownload,
  Clapperboard,
  Wallet,
  BookOpen,
  Calculator,
  GraduationCap,
  ShoppingCart,
  AlertTriangle,
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
} from "@/design-system/ui/sidebar";
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
  { title: "Pedidos", url: "/admin/pedidos", icon: ClipboardList },
  { title: "Carritos activos", url: "/admin/carritos", icon: ShoppingCart },
  {
    title: "Inventario",
    url: "/admin/equipos",
    icon: Package,
    children: [
      { title: "Equipos", url: "/admin/equipos", icon: List },
      { title: "Calidad", url: "/admin/equipos/calidad", icon: ShieldCheck },
      { title: "Categorías", url: "/admin/equipos/categorias", icon: FolderTree },
      { title: "Marcas", url: "/admin/equipos/marcas", icon: Building2 },
      { title: "Specs", url: "/admin/specs", icon: Database },
      { title: "Unidades", url: "/admin/unidades", icon: Ruler },
    ],
  },
  { title: "Estudio", url: "/admin/estudio", icon: Clapperboard },
  { title: "Talleres", url: "/admin/talleres", icon: GraduationCap },
  // Solicitudes se accede desde la página de Pedidos (no se duplica en el sidebar).
  { title: "Clientes", url: "/admin/clientes", icon: Users },
  { title: "Estadísticas", url: "/admin/estadisticas", icon: BarChart3 },
  {
    title: "Finanzas",
    url: "/admin/contabilidad",
    icon: Wallet,
    children: [
      { title: "Tablero", url: "/admin/contabilidad", icon: LayoutDashboard },
      { title: "Movimientos", url: "/admin/contabilidad/movimientos", icon: ClipboardList },
      { title: "Cuentas", url: "/admin/contabilidad/cuentas", icon: Wallet },
      { title: "Reporte mensual", url: "/admin/contabilidad/reporte", icon: BarChart3 },
      { title: "Liquidación", url: "/admin/contabilidad/liquidacion", icon: Calculator },
      { title: "Cobros de pedidos", url: "/admin/pagos", icon: List },
      { title: "Glosario", url: "/admin/contabilidad/glosario", icon: BookOpen },
    ],
  },
  { title: "Assets y diseño", url: "/admin/diseno", icon: Palette },
  { title: "Marca", url: "/admin/marca", icon: Megaphone },
  { title: "Novedades", url: "/admin/novedades", icon: Sparkles },
  { title: "Datos y backups", url: "/admin/dataio", icon: HardDriveDownload },
  { title: "Settings", url: "/admin/settings", icon: Settings },
  { title: "Errores del servidor", url: "/admin/errores", icon: AlertTriangle },
];

export function AdminSidebar({ email }: { email: string }) {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const currentPath = useRouterState({
    select: (router) => router.location.pathname,
  });
  const navigate = useNavigate();
  const [isSigningOut, setIsSigningOut] = useState(false);
  // Estado open/closed de cada grupo, persistido en localStorage para que el
  // dueño no tenga que re-abrir el inventario cada vez que entra.
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() => {
    const fallback: Record<string, boolean> = {};
    if (typeof window === "undefined") return fallback;
    try {
      const raw = window.localStorage.getItem("admin-sidebar:openGroups");
      if (raw) return { ...fallback, ...(JSON.parse(raw) as Record<string, boolean>) };
    } catch {
      /* ignored */
    }
    return fallback;
  });

  useEffect(() => {
    try {
      window.localStorage.setItem("admin-sidebar:openGroups", JSON.stringify(openGroups));
    } catch {
      /* ignored */
    }
  }, [openGroups]);

  // Cuando navego a una sub-ruta, auto-expandir el grupo padre
  useEffect(() => {
    for (const item of items) {
      if (item.children?.some((c) => isActive(c.url, false))) {
        setOpenGroups((s) => ({ ...s, [item.url]: true }));
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- auto-expandir solo al cambiar de ruta; items es config estable y setOpenGroups usa functional update
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
          <svg
            className="topbar-seal shrink-0 block h-9 w-9"
            viewBox="0 0 2000 2000"
            aria-hidden="true"
          >
            <path
              className="seal-badge"
              d="M1930.45,949.73c-.44-.28-.88-.55-1.32-.82l-5.91-3.61c-3.19-2.29-6.58-4.35-10.13-6.19l-121.29-74.1c-49.62-30.31-68.53-93.07-43.93-145.76l63.92-136.86c37.05-79.33-25.29-169.12-112.57-162.14l-150.57,12.05c-57.96,4.64-110.15-35.02-121.21-92.1l-28.73-148.29c-16.65-85.96-119.87-121.96-186.37-65.01l-114.72,98.25c-44.16,37.82-109.7,36.42-152.2-3.26l-110.4-103.08c-64-59.75-168.66-28.21-188.99,56.95l-35.07,146.92c-13.5,56.56-67.34,93.94-125.05,86.82l-149.9-18.5c-86.89-10.72-153.03,76.31-119.42,157.16l57.99,139.48c22.32,53.69.73,115.58-50.14,143.74l-140.79,77.93c-.61.33-1.21.68-1.8,1.02-31.8,18.36-44.19,49.65-41.44,79.73-2.42,22.36,6.21,45.75,29.16,60.2.44.28.88.55,1.32.82l5.91,3.61c3.19,2.29,6.58,4.35,10.13,6.19l121.29,74.1c49.62,30.31,68.54,93.08,43.93,145.76l-63.92,136.86c-37.05,79.33,25.29,169.12,112.57,162.14l150.57-12.05c57.96-4.64,110.15,35.02,121.21,92.1l28.73,148.29c16.65,85.96,119.87,121.96,186.37,65.01l114.72-98.25c44.17-37.82,109.7-36.42,152.2,3.26l110.4,103.08c64,59.75,168.66,28.21,188.99-56.95l35.07-146.92c13.5-56.56,67.34-93.94,125.05-86.82l149.9,18.5c86.89,10.72,153.03-76.31,119.42-157.16l-57.99-139.48c-22.32-53.69-.73-115.58,50.14-143.74l140.79-77.93c.61-.33,1.21-.67,1.8-1.02,31.8-18.36,44.19-49.65,41.44-79.72,2.42-22.36-6.21-45.75-29.16-60.2Z"
            />
            <path
              className="seal-r"
              fillRule="evenodd"
              d="M915.75,1195.19c4.65.25,9.34.57,14.09.7,180.57,4.81,361.28-126.11,403.64-292.43,42.36-166.32-69.69-323.8-250.26-328.61-60.73-1.62-124.87,22.33-177.52,54.92-12.49,7.73-28.44-1.73-27.15-16.37.03-.31.05-.61.08-.92.9-10.19-7.03-18.98-17.27-18.98h-187.42c-3.01,0-5.51,2.32-5.73,5.33-3.46,46.93-27.1,395.19,9.77,700.72,7.24,59.98,58.55,104.88,118.96,104.88h123.28c3.55,0,6.27-3.07,5.69-6.57-1.81-10.9-5.72-34.52-10.67-64.49-.88-5.33,5.3-8.96,9.37-5.4,43.04,37.71,196.54,152,393.92,65.79,2.12-.93,3.54-3.07,3.54-5.39v-254.14c0-9.38-10.05-15.37-18.26-10.83-57.94,32.1-242.52,124.87-389.33,93.98-18.62-3.92-17.49-23.19,1.25-22.2ZM876.68,978.38c26.29-62.04,108.33-118.54,183.26-126.2,74.92-7.66,114.35,36.41,88.07,98.45-26.29,62.04-108.33,118.54-183.26,126.2-74.92,7.66-114.35-36.41-88.07-98.45Z"
            />
          </svg>
          {!collapsed && (
            <div className="min-w-0">
              <div className="font-display text-base leading-tight text-ink truncate">Rambla</div>
              <div className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
                Back-office
              </div>
            </div>
          )}
        </Link>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          {!collapsed && (
            <SidebarGroupLabel className="font-mono text-2xs uppercase tracking-[0.2em]">
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
                          {(item.children ?? []).map((child) => {
                            const childActive =
                              child.url === item.url
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
            <div className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
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
