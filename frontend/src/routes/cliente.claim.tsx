/**
 * /cliente/claim — Activar una cuenta invitada por el admin (Fase 4 identidad #1098).
 *
 * El admin invita desde el back-office ("Invitar cliente") y manda este link single-use.
 * El cliente lo abre, **activa la cuenta** (consume el token → queda logueado) y, en el
 * mismo gesto, **registra su passkey** para entrar sin contraseña. Sin tipear nada
 * (decisión del dueño). El token `?t=` es de un solo uso (auth/magic).
 */
import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ShieldCheck, Loader2, KeyRound } from "lucide-react";

import { authedFetch } from "@/lib/authedFetch";
import { Button } from "@/design-system/ui/button";
import { registerPasskey, passkeySupported } from "@/lib/passkey";

export const Route = createFileRoute("/cliente/claim")({
  head: () => ({ meta: [{ title: "Activá tu cuenta — Rambla Rental" }] }),
  component: ClienteClaimPage,
});

type Info = { email: string; nombre: string | null };
type Fase = "cargando" | "listo" | "activada" | "invalido";

function ClienteClaimPage() {
  const [token, setToken] = useState<string | null>(null);
  const [info, setInfo] = useState<Info | null>(null);
  const [fase, setFase] = useState<Fase>("cargando");
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("t");
    if (!t) {
      setFase("invalido");
      return;
    }
    setToken(t);
    authedFetch(`/api/cliente/claim-info?t=${encodeURIComponent(t)}`)
      .then(async (r) => {
        if (!r.ok) return setFase("invalido");
        setInfo((await r.json()) as Info);
        setFase("listo");
      })
      .catch(() => setFase("invalido"));
  }, []);

  async function activar() {
    if (!token || cargando) return;
    setCargando(true);
    try {
      const r = await authedFetch("/api/cliente/claim", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        toast.error(err?.detail ?? "No se pudo activar la cuenta");
        return setFase("invalido");
      }
      // Cuenta activada y logueado. Pasamos a ofrecer la passkey (gesto propio para WebAuthn).
      setFase("activada");
      if (!passkeySupported()) window.location.assign("/cliente/portal?tab=perfil");
    } catch {
      toast.error("Error de red");
    } finally {
      setCargando(false);
    }
  }

  async function activarLlave() {
    if (cargando) return;
    setCargando(true);
    try {
      await registerPasskey("cliente");
      toast.success("Llave de acceso registrada");
    } catch {
      /* la puede agregar después desde Métodos de acceso */
    } finally {
      window.location.assign("/cliente/portal?tab=perfil");
    }
  }

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center px-6">
      <div className="w-full max-w-sm rounded-2xl border hairline bg-card p-7 text-center">
        {fase === "cargando" && (
          <Loader2 className="mx-auto h-7 w-7 animate-spin text-muted-foreground" />
        )}

        {fase === "invalido" && (
          <>
            <h1 className="font-display text-22 font-black text-ink mb-2">Invitación no válida</h1>
            <p className="font-sans text-sm text-muted-foreground">
              El link venció o ya se usó. Pedile al equipo de Rambla una invitación nueva.
            </p>
          </>
        )}

        {fase === "listo" && info && (
          <>
            <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-full bg-amber-soft text-amber">
              <ShieldCheck className="h-7 w-7" />
            </div>
            <h1 className="font-display text-22 font-black text-ink mb-1.5">
              {info.nombre ? `Hola, ${info.nombre}` : "Te invitamos a Rambla"}
            </h1>
            <p className="font-sans text-sm text-muted-foreground mb-6">
              Activá tu cuenta para ver tus pedidos y documentos. La asociamos a{" "}
              <span className="text-ink">{info.email}</span>.
            </p>
            <Button onClick={activar} disabled={cargando} className="w-full">
              {cargando ? <Loader2 className="h-4 w-4 animate-spin" /> : "Activar mi cuenta"}
            </Button>
          </>
        )}

        {fase === "activada" && (
          <>
            <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-full bg-verde/10 text-verde-ink">
              <KeyRound className="h-7 w-7" />
            </div>
            <h1 className="font-display text-22 font-black text-ink mb-1.5">Cuenta activada</h1>
            <p className="font-sans text-sm text-muted-foreground mb-6">
              Registrá tu llave de acceso para entrar sin contraseña — usás tu huella, Face ID o el
              PIN del dispositivo.
            </p>
            <Button onClick={activarLlave} disabled={cargando} className="w-full mb-2">
              {cargando ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Registrar mi llave de acceso"
              )}
            </Button>
            <button
              type="button"
              onClick={() => window.location.assign("/cliente/portal?tab=perfil")}
              className="font-sans text-xs text-muted-foreground hover:text-ink transition"
            >
              Más tarde
            </button>
          </>
        )}
      </div>
    </div>
  );
}
