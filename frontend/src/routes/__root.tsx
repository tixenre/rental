import { Outlet, createRootRouteWithContext } from "@tanstack/react-router";
import { QueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Toaster } from "@/design-system/ui/sonner";
import { PublicLayout } from "@/components/rental/PublicLayout";
import { FaviconSync } from "@/components/rental/FaviconSync";
import { useCartHeartbeat } from "@/hooks/useCartHeartbeat";
import { Component, type ReactNode } from "react";

class RootErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
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
    <PublicLayout>
      <div className="flex items-center justify-center px-4 py-24 min-h-[60vh]">
        <div className="max-w-md text-center">
          <h1 className="font-display text-7xl text-ink">404</h1>
          <h2 className="mt-4 font-display text-xl text-ink">Página no encontrada</h2>
          <div className="mt-6">
            <Link
              to="/rental"
              className="inline-flex items-center justify-center rounded-full bg-foreground px-5 py-2.5 text-sm font-semibold text-background transition hover:bg-amber hover:text-ink"
            >
              Volver al catálogo
            </Link>
          </div>
        </div>
      </div>
    </PublicLayout>
  );
}

function CartSync() {
  useCartHeartbeat();
  return null;
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: () => (
    <RootErrorBoundary>
      <FaviconSync />
      <CartSync />
      <Outlet />
      <Toaster richColors position="top-right" />
    </RootErrorBoundary>
  ),
  notFoundComponent: NotFoundComponent,
});
