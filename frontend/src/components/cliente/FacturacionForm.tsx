/**
 * FacturacionForm.tsx — perfiles fiscales del cliente (condición frente al
 * IVA + CUIT + datos de Factura A) y productoras vinculadas (solo lectura).
 * Extraído de ClientePortalHelpers.tsx. También lo reusa `FacturacionModal`
 * (components/rental) para editar el perfil fiscal sin salir del checkout —
 * un solo formulario, dos lugares desde donde se abre.
 */
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { BadgeCheck } from "lucide-react";
import { Button } from "@/design-system/ui/button";
import { Spinner } from "@/design-system/ui/spinner";
import { cn } from "@/lib/utils";
import { invalidateClienteSession, PERFIL_IMPUESTOS_LABEL } from "@/lib/iva";
import {
  cuitValido,
  crearPerfilFiscal,
  listarPerfilesFiscales,
  listarProductoras,
  marcarPerfilFiscalDefault,
  type PerfilFiscal,
  type Productora,
} from "@/lib/cuit";
import { Field } from "./primitives";
import type { Perfil } from "./ClientePortalTypes";

type PerfilImpuestos = "consumidor_final" | "responsable_inscripto" | "monotributo" | "exento";

// #1240: sin fallback de entrada manual — el cliente SOLO tipea el CUIT,
// todo lo demás (razón social/domicilio/condición IVA) sale de una
// verificación real y BLOQUEANTE contra ARCA (`crearPerfilFiscal`, 422 si
// AFIP no confirma — no se guarda nada a medias). Puede guardar VARIOS CUIT
// propios (perfiles fiscales) y elegir cuál usar por pedido en el checkout;
// las productoras (entidad fiscal compartida) las vincula el admin, acá
// solo se muestran en modo lectura.
export function FacturacionForm({
  perfil,
  onPerfilChange,
  onSaved,
}: {
  perfil: Perfil;
  onPerfilChange: (p: Perfil) => void;
  /** Se llama tras un alta exitosa — lo usa `FacturacionModal` para cerrarse
   *  solo; en el perfil del portal (no es un modal) se omite. */
  onSaved?: () => void;
}) {
  const [perfiles, setPerfiles] = useState<PerfilFiscal[] | null>(null);
  const [productoras, setProductoras] = useState<Productora[] | null>(null);
  const [cargando, setCargando] = useState(true);

  const [cuit, setCuit] = useState("");
  const [etiqueta, setEtiqueta] = useState("");
  const [verificando, setVerificando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cuitOk = cuit.trim() === "" || cuitValido(cuit);

  useEffect(() => {
    let alive = true;
    Promise.all([listarPerfilesFiscales(), listarProductoras()])
      .then(([p, pr]) => {
        if (!alive) return;
        setPerfiles(p);
        setProductoras(pr);
      })
      .catch(() => {
        if (alive) {
          setPerfiles([]);
          setProductoras([]);
        }
      })
      .finally(() => {
        if (alive) setCargando(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  function reflejarEnPerfil(p: {
    cuit: string;
    perfil_impuestos: PerfilImpuestos;
    razon_social: string | null;
    domicilio_fiscal: string | null;
  }) {
    onPerfilChange({
      ...perfil,
      cuit: p.cuit,
      perfil_impuestos: p.perfil_impuestos,
      razon_social: p.razon_social ?? "",
      domicilio_fiscal: p.domicilio_fiscal ?? "",
    });
    invalidateClienteSession();
  }

  async function handleAgregar(e: React.FormEvent) {
    e.preventDefault();
    if (verificando || !cuitOk || !cuit.trim()) return;
    setVerificando(true);
    setError(null);
    try {
      const nuevo = await crearPerfilFiscal(cuit, { etiqueta: etiqueta.trim() || undefined });
      setPerfiles((prev) => {
        const resto = (prev ?? []).filter((p) => p.cuit !== nuevo.cuit);
        return [
          ...(nuevo.es_default ? resto.map((p) => ({ ...p, es_default: false })) : resto),
          nuevo,
        ];
      });
      if (nuevo.es_default) reflejarEnPerfil(nuevo);
      setCuit("");
      setEtiqueta("");
      toast.success("CUIT verificado con ARCA");
      onSaved?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "AFIP no pudo confirmar este CUIT.");
    } finally {
      setVerificando(false);
    }
  }

  async function handleMarcarDefault(id: number) {
    const elegido = (perfiles ?? []).find((p) => p.id === id);
    if (!elegido) return;
    try {
      await marcarPerfilFiscalDefault(id);
      setPerfiles((prev) => (prev ?? []).map((p) => ({ ...p, es_default: p.id === id })));
      reflejarEnPerfil(elegido);
      toast.success("Perfil default actualizado");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error al actualizar");
    }
  }

  if (cargando) {
    return (
      <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
        <Spinner size="sm" />
        Cargando…
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {!!perfiles?.length && (
        <div className="space-y-2">
          <div className="text-xs font-semibold uppercase tracking-wider text-ink">
            Tus CUIT verificados
          </div>
          {perfiles.map((p) => (
            <div
              key={p.id}
              className="flex items-start justify-between gap-3 rounded-md border hairline p-3"
            >
              <div className="space-y-0.5">
                <div className="flex items-center gap-1.5 text-sm font-medium text-ink">
                  <BadgeCheck className="h-3.5 w-3.5 shrink-0 text-verde-ink" />
                  {p.etiqueta || p.razon_social || p.cuit}
                  {p.es_default && (
                    <span className="rounded-full bg-verde/15 px-2 py-0.5 text-3xs font-semibold uppercase tracking-wider text-verde-ink">
                      Default
                    </span>
                  )}
                </div>
                <div className="text-xs text-muted-foreground">
                  {p.cuit} · {PERFIL_IMPUESTOS_LABEL[p.perfil_impuestos]}
                </div>
                {p.domicilio_fiscal && (
                  <div className="text-xs text-muted-foreground">{p.domicilio_fiscal}</div>
                )}
              </div>
              {!p.es_default && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="shrink-0"
                  onClick={() => void handleMarcarDefault(p.id)}
                >
                  Usar como default
                </Button>
              )}
            </div>
          ))}
        </div>
      )}

      {!!productoras?.length && (
        <div className="space-y-2">
          <div className="text-xs font-semibold uppercase tracking-wider text-ink">
            Productoras vinculadas
          </div>
          {productoras.map((pr) => (
            <div key={pr.id} className="rounded-md border hairline p-3">
              <div className="text-sm font-medium text-ink">{pr.razon_social || pr.cuit}</div>
              <div className="text-xs text-muted-foreground">
                {pr.cuit} · {PERFIL_IMPUESTOS_LABEL[pr.perfil_impuestos]}
              </div>
            </div>
          ))}
        </div>
      )}

      <form
        onSubmit={handleAgregar}
        className={cn(
          "space-y-3",
          (perfiles?.length || productoras?.length) && "border-t hairline pt-5",
        )}
      >
        <Field
          label="Agregar un CUIT"
          hint="Lo verificamos contra ARCA — puede diferir del CUIL de tu identidad. Nunca se guarda un dato sin confirmar."
        >
          <input
            type="text"
            inputMode="numeric"
            value={cuit}
            onChange={(e) => {
              setCuit(e.target.value.replace(/[^\d-]/g, "").slice(0, 13));
              setError(null);
            }}
            placeholder="20-12345678-9"
            aria-invalid={!cuitOk}
            className={cn(
              "w-full rounded-md border bg-background px-3 py-2 text-base sm:text-sm text-ink",
              cuitOk ? "hairline" : "border-destructive",
            )}
          />
        </Field>
        <Field label="Etiqueta (opcional)" hint='Para reconocerlo, ej. "Personal" o "Freelance"'>
          <input
            type="text"
            value={etiqueta}
            onChange={(e) => setEtiqueta(e.target.value)}
            placeholder="Personal"
            maxLength={40}
            className="w-full rounded-md border hairline bg-background px-3 py-2 text-base sm:text-sm text-ink"
          />
        </Field>
        {!cuitOk && (
          <p className="text-xs text-destructive">CUIT/CUIL inválido — revisá el número.</p>
        )}
        {error && <p className="text-xs text-destructive">AFIP no pudo confirmarlo: {error}</p>}
        <Button type="submit" disabled={verificando || !cuitOk || !cuit.trim()} className="w-full">
          {verificando ? "Verificando…" : "Verificar y guardar"}
        </Button>
      </form>
    </div>
  );
}
