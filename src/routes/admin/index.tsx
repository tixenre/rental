import { createFileRoute, Link } from "@tanstack/react-router";
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
import { formatCurrencyARS } from "@/lib/format";

export const Route = createFileRoute("/admin/")({
  component: AdminDashboard,
});

function AdminDashboard() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["admin", "dashboard"],
    queryFn: () => adminApi.dashboard(),
    staleTime: 60_000,
  });

  return (
    <div className="px-4 md:px-8 py-6 md:py-10 max-w-6xl mx-auto">
      <div className="mb-8">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office
        </div>
        <h1 className="font-display text-3xl md:text-4xl text-ink">Dashboard</h1>
      </div>

      {isLoading && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-28 rounded-xl border hairline bg-surface animate-pulse" />
          ))}
        </div>
      )}

      {isError && (
        <div className="rounded-xl border border-destructive/40 bg-destructive/5 px-4 py-6 text-sm text-destructive">
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] mb-2">
            Error
          </div>
          <div>{(error as Error)?.message ?? "No se pudo cargar el dashboard"}</div>
          <div className="mt-2 text-xs opacity-80">
            Verificá que el backend esté corriendo y tu email esté en ADMIN_EMAILS.
          </div>
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
            <Stat
              label="Activos"
              value={data.activos}
              icon={<Package className="h-4 w-4" />}
            />
            <Stat
              label="Ingresos mes"
              value={formatCurrencyARS(Number(data.ingresos_mes ?? 0))}
              icon={<DollarSign className="h-4 w-4" />}
            />
            <Stat
              label="Clientes"
              value={data.total_clientes}
              icon={<Users className="h-4 w-4" />}
            />
          </div>

          <div className="grid md:grid-cols-2 gap-4 md:gap-6 mt-8">
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
        </>
      )}
    </div>
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
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          {label}
        </div>
        <div className="text-muted-foreground">{icon}</div>
      </div>
      <div className="mt-2 font-display text-2xl text-ink truncate" title={String(value)}>
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
        <span className="ml-auto font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          {pedidos.length}
        </span>
      </div>
      {pedidos.length === 0 ? (
        <div className="px-4 py-6 text-sm text-muted-foreground">{empty}</div>
      ) : (
        <ul className="divide-y hairline">
          {pedidos.map((p) => (
            <li key={p.id}>
              <Link
                to="/admin/pedidos"
                className="flex items-center gap-3 px-4 py-3 hover:bg-accent/30 transition-colors"
              >
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-ink truncate">{p.cliente_nombre}</div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                    #{p.id} · {formatCurrencyARS(Number(p.monto_total ?? 0))}
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

function EquiposAfueraCard({ items }: { items: { nombre: string; marca: string | null; cantidad: number; cliente_nombre: string; fecha_hasta: string }[] }) {
  return (
    <div className="rounded-xl border hairline bg-surface overflow-hidden">
      <div className="px-4 py-3 border-b hairline flex items-center gap-2">
        <span className="text-muted-foreground">
          <AlertCircle className="h-4 w-4" />
        </span>
        <h2 className="font-display text-base text-ink">Equipos afuera</h2>
        <span className="ml-auto font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          {items.length}
        </span>
      </div>
      {items.length === 0 ? (
        <div className="px-4 py-6 text-sm text-muted-foreground">
          No hay equipos en alquiler activo.
        </div>
      ) : (
        <ul className="divide-y hairline max-h-80 overflow-auto">
          {items.slice(0, 12).map((it, i) => (
            <li key={i} className="px-4 py-2.5 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-ink truncate">
                  {it.nombre}
                  {it.marca ? <span className="text-muted-foreground"> · {it.marca}</span> : null}
                </span>
                <span className="ml-auto font-mono text-[10px] text-muted-foreground shrink-0">
                  ×{it.cantidad}
                </span>
              </div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground truncate">
                {it.cliente_nombre} · vuelve {it.fecha_hasta?.slice(0, 10)}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
