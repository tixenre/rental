import { Outlet, createRootRouteWithContext } from "@tanstack/react-router";
import { QueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Toaster } from "@/components/ui/sonner";
import { Component, type ReactNode } from "react";

class RootErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-background px-4">
          <div className="max-w-md text-center space-y-4">
            <h1 className="text-2xl font-bold text-foreground">Algo salió mal</h1>
            <pre className="text-xs text-destructive bg-muted p-4 rounded text-left overflow-auto max-h-40">
              {(this.state.error as Error).message}
            </pre>
            <button
              onClick={() => window.location.reload()}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
            >
              Recargar
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">Página no encontrada</h2>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Volver al catálogo
          </Link>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: () => (
    <RootErrorBoundary>
      <Outlet />
      <Toaster richColors position="top-right" />
    </RootErrorBoundary>
  ),
  notFoundComponent: NotFoundComponent,
});
