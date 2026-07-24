import { createLazyFileRoute } from "@tanstack/react-router";

// El listado vive en escuela.index.lazy.tsx (ruta /escuela/).
// Este archivo existe vacío para que el generador de TanStack Router no cree
// un componente extra para /escuela — el Outlet viene de escuela.tsx.
export const Route = createLazyFileRoute("/escuela")({});
