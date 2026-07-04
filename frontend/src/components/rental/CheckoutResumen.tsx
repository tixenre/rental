import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ArrowLeft, AlertCircle, AlertTriangle, ShieldCheck } from "lucide-react";
import { format } from "date-fns";
import { es } from "date-fns/locale";

import { Button } from "@/design-system/ui/button";
import { Spinner } from "@/design-system/ui/spinner";
import { formatARS } from "@/lib/format";
import { descuentoLabel, type DescuentoOrigen } from "@/lib/cotizacion";
import { PERFIL_IMPUESTOS_LABEL, facturaTipoLabel, type PerfilImpuestos } from "@/lib/iva";
import { useBusinessContact } from "@/hooks/useBusinessContact";
import { aceptarTyc, validarCheckout, type FaltanItem } from "@/lib/checkout";
import { chequearEstadoVerificacion, iniciarVerificacionIdentidad } from "@/lib/verificacion";
import { firmarConPasskey, listPasskeys, passkeyErrorMessage } from "@/lib/passkey";
import {
  VerificacionRequeridaPanel,
  type VerificacionPanelEstado,
} from "@/components/rental/VerificacionRequeridaPanel";
import { FacturacionModal } from "@/components/rental/FacturacionModal";
import { TerminosModal } from "@/components/rental/TerminosModal";
import { ContratoPreviewModal } from "@/components/rental/ContratoPreviewModal";
import { DOC_LABEL, DOC_DESCRIPTION } from "@/routes/ClientePortalTypes";

/** Los 4 docs disponibles desde "presupuesto" (ver `_documentos_disponibles`
 *  en el backend) — "factura" queda afuera, no existe hasta que se facture. */
const DOCS_CHECKOUT = ["remito", "contrato", "albaran", "packing-list"] as const;

/** El return_to que le pasamos a Didit para que, al volver verificado, el
 *  carrito se reabra directo en ESTE paso (no en la lista de ítems). Espeja
 *  `?openCarrito=1` (RESUME_FLAG de verificacion.ts) sumando el paso. */
export const RESUME_STEP_PARAM = "carritoPaso";
export const RESUME_STEP_VALUE = "resumen";

/** Forma mínima de un ítem para el resumen — compacta (sin steppers ni foto,
 *  eso vive en el paso "carrito"): solo lo necesario para confirmar QUÉ se
 *  está pidiendo, no solo cuánto sale. */
export interface ResumenItem {
  id: string;
  nombre: string;
  marca?: string;
  cantidad: number;
}

/**
 * CheckoutResumen — el paso de revisión entre "Revisar pedido" (carrito) y
 * la creación real del pedido. NO hardcodea el orden de las validaciones: le
 * pregunta al backend (`validar_checkout`, el portero de `services/checkout/`)
 * qué falta (`{listo, faltan}`). Un solo botón "Confirmar" resuelve T&C y firma
 * (Face ID/huella) EN EL MISMO click, sin tarjetas intermedias — el usuario no
 * ve un paso separado por cada check, solo Fechas/Total/Tus datos + un botón.
 * La única excepción es **identidad**: como exige salir a Didit, no se puede
 * resolver en un click → mientras falte, el botón queda deshabilitado y se
 * muestra el panel de verificación (con su propio link a Didit) debajo.
 * Fuente única del paso de resumen — la usan el drawer desktop y el sheet
 * mobile por igual.
 *
 * El login (401 del guard `require_cliente`, que el portero no valida — es
 * responsabilidad del route) lo filtra el caller ANTES de montar este
 * componente; acá asumimos sesión de cliente ya presente.
 */
