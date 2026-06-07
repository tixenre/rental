/**
 * contabilidad.rendicion.lazy.tsx — Rendición de cuentas mensual (#809, Fase 5).
 *
 * Cruza, para el mes elegido, lo que LE CORRESPONDE a cada parte (del reporte de
 * liquidación) contra lo que COBRÓ físicamente (del ledger de Pagos), y dice quién
 * le debe a quién. Rambla es el fondo de la empresa: no cobra, su parte se aparta.
 * Registrar un saldado crea una transferencia entre las cajas (marcada rendición).
 */
import { createLazyFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { adminApi, type RendicionData, type SugeridoRendicion } from "@/lib/admin/api";
import { formatARS, formatFechaDisplay } from "@/lib/format";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/contabilidad/rendicion")({
  component: RendicionPage,
});

function mesActual(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function RendicionPage() {
  useDocumentTitle("Rendición · Finanzas");
  const qc = useQueryClient();
  const [mes, setMes] = useState(mesActual);

  const shift = (delta: number) => {
    const [y, m] = mes.split("-").map(Number);
    const d = new Date(y, m - 1 + delta, 1);
    setMes(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
  };
  const mesLabel = new Date(`${mes}-01T00:00:00`).toLocaleDateString("es-AR", {
    month: "long",
    year: "numeric",
  });

  const q = useQuery({
    queryKey: ["admin", "contabilidad", "rendicion", mes],
    queryFn: () => adminApi.getRendicion(mes),
  });
  const invalidar = () => qc.invalidateQueries({ queryKey: ["admin", "contabilidad"] });

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-4xl mx-auto">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Back-office · Finanzas
          </div>
          <h1 className="font-display text-3xl text-ink">Rendición</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Quién cobró, a quién le corresponde y quién le debe a quién este mes.
          </p>
        </div>
        <Link
          to="/admin/contabilidad"
          className="shrink-0 h-9 rounded-md border hairline px-3 text-sm flex items-center hover:bg-muted/40"
        >
          ← Tablero
        </Link>
      </header>

      {/* Navegador de mes */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => shift(-1)}
          className="h-9 w-9 rounded-md border hairline hover:bg-muted/40"
          aria-label="Mes anterior"
        >
          ‹
        </button>
        <span className="font-medium text-ink capitalize min-w-[10rem] text-center">
          {mesLabel}
        </span>
        <button
          type="button"
          onClick={() => shift(1)}
          className="h-9 w-9 rounded-md border hairline hover:bg-muted/40"
          aria-label="Mes siguiente"
        >
          ›
        </button>
      </div>

      {q.isLoading && <div className="text-sm text-muted-foreground">Cargando rendición…</div>}
      {q.isError && (
        <div className="text-sm text-destructive">
          Error cargando la rendición. {(q.error as Error)?.message}
        </div>
      )}

      {q.data && <RendicionDetalle data={q.data} mes={mes} onChanged={invalidar} />}
    </div>
  );
}

function RendicionDetalle({
  data,
  mes,
  onChanged,
}: {
  data: RendicionData;
  mes: string;
  onChanged: () => void;
}) {
  return (
    <div className="space-y-6">
      <CierreControl mes={mes} cerrado={data.cierre_contable} onChanged={onChanged} />

      {/* Alertas de integridad */}
      {data.advertencias.length > 0 && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 space-y-1">
          {data.advertencias.map((a, i) => (
            <div key={i} className="text-sm text-destructive">
              ⚠ {a}
            </div>
          ))}
        </div>
      )}

      {/* Tabla por persona */}
      <div className="overflow-x-auto rounded-lg border hairline">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b hairline text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              <th className="px-3 py-2 font-medium">Parte</th>
              <th className="px-3 py-2 font-medium text-right">Cobró</th>
              <th className="px-3 py-2 font-medium text-right">Le corresponde</th>
              <th className="px-3 py-2 font-medium text-right">Ya rindió</th>
              <th className="px-3 py-2 font-medium text-right">Pendiente</th>
            </tr>
          </thead>
          <tbody>
            {data.personas.map((p) => (
              <tr key={p.persona} className="border-b hairline last:border-0">
                <td className="px-3 py-2 font-medium text-ink">{p.persona}</td>
                <td className="px-3 py-2 text-right font-mono tabular-nums">
                  {formatARS(p.cobro)}
                </td>
                <td className="px-3 py-2 text-right font-mono tabular-nums">
                  {formatARS(p.le_corresponde)}
                </td>
                <td className="px-3 py-2 text-right font-mono tabular-nums text-muted-foreground">
                  {formatARS(p.ya_rindio)}
                </td>
                <td
                  className={`px-3 py-2 text-right font-mono tabular-nums font-semibold ${
                    p.pendiente < 0
                      ? "text-amber"
                      : p.pendiente > 0
                        ? "text-ink"
                        : "text-muted-foreground"
                  }`}
                >
                  {p.pendiente > 0 ? "le falta " : p.pendiente < 0 ? "tiene de más " : ""}
                  {formatARS(Math.abs(p.pendiente))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Movimientos sugeridos para saldar */}
      <SugeridosBox sugeridos={data.sugeridos} mes={mes} onChanged={onChanged} />

      {/* Libro de saldados registrados */}
      {data.movimientos.length > 0 && (
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground mb-2">
            Saldados registrados
          </div>
          <div className="overflow-x-auto rounded-lg border hairline">
            <table className="w-full text-sm">
              <tbody>
                {data.movimientos.map((m) => (
                  <tr
                    key={m.id}
                    className={`border-b hairline last:border-0 ${m.anulado ? "opacity-50" : ""}`}
                  >
                    <td className="px-3 py-2 whitespace-nowrap text-muted-foreground">
                      {formatFechaDisplay(m.fecha)}
                    </td>
                    <td className={`px-3 py-2 ${m.anulado ? "line-through" : ""}`}>
                      {m.origen} → {m.destino}
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">
                      {formatARS(m.monto)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function CierreControl({
  mes,
  cerrado,
  onChanged,
}: {
  mes: string;
  cerrado: boolean;
  onChanged: () => void;
}) {
  const cerrar = useMutation({
    mutationFn: () => adminApi.cerrarMesContable(mes),
    onSuccess: () => {
      toast.success("Mes cerrado");
      onChanged();
    },
    onError: (e) => toast.error("No se pudo cerrar", { description: (e as Error).message }),
  });
  const reabrir = useMutation({
    mutationFn: () => adminApi.reabrirMesContable(mes),
    onSuccess: () => {
      toast.success("Mes reabierto");
      onChanged();
    },
    onError: (e) => toast.error("No se pudo reabrir", { description: (e as Error).message }),
  });

  if (cerrado) {
    return (
      <div className="flex items-center justify-between gap-3 rounded-lg border hairline bg-muted/20 p-3">
        <span className="text-sm text-ink">
          🔒 Mes cerrado — los movimientos de este mes están trabados.
        </span>
        <button
          type="button"
          onClick={() => reabrir.mutate()}
          disabled={reabrir.isPending}
          className="h-9 shrink-0 rounded-md border hairline px-3 text-xs hover:bg-muted/40"
        >
          Reabrir
        </button>
      </div>
    );
  }
  return (
    <div className="flex justify-end">
      <button
        type="button"
        onClick={() => {
          if (
            window.confirm(
              "¿Cerrar el mes? Vas a trabar la edición de sus movimientos (se puede reabrir).",
            )
          )
            cerrar.mutate();
        }}
        disabled={cerrar.isPending}
        className="h-9 rounded-md border hairline px-3 text-xs hover:bg-muted/40"
      >
        Cerrar mes
      </button>
    </div>
  );
}

function SugeridosBox({
  sugeridos,
  mes,
  onChanged,
}: {
  sugeridos: SugeridoRendicion[];
  mes: string;
  onChanged: () => void;
}) {
  const saldar = useMutation({
    mutationFn: (s: SugeridoRendicion) =>
      adminApi.saldarRendicion(mes, { de: s.de, a: s.a, monto: s.monto }),
    onSuccess: () => {
      toast.success("Saldado registrado");
      onChanged();
    },
    onError: (e) => toast.error("No se pudo registrar", { description: (e as Error).message }),
  });

  if (sugeridos.length === 0) {
    return (
      <div className="rounded-lg border hairline bg-muted/20 p-4 text-sm text-ink">
        ✓ No queda nada por rendir este mes.
      </div>
    );
  }

  return (
    <div className="rounded-lg border hairline p-4 space-y-2">
      <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
        Para saldar
      </div>
      {sugeridos.map((s, i) => (
        <div key={i} className="flex items-center justify-between gap-3">
          <span className="text-sm">
            <span className="font-medium">{s.de}</span> le pasa{" "}
            <span className="font-mono tabular-nums">{formatARS(s.monto)}</span> a{" "}
            <span className="font-medium">{s.a}</span>
          </span>
          <button
            type="button"
            onClick={() => {
              if (window.confirm(`¿Registrar que ${s.de} le pasó ${formatARS(s.monto)} a ${s.a}?`))
                saldar.mutate(s);
            }}
            disabled={saldar.isPending}
            className="h-8 rounded-md bg-ink px-3 text-xs text-background disabled:opacity-50"
          >
            Registrar
          </button>
        </div>
      ))}
    </div>
  );
}
