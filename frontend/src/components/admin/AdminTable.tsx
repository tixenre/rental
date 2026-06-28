import { Fragment, type ReactNode } from "react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/design-system/ui/table";
import { cn } from "@/lib/utils";

/** Definición de una columna del AdminTable. */
export type Column<T> = {
  /** Encabezado de la columna. */
  header: ReactNode;
  /** Render de la celda para una fila. */
  cell: (row: T, index: number) => ReactNode;
  align?: "left" | "right" | "center";
  /** Clase extra para las celdas del cuerpo (ej. "tabular-nums"). */
  className?: string;
  /** Clase extra para el `<th>`. */
  headClassName?: string;
};

/**
 * AdminTable — shell de tabla del back-office.
 *
 * Una sola forma de la tabla: thead + filas a partir de una def de columnas,
 * sobre el primitivo `Table` del DS. Reemplaza las tablas `<table>` crudas con
 * 4 variantes de `<thead>` a mano. Los estados (loading/error/empty) los maneja
 * `QueryState` por fuera; acá solo se renderiza la data ya cargada.
 */
export function AdminTable<T>({
  columns,
  rows,
  getRowKey,
  onRowClick,
  rowClassName,
  className,
  isExpanded,
  renderExpanded,
}: {
  columns: Column<T>[];
  rows: T[];
  getRowKey: (row: T, index: number) => string | number;
  onRowClick?: (row: T) => void;
  rowClassName?: (row: T) => string | undefined;
  className?: string;
  /** Si la fila está expandida (muestra `renderExpanded` debajo, a todo el ancho). */
  isExpanded?: (row: T) => boolean;
  /** Contenido del detalle desplegable de una fila. */
  renderExpanded?: (row: T) => ReactNode;
}) {
  const alignClass = (a?: Column<T>["align"]) =>
    a === "right" ? "text-right" : a === "center" ? "text-center" : undefined;

  return (
    <div className={cn("rounded-md border hairline overflow-hidden", className)}>
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((c, i) => (
              <TableHead key={i} className={cn(alignClass(c.align), c.headClassName)}>
                {c.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, index) => (
            <Fragment key={getRowKey(row, index)}>
              <TableRow
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={cn(onRowClick && "cursor-pointer", rowClassName?.(row))}
              >
                {columns.map((c, i) => (
                  <TableCell key={i} className={cn(alignClass(c.align), c.className)}>
                    {c.cell(row, index)}
                  </TableCell>
                ))}
              </TableRow>
              {isExpanded?.(row) && renderExpanded && (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={columns.length} className="bg-muted/15 p-0">
                    {renderExpanded(row)}
                  </TableCell>
                </TableRow>
              )}
            </Fragment>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
