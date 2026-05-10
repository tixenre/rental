import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { FileText, Truck, FileSignature, Trash2, Plus } from "lucide-react";
import { toast } from "sonner";

import {
  adminApi, type Pedido, type PedidoEstado, ESTADO_LABEL, pedidoPdfUrl,
} from "@/lib/admin/api";

const ESTADOS: PedidoEstado[] = [
  "borrador", "presupuesto", "confirmado", "retirado", "devuelto", "finalizado", "cancelado",
];

const fmtArs = (n: number | null | undefined) =>
  n ? `$${Number(n).toLocaleString("es-AR")}` : "$0";

export function PedidoDetailSheet({
  pedidoId,
  open,
  onOpenChange,
}: {
  pedidoId: number | null;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const qc = useQueryClient();
  const pedidoQ = useQuery({
    queryKey: ["admin", "pedido", pedidoId],
    queryFn: () => adminApi.getPedido(pedidoId!),
    enabled: !!pedidoId && open,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
    qc.invalidateQueries({ queryKey: ["admin", "pedido", pedidoId] });
  };

  const estadoMut = useMutation({
    mutationFn: (estado: PedidoEstado) => adminApi.setPedidoEstado(pedidoId!, estado),
    onSuccess: () => { toast.success("Estado actualizado"); invalidate(); },
    onError: (e: Error) => toast.error(e.message),
  });

  const datosMut = useMutation({
    mutationFn: (data: Parameters<typeof adminApi.updatePedidoDatos>[1]) =>
      adminApi.updatePedidoDatos(pedidoId!, data),
    onSuccess: () => { toast.success("Datos guardados"); invalidate(); },
    onError: (e: Error) => toast.error(e.message),
  });

  const pagoMut = useMutation({
    mutationFn: ({ monto, concepto }: { monto: number; concepto?: string }) =>
      adminApi.addPago(pedidoId!, monto, concepto),
    onSuccess: () => { toast.success("Pago registrado"); invalidate(); setMonto(""); setConcepto(""); },
    onError: (e: Error) => toast.error(e.message),
  });

  const deletePagoMut = useMutation({
    mutationFn: (pagoId: number) => adminApi.deletePago(pedidoId!, pagoId),
    onSuccess: () => { toast.success("Pago eliminado"); invalidate(); },
    onError: (e: Error) => toast.error(e.message),
  });

  const [monto, setMonto] = useState("");
  const [concepto, setConcepto] = useState("");

  const p = pedidoQ.data;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="font-display text-2xl">
            Pedido {p?.numero_pedido ? `#${p.numero_pedido}` : `(borrador #${pedidoId})`}
          </SheetTitle>
        </SheetHeader>

        {pedidoQ.isLoading && <p className="text-sm text-muted-foreground mt-6">Cargando…</p>}
        {pedidoQ.error && (
          <p className="text-sm text-destructive mt-6">Error: {(pedidoQ.error as Error).message}</p>
        )}

        {p && (
          <div className="mt-6 space-y-6">
            {/* Estado + acciones rápidas */}
            <section className="space-y-2">
              <Label className="text-xs uppercase tracking-wide text-muted-foreground">Estado</Label>
              <div className="flex gap-2">
                <Select
                  value={p.estado}
                  onValueChange={(v) => estadoMut.mutate(v as PedidoEstado)}
                  disabled={estadoMut.isPending}
                >
                  <SelectTrigger className="flex-1"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {ESTADOS.map((e) => (
                      <SelectItem key={e} value={e}>{ESTADO_LABEL[e]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </section>

            {/* PDFs */}
            <section className="flex flex-wrap gap-2">
              <Button asChild variant="outline" size="sm">
                <a href={pedidoPdfUrl(p.id, "pdf")} target="_blank" rel="noreferrer">
                  <FileText className="h-4 w-4 mr-1" /> Presupuesto
                </a>
              </Button>
              <Button asChild variant="outline" size="sm">
                <a href={pedidoPdfUrl(p.id, "albaran")} target="_blank" rel="noreferrer">
                  <Truck className="h-4 w-4 mr-1" /> Albarán
                </a>
              </Button>
              <Button asChild variant="outline" size="sm">
                <a href={pedidoPdfUrl(p.id, "contrato")} target="_blank" rel="noreferrer">
                  <FileSignature className="h-4 w-4 mr-1" /> Contrato
                </a>
              </Button>
            </section>

            {/* Cliente + fechas */}
            <PedidoDatosForm
              pedido={p}
              saving={datosMut.isPending}
              onSave={(data) => datosMut.mutate(data)}
            />

            {/* Items */}
            <section>
              <h3 className="font-display text-lg mb-2">Equipos</h3>
              <div className="rounded-md border hairline divide-y">
                {p.items.length === 0 && (
                  <p className="text-sm text-muted-foreground p-3">Sin equipos cargados.</p>
                )}
                {p.items.map((it) => (
                  <div key={it.id} className="flex justify-between p-3 text-sm">
                    <div>
                      <div className="text-ink">{it.nombre}</div>
                      <div className="text-xs text-muted-foreground">
                        {it.cantidad} × {fmtArs(it.precio_jornada)}/día
                      </div>
                    </div>
                    <div className="tabular-nums text-ink">{fmtArs(it.subtotal)}</div>
                  </div>
                ))}
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                <div className="text-muted-foreground">Total</div>
                <div className="text-right tabular-nums">{fmtArs(p.monto_total)}</div>
                <div className="text-muted-foreground">Pagado</div>
                <div className="text-right tabular-nums">{fmtArs(p.monto_pagado)}</div>
                <div className="text-ink font-medium">Saldo</div>
                <div className="text-right tabular-nums font-medium">
                  {fmtArs((p.monto_total ?? 0) - (p.monto_pagado ?? 0))}
                </div>
              </div>
            </section>

            {/* Pagos */}
            <section>
              <h3 className="font-display text-lg mb-2">Pagos</h3>
              {(p.pagos ?? []).length > 0 && (
                <div className="rounded-md border hairline divide-y mb-3">
                  {p.pagos!.map((pg) => (
                    <div key={pg.id} className="flex items-center justify-between p-3 text-sm">
                      <div>
                        <div className="tabular-nums">{fmtArs(pg.monto)}</div>
                        <div className="text-xs text-muted-foreground">
                          {pg.fecha} {pg.concepto ? `· ${pg.concepto}` : ""}
                        </div>
                      </div>
                      <Button
                        size="icon" variant="ghost"
                        onClick={() => deletePagoMut.mutate(pg.id)}
                        disabled={deletePagoMut.isPending}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
              <div className="grid grid-cols-[1fr_1fr_auto] gap-2 items-end">
                <div>
                  <Label className="text-xs">Monto</Label>
                  <Input
                    type="number" min={1} value={monto}
                    onChange={(e) => setMonto(e.target.value)}
                    placeholder="0"
                  />
                </div>
                <div>
                  <Label className="text-xs">Concepto</Label>
                  <Input
                    value={concepto}
                    onChange={(e) => setConcepto(e.target.value)}
                    placeholder="Seña, saldo…"
                  />
                </div>
                <Button
                  onClick={() => {
                    const n = parseInt(monto || "0", 10);
                    if (!n || n <= 0) return toast.error("Monto inválido");
                    pagoMut.mutate({ monto: n, concepto: concepto || undefined });
                  }}
                  disabled={pagoMut.isPending}
                >
                  <Plus className="h-4 w-4 mr-1" /> Agregar
                </Button>
              </div>
            </section>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

function PedidoDatosForm({
  pedido,
  saving,
  onSave,
}: {
  pedido: Pedido;
  saving?: boolean;
  onSave: (data: Parameters<typeof adminApi.updatePedidoDatos>[1]) => void;
}) {
  const [form, setForm] = useState({
    cliente_nombre: pedido.cliente_nombre ?? "",
    cliente_email: pedido.cliente_email ?? "",
    cliente_telefono: pedido.cliente_telefono ?? "",
    fecha_desde: (pedido.fecha_desde ?? "").slice(0, 10),
    fecha_hasta: (pedido.fecha_hasta ?? "").slice(0, 10),
    notas: pedido.notas ?? "",
    descuento_pct: String(pedido.descuento_pct ?? 0),
  });

  return (
    <section className="space-y-3">
      <h3 className="font-display text-lg">Cliente y fechas</h3>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="sm:col-span-3">
          <Label className="text-xs">Cliente</Label>
          <Input
            value={form.cliente_nombre}
            onChange={(e) => setForm({ ...form, cliente_nombre: e.target.value })}
          />
        </div>
        <div>
          <Label className="text-xs">Email</Label>
          <Input
            value={form.cliente_email}
            onChange={(e) => setForm({ ...form, cliente_email: e.target.value })}
          />
        </div>
        <div>
          <Label className="text-xs">Teléfono</Label>
          <Input
            value={form.cliente_telefono}
            onChange={(e) => setForm({ ...form, cliente_telefono: e.target.value })}
          />
        </div>
        <div>
          <Label className="text-xs">Descuento %</Label>
          <Input
            type="number" min={0} max={100} step="0.5"
            value={form.descuento_pct}
            onChange={(e) => setForm({ ...form, descuento_pct: e.target.value })}
          />
        </div>
        <div>
          <Label className="text-xs">Desde</Label>
          <Input
            type="date" value={form.fecha_desde}
            onChange={(e) => setForm({ ...form, fecha_desde: e.target.value })}
          />
        </div>
        <div>
          <Label className="text-xs">Hasta</Label>
          <Input
            type="date" value={form.fecha_hasta}
            onChange={(e) => setForm({ ...form, fecha_hasta: e.target.value })}
          />
        </div>
        <div className="sm:col-span-3">
          <Label className="text-xs">Notas</Label>
          <Textarea
            rows={2} value={form.notas}
            onChange={(e) => setForm({ ...form, notas: e.target.value })}
          />
        </div>
      </div>
      <div className="flex justify-end">
        <Button
          size="sm"
          disabled={saving}
          onClick={() =>
            onSave({
              cliente_nombre: form.cliente_nombre || null,
              cliente_email: form.cliente_email || null,
              cliente_telefono: form.cliente_telefono || null,
              fecha_desde: form.fecha_desde || null,
              fecha_hasta: form.fecha_hasta || null,
              notas: form.notas || null,
              descuento_pct: parseFloat(form.descuento_pct) || 0,
              cliente_id: pedido.cliente_id,
            })
          }
        >
          {saving ? "Guardando…" : "Guardar datos"}
        </Button>
      </div>
    </section>
  );
}

export function pedidoEstadoVariant(e: PedidoEstado): "default" | "secondary" | "outline" | "destructive" {
  if (e === "cancelado") return "destructive";
  if (e === "finalizado" || e === "devuelto") return "secondary";
  if (e === "borrador" || e === "presupuesto") return "outline";
  return "default";
}
