import { createLazyFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  Calendar,
  ClipboardList,
  DollarSign,
  Package,
  Users,
  AlertCircle,
  ArrowRight,
} from "lucide-react";

import { adminApi, type PedidoResumen } from "@/lib/admin/api";
import { formatARS } from "@/lib/format";
import { cn } from "@/lib/utils";
import { AdminPage } from "@/components/admin/AdminPage";
import { CalendarioWidget } from "@/components/admin/CalendarioWidget";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/")({
  component: AdminDashboard,
});

function AdminDashboard() {
  useDocumentTitle("Dashboard · Back Office");
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["admin", "dashboard"],
    queryFn: () => adminApi.dashboard(),
    staleTime: 60_000,
  });
  // Conteo de pedidos con saldo pendiente (atajo a cobranzas).
  const saldoQ = useQuery({
    queryKey: ["admin", "pedidos", "con_saldo_count"],
    queryFn: () => adminApi.listPedidos({ con_saldo: true, per_page: 1 }),
    staleTime: 60_000,
  });
  const conSaldo = saldoQ.data?.total ?? 0;

  return (
    <AdminPage title="Dashboard" maxW="max-w-6xl">
      {isLoading && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="min-h-[5.5rem] rounded-xl border hairline bg-surface animate-pulse"
            />
          ))}
        </div>
      )}

      {isError && (
        <div className="rounded-xl border border-destructive/40 bg-destructive/5 px-4 py-6 text-sm text-destructive">
          <div className="font-mono text-2xs uppercase tracking-[0.2em] mb-2">Error</div>
          <div>{(error as Error)?.message ?? "No se pudo cargar el dashboard"}</div>
          <div className="mt-2 text-xs opacity-80">Verificá que el backend esté corriendo.</div>
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
            <Stat
              label="Pendientes"
              value={data.pendientes}
              icon={<ClipboardList className="h-4 w-4" />}
              tone="amber"
            />
            <Stat label="Activos" value={data.activos} icon={<Package className="h-4 w-4" />} />
            <Stat
              label="Ingresos mes"
              value={formatARS(Number(data.ingresos_mes ?? 0))}
              icon={<DollarSign className="h-4 w-4" />}
            />
            <Stat
              label="Clientes"
              value={data.total_clientes}
              icon={<Users className="h-4 w-4" />}
            />
          </div>

          {/* Atajos a Pedidos — entran a la lista ya filtrada (?f=). Reemplazan los
              chips que antes vivían en /admin/pedidos. */}
          <div className="mt-4 flex flex-wrap gap-2">
            <AtajoPedidos
              f="retiraHoy"
              label="Retiran hoy"
              n={data.salen_hoy.length}
              dot="bg-amber"
            />
            <AtajoPedidos
              f="devuelveHoy"
              label="Devuelven hoy"
              n={data.devuelven_hoy.length}
              dot="bg-rosa"
            />
            <AtajoPedidos
              f="nuevos"
              label="Presupuestos nuevos"
              n={data.pendientes}
              dot="bg-azul"
            />
            <AtajoPedidos f="saldo" label="Con saldo" n={conSaldo} dot="bg-verde" />
          </div>

          {/* Movimientos del día */}
          <div className="mt-10">
            <div className="mb-4">
              <div className="t-eyebrow">Movimiento de equipos</div>
              <h2 className="font-display text-xl text-ink mt-0.5">Hoy y mañana</h2>
            </div>

            <div className="grid md:grid-cols-2 gap-4 md:gap-6">
              <PedidosCard
                title="Salen hoy"
                icon={<Calendar className="h-4 w-4" />}
                pedidos={data.salen_hoy}
                empty="Nadie retira hoy."
              />
              <PedidosCard
                title="Devuelven hoy"
                icon={<Calendar className="h-4 w-4" />}
                pedidos={data.devuelven_hoy}
                empty="Sin devoluciones hoy."
              />
              <PedidosCard
                title="Devuelven mañana"
                icon={<Calendar className="h-4 w-4" />}
                pedidos={data.devuelven_manana}
                empty="Sin devoluciones mañana."
              />
              <EquiposAfueraCard items={data.equipos_afuera} />
            </div>
          </div>

          {/* Calendario full — antes vivía en /admin/calendario */}
          <div className="mt-10">
            <div className="mb-4">
              <div className="t-eyebrow">Vista mensual</div>
              <h2 className="font-display text-xl text-ink mt-0.5">Calendario</h2>
            </div>

            <CalendarioWidget variant="full" initialView="mes" />
          </div>
        </>
      )}
    </AdminPage>
  );
}

