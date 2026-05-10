import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { lovable } from "@/integrations/lovable";
import { useAuth } from "@/hooks/use-auth";
import { getAppOrigin, isLovableHost } from "@/lib/app-origin";

import { ArrowLeft } from "lucide-react";

type LoginSearch = {
  redirect?: string;
  oauth?: "google";
};

function validateLoginSearch(search: Record<string, unknown>): LoginSearch {
  const parsed: LoginSearch = {};
  if (typeof search.redirect === "string") parsed.redirect = search.redirect;
  if (search.oauth === "google") parsed.oauth = "google";
  return parsed;
}

export const Route = createFileRoute("/login")({
  validateSearch: validateLoginSearch,
  head: () => ({
    meta: [
      { title: "Iniciar sesión — Rambla Rental" },
      { name: "description", content: "Accedé a tu cuenta para ver y gestionar tus pedidos." },
    ],
  }),
  component: LoginPage,
});

function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.99.67-2.26 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z"/>
      <path fill="#FBBC05" d="M5.84 14.1A6.6 6.6 0 0 1 5.5 12c0-.73.13-1.44.34-2.1V7.07H2.18A11 11 0 0 0 1 12c0 1.78.43 3.46 1.18 4.93l3.66-2.83z"/>
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.07.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.07l3.66 2.83C6.71 7.31 9.14 5.38 12 5.38z"/>
    </svg>
  );
}

function LoginPage() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const { redirect, oauth } = Route.useSearch();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoStarted, setAutoStarted] = useState(false);
  const redirectPath = redirect === "/admin" ? "/admin" : "/mis-pedidos";

  const buildLoginUrl = useCallback((origin: string, startOAuth = false) => {
    const url = new URL("/login", origin);
    url.searchParams.set("redirect", redirectPath);
    if (startOAuth) url.searchParams.set("oauth", "google");
    return url.toString();
  }, [redirectPath]);

  useEffect(() => {
    if (loading || !user) return;
    const stored = typeof window !== "undefined" ? sessionStorage.getItem("postLoginRedirect") : null;
    if (stored) sessionStorage.removeItem("postLoginRedirect");
    const target = stored ?? redirect;
    navigate({ to: target === "/admin" ? "/admin" : "/mis-pedidos" });
  }, [user, loading, navigate, redirect]);

  const handleGoogle = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      // Persistimos el destino: el broker OAuth pierde el query string al
      // rebotar, así que sin esto siempre caeríamos en /mis-pedidos.
      sessionStorage.setItem("postLoginRedirect", redirectPath);

      const appOrigin = getAppOrigin();

      // El broker OAuth vive en dominios Lovable. Si alguien entra al login
      // desde Railway, moverlo primero al frontend para evitar el 404 en /~oauth.
      if (!isLovableHost(window.location.hostname)) {
        window.location.replace(buildLoginUrl(appOrigin, true));
        return;
      }

      const callbackUrl = buildLoginUrl(appOrigin);
      const result = await lovable.auth.signInWithOAuth("google", {
        redirect_uri: callbackUrl,
      });
      if (result.error) {
        setError("No pudimos iniciar sesión. Probá de nuevo.");
        setBusy(false);
        return;
      }
    } catch (err) {
      setError("No pudimos iniciar sesión. Probá de nuevo.");
      setBusy(false);
    }
  }, [buildLoginUrl, redirectPath]);

  useEffect(() => {
    if (loading || user || busy || autoStarted || oauth !== "google") return;
    setAutoStarted(true);
    void handleGoogle();
  }, [autoStarted, busy, handleGoogle, loading, oauth, user]);

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <div className="px-4 pt-6">
        <Link to="/" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-ink">
          <ArrowLeft className="h-4 w-4" /> Volver al catálogo
        </Link>
      </div>
      <div className="flex-1 grid place-items-center px-4 py-12">
        <div className="w-full max-w-sm rounded-2xl border hairline bg-surface p-8 shadow-sm">
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Tu cuenta
          </div>
          <h1 className="mt-2 font-display text-3xl text-ink">Ingresar</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Iniciá sesión para guardar tus pedidos, ver el historial y solicitar cambios.
          </p>

          {error && (
            <div className="mt-4 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              {error}
            </div>
          )}

          <button
            onClick={handleGoogle}
            disabled={busy}
            className="mt-6 w-full inline-flex items-center justify-center gap-3 rounded-md border hairline bg-background px-4 py-3 text-sm font-medium text-ink hover:bg-surface transition disabled:opacity-50"
          >
            <GoogleIcon className="h-4 w-4" />
            {busy ? "Conectando..." : "Continuar con Google"}
          </button>

          <p className="mt-6 text-[11px] text-muted-foreground">
            Al continuar aceptás recibir comunicaciones operativas sobre tus pedidos.
          </p>
        </div>
      </div>
    </div>
  );
}
