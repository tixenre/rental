import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft, ExternalLink, ShieldCheck, ShieldAlert, ShieldQuestion } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { isAdminEmail, BACKOFFICE_URL } from "@/lib/admin-emails";

export const Route = createFileRoute("/admin")({
  head: () => ({
    meta: [
      { title: "Acceso admin — Rambla Rental" },
      { name: "robots", content: "noindex, nofollow" },
    ],
  }),
  component: AdminAccessPage,
});

function AdminAccessPage() {
  const { user, loading } = useAuth();
  const isAdmin = isAdminEmail(user?.email);

  return (
    <div className="min-h-screen bg-background">
      <div className="border-b hairline px-4 py-4 md:px-8">
        <Link to="/" className="inline-flex items-center gap-2 text-xs text-muted-foreground hover:text-ink">
          <ArrowLeft className="h-3.5 w-3.5" /> Catálogo
        </Link>
      </div>

      <div className="mx-auto max-w-md px-4 py-12 md:px-8">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Administración
        </div>
        <h1 className="font-display text-3xl text-ink">Acceso admin</h1>

        {loading ? (
          <p className="mt-8 text-sm text-muted-foreground">Verificando sesión…</p>
        ) : !user ? (
          <StateCard
            tone="neutral"
            icon={<ShieldQuestion className="h-5 w-5" />}
            title="No iniciaste sesión"
            body="Necesitás iniciar sesión para acceder al área de administración."
          >
            <Link
              to="/login"
              className="inline-flex items-center justify-center rounded-md bg-amber px-4 py-2 text-sm font-medium uppercase tracking-widest text-ink hover:brightness-110"
            >
              Iniciar sesión
            </Link>
          </StateCard>
        ) : !isAdmin ? (
          <StateCard
            tone="warn"
            icon={<ShieldAlert className="h-5 w-5" />}
            title="Sin permisos de administración"
            body={`La cuenta ${user.email} no figura como administradora.`}
          >
            <div className="flex flex-wrap gap-3">
              <Link
                to="/cuenta"
                className="inline-flex items-center justify-center rounded-md border hairline px-4 py-2 text-sm text-ink hover:bg-accent/30"
              >
                Mi cuenta
              </Link>
              <Link
                to="/"
                className="inline-flex items-center justify-center rounded-md px-4 py-2 text-sm text-muted-foreground hover:text-ink"
              >
                Volver al catálogo
              </Link>
            </div>
          </StateCard>
        ) : (
          <StateCard
            tone="ok"
            icon={<ShieldCheck className="h-5 w-5" />}
            title="Acceso autorizado"
            body={`Logueado como ${user.email}.`}
          >
            <a
              href={BACKOFFICE_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-md bg-amber px-4 py-2 text-sm font-medium uppercase tracking-widest text-ink hover:brightness-110"
            >
              Abrir back-office <ExternalLink className="h-3.5 w-3.5" />
            </a>
            <p className="mt-3 text-xs text-muted-foreground">
              Vas a tener que loguearte ahí con tu usuario admin del back-office (sesión separada).
            </p>
          </StateCard>
        )}
      </div>
    </div>
  );
}

function StateCard({
  tone,
  icon,
  title,
  body,
  children,
}: {
  tone: "ok" | "warn" | "neutral";
  icon: React.ReactNode;
  title: string;
  body: string;
  children: React.ReactNode;
}) {
  const toneClasses =
    tone === "ok"
      ? "border-green-600/30 bg-green-50/50 text-green-900"
      : tone === "warn"
      ? "border-amber-600/30 bg-amber-50/50 text-amber-900"
      : "border-ink/20 bg-muted/40 text-ink";

  return (
    <div className="mt-8 space-y-5">
      <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs ${toneClasses}`}>
        {icon}
        <span className="font-mono uppercase tracking-widest">{title}</span>
      </div>
      <p className="text-sm text-muted-foreground">{body}</p>
      <div>{children}</div>
    </div>
  );
}
