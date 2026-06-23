import { useEffect } from "react";

/**
 * Setea `document.title` mientras el componente está montado. Restaura
 * el título previo al desmontar para que la página parent (ej. `/admin`)
 * recupere su título cuando se sale de la sub-página.
 *
 * Workaround para `createLazyFileRoute`: TanStack Router solo acepta
 * `head` en `createFileRoute` (non-lazy). Las rutas con code-splitting
 * (`.lazy.tsx`) tienen que setear el título desde el componente.
 */
export function useDocumentTitle(title: string) {
  useEffect(() => {
    const previous = document.title;
    document.title = title;
    return () => {
      document.title = previous;
    };
  }, [title]);
}
