/**
 * Sección Contenedores & Datos — superficies que envuelven y muestran datos.
 * Table (primitivo), AdminTable (shell de tabla del back-office con
 * column-def) y Alert (avisos inline).
 */
import { useState } from "react";

import { type CatalogSection } from "../types";
import { Caption, Stack } from "../catalog-kit";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  TableCaption,
  TableFooter,
} from "@/design-system/ui/table";
import { Alert, AlertTitle, AlertDescription } from "@/design-system/ui/alert";
import { Info, AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import { AdminTable, type Column } from "@/components/admin/AdminTable";

const PEDIDOS = [
  { numero: "#1042", cliente: "Pablo Ferrari", estado: "Confirmado", monto: "$ 48.500" },
  { numero: "#1043", cliente: "María González", estado: "Solicitud", monto: "$ 12.000" },
  { numero: "#1044", cliente: "Juan Pérez", estado: "Retirado", monto: "$ 31.200" },
];

// ── AdminTable demo ───────────────────────────────────────────────────────────
type PedidoRow = (typeof PEDIDOS)[number];

const COLUMNS: Column<PedidoRow>[] = [
  { header: "Nº", cell: (r) => <span className="font-medium">{r.numero}</span> },
  { header: "Cliente", cell: (r) => r.cliente },
  { header: "Estado", cell: (r) => r.estado },
  { header: "Monto", cell: (r) => r.monto, align: "right", className: "tabular-nums" },
];

function AdminTableDemo() {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <AdminTable
      columns={[
        ...COLUMNS,
        {
          header: "",
          cell: (r) => (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setExpanded((prev) => (prev === r.numero ? null : r.numero));
              }}
              className="grid h-7 w-7 place-items-center rounded text-muted-foreground hover:text-ink transition"
              aria-label={expanded === r.numero ? "Colapsar" : "Expandir"}
            >
              {expanded === r.numero ? (
                <ChevronUp className="h-3.5 w-3.5" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" />
              )}
            </button>
          ),
          align: "right",
          headClassName: "w-10",
        },
      ]}
      rows={PEDIDOS}
      getRowKey={(r) => r.numero}
      isExpanded={(r) => expanded === r.numero}
      renderExpanded={(r) => (
        <div className="px-4 py-3 text-sm text-muted-foreground">
          Detalle del pedido {r.numero} — {r.cliente}. Acá irían los ítems, fechas, notas, etc.
        </div>
      )}
    />
  );
}

export const containersSection: CatalogSection = {
  id: "contenedores",
  title: "Contenedores & Datos",
  hint: "Superficies que envuelven y muestran datos: tabla y aviso.",
  specimens: [
    {
      name: "Table",
      files: ["design-system/ui/table.tsx"],
      blurb:
        "El arquetipo dominante del back-office: header + filas + caption + footer. Se scrollea sola en mobile.",
      render: () => (
        <Table>
          <TableCaption>Pedidos recientes</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>Nº</TableHead>
              <TableHead>Cliente</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead className="text-right">Monto</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {PEDIDOS.map((p) => (
              <TableRow key={p.numero}>
                <TableCell className="font-medium">{p.numero}</TableCell>
                <TableCell>{p.cliente}</TableCell>
                <TableCell>{p.estado}</TableCell>
                <TableCell className="text-right">{p.monto}</TableCell>
              </TableRow>
            ))}
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell colSpan={3}>Total</TableCell>
              <TableCell className="text-right">$ 91.700</TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      ),
    },
    {
      name: "AdminTable",
      files: ["components/admin/AdminTable.tsx"],
      blurb:
        "La tabla del back-office: def de columnas + filas, alineación por columna, filas expandibles con detalle. Envuelve el primitivo Table. Clickeá la flecha para ver el detalle desplegable.",
      render: () => (
        <Stack>
          <AdminTableDemo />
          <Caption>
            cliqueá la flecha → renderExpanded a todo el ancho. onRowClick hace la fila clickeable
            (cursor pointer).
          </Caption>
        </Stack>
      ),
    },
    {
      name: "Alert",
      files: ["design-system/ui/alert.tsx"],
      blurb: "Aviso inline con icono. variant default (neutro) y destructive (error/peligro).",
      render: () => (
        <Stack className="max-w-md">
          <Alert>
            <Info />
            <AlertTitle>Pedido en solicitud</AlertTitle>
            <AlertDescription>
              Todavía no está confirmado. El stock se reserva recién al confirmar.
            </AlertDescription>
          </Alert>
          <Alert variant="destructive">
            <AlertTriangle />
            <AlertTitle>Saldo impago</AlertTitle>
            <AlertDescription>
              El cliente debe el saldo y el retiro es mañana. Cobrá antes de entregar.
            </AlertDescription>
          </Alert>
        </Stack>
      ),
    },
  ],
};
