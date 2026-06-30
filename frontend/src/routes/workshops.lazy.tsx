import { createLazyFileRoute } from "@tanstack/react-router";

// El listado vive en talleres.index.lazy.tsx (ruta /talleres/).
// Este archivo existe vacío para que el generador de TanStack Router no cree
// un componente extra para /talleres — el Outlet viene de talleres.tsx.
export const Route = createLazyFileRoute("/workshops")({});
