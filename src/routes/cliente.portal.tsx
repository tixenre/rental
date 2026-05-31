/**
 * cliente.portal.tsx — Portal del cliente.
 *
 * Layout: sidebar 220px en desktop + bottom-nav en mobile, con 3 tabs:
 * Pedidos · Notificaciones · Perfil. El perfil vive como tab (PerfilSection),
 * no como drawer lateral. Notificaciones es un empty-state hasta que exista el
 * endpoint (ver TODO en NotificacionesSection).
 *
 * Toda la lógica de pedidos (fetch, filtros, cancelaciones, documentos,
 * solicitudes, timeline) se preserva en los componentes PedidoCard, DocActions,
 * DocPreviewModal, DocAvailablePopup, PedidoTimeline, buildTimelineSteps.
 */

import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { useEquipos } from "@/hooks/useEquipos";
import { useFavoritos } from "@/hooks/useFavoritos";
import { EquipmentCard } from "@/components/rental/EquipmentCard";
import { authedFetch } from "@/lib/authedFetch";
import { clienteApi } from "@/lib/cliente/api";
import { TopBar } from "@/components/rental/TopBar";
import { StatCard } from "@/components/rental/StatCard";
import { EstadoBadge } from "@/components/kit/EstadoBadge";
import {
  ArrowRight,
  ChevronDown,
  ShoppingBag,
  Pencil,
  Clock,
  X as XIcon,
  CheckCircle2,
  XCircle,
  Info,
  FileText,
  FileSignature,
  Truck,
  MessageCircle,
  Search,
  Mail,
  Phone,
  MapPin,
  Building2,
  Receipt,
  LogOut,
  CircleCheckBig,
  Lock,
  Bell,
  User,
  Package,
} from "lucide-react";
import { toast } from "sonner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useBusinessPhone } from "@/lib/business";
import { jornadasFromISO as jornadasEntre } from "@/lib/rental-dates";
import { whatsappLink } from "@/lib/whatsapp";
import { cn } from "@/lib/utils";
import { GoogleIcon } from "@/components/ui/GoogleIcon";
import { formatARS } from "@/lib/format";

export const Route = createFileRoute("/cliente/portal")({
  head: () => ({ meta: [{ title: "Mis pedidos — Rambla Rental" }] }),
  validateSearch: (search: Record<string, unknown>): { nuevo?: number } => {
    const n = Number(search.nuevo);
    return Number.isFinite(n) && n > 0 ? { nuevo: n } : {};
  },
  component: ClientePortal,
});

// ── Tipos (igual que el original) ────────────────────────────────────────────

type Perfil = {
  id: number;
  nombre: string;
  apellido: string;
  email: string;
  telefono: string;
  direccion: string;
  cuit?: string | null;
  perfil_impuestos?: string | null;
  descuento?: number;
  direccion_maps_url?: string | null;
  created_at?: string | null;
};

type Item = {
  nombre: string;
  marca: string;
  modelo?: string | null;
  cantidad: number;
  precio_jornada: number;
  subtotal: number;
  foto_url?: string;
  nombre_publico?: string | null;
  nombre_publico_largo?: string | null;
};
type Pago = { monto: number; concepto?: string | null; fecha: string };
type SolicitudPortal = {
  id: number;
  estado: "pendiente" | "aprobada" | "rechazada" | "cancelada";
  respuesta?: string | null;
  resolved_by?: string | null;
  resolved_at?: string | null;
  created_at: string;
};
type Pedido = {
  id: number;
  numero_pedido: string;
  estado: string;
  fecha_desde?: string;
  fecha_hasta?: string;
  monto_total?: number;
  monto_pagado?: number;
  descuento_pct?: number | null;
  notas?: string | null;
  created_at?: string | null;
  items: Item[];
  pagos?: Pago[];
  solicitudes?: SolicitudPortal[];
  documentos_disponibles: { remito: boolean; contrato: boolean; albaran: boolean };
  bruto?: number;
  descuento_monto?: number;
  monto_neto?: number;
  iva_pct?: number;
  iva_monto?: number;
  total_con_iva?: number;
  con_iva?: boolean;
  cantidad_jornadas?: number;
};

// ── Nuevo: tipo de tab del portal ─────────────────────────────────────────────
type PortalTab = "pedidos" | "notificaciones" | "perfil";

const ACTIVE_STATES = new Set(["borrador", "presupuesto", "confirmado", "retirado"]);
const HIST_STATES = new Set(["devuelto", "finalizado", "cancelado"]);
const MODIFICABLE_STATES = new Set(["presupuesto", "confirmado"]);

type DocTipo = "remito" | "contrato" | "albaran";
const DOC_LABEL: Record<DocTipo, string> = {
  remito: "Remito",
  contrato: "Contrato",
  albaran: "Albarán",
};
const DOC_DESCRIPTION: Partial<Record<DocTipo, string>> = {
  contrato: "Es el documento de alquiler firmado entre vos y nosotros.",
  albaran: "Te sirve para tener constancia ante tu aseguradora.",
};
const DOC_NOTIFICABLE: DocTipo[] = ["contrato", "albaran"];
const docSeenKey = (pedidoId: number, tipo: DocTipo) => `rambla.doc_seen.${pedidoId}.${tipo}`;
function wasDocSeen(pedidoId: number, tipo: DocTipo): boolean {
  try {
    return localStorage.getItem(docSeenKey(pedidoId, tipo)) === "1";
  } catch {
    return false;
  }
}
function markDocSeen(pedidoId: number, tipo: DocTipo): void {
  try {
    localStorage.setItem(docSeenKey(pedidoId, tipo), "1");
  } catch {
    /* ignore */
  }
}

type Filtro = "todos" | "activos" | "historial";
const TAB_OPTIONS: { value: Filtro; label: string }[] = [
  { value: "todos", label: "Todos" },
  { value: "activos", label: "Activos" },
  { value: "historial", label: "Historial" },
];

// Reemplazar fmt() con formatARS() del sistema
function fmt(n?: number) {
  if (n == null) return "—";
  return formatARS(n);
}
function fmtDate(s?: string) {
  if (!s) return "—";
  const d = new Date(s.slice(0, 10) + "T12:00:00");
  const dias = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
  const meses = [
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
  ];
  return `${dias[d.getDay()]} ${d.getDate()} ${meses[d.getMonth()]}`;
}
function fmtTime(s?: string) {
  if (!s || s.length < 16) return null;
  return s.slice(11, 16);
}

// ── Componente principal ──────────────────────────────────────────────────────

