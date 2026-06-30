/**
 * SessionManager — gestión de sesiones activas (listar / cerrar otras / cerrar una).
 *
 * Compartido por el back-office (settings) y el portal del cliente, parametrizado
 * por `scope` (resuelve los paths de la API). Una sola forma de la gestión —
 * `pulido-frontend`/DS: usa los primitivos del kit (Button), sin one-offs. Espeja
 * `PasskeyManager`. Habilita el "logout real": cerrar una sesión la mata
 * server-side (la cookie deja de valer al instante), no solo en este navegador.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LogOut, Monitor } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { AuthedHttpError } from "@/lib/authedFetch";
import {
  listSessions,
  revokeOtherSessions,
  revokeSession,
  type ActiveSession,
  type SessionScope,
} from "@/lib/sessions";

export function SessionManager({ scope }: { scope: SessionScope }) {
  const qc = useQueryClient();
  const queryKey = ["sessions", scope];

  const q = useQuery({
    queryKey,
    queryFn: () => listSessions(scope),
    retry: false,
  });

  const revokeAllMut = useMutation({
    mutationFn: () => revokeOtherSessions(scope),
    onSuccess: (n) => {
      toast.success(
        n === 0
          ? "No había otras sesiones abiertas"
          : `Cerraste ${n} ${n === 1 ? "sesión" : "sesiones"}`,
      );
      qc.invalidateQueries({ queryKey });
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const sessions = q.data?.sessions ?? [];
  const otras = sessions.filter((s) => !s.current).length;

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground leading-relaxed">
        Estos son los dispositivos donde tu sesión sigue abierta. Si perdiste un dispositivo o ves
        algo que no reconocés, cerrá las demás sesiones — esta queda activa.
      </p>

      {q.isLoading ? (
        <div className="text-sm text-muted-foreground">Cargando…</div>
      ) : sessions.length === 0 ? (
        <div className="rounded-md border border-dashed hairline px-3 py-4 text-sm text-muted-foreground">
          No hay sesiones activas.
        </div>
      ) : (
        <ul className="space-y-2">
          {sessions.map((s) => (
            <SessionRow key={s.jti} scope={scope} session={s} queryKey={queryKey} />
          ))}
        </ul>
      )}

      <Button
        type="button"
        size="sm"
        variant="destructive"
        onClick={() => revokeAllMut.mutate()}
        loading={revokeAllMut.isPending}
        disabled={revokeAllMut.isPending || otras === 0}
      >
        <LogOut /> Cerrar mis otras sesiones
      </Button>
    </div>
  );
}

function SessionRow({
  scope,
  session,
  queryKey,
}: {
  scope: SessionScope;
  session: ActiveSession;
  queryKey: string[];
}) {
  const qc = useQueryClient();

  const delMut = useMutation({
    mutationFn: () => revokeSession(scope, session.jti),
    onSuccess: () => {
      toast.success("Sesión cerrada");
      qc.invalidateQueries({ queryKey });
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  return (
    <li className="flex items-center gap-3 rounded-md border hairline bg-background px-3 py-2.5">
      <Monitor className="h-4 w-4 shrink-0 text-muted-foreground" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 truncate text-sm font-medium text-ink">
          {deviceLabel(session.user_agent)}
          {session.current && (
            <span className="rounded-full bg-amber/15 px-2 py-0.5 text-2xs font-medium uppercase tracking-wider text-ink">
              Este dispositivo
            </span>
          )}
        </div>
        <div className="font-mono text-2xs uppercase tracking-wider text-muted-foreground">
          {fmtFecha(session.created_at)}
        </div>
      </div>

      {!session.current && (
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => delMut.mutate()}
          loading={delMut.isPending}
        >
          Cerrar
        </Button>
      )}
    </li>
  );
}

/** Etiqueta amigable del dispositivo a partir del user-agent (espeja passkey.ts). */
function deviceLabel(ua: string | null): string {
  if (!ua) return "Dispositivo desconocido";
  if (/iPhone|iPad|iPod/.test(ua)) return "iPhone/iPad";
  if (/Android/.test(ua)) return "Android";
  if (/Macintosh|Mac OS X/.test(ua)) return "Mac";
  if (/Windows/.test(ua)) return "Windows";
  if (/CrOS/.test(ua)) return "Chromebook";
  if (/Linux/.test(ua)) return "Linux";
  return "Navegador";
}

function fmtFecha(created: string | null): string {
  if (!created) return "—";
  try {
    return `Iniciada ${new Date(created).toLocaleDateString("es-AR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    })}`;
  } catch {
    return "Iniciada";
  }
}

function errMsg(e: unknown): string {
  if (e instanceof AuthedHttpError) return e.message;
  if (e instanceof Error && e.message) return e.message;
  return "No se pudo completar la operación.";
}