/** Chip-atajo que entra a /admin/pedidos con un filtro del día pre-aplicado (?f=). */
function AtajoPedidos({
  f,
  label,
  n,
  dot,
}: {
  f: "retiraHoy" | "devuelveHoy" | "nuevos" | "saldo";
  label: string;
  n: number;
  dot: string;
}) {
  return (
    <Link
      to="/admin/pedidos"
      search={{ f }}
      className="inline-flex items-center gap-1.5 rounded-full border hairline bg-surface px-3 py-1.5 text-xs font-medium text-ink transition-colors hover:border-ink"
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", dot)} />
      {label}
      <span className="font-mono text-2xs tabular-nums text-muted-foreground">{n}</span>
    </Link>
  );
}

function Stat({
  label,
  value,
  icon,
  tone,
}: {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  tone?: "amber";
}) {
  return (
    <div
      className={`rounded-xl border hairline px-4 py-4 bg-surface ${
        tone === "amber" ? "ring-1 ring-amber/30" : ""
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="t-eyebrow">{label}</div>
        <div className="text-muted-foreground">{icon}</div>
      </div>
      <div
        className="mt-2 font-display text-xl sm:text-2xl text-ink truncate"
        title={String(value)}
      >
        {value}
      </div>
    </div>
  );
}

function PedidosCard({
  title,
  icon,
  pedidos,
  empty,
}: {
  title: string;
  icon: React.ReactNode;
  pedidos: PedidoResumen[];
  empty: string;
}) {
  return (
    <div className="rounded-xl border hairline bg-surface overflow-hidden">
      <div className="px-4 py-3 border-b hairline flex items-center gap-2">
        <span className="text-muted-foreground">{icon}</span>
        <h2 className="font-display text-base text-ink">{title}</h2>
        <span className="ml-auto t-eyebrow">{pedidos.length}</span>
      </div>
      {pedidos.length === 0 ? (
        <div className="px-4 py-6 text-sm text-muted-foreground">{empty}</div>
      ) : (
        <ul className="divide-y hairline">
          {pedidos.map((p) => (
            <li key={p.id}>
              <Link
                to="/admin/pedidos/$id"
                params={{ id: String(p.id) }}
                className="flex items-center gap-3 px-4 py-3 hover:bg-accent/30 transition-colors"
              >
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-ink truncate">{p.cliente_nombre}</div>
                  <div className="t-eyebrow">
                    #{p.id} · {formatARS(Number(p.monto_total ?? 0))}
                  </div>
                </div>
                <ArrowRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function EquiposAfueraCard({
  items,
}: {
  items: {
    nombre: string;
    marca: string | null;
    cantidad: number;
    cliente_nombre: string;
    fecha_hasta: string;
  }[];
}) {
  return (
    <div className="rounded-xl border hairline bg-surface overflow-hidden">
      <div className="px-4 py-3 border-b hairline flex items-center gap-2">
        <span className="text-muted-foreground">
          <AlertCircle className="h-4 w-4" />
        </span>
        <h2 className="font-display text-base text-ink">Equipos afuera</h2>
        <span className="ml-auto t-eyebrow">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="px-4 py-6 text-sm text-muted-foreground">
          No hay equipos en alquiler activo.
        </div>
      ) : (
        <ul className="divide-y hairline max-h-48 md:max-h-80 overflow-auto">
          {items.slice(0, 12).map((it, i) => (
            <li key={i} className="px-4 py-2.5 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-ink truncate">
                  {it.nombre}
                  {it.marca ? <span className="text-muted-foreground"> · {it.marca}</span> : null}
                </span>
                <span className="ml-auto font-mono text-2xs text-muted-foreground shrink-0">
                  ×{it.cantidad}
                </span>
              </div>
              <div className="t-eyebrow truncate">
                {it.cliente_nombre} · vuelve {it.fecha_hasta?.slice(0, 10)}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
