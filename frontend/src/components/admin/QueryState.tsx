import { type ReactNode } from "react";
import { Inbox } from "lucide-react";

import { EmptyState } from "@/components/rental/EmptyState";
import { ErrorState } from "./ErrorState";
import { ListSkeleton } from "./skeletons";

/** Forma mínima de un resultado de useQuery (TanStack) que consume QueryState. */
type QueryLike<T> = {
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  data: T | undefined;
  refetch?: () => void;
};

/**
 * QueryState — ramifica loading / error / empty / ok en UN solo lugar.
 *
 * Resuelve el problema sistémico "cada pantalla ramifica el estado a mano" y la
 * falta de error/empty consistentes (varias ni manejan isError). Cablea
 * `<Skeleton>` (loading), `<ErrorState>` (error, loguea el .message) y
 * `<EmptyState>` (vacío) — las tres formas canónicas — sobre un resultado de
 * useQuery. El children es render-prop con la data ya garantizada no-undefined.
 *
 * Uso:
 *   <QueryState query={q} isEmpty={(d) => d.items.length === 0}
 *     skeleton={<TableSkeleton />} empty={<EmptyState icon={…} title="Sin equipos" />}>
 *     {(data) => <Tabla items={data.items} />}
 *   </QueryState>
 */
export function QueryState<T>({
  query,
  isEmpty,
  skeleton,
  empty,
  errorTitle,
  children,
}: {
  query: QueryLike<T>;
  /** Predicado de vacío sobre la data ya cargada. */
  isEmpty?: (data: T) => boolean;
  /** Skeleton a mostrar mientras carga (default: ListSkeleton). */
  skeleton?: ReactNode;
  /** Empty state a mostrar si `isEmpty` da true (default: genérico). */
  empty?: ReactNode;
  errorTitle?: string;
  children: (data: T) => ReactNode;
}) {
  if (query.isLoading) return <>{skeleton ?? <ListSkeleton />}</>;
  if (query.isError) {
    return <ErrorState error={query.error} title={errorTitle} onRetry={query.refetch} />;
  }
  const data = query.data;
  if (data === undefined) return <>{skeleton ?? <ListSkeleton />}</>;
  if (isEmpty?.(data)) {
    return (
      <>
        {empty ?? <EmptyState icon={<Inbox className="h-6 w-6" />} title="No hay datos todavía" />}
      </>
    );
  }
  return <>{children(data)}</>;
}