export function CheckoutResumen({
  sessionId,
  startDate,
  endDate,
  startTime,
  endTime,
  d,
  items,
  subtotalTotal,
  descuentoPct,
  descuentoOrigen,
  descuentoMonto,
  totalNeto,
  conIva,
  clienteNombre,
  nombreLegal,
  emailComunicacion,
  telefonoContacto,
  direccionLegal,
  perfilImpuestos,
  onBack,
  onCrearPedido,
}: {
  sessionId: string;
  startDate?: Date;
  endDate?: Date;
  startTime: string;
  endTime: string;
  d: number;
  /** Composición del pedido — solo se usa para el contador del subtotal (no se
   *  vuelve a listar ítem por ítem: esa vista completa ya está en el carrito,
   *  un paso atrás — repetirla acá era ruido, no confirmación). */
  items: ResumenItem[];
  subtotalTotal: number;
  descuentoPct: number;
  descuentoOrigen: DescuentoOrigen;
  descuentoMonto: number;
  totalNeto: number;
  conIva: boolean;
  /** Nombre de pila (casual) — se usa para "Descuento para X". */
  clienteNombre?: string | null;
  /** "Tus datos" — ya resueltos por el backend (`GET /api/cliente/me`):
   *  RENAPER si está verificado (si no, el dato base) + contacto canónico
   *  (teléfono verificado por Didit si existe). Se muestran tal cual. */
  nombreLegal?: string | null;
  emailComunicacion?: string | null;
  telefonoContacto?: string | null;
  direccionLegal?: string | null;
  /** Perfil fiscal — el valor inicial (el editable en vivo vía
   *  `FacturacionModal` vive en estado local, sembrado con este prop). */
  perfilImpuestos?: PerfilImpuestos | null;
  onBack: () => void;
  /** Crea el pedido de verdad (createOrder) — cada superficie decide qué pasa
   *  después (desktop: toast + redirect al portal; mobile: banner inline). Si
   *  tira, este componente lo muestra como error inline sin perder el estado. */
  onCrearPedido: (sessionConfirmed: boolean) => Promise<void>;
}) {
  const itemCount = items.reduce((acc, it) => acc + it.cantidad, 0);
  const [cargando, setCargando] = useState(true);
  const [faltan, setFaltan] = useState<FaltanItem[]>([]);
  const [errorValidar, setErrorValidar] = useState<string | null>(null);
  const [creando, setCreando] = useState(false);
  const [errorCrear, setErrorCrear] = useState<string | null>(null);
  // Fallback de firma sin passkey (sin soporte / canceló): "Confirmo y acepto"
  // por sesión — ver services/checkout/validar.py::_check_firma.
  const [sessionConfirmed, setSessionConfirmed] = useState(false);
  // Sub-estado de identidad (no-verificado / en-revision / rechazado): el
  // portero solo dice "falta identidad" (booleano); para el copy correcto del
  // panel reusamos /api/cliente/me (misma fuente que el resto del checkout).
  const [identidadEstado, setIdentidadEstado] = useState<VerificacionPanelEstado>("no-verificado");
  const [identidadMotivo, setIdentidadMotivo] = useState<string | null>(null);
  // Perfil fiscal en vivo: arranca con lo que llegó por prop, pero si el
  // cliente lo edita desde `FacturacionModal` (sin salir del checkout) se
  // refleja al toque acá, sin esperar a que el caller vuelva a pedir la sesión.
  const [perfilImpuestosLive, setPerfilImpuestosLive] = useState(perfilImpuestos ?? null);
  const [facturacionOpen, setFacturacionOpen] = useState(false);
  const [terminosOpen, setTerminosOpen] = useState(false);
  const [contratoOpen, setContratoOpen] = useState(false);

  async function revalidar(nextSessionConfirmed = sessionConfirmed) {
    setCargando(true);
    setErrorValidar(null);
    try {
      const { listo, faltan: nuevo } = await validarCheckout(sessionId, nextSessionConfirmed);
      setFaltan(listo ? [] : nuevo);
      if (nuevo.some((f) => f.check === "identidad")) {
        const { estado, motivo } = await chequearEstadoVerificacion();
        if (estado === "en-revision" || estado === "rechazado") {
          setIdentidadEstado(estado);
          setIdentidadMotivo(motivo ?? null);
        } else {
          setIdentidadEstado("no-verificado");
          setIdentidadMotivo(null);
        }
      }
    } catch {
      setErrorValidar("No pudimos validar tu pedido. Reintentá en unos segundos.");
    } finally {
      setCargando(false);
    }
  }

  useEffect(() => {
    void revalidar(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo al entrar al paso; revalidar se llama explícitamente en las acciones
  }, [sessionId]);

  const [iniciandoVerif, setIniciandoVerif] = useState(false);
  async function resolverIdentidad() {
    setIniciandoVerif(true);
    try {
      await iniciarVerificacionIdentidad(
        `/?openCarrito=1&${RESUME_STEP_PARAM}=${RESUME_STEP_VALUE}`,
      );
    } catch {
      /* el helper ya hizo toast */
    } finally {
      setIniciandoVerif(false);
    }
  }

  const faltaIdentidad = faltan.some((f) => f.check === "identidad");
  const otrosFaltantes = faltan.filter((f) => !["identidad", "tyc", "firma"].includes(f.check));

  // Un solo click resuelve T&C + firma (sin tarjetas intermedias) y recién
  // ahí crea el pedido — identidad es la única excepción (exige salir a
  // Didit) y por eso el botón está deshabilitado mientras falte.
  async function handleConfirmar() {
    setCreando(true);
    setErrorCrear(null);
    try {
      if (faltan.some((f) => f.check === "tyc")) {
        await aceptarTyc();
      }
      let confirmado = sessionConfirmed;
      if (faltan.some((f) => f.check === "firma")) {
        const credenciales = await listPasskeys("cliente").catch(() => []);
        const resultado = await firmarConPasskey(credenciales.length > 0);
        if (resultado !== "passkey") {
          // Sin soporte de passkey o canceló el prompt: fallback "Confirmo y
          // acepto" por sesión (mismo criterio que el backend).
          confirmado = true;
          setSessionConfirmed(true);
        }
      }
      // Re-confirmamos contra el portero (fuente única) antes de crear — no
      // confiamos en el estado local de arriba.
      const { listo: listoAhora, faltan: faltanAhora } = await validarCheckout(
        sessionId,
        confirmado,
      );
      if (!listoAhora) {
        setFaltan(faltanAhora);
        setErrorCrear(faltanAhora.map((f) => f.mensaje).join(" • "));
        return;
      }
      await onCrearPedido(confirmado);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? passkeyErrorMessage(err) : "No pudimos enviar el pedido, reintentá.";
      setErrorCrear(msg);
      toast.error(msg, { duration: 6000 });
    } finally {
      setCreando(false);
    }
  }

  const puedeConfirmar =
    !cargando && !errorValidar && !faltaIdentidad && otrosFaltantes.length === 0 && !creando;

  const { address: direccionRetiro } = useBusinessContact();
  // Facturación solo se muestra una vez que la identidad está confirmada —
  // antes de eso el perfil fiscal puede ni estar cargado, y no es un dato
  // que valga la pena mostrar mientras el pedido puede no prosperar.
  const mostrarFacturacion = !cargando && !faltaIdentidad && !!perfilImpuestosLive;

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Área scrolleable — el footer con el botón de confirmar vive AFUERA
          (abajo), fijo, para que un pedido largo no lo empuje fuera de vista:
          no querés tener que scrollear para poder confirmar. */}
      <div className="flex-1 overflow-y-auto overscroll-contain px-5 py-4 sm:px-6">
        <button
          type="button"
          onClick={onBack}
          className="mb-4 flex w-fit items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-ink focus:outline-none focus-visible:underline"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Volver al pedido
        </button>

        <div className="space-y-4">
          <div className="rounded-lg border hairline bg-surface p-3">
            <div className="mb-1 font-mono text-2xs uppercase tracking-widest text-muted-foreground">
              Fechas
            </div>
            {startDate && endDate ? (
              <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm font-semibold tabular-nums">
                <span>
                  {format(startDate, "EEE dd MMM", { locale: es })} {startTime}
                </span>
                <span className="text-muted-foreground">→</span>
                <span>
                  {format(endDate, "EEE dd MMM", { locale: es })} {endTime}
                </span>
                <span className="font-mono text-2xs uppercase tracking-wider text-muted-foreground">
                  · {d} {d === 1 ? "jornada" : "jornadas"}
                </span>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">Sin fechas seleccionadas</div>
            )}

            {/* Detalle del retiro — el horario elegido ya está arriba; acá solo
              dónde retirar (sin link para no sacar al cliente del checkout). */}
            <div className="mt-2 border-t hairline pt-2 text-xs text-muted-foreground">
              Retirás en {direccionRetiro}
            </div>
          </div>

          {clienteNombre && (
            <div className="space-y-0.5 rounded-lg border hairline bg-surface p-3">
              <div className="mb-0.5 font-mono text-2xs uppercase tracking-widest text-muted-foreground">
                Tus datos
              </div>
              <div className="text-sm font-semibold text-ink">{nombreLegal || clienteNombre}</div>
              {emailComunicacion && (
                <div className="text-sm text-muted-foreground">{emailComunicacion}</div>
              )}
              {telefonoContacto && (
                <div className="text-sm text-muted-foreground">{telefonoContacto}</div>
              )}
              {direccionLegal && (
                <div className="text-sm text-muted-foreground">{direccionLegal}</div>
              )}
            </div>
          )}

          {mostrarFacturacion && perfilImpuestosLive && (
            <div className="rounded-lg border hairline bg-surface p-3">
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="font-mono text-2xs uppercase tracking-widest text-muted-foreground">
                  Facturación
                </span>
                <button
                  type="button"
                  onClick={() => setFacturacionOpen(true)}
                  className="shrink-0 text-2xs text-muted-foreground underline underline-offset-2 hover:text-ink"
                >
                  Modificar
                </button>
              </div>
              <div className="text-sm font-semibold text-ink">
                {PERFIL_IMPUESTOS_LABEL[perfilImpuestosLive]}
              </div>
              <div className="mt-0.5 text-xs text-muted-foreground">
                Te facturamos: {facturaTipoLabel(perfilImpuestosLive)}
              </div>
            </div>
          )}

          {/* Disclaimer de responsabilidad/seguro — tiene que leerse, no pasar
            desapercibido: un ítem más del resumen, con el rojo suave del DS
            (mismo token que los alerts de error) y tamaño de texto normal
            (no letra chica) para que llame la atención sin gritar tanto como
            un error real. */}
          <div className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
            <p className="text-sm leading-relaxed text-destructive">
              A partir del retiro, sos responsable por daños evitables, pérdida o robo del equipo —
              te recomendamos contratar un seguro propio para tus producciones. Encontrás el Detalle
              de seguro en la sección de documentos de tu perfil apenas hacés el pedido (es
              provisorio hasta que lo confirmemos). Al confirmar aceptás nuestros{" "}
              <button
                type="button"
                onClick={() => setTerminosOpen(true)}
                className="underline underline-offset-2 hover:text-ink"
              >
                Términos y Condiciones
              </button>
              .
            </p>
          </div>

          {/* Documentos — qué se va a encontrar en el portal apenas se hace el
            pedido, para que sepa qué esperar (no solo el disclaimer de
            seguro). El Contrato además se puede LEER ahora mismo: una
            simulación del pedido en curso, antes de firmar nada (sienta base
            para la firma digital de #1098 Fase 5). */}
          <div className="space-y-1.5 rounded-lg border hairline bg-surface p-3">
            <div className="mb-0.5 font-mono text-2xs uppercase tracking-widest text-muted-foreground">
              Documentos de tu pedido
            </div>
            <ul className="space-y-1.5">
              {DOCS_CHECKOUT.map((tipo) => (
                <li key={tipo} className="flex items-start justify-between gap-3 text-sm">
                  <span className="text-muted-foreground">
                    <span className="font-medium text-ink">{DOC_LABEL[tipo]}</span>
                    {DOC_DESCRIPTION[tipo] && <> · {DOC_DESCRIPTION[tipo]}</>}
                  </span>
                  {tipo === "contrato" && (
                    <button
                      type="button"
                      onClick={() => setContratoOpen(true)}
                      className="shrink-0 text-xs text-muted-foreground underline underline-offset-2 hover:text-ink"
                    >
                      Leer
                    </button>
                  )}
                </li>
              ))}
            </ul>
            <p className="pt-0.5 text-2xs text-muted-foreground">
              Los vas a encontrar en tu portal apenas hagas el pedido.
            </p>
          </div>

          {/* Total — al final, justo arriba del botón de confirmar (en el
            footer fijo, inmediatamente debajo de esta tarjeta). */}
          <div className="space-y-2 rounded-lg border hairline bg-surface p-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                Subtotal · {itemCount} {itemCount === 1 ? "ítem" : "ítems"} · {d}{" "}
                {d === 1 ? "jornada" : "jornadas"}
              </span>
              <span className="tabular">{formatARS(subtotalTotal)}</span>
            </div>
            {descuentoPct > 0 && (
              <div className="flex items-center justify-between text-sm text-verde-ink">
                <span>
                  {descuentoLabel(descuentoOrigen, d, clienteNombre)} · {descuentoPct}%
                </span>
                <span className="tabular">−{formatARS(descuentoMonto)}</span>
              </div>
            )}
            <div className="flex items-center justify-between border-t hairline pt-2">
              <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
                Total
              </span>
              <span className="font-display text-2xl tabular text-ink">
                {formatARS(totalNeto)}
                {conIva && (
                  <span className="ml-1 align-baseline font-sans text-sm text-muted-foreground">
                    {" "}
                    + IVA
                  </span>
                )}
              </span>
            </div>
          </div>

          {cargando && (
            <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground">
              <Spinner size="sm" />
              Revisando tu pedido…
            </div>
          )}

          {errorValidar && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2.5 text-sm text-destructive"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{errorValidar}</span>
              <button
                onClick={() => void revalidar()}
                className="ml-auto shrink-0 underline underline-offset-2"
              >
                Reintentar
              </button>
            </div>
          )}

          {/* Identidad — única excepción que no se resuelve en el mismo click (exige
            salir a Didit). Reusa el panel existente (distingue no-verificado/
            en-revisión/rechazado); el botón de confirmar abajo queda deshabilitado
            mientras tanto. */}
          {!cargando && faltaIdentidad && (
            <VerificacionRequeridaPanel
              estado={identidadEstado}
              motivo={identidadMotivo}
              iniciando={iniciandoVerif}
              onVerificar={resolverIdentidad}
            />
          )}

          {/* Cualquier otro faltante (carrito/fechas/stock/precio/contacto/antelación…):
            no tiene una resolución automática acá — el mensaje del backend YA dice
            qué hacer; ofrecemos volver al carrito. */}
          {!cargando &&
            otrosFaltantes.map((f) => (
              <div
                key={f.check}
                role="alert"
                className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2.5 text-sm text-destructive"
              >
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span className="flex-1">{f.mensaje}</span>
                <button onClick={onBack} className="shrink-0 underline underline-offset-2">
                  Volver
                </button>
              </div>
            ))}

          {errorCrear && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2.5 text-sm text-destructive"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{errorCrear}</span>
            </div>
          )}
        </div>
      </div>

      {/* Footer fijo — mismo criterio que el paso "carrito" (footer sticky con totales). */}
      <div
        className="border-t hairline bg-background px-5 py-4 sm:px-6"
        style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}
      >
        <Button
          variant="amber"
          size="lg"
          className="w-full uppercase tracking-widest"
          disabled={!puedeConfirmar}
          loading={creando}
          onClick={() => void handleConfirmar()}
        >
          {creando ? (
            "Enviando…"
          ) : (
            <span className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4" />
              Confirmar pedido
            </span>
          )}
        </Button>
      </div>

      <FacturacionModal
        open={facturacionOpen}
        onOpenChange={setFacturacionOpen}
        onPerfilChange={(p) =>
          setPerfilImpuestosLive((p.perfil_impuestos ?? null) as PerfilImpuestos | null)
        }
      />
      <TerminosModal open={terminosOpen} onOpenChange={setTerminosOpen} />
      <ContratoPreviewModal
        open={contratoOpen}
        onOpenChange={setContratoOpen}
        sessionId={sessionId}
      />
    </div>
  );
}
