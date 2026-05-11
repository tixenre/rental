import "./styles.css";
import { RouterProvider } from "@tanstack/react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ReactDOM from "react-dom/client";
import { createRouter } from "@tanstack/react-router";
import { routeTree } from "./routeTree.gen";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      // Mantener datos "frescos" 30 segundos antes de re-fetchear.
      // Para datos que cambian con baja frecuencia (catálogo, categorías,
      // marcas) y querés que la navegación instantánea sea rápida.
      // Endpoints específicos pueden sobrescribir con staleTime propio
      // (ej. admin/pedidos.index.tsx con refetchInterval: 5000).
      staleTime: 30_000,
      // Mantener en caché 5 minutos después de que se quede sin observadores.
      // Mejora navegación back/forward.
      gcTime: 5 * 60_000,
    },
  },
});

const router = createRouter({
  routeTree,
  context: { queryClient },
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <RouterProvider router={router} />
  </QueryClientProvider>,
);
