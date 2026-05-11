import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { adminApi, type PedidoResumen } from "@/lib/admin/api";
import {
  AdminCard,
  AdminCardHeader,
  AdminCardMeta,
  AdminCardFooter,
  AdminCardPrice,
  AdminCardActions,
} from "@/components/mobile";

export const Route = createLazyFileRoute("/admin/hoy")({
  component: HoyPage,
});

const DIAS = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"];
const MESES_CORTO = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

function todayLabel() {
  const d = new Date();
  return `${DIAS[d.getDay()]} ${d.getDate()} ${MESES_CORTO[d.getMonth()]}`;
}

const fmtFecha = (s: string | null | undefined) => {
  if (!s) return "—";
  const [, m, d] = s.slice(0, 10).split("-");
  return `${parseInt(d)} ${MESES_CORTO[parseInt(m) - 1]}`;
};

type Badge = { label: string; className: string };

function PedidoCard({
  p,
  badge,
  onClick,
}: {
  p: PedidoResumen;
  badge: Badge;
  onClick: () => void;
}) {
  return (
    <AdminCard onClick={onClick}>
      <AdminCardHeader
        title={p.cliente_nombre || "Sin cliente"}
        badge={
          <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${badge.className}`}>
            {badge.label}
          </span>
        }
      />
      <AdminCardMeta>
        {fmtFecha(p.fecha_desde)} → {fmtFecha(p.fecha_hasta)}
      </AdminCardMeta>
      <AdminCardFooter>
        <AdminCardPrice total={p.monto_total ?? 0} />
        <AdminCardActions>
          <Button
            size="icon"
            variant="ghost"
            onClick={(e) => { e.stopPropagation(); onClick(); }}
          >
            <ExternalLink className="h-4 w-4" />
          </Button>
        </AdminCardActions>
      </AdminCardFooter>
    </AdminCard>
  );
}

function Section({
  title,
  items,
  badge,
  emptyText,
  onOpen,
}: {
  title: string;
  items: PedidoResumen[];
  badge: Badge;
  emptyText: string;
  onOpen: (id: number) => void;
}) {
  return (
    <section className="space-y-2.5">
      <div className="flex items-baseline gap-2">
        <h2 className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          {title}
        </h2>
        {items.length > 0 && (
          <span className="font-mono text-[10px] font-bold text-ink">{items.length}</span>
        )}
      </div>
      {items.length === 0 ? (
        <p className="rounded-xl border hairline bg-surface px-4 py-3 text-sm text-muted-foreground">
          {emptyText}
        </p>
      ) : (
        <div className="space-y-2">
          {items.map((p) => (
            <PedidoCard key={p.id} p={p} badge={badge} onClick={() => onOpen(p.id)} />
          ))}
        </div>
      )}
    </section>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-8">
      {[0, 1, 2].map((i) => (
        <div key={i} className="space-y-2.5">
          <Skeleton className="h-3 w-24" />
          <div className="rounded-xl border hairline bg-surface p-4 space-y-2.5">
            <div className="flex items-start justify-between">
              <Skeleton className="h-4 w-36" />
              <Skeleton className="h-5 w-16 rounded-full" />
            </div>
            <Skeleton className="h-3 w-32" />
            <div className="flex items-center justify-between">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-9 w-9 rounded-md" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function HoyPage() {
  const navigate = useNavigate();

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "dashboard"],
    queryFn: () => adminApi.dashboard(),
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  });

  const openPedido = (id: number) =>
    navigate({ to: "/admin/pedidos/$id", params: { id: String(id) } });

  return (
    <div className="px-4 md:px-6 py-6 space-y-8 max-w-2xl mx-auto">
      <header>
        <div className="mb-1 flex items-center gap-2 text-amber">
          <Sun className="h-4 w-4" />
          <span className="font-mono text-[10px] uppercase tracking-[0.25em]">
            {todayLabel()}
          </span>
        </div>
        <h1 className="font-display text-3xl text-ink">Hoy</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {isLoading
            ? "Cargando…"
            : `${(data?.salen_hoy?.length ?? 0) + (data?.devuelven_hoy?.length ?? 0)} movimientos`}
        </p>
      </header>

      {isLoading ? (
        <LoadingSkeleton />
      ) : (
        <>
          <Section
            title="Salen hoy"
            items={data?.salen_hoy ?? []}
            badge={{ label: "Retira", className: "bg-green-50 text-green-700 border-green-200" }}
            emptyText="Ningún equipo sale hoy."
            onOpen={openPedido}
          />

          <Section
            title="Devuelven hoy"
            items={data?.devuelven_hoy ?? []}
            badge={{ label: "Devuelve", className: "bg-blue-50 text-blue-700 border-blue-200" }}
            emptyText="Ningún equipo vuelve hoy."
            onOpen={openPedido}
          />

          <Section
            title="Devuelven mañana"
            items={data?.devuelven_manana ?? []}
            badge={{ label: "Mañana", className: "bg-amber-soft text-amber border-amber/30" }}
            emptyText="Ningún equipo vuelve mañana."
            onOpen={openPedido}
          />
        </>
      )}
    </div>
  );
}
