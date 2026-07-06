/**
 * AccessMethods — "Métodos de acceso" del cliente: vista unificada de las llaves
 * de login (passkeys + Google), con agregar/quitar y el guardrail "no podés quedarte
 * sin llave". Generaliza PasskeyManager para el portal (passkey + Google); el admin
 * sigue con PasskeyManager (solo passkeys, sin login_identities).
 *
 * DS: reusa los primitivos del kit (Button, GoogleIcon) — sin one-offs.
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { GoogleIcon } from "@/design-system/ui/GoogleIcon";
import {
  passkeyErrorMessage,
  passkeySupported,
  registerPasskey,
  renamePasskey,
  stepUpWithPasskey,
} from "@/lib/passkey";
import { listAccessKeys, removeAccessKey, GOOGLE_LINK_URL, type AccessKey } from "@/lib/accessKeys";

const LINK_RESULT: Record<string, { ok: boolean; msg: string }> = {
  ok: { ok: true, msg: "Vinculaste tu cuenta de Google." },
  ya: { ok: true, msg: "Esa cuenta de Google ya estaba vinculada." },
  merged: { ok: true, msg: "Unimos tus cuentas en una sola." },
  ya_google: {
    ok: false,
    msg: "Ya tenés una cuenta de Google vinculada. Quitá la actual primero si querés cambiarla.",
  },
  taken: { ok: false, msg: "Esa cuenta de Google ya está en uso por otra cuenta." },
  error: { ok: false, msg: "No se pudo vincular Google. Probá de nuevo." },
};

const QUERY_KEY = ["access-keys"];

export function AccessMethods() {
  const qc = useQueryClient();
  const [supported] = useState(() => passkeySupported());

  // Resultado del linking de Google (vuelve por ?keys=...): mostrar y limpiar la URL.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const r = params.get("keys");
    if (!r) return;
    const m = LINK_RESULT[r];
    if (m) (m.ok ? toast.success : toast.error)(m.msg);
    params.delete("keys");
    const qs = params.toString();
    window.history.replaceState({}, "", window.location.pathname + (qs ? `?${qs}` : ""));
  }, []);

  const q = useQuery({ queryKey: QUERY_KEY, queryFn: listAccessKeys, retry: false });

  const addPasskeyMut = useMutation({
    mutationFn: () => registerPasskey("cliente"),
    onSuccess: () => {
      toast.success("Clave de acceso agregada");
      qc.invalidateQueries({ queryKey: QUERY_KEY });
    },
    onError: (e) => toast.error(passkeyErrorMessage(e)),
  });

  const keys = q.data?.keys ?? [];
  const total = q.data?.total ?? 0;
  const hasGoogle = keys.some((k) => k.kind === "google"); // una cuenta = un Google

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground leading-relaxed">
        Estas son tus formas de entrar. Tené al menos dos —una clave de acceso y tu Google— para no
        quedarte afuera si perdés un dispositivo.
      </p>

      {q.isLoading ? (
        <div className="text-sm text-muted-foreground">Cargando…</div>
      ) : keys.length === 0 ? (
        <div className="rounded-md border border-dashed hairline px-3 py-4 text-sm text-muted-foreground">
          Todavía no tenés métodos de acceso registrados.
        </div>
      ) : (
        <ul className="space-y-2">
          {keys.map((k) => (
            <AccessKeyRow key={`${k.kind}-${k.id}`} k={k} isOnly={total <= 1} />
          ))}
        </ul>
      )}

      <div className="flex flex-wrap gap-2">
        {supported && (
          <Button
            type="button"
            size="sm"
            onClick={() => addPasskeyMut.mutate()}
            loading={addPasskeyMut.isPending}
            disabled={addPasskeyMut.isPending}
          >
            <KeyRound /> Agregar clave de acceso
          </Button>
        )}
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={hasGoogle}
          title={hasGoogle ? "Ya tenés una cuenta de Google vinculada" : undefined}
          onClick={() => {
            window.location.href = GOOGLE_LINK_URL;
          }}
        >
          <GoogleIcon /> Vincular Google
        </Button>
      </div>
    </div>
  );
}

function AccessKeyRow({ k, isOnly }: { k: AccessKey; isOnly: boolean }) {
  const qc = useQueryClient();
  const [confirmDel, setConfirmDel] = useState(false);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(k.label);

  const delMut = useMutation({
    // Step-up: confirmá con passkey antes de quitar un método de acceso (acción sensible).
    mutationFn: async () => {
      await stepUpWithPasskey();
      await removeAccessKey(k.kind === "passkey" ? "passkey" : "identity", k.id);
    },
    onSuccess: () => {
      toast.success("Llave eliminada");
      qc.invalidateQueries({ queryKey: QUERY_KEY });
    },
    onError: (e) => toast.error(passkeyErrorMessage(e)),
  });

  // Renombrar solo aplica a passkeys (las identidades Google/mail no tienen nombre editable).
  const renameMut = useMutation({
    mutationFn: (n: string) => renamePasskey("cliente", k.id, n),
    onSuccess: () => {
      setEditing(false);
      toast.success("Nombre actualizado");
      qc.invalidateQueries({ queryKey: QUERY_KEY });
    },
    onError: (e) => toast.error(passkeyErrorMessage(e)),
  });

  return (
    <li className="flex items-center gap-3 card px-3 py-2.5">
      <span className="shrink-0">
        {k.kind === "google" ? (
          <GoogleIcon />
        ) : (
          <KeyRound className="h-4 w-4 text-muted-foreground" />
        )}
      </span>
      <div className="min-w-0 flex-1">
        {editing ? (
          <div className="flex items-center gap-2">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-8 text-sm"
              maxLength={40}
              autoFocus
            />
            <Button
              type="button"
              size="sm"
              onClick={() => renameMut.mutate(name.trim())}
              loading={renameMut.isPending}
              disabled={!name.trim()}
            >
              Guardar
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => {
                setEditing(false);
                setName(k.label);
              }}
            >
              Cancelar
            </Button>
          </div>
        ) : (
          <>
            <div className="truncate text-sm font-medium text-ink">{k.label}</div>
            <div className="font-mono text-2xs uppercase tracking-wider text-muted-foreground">
              {typeLabel(k.kind)} · {fmtFecha(k.created_at, k.last_used_at)}
            </div>
          </>
        )}
      </div>
      {!editing && (
        <div className="flex shrink-0 items-center gap-1">
          {k.kind === "passkey" && (
            <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(true)}>
              Renombrar
            </Button>
          )}
          {isOnly ? (
            <span className="text-2xs text-muted-foreground">Única llave</span>
          ) : confirmDel ? (
            <>
              <Button
                type="button"
                size="sm"
                variant="destructive"
                onClick={() => delMut.mutate()}
                loading={delMut.isPending}
              >
                Quitar
              </Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => setConfirmDel(false)}>
                No
              </Button>
            </>
          ) : (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setConfirmDel(true)}
              aria-label="Quitar llave"
            >
              <Trash2 />
            </Button>
          )}
        </div>
      )}
    </li>
  );
}

/** Tipo de la llave en claro — para que una passkey con nombre raro (un mail viejo) no
 * se confunda con la cuenta de Google. */
function typeLabel(kind: AccessKey["kind"]): string {
  if (kind === "google") return "Google";
  if (kind === "email") return "Mail";
  return "Clave de acceso";
}

function fmtFecha(created: string | null, lastUsed: string | null): string {
  const d = lastUsed ?? created;
  if (!d) return "—";
  const label = lastUsed ? "Último uso" : "Agregada";
  try {
    return `${label} ${new Date(d).toLocaleDateString("es-AR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    })}`;
  } catch {
    return label;
  }
}