export default function ClientePortal() {
  const navigate = useNavigate();
  const { nuevo } = Route.useSearch();
  const fav = useFavoritos();
  const { data: allEquipos = [] } = useEquipos();
  const favEquipos = useMemo(
    () => allEquipos.filter((e) => fav.has(String(e.id))),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [allEquipos, fav.items],
  );

  // Estado del portal
  const [activeTab, setActiveTab] = useState<PortalTab>("pedidos");
  const [perfil, setPerfil] = useState<Perfil | null>(null);
  const [pedidos, setPedidos] = useState<Pedido[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [highlightId, setHighlightId] = useState<number | null>(null);
  const nuevoHandledRef = useRef(false);
  const [tab, setTab] = useState<Filtro>("todos");
  const [query, setQuery] = useState<string>("");
  const [ventanaHoras, setVentanaHoras] = useState<number>(24);
  const [docsNuevos, setDocsNuevos] = useState<
    Array<{ pedidoId: number; numero: string; tipo: DocTipo }>
  >([]);

  function reloadPedidos() {
    authedFetch("/api/cliente/pedidos").then(async (r) => {
      if (r.ok) setPedidos(await r.json());
    });
  }

  useEffect(() => {
    let alive = true;
    Promise.all([authedFetch("/api/cliente/me"), authedFetch("/api/cliente/pedidos")])
      .then(async ([rp, ro]) => {
        if (!alive) return;
        if (!rp.ok || !ro.ok) {
          navigate({ to: "/cliente/login" });
          return;
        }
        setPerfil(await rp.json());
        setPedidos(await ro.json());
      })
      .catch(() => navigate({ to: "/cliente/login" }))
      .finally(() => alive && setLoading(false));
    clienteApi
      .modificacionConfig()
      .then((c) => {
        if (alive) setVentanaHoras(c.ventana_horas);
      })
      .catch(() => {
        /* default 24 */
      });
    return () => {
      alive = false;
    };
  }, [navigate]);

  useEffect(() => {
    const nuevos: Array<{ pedidoId: number; numero: string; tipo: DocTipo }> = [];
    for (const p of pedidos) {
      const docs = p.documentos_disponibles;
      if (!docs) continue;
      for (const tipo of DOC_NOTIFICABLE) {
        if (docs[tipo] && !wasDocSeen(p.id, tipo))
          nuevos.push({ pedidoId: p.id, numero: String(p.numero_pedido ?? p.id), tipo });
      }
    }
    setDocsNuevos(nuevos);
  }, [pedidos]);

  function dismissDocsPopup() {
    for (const d of docsNuevos) markDocSeen(d.pedidoId, d.tipo);
    setDocsNuevos([]);
  }

  function verPedido(pedidoId: number) {
    setActiveTab("pedidos");
    setExpanded(pedidoId);
    dismissDocsPopup();
    setTimeout(() => {
      const el = document.getElementById(`pedido-${pedidoId}`);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 100);
  }

  useEffect(() => {
    if (loading || nuevo == null || nuevoHandledRef.current) return;
    if (!pedidos.some((p) => p.id === nuevo)) return;
    nuevoHandledRef.current = true;
    verPedido(nuevo);
    setHighlightId(nuevo);
    navigate({ to: "/cliente/portal", search: {}, replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, nuevo, pedidos, navigate]);

  useEffect(() => {
    if (highlightId == null) return;
    const t = setTimeout(() => setHighlightId(null), 3500);
    return () => clearTimeout(t);
  }, [highlightId]);

  async function handleLogout() {
    await authedFetch("/auth/logout", { method: "POST" }).catch(() => {});
    navigate({ to: "/cliente/login" });
  }

  const tabFiltered = useMemo(
    () =>
      tab === "activos"
        ? pedidos.filter((p) => ACTIVE_STATES.has(p.estado))
        : tab === "historial"
          ? pedidos.filter((p) => HIST_STATES.has(p.estado))
          : pedidos,
    [tab, pedidos],
  );

  const q = query.trim().toLowerCase();
  const filteredPedidos = useMemo(() => {
    if (!q) return tabFiltered;
    return tabFiltered.filter((p) => {
      if (
        String(p.numero_pedido ?? "")
          .toLowerCase()
          .includes(q)
      )
        return true;
      if (p.estado.toLowerCase().includes(q)) return true;
      if ((p.notas ?? "").toLowerCase().includes(q)) return true;
      if (
        p.items.some(
          (it) =>
            (it.nombre_publico ?? it.nombre).toLowerCase().includes(q) ||
            (it.marca ?? "").toLowerCase().includes(q) ||
            (it.modelo ?? "").toLowerCase().includes(q),
        )
      )
        return true;
      return false;
    });
  }, [tabFiltered, q]);

  const userName = perfil ? `${perfil.nombre} ${perfil.apellido}` : undefined;
  const activosPedidos = pedidos.filter((p) => ACTIVE_STATES.has(p.estado));
  const totalActivos = activosPedidos.reduce((sum, p) => sum + (p.monto_total ?? 0), 0);
  const pendientePago = activosPedidos.reduce(
    (sum, p) => sum + Math.max(0, (p.monto_total ?? 0) - (p.monto_pagado ?? 0)),
    0,
  );
  const historico = pedidos.filter((p) => HIST_STATES.has(p.estado)).length;
  const ahora = Date.now();
  const proximo = activosPedidos
    .flatMap((p) => {
      const ev: { ts: number; iso: string; tipo: string }[] = [];
      const d = p.fecha_desde ? new Date(p.fecha_desde).getTime() : NaN;
      const h = p.fecha_hasta ? new Date(p.fecha_hasta).getTime() : NaN;
      if (!Number.isNaN(d) && d >= ahora) ev.push({ ts: d, iso: p.fecha_desde!, tipo: "retiro" });
      if (!Number.isNaN(h) && h >= ahora)
        ev.push({ ts: h, iso: p.fecha_hasta!, tipo: "devolución" });
      return ev;
    })
    .sort((a, b) => a.ts - b.ts)[0];

  const counts: Record<Filtro, number> = {
    todos: pedidos.length,
    activos: activosPedidos.length,
    historial: historico,
  };

  if (loading) {
    return (
      <div className="min-h-dvh bg-background flex flex-col">
        <TopBar variant="cliente" userName={undefined} />
        <div className="flex flex-1">
          <aside className="hidden md:block w-[220px] shrink-0 border-r hairline" />
          <main className="flex-1 px-5 lg:px-12 pt-8">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 mb-9">
              {[0, 1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-[88px] rounded-md border hairline bg-muted/30 animate-pulse"
                />
              ))}
            </div>
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="h-14 rounded-xl border hairline bg-muted/20 animate-pulse mb-2.5"
              />
            ))}
          </main>
        </div>
      </div>
    );
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-dvh bg-background flex flex-col">
      {/* TopBar — logo + nombre + avatar que abre tab Perfil */}
      <TopBar
        variant="cliente"
        userName={userName}
        onLogout={handleLogout}
        onProfileClick={() => setActiveTab("perfil")}
      />

      <div className="flex flex-1 overflow-hidden">
        {/* ── Sidebar desktop ─────────────────────────────────────────── */}
        <nav
          className="hidden md:flex flex-col w-[220px] shrink-0 border-r hairline bg-background sticky top-16 h-[calc(100dvh-4rem)] overflow-y-auto py-4"
          aria-label="Navegación del portal"
        >
          {/* Saludo */}
          {perfil && (
            <div className="px-4 mb-5">
              <div className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted-foreground">
                Portal · cliente
              </div>
              <div className="font-sans text-sm font-semibold text-ink mt-0.5 truncate">
                {perfil.nombre} {perfil.apellido}
              </div>
            </div>
          )}

          {/* Nav items */}
          <div className="flex flex-col gap-0.5 px-2">
            <SidebarNavItem
              icon={<Package className="h-4 w-4" />}
              label="Pedidos"
              count={pedidos.length}
              active={activeTab === "pedidos"}
              onClick={() => setActiveTab("pedidos")}
            />
            <SidebarNavItem
              icon={<Bell className="h-4 w-4" />}
              label="Notificaciones"
              active={activeTab === "notificaciones"}
              onClick={() => setActiveTab("notificaciones")}
            />
            <SidebarNavItem
              icon={<User className="h-4 w-4" />}
              label="Perfil"
              active={activeTab === "perfil"}
              onClick={() => setActiveTab("perfil")}
            />
          </div>

          {/* Logout al fondo */}
          <div className="mt-auto px-2 pt-4 border-t hairline mx-2">
            <button
              type="button"
              onClick={handleLogout}
              className="w-full flex items-center gap-2.5 rounded-md px-3 py-2.5 font-sans text-sm text-muted-foreground hover:text-destructive hover:bg-destructive/8 transition"
            >
              <LogOut className="h-4 w-4" />
              Cerrar sesión
            </button>
          </div>
        </nav>

        {/* ── Contenido principal ──────────────────────────────────────── */}
        <main className="flex-1 overflow-y-auto pb-24 md:pb-8">
          {/* TAB: PEDIDOS */}
          {activeTab === "pedidos" && (
            <div className="px-5 lg:px-10 pt-8">
              {/* Stats */}
              {pedidos.length > 0 && (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-2.5 mb-9">
                  <StatCard
                    label="Activos"
                    value={String(activosPedidos.length)}
                    meta={`${fmt(totalActivos)} en rentals`}
                  />
                  <StatCard
                    label="Próximo"
                    value={proximo ? fmtDate(proximo.iso) : "—"}
                    meta={proximo ? proximo.tipo : "sin fechas próximas"}
                  />
                  <StatCard
                    label="A pagar"
                    value={pendientePago > 0 ? fmt(pendientePago) : "$ 0"}
                    meta={pendientePago > 0 ? "saldo pendiente" : "todo al día"}
                    valueClassName={pendientePago === 0 ? "text-verde" : undefined}
                  />
                  <StatCard
                    label="Histórico"
                    value={String(historico)}
                    meta="pedidos completados"
                  />
                </div>
              )}

              {/* Favoritos */}
              {favEquipos.length > 0 && (
                <section className="mb-8">
                  <h2 className="font-display text-[22px] font-black text-ink tracking-[-0.01em] mb-4">
                    Mis favoritos
                  </h2>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3 lg:grid-cols-4">
                    {favEquipos.map((item, i) => (
                      <EquipmentCard key={item.id} item={item} index={i} />
                    ))}
                  </div>
                </section>
              )}

              {/* Header pedidos */}
              <div className="flex items-baseline justify-between gap-3 mb-4">
                <h2 className="font-display text-[22px] font-black text-ink tracking-[-0.01em]">
                  mis pedidos.
                </h2>
                {pedidos.length > 0 && (
                  <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
                    {pedidos.length} {pedidos.length === 1 ? "pedido" : "pedidos"}
                  </span>
                )}
              </div>

              {/* Search */}
              {pedidos.length > 0 && (
                <div className="mb-3 relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Buscar por número, equipo, marca…"
                    className="w-full rounded-full border hairline bg-surface px-9 py-2.5 font-sans text-[13px] text-ink outline-none transition placeholder:text-muted-foreground hover:border-ink/30 focus:border-ink focus:bg-card"
                  />
                  {query && (
                    <button
                      type="button"
                      onClick={() => setQuery("")}
                      className="absolute right-2 top-1/2 -translate-y-1/2 grid h-[22px] w-[22px] place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-ink"
                      aria-label="Limpiar búsqueda"
                    >
                      <XIcon className="h-3 w-3" />
                    </button>
                  )}
                </div>
              )}

              {/* Filter chips */}
              {pedidos.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-4">
                  {TAB_OPTIONS.map(({ value, label }) => {
                    const active = tab === value;
                    return (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setTab(value)}
                        className={cn(
                          "inline-flex items-center gap-1 rounded-full border px-3.5 py-1.5 font-sans text-xs font-semibold transition",
                          active
                            ? "bg-ink text-amber border-ink"
                            : "border-hairline text-muted-foreground hover:text-ink hover:border-ink",
                        )}
                      >
                        {label}
                        <span
                          className={cn(
                            "font-mono text-[9px] tabular-nums",
                            active ? "opacity-85" : "opacity-60",
                          )}
                        >
                          {counts[value]}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}

              {/* Lista */}
              {pedidos.length === 0 ? (
                <PedidoEmpty
                  title="Sin pedidos aún"
                  sub="Todavía no tenés pedidos registrados."
                  cta
                />
              ) : filteredPedidos.length === 0 ? (
                q ? (
                  <PedidoEmpty
                    title="Nada coincide con tu búsqueda"
                    sub={`No encontramos pedidos para "${query}".`}
                    actionLabel="Limpiar búsqueda"
                    onAction={() => setQuery("")}
                    icon="search"
                  />
                ) : (
                  <PedidoEmpty
                    title={tab === "activos" ? "Sin rentals activos" : "Sin pedidos por acá"}
                    sub={
                      tab === "activos"
                        ? "No tenés rentals activos en este momento."
                        : "No tenés pedidos en esta sección."
                    }
                    cta
                  />
                )
              ) : (
                <div className="flex flex-col gap-2.5">
                  {filteredPedidos.map((p) => (
                    <PedidoCard
                      key={p.id}
                      pedido={p}
                      expanded={expanded === p.id}
                      highlight={highlightId === p.id}
                      onToggle={() => setExpanded(expanded === p.id ? null : p.id)}
                      ventanaHoras={ventanaHoras}
                      onChanged={reloadPedidos}
                      perfilImpuestos={perfil?.perfil_impuestos ?? null}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB: NOTIFICACIONES */}
          {activeTab === "notificaciones" && <NotificacionesSection />}

          {/* TAB: PERFIL */}
          {activeTab === "perfil" && perfil && (
            <PerfilSection
              perfil={perfil}
              pedidosCount={pedidos.length}
              totalAlquilado={pedidos.reduce((s, p) => s + (p.monto_total ?? 0), 0)}
              onLogout={handleLogout}
            />
          )}
        </main>
      </div>

      {/* ── Bottom nav mobile ─────────────────────────────────────────── */}
      <nav
        className="md:hidden fixed bottom-0 inset-x-0 z-40 border-t hairline bg-background/95 backdrop-blur-md"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
        aria-label="Navegación del portal"
      >
        <div className="grid grid-cols-3">
          <BottomNavItem
            icon={<Package className="h-5 w-5" />}
            label="Pedidos"
            active={activeTab === "pedidos"}
            onClick={() => setActiveTab("pedidos")}
          />
          <BottomNavItem
            icon={<Bell className="h-5 w-5" />}
            label="Notificaciones"
            active={activeTab === "notificaciones"}
            onClick={() => setActiveTab("notificaciones")}
          />
          <BottomNavItem
            icon={<User className="h-5 w-5" />}
            label="Perfil"
            active={activeTab === "perfil"}
            onClick={() => setActiveTab("perfil")}
          />
        </div>
      </nav>

      <DocAvailablePopup nuevos={docsNuevos} onDismiss={dismissDocsPopup} onVerPedido={verPedido} />
    </div>
  );
}

// ── Navegación: sidebar item ──────────────────────────────────────────────────

function SidebarNavItem({
  icon,
  label,
  count,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  count?: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-2.5 rounded-md px-3 py-2.5 font-sans text-sm font-medium transition text-left",
        active
          ? "bg-amber-soft text-ink font-semibold"
          : "text-muted-foreground hover:text-ink hover:bg-surface",
      )}
    >
      <span className={cn("shrink-0", active ? "text-ink" : "text-muted-foreground")}>{icon}</span>
      <span className="flex-1">{label}</span>
      {count != null && count > 0 && (
        <span
          className={cn(
            "font-mono text-[10px] tabular-nums rounded-full px-1.5 py-px",
            active ? "bg-amber text-ink" : "bg-muted text-muted-foreground",
          )}
        >
          {count}
        </span>
      )}
    </button>
  );
}

// ── Navegación: bottom nav item ───────────────────────────────────────────────

function BottomNavItem({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex flex-col items-center justify-center gap-1 py-2.5 min-h-[56px] transition",
        active ? "text-ink" : "text-muted-foreground",
      )}
    >
      <span className={cn("transition", active && "text-ink")}>{icon}</span>
      <span
        className={cn(
          "font-mono text-[9px] uppercase tracking-[0.12em] transition",
          active ? "text-ink font-semibold" : "text-muted-foreground",
        )}
      >
        {label}
      </span>
      {active && (
        <span className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-0.5 bg-amber rounded-b" />
      )}
    </button>
  );
}

// ── Tab: Notificaciones ───────────────────────────────────────────────────────

function NotificacionesSection() {
  return (
    <div className="px-5 lg:px-10 pt-8">
      <div className="flex items-baseline justify-between gap-3 mb-8">
        <h2 className="font-display text-[22px] font-black text-ink tracking-[-0.01em]">
          notificaciones.
        </h2>
      </div>
      <div className="rounded-xl border border-dashed hairline px-6 py-[60px] text-center">
        <div className="mx-auto mb-3.5 grid h-14 w-14 place-items-center rounded-full bg-amber-soft text-amber">
          <Bell className="h-6 w-6" strokeWidth={1.5} />
        </div>
        <div className="font-display text-xl font-black text-ink mb-1.5">Sin notificaciones</div>
        <div className="font-sans text-[13px] text-muted-foreground max-w-[30ch] mx-auto">
          Cuando haya novedades sobre tus pedidos o documentos aparecerán acá.
        </div>
        {/* TODO: conectar a /api/cliente/notificaciones cuando el endpoint esté disponible */}
      </div>
    </div>
  );
}

// ── Tab: Perfil ───────────────────────────────────────────────────────────────

function PerfilSection({
  perfil,
  pedidosCount,
  totalAlquilado,
  onLogout,
}: {
  perfil: {
    nombre: string;
    apellido: string;
    email: string;
    telefono: string;
    direccion: string;
    cuit?: string | null;
    perfil_impuestos?: string | null;
    created_at?: string | null;
  };
  pedidosCount: number;
  totalAlquilado: number;
  onLogout: () => void;
}) {
  const initial = perfil.nombre?.[0]?.toUpperCase() ?? "?";
  const fullName = `${perfil.nombre} ${perfil.apellido}`;

  const memberSince = (() => {
    if (!perfil.created_at) return null;
    const d = new Date(perfil.created_at);
    const meses = [
      "ene",
      "feb",
      "mar",
      "abr",
      "may",
      "jun",
      "jul",
      "ago",
      "sep",
      "oct",
      "nov",
      "dic",
    ];
    return `cliente desde ${meses[d.getMonth()]} ${d.getFullYear()}`;
  })();

  return (
    <div className="px-5 lg:px-10 pt-8 max-w-xl">
      <h2 className="font-display text-[22px] font-black text-ink tracking-[-0.01em] mb-6">
        mi perfil.
      </h2>

      {/* Avatar + nombre */}
      <div className="flex items-center gap-4 mb-6">
        <div className="flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-full bg-amber">
          <span className="font-display font-black text-[20px] text-ink leading-none">
            {initial}
          </span>
        </div>
        <div>
          <div className="font-sans font-bold text-[17px] text-ink">{fullName}</div>
          {memberSince && (
            <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground mt-0.5">
              {memberSince}
            </div>
          )}
          {/* Badge Google (siempre OAuth) */}
          <div className="mt-1.5 inline-flex items-center gap-1.5 rounded-full border hairline px-2 py-0.5">
            <GoogleIcon size={12} />
            <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted-foreground">
              Google
            </span>
          </div>
        </div>
      </div>

      {/* Datos de contacto */}
      <div className="rounded-lg border hairline bg-card divide-y divide-hairline mb-4">
        <div className="flex items-center gap-3 px-4 py-3">
          <Mail className="h-4 w-4 text-muted-foreground shrink-0" />
          <span className="font-sans text-sm text-ink flex-1 min-w-0 truncate">{perfil.email}</span>
          <span className="inline-flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.1em] text-muted-foreground">
            <Lock className="h-2.5 w-2.5" /> Verificado
          </span>
        </div>
        {perfil.telefono && (
          <div className="flex items-center gap-3 px-4 py-3">
            <Phone className="h-4 w-4 text-muted-foreground shrink-0" />
            <span className="font-sans text-sm text-ink flex-1">{perfil.telefono}</span>
            <span className="inline-flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.1em] text-muted-foreground">
              <Lock className="h-2.5 w-2.5" /> Verificado
            </span>
          </div>
        )}
        {perfil.direccion && (
          <div className="flex items-center gap-3 px-4 py-3">
            <MapPin className="h-4 w-4 text-muted-foreground shrink-0" />
            <span className="font-sans text-sm text-ink flex-1 min-w-0 truncate">
              {perfil.direccion}
            </span>
          </div>
        )}
        {perfil.cuit && (
          <div className="flex items-center gap-3 px-4 py-3">
            <Building2 className="h-4 w-4 text-muted-foreground shrink-0" />
            <span className="font-sans text-sm text-ink">CUIT {perfil.cuit}</span>
          </div>
        )}
      </div>

      <p className="font-sans text-xs text-muted-foreground mb-6 leading-[1.5]">
        Estos datos son los que usamos para los contratos y remitos. Si necesitás actualizarlos,
        contactanos por WhatsApp.
      </p>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-2 mb-6">
        <div className="rounded-lg border hairline bg-card px-4 py-3 text-center">
          <div className="font-sans font-extrabold text-[26px] text-ink leading-none tabular-nums">
            {pedidosCount}
          </div>
          <div className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted-foreground mt-1">
            Pedidos
          </div>
        </div>
        <div className="rounded-lg border hairline bg-card px-4 py-3 text-center">
          <div className="font-sans font-extrabold text-[22px] text-ink leading-none tabular-nums">
            {formatARS(totalAlquilado)}
          </div>
          <div className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted-foreground mt-1">
            Total alquilado
          </div>
        </div>
      </div>

      {/* Logout */}
      <button
        type="button"
        onClick={onLogout}
        className="w-full flex items-center justify-center gap-2 rounded-[10px] border border-destructive/25 h-[42px] font-sans text-sm text-destructive hover:bg-destructive/5 transition"
      >
        <LogOut className="h-4 w-4" /> Cerrar sesión
      </button>
    </div>
  );
}

function PedidoEmpty({
  title,
  sub,
  cta,
  actionLabel,
  onAction,
  icon = "bag",
}: {
  title: string;
  sub: string;
  cta?: boolean;
  actionLabel?: string;
  onAction?: () => void;
  icon?: "bag" | "search";
}) {
  const Icon = icon === "search" ? Search : ShoppingBag;
  return (
    <div className="rounded-xl border border-dashed border-[var(--hairline)] px-6 py-[60px] text-center">
      <div className="mx-auto mb-3.5 grid h-14 w-14 place-items-center rounded-full bg-amber-soft text-amber">
        <Icon className="h-6 w-6" strokeWidth={1.5} />
      </div>
      <div className="font-display text-xl font-black text-ink mb-1.5">{title}</div>
      <div className="font-sans text-[13px] text-muted-foreground mb-[18px]">{sub}</div>
      {actionLabel && onAction ? (
        <button
          type="button"
          onClick={onAction}
          className="inline-flex items-center gap-1.5 rounded-full bg-ink px-5 py-2.5 font-sans text-[13px] font-bold text-amber transition hover:bg-amber hover:text-ink"
        >
          {actionLabel} <XIcon className="h-3.5 w-3.5" />
        </button>
      ) : (
        cta && (
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 rounded-full bg-ink px-5 py-2.5 font-sans text-[13px] font-bold text-amber transition hover:bg-amber hover:text-ink"
          >
            Explorar catálogo <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        )
      )}
    </div>
  );
}

function PedidoCard({
  pedido,
  expanded,
  highlight = false,
  onToggle,
  ventanaHoras,
  onChanged,
  perfilImpuestos,
}: {
  pedido: Pedido;
  expanded: boolean;
  highlight?: boolean;
  onToggle: () => void;
  ventanaHoras: number;
  onChanged: () => void;
  perfilImpuestos: string | null;
}) {
  const navigate = useNavigate();
  const businessPhone = useBusinessPhone();
  const { documentos_disponibles: docs } = pedido;
  const numero = pedido.numero_pedido ?? pedido.id;
  // Pedido recién enviado: banner de bienvenida con los próximos pasos.
  const showWelcome = highlight && pedido.estado === "presupuesto";
  const jornadas = jornadasEntre(pedido.fecha_desde, pedido.fecha_hasta);
  const tlCurrent = buildTimelineSteps(pedido).find((s) => s.state === "current");
  const cardRef = useRef<HTMLDivElement>(null);

  // Al colapsar, la página pierde alto y el scroll se clampea saltando arriba.
  // Capturamos el top del head antes del toggle y compensamos con scrollBy en
  // el próximo frame para que la card quede en la misma posición visual.
  function handleToggle() {
    if (expanded && cardRef.current) {
      const before = cardRef.current.getBoundingClientRect().top;
      onToggle();
      requestAnimationFrame(() => {
        if (!cardRef.current) return;
        const after = cardRef.current.getBoundingClientRect().top;
        if (after !== before) window.scrollBy(0, after - before);
      });
    } else {
      onToggle();
    }
  }

  const [askCancel, setAskCancel] = useState(false);
  const pendiente = (pedido.solicitudes ?? []).find((s) => s.estado === "pendiente");
  // Última solicitud que el cliente debe ver: aprobada, rechazada, o
  // cancelada por el sistema (cuando el pedido cambia de estado). Las
  // canceladas por el propio cliente las ocultamos: él la canceló.
  const ultimaResuelta = !pendiente
    ? (pedido.solicitudes ?? [])
        .filter((s) => {
          if (s.estado === "aprobada" || s.estado === "rechazada") return true;
          if (s.estado === "cancelada" && s.resolved_by === "system") return true;
          return false;
        })
        .sort((a, b) =>
          (b.resolved_at ?? b.created_at).localeCompare(a.resolved_at ?? a.created_at),
        )[0]
    : undefined;

  const dentroVentana = (() => {
    if (!pedido.fecha_desde) return true; // pedido sin fechas: permitir editar
    const desde = new Date(pedido.fecha_desde.slice(0, 10) + "T00:00:00").getTime();
    if (Number.isNaN(desde)) return true; // fecha inválida: no bloqueamos
    const ms = ventanaHoras * 60 * 60 * 1000;
    return desde - Date.now() >= ms;
  })();

  const puedeModificar = MODIFICABLE_STATES.has(pedido.estado) && !pendiente && dentroVentana;

  async function cancelarSolicitud() {
    if (!pendiente) return;
    try {
      await clienteApi.cancelarSolicitud(pedido.id, pendiente.id);
      toast.success("Solicitud cancelada");
      onChanged();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  // Desglose canónico desde el backend (services/precios.calcular_total).
  // Antes este componente hardcodeaba `* 0.21` y comparaba el literal
  // "responsable_inscripto" — el backend ya lo provee aplicando la misma
  // regla que el carrito, el admin y el PDF (#496).
  const subtotalItems = pedido.bruto ?? pedido.items.reduce((acc, it) => acc + it.subtotal, 0);
  const descuentoPct = pedido.descuento_pct ?? 0;
  const descuentoMonto = pedido.descuento_monto ?? Math.round(subtotalItems * (descuentoPct / 100));
  const totalNeto = pedido.monto_neto ?? pedido.monto_total ?? subtotalItems - descuentoMonto;
  const conIva = pedido.con_iva ?? false;
  const ivaPct = pedido.iva_pct ?? 21;
  const ivaMonto = pedido.iva_monto ?? 0;
  const total = pedido.total_con_iva ?? totalNeto;
  const pagado = pedido.monto_pagado ?? 0;
  const balance = Math.max(0, total - pagado);

  const retiroTime = fmtTime(pedido.fecha_desde);
  const devolucionTime = fmtTime(pedido.fecha_hasta);

  return (
    <div
      ref={cardRef}
      id={`pedido-${pedido.id}`}
      className={cn(
        "rounded-xl border bg-surface overflow-hidden transition-[border-color,box-shadow] scroll-mt-4",
        expanded
          ? "border-amber shadow-[0_0_0_1px_var(--amber)]"
          : "border-[var(--hairline)] hover:border-ink/30",
        highlight && "ring-2 ring-amber ring-offset-2 ring-offset-background animate-pulse",
      )}
    >
      <div className="flex items-stretch">
        <button
          type="button"
          onClick={handleToggle}
          className="flex-1 min-w-0 flex items-center gap-3.5 px-4 sm:px-[18px] py-3.5 transition hover:bg-[color-mix(in_oklch,var(--ink)_2%,transparent)] text-left"
        >
          <span className="font-mono text-[13px] font-bold text-ink tracking-[0.04em]">
            #{pedido.numero_pedido}
          </span>
          {pendiente ? (
            <span className="inline-flex items-center rounded-full border border-amber/30 bg-amber/15 px-2 py-0.5 text-[10px] font-medium text-ink">
              Mod. pendiente
            </span>
          ) : (
            <EstadoBadge estado={pedido.estado} />
          )}
          <span className="font-sans text-[13px] text-muted-foreground flex-1 min-w-0 truncate">
            {fmtDate(pedido.fecha_desde)}
            <span className="opacity-40 mx-1">→</span>
            {fmtDate(pedido.fecha_hasta)}
          </span>
          {pedido.monto_total != null && (
            <span className="font-sans text-[17px] font-extrabold text-ink tabular-nums shrink-0">
              {/* Header colapsado: muestra el total que el cliente paga
                  (con IVA si es RI) — alineado con el desglose expandido y
                  el carrito/PDF. Fallback al neto si el backend no envió
                  el desglose (pedidos cargados desde un endpoint viejo). */}
              {fmt(pedido.total_con_iva ?? pedido.monto_total)}
            </span>
          )}
          <ChevronDown
            className={cn(
              "h-4 w-4 shrink-0 transition-[transform,color] duration-200",
              expanded ? "rotate-180 text-ink" : "text-muted-foreground",
            )}
          />
        </button>
        {!expanded && puedeModificar && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              navigate({
                to: "/cliente/pedidos/$id/editar",
                params: { id: String(pedido.id) },
              });
            }}
            className="shrink-0 px-3 sm:px-4 border-l border-[var(--hairline)] text-ink hover:bg-amber-soft transition inline-flex items-center gap-1.5"
            aria-label="Modificar pedido"
          >
            <Pencil className="h-3.5 w-3.5" />
            <span className="font-sans text-xs font-semibold hidden sm:inline">Modificar</span>
          </button>
        )}
      </div>

      {expanded && (
        <div className="border-t border-dashed border-[var(--hairline)] px-4 sm:px-[18px] pt-[18px] pb-[22px] grid gap-y-5 gap-x-7 animate-[expand-in_.22s_ease-out] [grid-template-areas:'banner''timeline''main''side'] lg:[grid-template-columns:minmax(0,1fr)_clamp(20rem,26%,25rem)] lg:[grid-template-areas:'banner_banner''timeline_timeline''main_side']">
          {/* ── Banner: solicitud pendiente / resuelta / bienvenida (full width) ── */}
          {(pendiente || ultimaResuelta || showWelcome) && (
            <div className="[grid-area:banner] flex flex-col gap-3">
              {showWelcome && (
                <section className="rounded-md border border-amber bg-amber-soft px-3.5 py-3 flex items-start gap-2.5">
                  <CircleCheckBig className="h-4 w-4 text-amber mt-0.5 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="font-sans text-[13px] font-semibold text-ink">
                      ¡Recibimos tu solicitud!
                    </div>
                    <div className="font-sans text-xs text-ink/70 mt-0.5">
                      La estamos revisando. Cuando confirmemos la disponibilidad vas a poder
                      descargar el remito y el contrato desde acá. Seguí el estado en la línea de
                      tiempo de abajo.
                    </div>
                  </div>
                </section>
              )}
              {pendiente && (
                <section className="rounded-md border border-amber bg-amber-soft px-3.5 py-3 flex items-start gap-2.5">
                  <Clock className="h-4 w-4 text-amber mt-0.5 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="font-sans text-[13px] font-semibold text-ink">
                      Solicitud de modificación pendiente
                    </div>
                    <div className="font-sans text-xs text-ink/70 mt-0.5">
                      Estamos revisando los cambios que pediste. Te avisamos por mail cuando los
                      resolvamos.
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setAskCancel(true)}
                    className="rounded-full px-4 py-2 font-sans text-sm font-semibold text-ink border border-ink/20 hover:border-ink transition shrink-0 inline-flex items-center gap-1.5 min-h-[40px]"
                  >
                    <XIcon className="h-3.5 w-3.5" /> Cancelar
                  </button>
                </section>
              )}

              {ultimaResuelta &&
                (() => {
                  const isAprobada = ultimaResuelta.estado === "aprobada";
                  const isRechazada = ultimaResuelta.estado === "rechazada";
                  const isSystemCancel = ultimaResuelta.estado === "cancelada"; // ya filtramos por resolved_by='system'
                  const titulo = isAprobada
                    ? "Tu última solicitud fue aprobada"
                    : isRechazada
                      ? "Tu última solicitud fue rechazada"
                      : "Tu solicitud quedó sin efecto";
                  return (
                    <section
                      className={cn(
                        "rounded-md border px-3.5 py-3 flex items-start gap-2.5",
                        isAprobada
                          ? "border-verde/30 bg-verde/10"
                          : isRechazada
                            ? "border-destructive/30 bg-destructive/10"
                            : "border-azul/30 bg-azul/10",
                      )}
                    >
                      {isAprobada ? (
                        <CheckCircle2 className="h-4 w-4 text-verde mt-0.5 shrink-0" />
                      ) : isRechazada ? (
                        <XCircle className="h-4 w-4 text-destructive mt-0.5 shrink-0" />
                      ) : (
                        <Info className="h-4 w-4 text-azul mt-0.5 shrink-0" />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="font-sans text-[13px] font-semibold text-ink">{titulo}</div>
                        {ultimaResuelta.respuesta && (
                          <div className="font-sans text-xs text-ink/80 mt-0.5 whitespace-pre-wrap">
                            {isSystemCancel ? ultimaResuelta.respuesta : ultimaResuelta.respuesta}
                          </div>
                        )}
                      </div>
                    </section>
                  );
                })()}
            </div>
          )}

          {/* ── Timeline: card propia, full width ── */}
          <section className="[grid-area:timeline] rounded-lg border border-[var(--hairline)] bg-card px-5 pt-[18px] pb-4">
            <div className="flex items-baseline justify-between gap-3 mb-3.5">
              <h3 className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted-foreground">
                Estado del pedido
              </h3>
              {tlCurrent && (
                <div className="font-sans text-xs text-muted-foreground text-right flex-1 min-w-0 leading-[1.4]">
                  <strong className="text-ink font-semibold">{tlCurrent.label}</strong>
                  {tlCurrent.desc ? ` · ${tlCurrent.desc}` : ""}
                </div>
              )}
            </div>
            <PedidoTimeline pedido={pedido} />
          </section>

          {/* ── Main (izquierda): período → equipos → acciones ── */}
          <div className="[grid-area:main] flex flex-col gap-5 min-w-0">
            <section className="grid grid-cols-3 gap-2">
              <div className="rounded-md border border-[var(--hairline)] bg-card px-3 py-2.5">
                <div className="font-mono text-[8px] uppercase tracking-[0.22em] text-muted-foreground">
                  Retiro
                </div>
                <div className="font-sans text-sm font-semibold text-ink mt-0.5">
                  {fmtDate(pedido.fecha_desde)}
                </div>
                {retiroTime && (
                  <div className="font-mono text-[10px] text-muted-foreground">{retiroTime}</div>
                )}
              </div>
              <div className="rounded-md border border-[var(--hairline)] bg-card px-3 py-2.5">
                <div className="font-mono text-[8px] uppercase tracking-[0.22em] text-muted-foreground">
                  Devolución
                </div>
                <div className="font-sans text-sm font-semibold text-ink mt-0.5">
                  {fmtDate(pedido.fecha_hasta)}
                </div>
                {devolucionTime && (
                  <div className="font-mono text-[10px] text-muted-foreground">
                    {devolucionTime}
                  </div>
                )}
              </div>
              <div className="rounded-md border border-[var(--hairline)] bg-card px-3 py-2.5">
                <div className="font-mono text-[8px] uppercase tracking-[0.22em] text-muted-foreground">
                  Jornadas
                </div>
                <div className="font-sans text-2xl font-extrabold text-ink tabular-nums leading-none mt-1">
                  {jornadas}
                </div>
              </div>
            </section>

            <section>
              <h3 className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted-foreground mb-2">
                Equipos ({pedido.items.length})
              </h3>
              <ul>
                {pedido.items.map((item, i) => {
                  const display = item.nombre_publico || item.nombre;
                  return (
                    <li
                      key={item.id ?? i}
                      className="flex items-center gap-2.5 py-2 border-b border-[var(--hairline)] last:border-b-0"
                    >
                      {item.foto_url ? (
                        <img
                          src={item.foto_url}
                          alt={display}
                          loading="lazy"
                          className="h-10 w-10 rounded-sm border border-[var(--hairline)] bg-white object-cover shrink-0"
                        />
                      ) : (
                        <div className="h-10 w-10 rounded-sm border border-[var(--hairline)] bg-white grid place-items-center shrink-0">
                          <ShoppingBag
                            className="h-4 w-4 text-muted-foreground"
                            strokeWidth={1.5}
                          />
                        </div>
                      )}
                      <div className="min-w-0 flex-1">
                        {item.marca && (
                          <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground leading-none">
                            {item.marca}
                          </div>
                        )}
                        <div className="font-sans text-[13px] font-semibold text-ink leading-tight mt-0.5 truncate">
                          {display}
                        </div>
                        <div className="font-mono text-[10px] text-muted-foreground tabular-nums mt-0.5">
                          {item.cantidad} × {fmt(item.precio_jornada)}/j · {jornadas}j
                        </div>
                      </div>
                      <div className="font-mono text-[13px] font-bold text-ink tabular-nums shrink-0">
                        {fmt(item.subtotal)}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>

            {puedeModificar && (
              <section>
                <button
                  type="button"
                  onClick={() =>
                    navigate({
                      to: "/cliente/pedidos/$id/editar",
                      params: { id: String(pedido.id) },
                    })
                  }
                  className="inline-flex items-center gap-1.5 rounded-full bg-ink px-4 py-2 font-sans text-[13px] font-bold text-amber hover:bg-amber hover:text-ink transition"
                >
                  <Pencil className="h-3.5 w-3.5" /> Modificar pedido
                </button>
                {pedido.estado === "confirmado" && (
                  <p className="mt-2 font-sans text-xs text-muted-foreground">
                    Los cambios necesitarán nuestra aprobación.
                  </p>
                )}
              </section>
            )}

            {!puedeModificar &&
              MODIFICABLE_STATES.has(pedido.estado) &&
              !pendiente &&
              !dentroVentana && (
                <section className="rounded-md border border-dashed border-[var(--hairline)] px-3.5 py-2.5 font-sans text-xs text-muted-foreground">
                  No es posible modificar este pedido a menos de {ventanaHoras} h del retiro.
                  Contactanos directamente.
                </section>
              )}

            {(() => {
              const waHref = whatsappLink({
                phone: businessPhone,
                message: `Hola, consulta sobre el pedido #${numero}`,
              });
              if (!waHref) return null;
              return (
                <section>
                  <a
                    href={waHref}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 rounded-full bg-[#25D366] text-white px-4 py-2.5 font-sans text-sm font-semibold hover:brightness-95 transition min-h-[44px]"
                  >
                    <MessageCircle className="h-4 w-4" strokeWidth={2.2} />
                    Consulta por WhatsApp
                  </a>
                </section>
              );
            })()}
          </div>

          {/* ── Side (derecha): documentos → totales → pagos → notas ── */}
          <aside className="[grid-area:side] flex flex-col gap-4 min-w-0">
            {(docs.remito || docs.contrato || docs.albaran) && (
              <section
                className="rounded-md border px-3 py-3"
                style={{
                  background: "color-mix(in oklch, var(--amber) 6%, var(--background))",
                  borderColor: "color-mix(in oklch, var(--amber) 35%, transparent)",
                }}
              >
                <h3 className="font-mono text-[9px] uppercase tracking-[0.22em] text-ink/70 mb-2">
                  Documentos
                </h3>
                <div className="grid gap-2 [grid-template-columns:repeat(auto-fill,minmax(150px,1fr))]">
                  {docs.remito && (
                    <DocActions pedidoId={pedido.id} numero={numero} tipo="remito" label="Remito" />
                  )}
                  {docs.contrato && (
                    <DocActions
                      pedidoId={pedido.id}
                      numero={numero}
                      tipo="contrato"
                      label="Contrato"
                      description={DOC_DESCRIPTION.contrato}
                    />
                  )}
                  {docs.albaran && (
                    <DocActions
                      pedidoId={pedido.id}
                      numero={numero}
                      tipo="albaran"
                      label="Albarán"
                      description={DOC_DESCRIPTION.albaran}
                    />
                  )}
                </div>
              </section>
            )}

            <section className="flex flex-col gap-1.5 rounded-md border border-[var(--hairline)] bg-card px-3.5 py-3">
              <div className="flex justify-between items-baseline font-sans text-[13px]">
                <span className="text-muted-foreground">Subtotal equipos</span>
                <span className="font-mono font-semibold text-ink tabular-nums">
                  {fmt(subtotalItems)}
                </span>
              </div>
              {descuentoPct > 0 && (
                <div className="flex justify-between items-baseline font-sans text-[13px]">
                  <span className="text-muted-foreground">Descuento ({descuentoPct}%)</span>
                  <span className="font-mono font-semibold tabular-nums text-verde">
                    −{fmt(descuentoMonto)}
                  </span>
                </div>
              )}
              {conIva && (
                <>
                  <div className="flex justify-between items-baseline font-sans text-[13px]">
                    <span className="text-muted-foreground">Subtotal neto</span>
                    <span className="font-mono font-semibold text-ink tabular-nums">
                      {fmt(totalNeto)}
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline font-sans text-[13px]">
                    <span className="text-muted-foreground">IVA {ivaPct}%</span>
                    <span className="font-mono font-semibold text-ink tabular-nums">
                      +{fmt(ivaMonto)}
                    </span>
                  </div>
                </>
              )}
              <div className="flex justify-between items-baseline pt-1.5 mt-1 border-t border-[var(--hairline)]">
                <span className="font-sans text-[15px] font-bold text-ink">
                  Total{conIva ? " · IVA incluído" : ""}
                </span>
                <span className="font-sans text-[22px] font-extrabold text-ink tabular-nums">
                  {fmt(total)}
                </span>
              </div>
              {pagado > 0 && (
                <>
                  <div className="flex justify-between items-baseline font-sans text-[13px]">
                    <span className="text-muted-foreground">Pagado</span>
                    <span className="font-mono font-semibold tabular-nums text-verde">
                      {fmt(pagado)}
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline font-sans text-[13px]">
                    <span className="text-muted-foreground">
                      {balance > 0 ? "Balance pendiente" : "Saldo"}
                    </span>
                    <span
                      className={cn(
                        "font-mono font-bold tabular-nums",
                        balance > 0 ? "text-ink" : "text-verde",
                      )}
                    >
                      {fmt(balance)}
                    </span>
                  </div>
                </>
              )}
            </section>

            {pedido.pagos && pedido.pagos.length > 0 && (
              <section>
                <h3 className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted-foreground mb-2">
                  Pagos
                </h3>
                <ul className="flex flex-col gap-1">
                  {pedido.pagos.map((pg, i) => (
                    <li
                      key={pg.id ?? i}
                      className="flex items-center justify-between gap-2 font-sans text-xs text-muted-foreground"
                    >
                      <span className="truncate">
                        {fmtDate(pg.fecha)}
                        {pg.concepto ? ` · ${pg.concepto}` : ""}
                      </span>
                      <span className="font-mono tabular-nums text-verde shrink-0">
                        {fmt(pg.monto)}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {pedido.notas && (
              <section>
                <h3 className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted-foreground mb-2">
                  Notas
                </h3>
                <div className="rounded-md border border-[color-mix(in_oklch,var(--amber)_40%,transparent)] bg-amber-soft px-3.5 py-3 font-sans text-xs text-ink leading-[1.5] whitespace-pre-wrap">
                  {pedido.notas}
                </div>
              </section>
            )}
          </aside>
        </div>
      )}

      <AlertDialog open={askCancel} onOpenChange={setAskCancel}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancelar solicitud de modificación</AlertDialogTitle>
            <AlertDialogDescription>
              Vamos a descartar los cambios que pediste. El pedido va a quedar como estaba.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Volver</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setAskCancel(false);
                cancelarSolicitud();
              }}
            >
              Cancelar solicitud
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

const DOC_ICONS: Record<"remito" | "contrato" | "albaran", string> = {
  remito:
    "M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8",
  contrato: "M9 11l3 3 8-8 M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11",
  albaran:
    "M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z",
};

function DocPath({ tipo }: { tipo: keyof typeof DOC_ICONS }) {
  const paths = DOC_ICONS[tipo].split(" M");
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths.map((p, i) => (
        <path key={i} d={i === 0 ? p : `M${p}`} />
      ))}
    </svg>
  );
}

/**
 * Acciones por documento: Ver (preview HTML en modal) + Descargar (PDF).
 * Issue #106.
 */
function DocActions({
  pedidoId,
  numero,
  tipo,
  label,
  description,
}: {
  pedidoId: number;
  numero: string;
  tipo: "remito" | "contrato" | "albaran";
  label: string;
  description?: string;
}) {
  const [previewOpen, setPreviewOpen] = useState(false);
  // Badge "Nuevo" si todavía no se vio. Sólo para contrato/albaran (los
  // notificables). El estado vive en localStorage; lo trackeamos con un
  // ref local para que el badge desaparezca instantáneamente al tocar.
  const [seen, setSeen] = useState<boolean>(() =>
    tipo === "remito" ? true : wasDocSeen(pedidoId, tipo),
  );
  const showNewBadge = !seen;

  function markSeen() {
    if (tipo === "remito") return;
    markDocSeen(pedidoId, tipo);
    setSeen(true);
  }

  return (
    <>
      <div className="flex items-stretch gap-1">
        <button
          type="button"
          onClick={() => {
            markSeen();
            setPreviewOpen(true);
          }}
          className="flex-1 relative flex items-center gap-2.5 rounded-md border border-[var(--hairline)] bg-card px-3 py-2.5 text-left transition hover:border-ink hover:bg-muted"
        >
          {showNewBadge && (
            <span className="absolute -top-1.5 -right-1.5 rounded-full bg-ink text-amber text-[9px] font-bold tracking-wide px-1.5 py-0.5 leading-none shadow">
              Nuevo
            </span>
          )}
          <div className="grid h-8 w-8 place-items-center rounded-sm bg-amber-soft text-amber shrink-0">
            <DocPath tipo={tipo} />
          </div>
          <div className="min-w-0">
            <div className="font-sans text-xs font-semibold text-ink leading-tight">{label}</div>
            {description ? (
              <div className="font-sans text-[11px] text-muted-foreground leading-tight mt-0.5 line-clamp-2">
                {description}
              </div>
            ) : (
              <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted-foreground mt-0.5">
                Ver · PDF
              </div>
            )}
          </div>
        </button>
        <a
          href={`/api/cliente/pedidos/${pedidoId}/${tipo}.pdf`}
          download={`${tipo}-${numero}.pdf`}
          onClick={markSeen}
          className="grid place-items-center w-10 rounded-md border border-[var(--hairline)] bg-card text-muted-foreground transition hover:border-ink hover:text-ink"
          title={`Descargar ${label} en PDF`}
          aria-label={`Descargar ${label} en PDF`}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
        </a>
      </div>

      {previewOpen && (
        <DocPreviewModal
          title={label}
          url={`/api/cliente/pedidos/${pedidoId}/${tipo}?format=html`}
          downloadUrl={`/api/cliente/pedidos/${pedidoId}/${tipo}.pdf`}
          downloadFilename={`${tipo}-${numero}.pdf`}
          onClose={() => setPreviewOpen(false)}
        />
      )}
    </>
  );
}

/**
 * Modal con iframe que muestra el HTML del documento. Botón de descargar
 * PDF en el header. ESC o click afuera cierra.
 */
function DocPreviewModal({
  title,
  url,
  downloadUrl,
  downloadFilename,
  onClose,
}: {
  title: string;
  url: string;
  downloadUrl: string;
  downloadFilename: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-stretch sm:items-center justify-center sm:p-6"
      onClick={onClose}
    >
      <div
        className="bg-background w-full sm:max-w-4xl sm:max-h-[90vh] h-full sm:h-auto flex flex-col sm:rounded-lg overflow-hidden shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between gap-2 border-b hairline px-3 sm:px-4 py-3 shrink-0">
          <h2 className="font-display text-base text-ink truncate min-w-0">{title}</h2>
          <div className="flex items-center gap-1 sm:gap-2 shrink-0">
            <a
              href={downloadUrl}
              download={downloadFilename}
              className="inline-flex items-center gap-1.5 rounded-md bg-ink text-amber px-2.5 sm:px-3 py-2 text-xs font-medium hover:brightness-110 transition"
              aria-label="Descargar PDF"
            >
              <span aria-hidden>⬇</span>
              <span className="hidden sm:inline">Descargar PDF</span>
            </a>
            <button
              type="button"
              onClick={onClose}
              className="grid h-10 w-10 place-items-center rounded-md hover:bg-muted transition"
              aria-label="Cerrar"
            >
              ✕
            </button>
          </div>
        </header>
        <iframe src={url} title={title} className="flex-1 w-full bg-white border-0" />
      </div>
    </div>
  );
}

/**
 * Popup one-shot que notifica al cliente cuando un documento nuevo
 * (Contrato/Albarán) está disponible. Cada (pedido, doc) se persiste en
 * localStorage al cerrar para no volver a aparecer.
 */
function DocAvailablePopup({
  nuevos,
  onDismiss,
  onVerPedido,
}: {
  nuevos: Array<{ pedidoId: number; numero: string; tipo: DocTipo }>;
  onDismiss: () => void;
  onVerPedido: (pedidoId: number) => void;
}) {
  const open = nuevos.length > 0;
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onDismiss();
      }}
    >
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Tenés documentos nuevos disponibles</DialogTitle>
          <DialogDescription>
            Estos documentos quedaron habilitados en tu portal. Podés verlos cuando quieras.
          </DialogDescription>
        </DialogHeader>
        <ul className="space-y-2.5 my-2">
          {nuevos.map((d) => {
            const Icon =
              d.tipo === "contrato" ? FileSignature : d.tipo === "albaran" ? Truck : FileText;
            return (
              <li
                key={`${d.pedidoId}-${d.tipo}`}
                className="flex items-start gap-3 rounded-md border hairline px-3 py-2.5"
              >
                <div className="grid h-9 w-9 place-items-center rounded-sm bg-amber-soft text-amber shrink-0">
                  <Icon className="h-4 w-4" strokeWidth={1.7} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-sans text-sm font-semibold text-ink">
                    {DOC_LABEL[d.tipo]}
                    <span className="text-muted-foreground font-mono text-xs ml-1.5">
                      #{d.numero}
                    </span>
                  </div>
                  {DOC_DESCRIPTION[d.tipo] && (
                    <div className="font-sans text-xs text-muted-foreground mt-0.5">
                      {DOC_DESCRIPTION[d.tipo]}
                    </div>
                  )}
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="shrink-0"
                  onClick={() => onVerPedido(d.pedidoId)}
                >
                  Ver pedido
                </Button>
              </li>
            );
          })}
        </ul>
        <DialogFooter>
          <Button onClick={onDismiss}>Entendido</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Timeline cronológico del pedido ────────────────────────────────────────
// Derivado en frontend de `created_at` del pedido + `solicitudes[]` + el
// `estado` actual. Camino A del HANDOFF_BACKEND.md — el backend no guarda
// (todavía) un log de transiciones de estado, así que mostramos el flujo
// canónico y marcamos cada paso como done/current/pending según el estado
// actual; solo "solicitado" y los eventos de modificación tienen fecha
// exacta.

type TLState = "pending" | "done" | "current" | "rejected";
type TLStep = {
  key: string;
  label: string;
  desc: string;
  fecha?: string | null;
  nota?: string | null;
  state: TLState;
};

const FLOW_STEPS: ReadonlyArray<{ tipo: string; label: string; desc: string }> = [
  {
    tipo: "solicitado",
    label: "Solicitado",
    desc: "Recibimos tu pedido. Lo revisamos y te confirmamos disponibilidad.",
  },
  {
    tipo: "confirmado",
    label: "Confirmado",
    desc: "Equipos reservados a tu nombre. Listo para retirar en la fecha.",
  },
  { tipo: "retirado", label: "Retirado", desc: "Pasaste por el local y te llevaste el equipo." },
  { tipo: "devuelto", label: "Devuelto", desc: "Recibimos el equipo de vuelta y lo revisamos." },
  { tipo: "finalizado", label: "Finalizado", desc: "Pedido cerrado. Gracias por elegirnos." },
];

// Cuántos FLOW_STEPS están completados según el estado actual.
const ESTADO_PROGRESS: Record<string, number> = {
  borrador: 0,
  presupuesto: 1,
  confirmado: 2,
  retirado: 3,
  devuelto: 4,
  finalizado: 5,
};

function buildTimelineSteps(pedido: Pedido): TLStep[] {
  const cancelado = pedido.estado === "cancelado";
  const progress = ESTADO_PROGRESS[pedido.estado] ?? 1;

  const flow: TLStep[] = FLOW_STEPS.map((step, idx) => ({
    key: step.tipo,
    label: step.label,
    desc: step.desc,
    // Solo el primer paso ("solicitado") tiene fecha exacta — viene de
    // created_at del pedido. Los demás no se loggean en backend (gap).
    fecha: step.tipo === "solicitado" ? (pedido.created_at ?? null) : null,
    state: idx < progress ? "done" : "pending",
  }));

  // Eventos de modificación derivados de solicitudes[]. Solo mostramos al
  // cliente las que él inició: pendiente/aprobada/rechazada, más las
  // canceladas-por-sistema (cuando el pedido cambia de estado y se anula
  // la solicitud). Las que él mismo canceló no las mostramos — ya lo sabe.
  const mods: TLStep[] = [];
  for (const sol of pedido.solicitudes ?? []) {
    mods.push({
      key: `mod_sol-${sol.id}`,
      label: "Modificación solicitada",
      desc: "Pediste un cambio en el pedido.",
      fecha: sol.created_at,
      state: sol.estado === "pendiente" ? "current" : "done",
    });
    if (sol.estado === "aprobada") {
      mods.push({
        key: `mod_ap-${sol.id}`,
        label: "Modificación aceptada",
        desc: "Aplicamos el cambio que pediste.",
        fecha: sol.resolved_at,
        nota: sol.respuesta,
        state: "done",
      });
    } else if (sol.estado === "rechazada") {
      mods.push({
        key: `mod_re-${sol.id}`,
        label: "Modificación rechazada",
        desc: "No pudimos aplicar el cambio.",
        fecha: sol.resolved_at,
        nota: sol.respuesta,
        state: "rejected",
      });
    } else if (sol.estado === "cancelada" && sol.resolved_by === "system") {
      mods.push({
        key: `mod_ca-${sol.id}`,
        label: "Solicitud anulada",
        desc: "El pedido cambió de estado y la solicitud quedó sin efecto.",
        fecha: sol.resolved_at,
        nota: sol.respuesta,
        state: "rejected",
      });
    }
  }

  // Mezclar: ítems con fecha en orden cronológico + flow sin fecha
  // mantienen su posición relativa después.
  const withDate = [...flow.filter((s) => s.fecha), ...mods.filter((m) => m.fecha)].sort((a, b) =>
    (a.fecha ?? "").localeCompare(b.fecha ?? ""),
  );
  const withoutDate = flow.filter((s) => !s.fecha);

  let merged: TLStep[] = [...withDate, ...withoutDate];

  if (cancelado) {
    merged = merged.filter((it) => it.state !== "pending");
    merged.push({
      key: "cancelado",
      label: "Cancelado",
      desc: "El pedido fue cancelado.",
      state: "rejected",
    });
    return merged;
  }

  // Marcar paso actual: si ya hay un "current" (por solicitud pendiente)
  // no tocamos; sino, el último "done" pasa a "current".
  const hasCurrent = merged.some((it) => it.state === "current");
  if (!hasCurrent) {
    let lastDone = -1;
    for (let i = 0; i < merged.length; i++) {
      if (merged[i].state === "done") lastDone = i;
    }
    if (lastDone >= 0) merged[lastDone].state = "current";
  }

  return merged;
}

function fmtTimelineDateTime(s?: string | null): string | null {
  if (!s) return null;
  const dStr = s.slice(0, 10);
  if (dStr.length < 10) return null;
  const d = new Date(dStr + "T" + (s.length >= 16 ? s.slice(11, 16) : "12:00") + ":00");
  if (Number.isNaN(d.getTime())) return null;
  const dias = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
  const meses = [
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
  ];
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${dias[d.getDay()]} ${d.getDate()} ${meses[d.getMonth()]} · ${hh}:${mm}`;
}

function PedidoTimeline({ pedido }: { pedido: Pedido }) {
  const steps = buildTimelineSteps(pedido);
  return (
    <div className="flex flex-row items-start gap-0 pt-1">
      {steps.map((s, i) => {
        const isLast = i === steps.length - 1;
        const dotCls =
          s.state === "done"
            ? "border-ink bg-ink text-amber"
            : s.state === "current"
              ? "border-amber bg-amber text-ink shadow-[0_0_0_4px_var(--amber-soft)]"
              : s.state === "rejected"
                ? "border-destructive bg-destructive text-white"
                : "border-[var(--hairline)] bg-background text-muted-foreground border-dashed";
        const connectorCls =
          s.state === "done"
            ? "after:bg-ink/25"
            : s.state === "current"
              ? "after:bg-[image:linear-gradient(to_right,var(--amber)_0%,var(--amber)_50%,var(--hairline)_50%)]"
              : s.state === "rejected"
                ? "after:bg-destructive/30"
                : "after:bg-[var(--hairline)]";
        const Icon =
          s.state === "rejected"
            ? XCircle
            : s.state === "current"
              ? Clock
              : s.state === "done"
                ? CircleCheckBig
                : Clock;
        return (
          <div
            key={s.key}
            className={cn(
              "relative flex-1 min-w-0 flex flex-col items-center text-center px-1 gap-2",
              !isLast &&
                "after:content-[''] after:absolute after:top-[13px] after:left-[calc(50%+18px)] after:right-[calc(-50%+18px)] after:h-0.5",
              !isLast && connectorCls,
            )}
          >
            <div
              className={cn(
                "z-[1] grid h-7 w-7 shrink-0 place-items-center rounded-full border-2",
                dotCls,
              )}
            >
              <Icon className="h-3 w-3" strokeWidth={2} />
            </div>
            <div className="w-full min-w-0">
              <div
                className={cn(
                  "font-sans text-xs leading-tight truncate",
                  s.state === "pending"
                    ? "text-muted-foreground font-semibold"
                    : "font-bold text-ink",
                )}
              >
                {s.label}
              </div>
              <div className="font-mono text-[9.5px] uppercase tracking-[0.06em] text-muted-foreground tabular-nums mt-0.5">
                {s.fecha ? fmtTimelineDateTime(s.fecha) : "—"}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
