/**
 * facturacion.emisores.lazy.tsx — Gestión de emisores ARCA.
 *
 * Permite agregar, editar, subir certs y activar/desactivar los
 * emisores (CUITs habilitados ante ARCA) sin tocar Railway.
 */
import { createLazyFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Plus,
  KeyRound,
  CheckCircle2,
  XCircle,
  Pencil,
  ChevronDown,
  Upload,
  Search,
  Fingerprint,
  MoreHorizontal,
  Power,
  Stethoscope,
  BookOpen,
} from "lucide-react";

import { facturacionApi, type EmisorArca } from "@/lib/admin/api";
import { usePadronLookup, type PadronImpuesto } from "@/lib/admin/usePadronLookup";
import { useDocumentTitle } from "@/lib/use-document-title";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/design-system/ui/dropdown-menu";
import { Chequeos } from "@/design-system/composites/Chequeos";

export const Route = createLazyFileRoute("/admin/facturacion/emisores")({
  component: EmisoresPage,
});

const CONDICIONES = [
  { value: "responsable_inscripto", label: "Responsable Inscripto (Factura A)" },
  { value: "monotributo", label: "Monotributo (Factura C)" },
  { value: "exento", label: "Exento (Factura B)" },
] as const;

function EmisoresPage() {
  useDocumentTitle("Emisores ARCA · Back Office");

  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["admin", "emisores-arca"],
    queryFn: () => facturacionApi.listEmisores(),
  });

  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [certId, setCertId] = useState<number | null>(null);
  const [showGuia, setShowGuia] = useState(false);

  const emisores = q.data ?? [];
  const editEmisor = editId !== null ? emisores.find((e) => e.id === editId) : null;
  const certEmisor = certId !== null ? emisores.find((e) => e.id === certId) : null;

  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin", "emisores-arca"] });

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-3xl mx-auto">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="font-mono text-2xs uppercase tracking-[0.25em] text-muted-foreground">
            Back-office · Facturación ARCA
          </div>
          <h1 className="font-display text-3xl text-ink">Emisores</h1>
          <p className="text-sm text-muted-foreground mt-1">
            CUITs habilitados para emitir comprobantes electrónicos. Las claves se cifran con AES
            antes de guardarse.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => setShowGuia(true)}
            className="flex items-center gap-1.5 h-9 px-3 rounded-md border hairline text-sm font-medium text-ink hover:bg-muted/50"
          >
            <BookOpen className="h-3.5 w-3.5" />
            Guía de AFIP
          </button>
          <button
            type="button"
            onClick={() => {
              setEditId(null);
              setShowForm(true);
            }}
            className="flex items-center gap-1.5 h-9 px-3 rounded-md bg-ink text-background text-sm font-medium"
          >
            <Plus className="h-3.5 w-3.5" />
            Nuevo emisor
          </button>
        </div>
      </header>

      {q.isLoading && <div className="text-sm text-muted-foreground">Cargando…</div>}
      {q.isError && (
        <div className="text-sm text-destructive">
          Error cargando emisores. {(q.error as Error)?.message}
        </div>
      )}

      {/* Lista */}
      {emisores.length > 0 && (
        <div className="space-y-3">
          {emisores.map((e) => (
            <EmisorCard
              key={e.id}
              emisor={e}
              onEdit={() => {
                setEditId(e.id);
                setShowForm(true);
              }}
              onCert={() => setCertId(e.id)}
              onToggleActivo={invalidate}
            />
          ))}
        </div>
      )}

      {!q.isLoading && emisores.length === 0 && (
        <div className="text-sm text-muted-foreground py-8 text-center">
          No hay emisores configurados. Agregá el primero.
        </div>
      )}

      {/* Formulario crear/editar */}
      {showForm && (
        <EmisorFormModal
          emisor={editEmisor ?? null}
          onClose={() => {
            setShowForm(false);
            setEditId(null);
          }}
          onSaved={invalidate}
        />
      )}

      {/* Formulario de cert/clave */}
      {certId !== null && certEmisor && (
        <CertFormModal emisor={certEmisor} onClose={() => setCertId(null)} onSaved={invalidate} />
      )}

      {/* Guía de trámites de AFIP */}
      {showGuia && <GuiaAfipModal onClose={() => setShowGuia(false)} />}
    </div>
  );
}

// ── Guía de trámites de AFIP ───────────────────────────────────────────────────

function GuiaAfipModal({ onClose }: { onClose: () => void }) {
  const q = useQuery({
    queryKey: ["admin", "emisores-arca", "guia"],
    queryFn: () => facturacionApi.getGuiaAfip(),
  });

  return (
    <Overlay onClose={onClose}>
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-display text-xl text-ink">Guía de trámites de AFIP</h2>
        <button
          type="button"
          onClick={onClose}
          className="h-8 w-8 grid place-items-center rounded-md text-muted-foreground hover:text-ink hover:bg-muted"
        >
          <XCircle className="h-4 w-4" />
        </button>
      </div>
      {q.isLoading && <div className="text-sm text-muted-foreground">Cargando…</div>}
      {q.isError && (
        <div className="text-sm text-destructive">
          No se pudo cargar la guía. {(q.error as Error)?.message}
        </div>
      )}
      {q.data && (
        <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-ink bg-surface-elevated rounded-md p-4 border hairline">
          {q.data.markdown}
        </pre>
      )}
    </Overlay>
  );
}

// ── Card de emisor ─────────────────────────────────────────────────────────────

function EmisorCard({
  emisor,
  onEdit,
  onCert,
  onToggleActivo,
}: {
  emisor: EmisorArca;
  onEdit: () => void;
  onCert: () => void;
  onToggleActivo: () => void;
}) {
  const qc = useQueryClient();
  const toggle = useMutation({
    mutationFn: async () => {
      if (emisor.activo) {
        await facturacionApi.desactivarEmisor(emisor.id);
      } else {
        await facturacionApi.updateEmisor(emisor.id, { activo: true });
      }
    },
    onSuccess: () => {
      toast.success(emisor.activo ? "Emisor desactivado" : "Emisor activado");
      qc.invalidateQueries({ queryKey: ["admin", "emisores-arca"] });
      onToggleActivo();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const certInfo = useMutation({
    mutationFn: () => facturacionApi.consultarCertInfo(emisor.id),
    onError: (e: Error) => toast.error(e.message),
  });

  const diagnostico = useMutation({
    mutationFn: () => facturacionApi.diagnosticarEmisor(emisor.id),
    onError: (e: Error) => toast.error(e.message),
  });

  const condLabel =
    CONDICIONES.find((c) => c.value === emisor.condicion_iva)?.label ?? emisor.condicion_iva;

  return (
    <div className={cn("rounded-xl border hairline p-4 space-y-3", !emisor.activo && "opacity-60")}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-ink">{emisor.nombre}</span>
            {emisor.activo ? (
              <span className="inline-flex items-center gap-1 text-2xs font-mono font-medium text-verde-ink border border-verde/30 bg-verde/10 rounded-full px-2 py-0.5">
                <CheckCircle2 className="h-3 w-3" /> Activo
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-2xs font-mono font-medium text-muted-foreground border hairline bg-muted/30 rounded-full px-2 py-0.5">
                <XCircle className="h-3 w-3" /> Inactivo
              </span>
            )}
            <span
              className={cn(
                "inline-flex text-2xs font-mono font-medium rounded-full px-2 py-0.5 border",
                emisor.cert_cargado
                  ? "bg-verde/10 text-verde-ink border-verde/30"
                  : "bg-amber/10 text-amber-700 border-amber/40", // eslint-disable-line no-restricted-syntax -- paleta categórica Tier 3: amber-700 sin-cert
              )}
            >
              {emisor.cert_cargado ? "🔑 Cert cargado" : "⚠ Sin cert"}
            </span>
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">
            CUIT {emisor.cuit} · Pto Vta {String(emisor.pto_vta).padStart(5, "0")} · {condLabel}
          </div>
          {emisor.notas && (
            <div className="text-xs text-muted-foreground mt-1 italic">{emisor.notas}</div>
          )}
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label={`Acciones de ${emisor.nombre}`}
              className="h-8 w-8 grid place-items-center rounded-md text-muted-foreground hover:text-ink hover:bg-muted shrink-0"
            >
              <MoreHorizontal className="h-4 w-4" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            {emisor.cert_cargado && (
              <DropdownMenuItem onClick={() => certInfo.mutate()} disabled={certInfo.isPending}>
                <Fingerprint className="mr-2 h-4 w-4" />
                {certInfo.isPending ? "Leyendo…" : "Ver cert"}
              </DropdownMenuItem>
            )}
            <DropdownMenuItem onClick={() => diagnostico.mutate()} disabled={diagnostico.isPending}>
              <Stethoscope className="mr-2 h-4 w-4" />
              {diagnostico.isPending ? "Diagnosticando…" : "Diagnosticar"}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={onCert}>
              <KeyRound className="mr-2 h-4 w-4" />
              {emisor.cert_cargado ? "Renovar cert" : "Cargar cert"}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={onEdit}>
              <Pencil className="mr-2 h-4 w-4" />
              Editar
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => toggle.mutate()} disabled={toggle.isPending}>
              <Power className="mr-2 h-4 w-4" />
              {emisor.activo ? "Desactivar" : "Activar"}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      {certInfo.data && (
        <div className="rounded-md border hairline bg-surface-elevated px-3 py-2 text-xs space-y-1 font-mono">
          <div>
            <span className="text-muted-foreground">Nº de serie: </span>
            {certInfo.data.numero_serie}
          </div>
          <div>
            <span className="text-muted-foreground">Subject: </span>
            {certInfo.data.subject}
          </div>
          <div>
            <span className="text-muted-foreground">Vigencia: </span>
            {certInfo.data.vigente_desde} → {certInfo.data.vigente_hasta}
          </div>
          <div className="text-muted-foreground/70">
            Comparar el Nº de serie contra el "Computador Fiscal" en Administración de Certificados
            Digitales de ARCA.
          </div>
        </div>
      )}
      {diagnostico.data && (
        <div className="rounded-md border hairline bg-surface-elevated px-3 py-2.5">
          <div
            className={cn(
              "text-2xs font-mono font-medium mb-2",
              diagnostico.data.listo ? "text-verde-ink" : "text-destructive",
            )}
          >
            {diagnostico.data.listo ? "✓ Listo para facturar" : "✗ Hay algo por resolver"}
          </div>
          <Chequeos items={diagnostico.data.chequeos} />
        </div>
      )}
    </div>
  );
}

// ── Helpers de CUIT ───────────────────────────────────────────────────────────

function formatCuit(raw: string): string {
  const digits = raw.replace(/\D/g, "").slice(0, 11);
  if (digits.length <= 2) return digits;
  if (digits.length <= 10) return `${digits.slice(0, 2)}-${digits.slice(2)}`;
  return `${digits.slice(0, 2)}-${digits.slice(2, 10)}-${digits.slice(10)}`;
}

// ── Modal crear/editar emisor ──────────────────────────────────────────────────

function EmisorFormModal({
  emisor,
  onClose,
  onSaved,
}: {
  emisor: EmisorArca | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isNew = emisor === null;
  const [nombre, setNombre] = useState(emisor?.nombre ?? "");
  const [razonSocial, setRazonSocial] = useState(emisor?.razon_social ?? "");
  const [cuit, setCuit] = useState(emisor?.cuit ?? "");
  const [ptoVta, setPtoVta] = useState(String(emisor?.pto_vta ?? ""));
  const [condicion, setCondicion] = useState<string>(emisor?.condicion_iva ?? "monotributo");
  const [domicilio, setDomicilio] = useState(emisor?.domicilio ?? "");
  const [iibb, setIibb] = useState(emisor?.iibb ?? "");
  const [inicioActividades, setInicioActividades] = useState(emisor?.inicio_actividades ?? "");
  const [notas, setNotas] = useState(emisor?.notas ?? "");
  // Cert opcional al crear
  const [cert, setCert] = useState("");
  const [key, setKey] = useState("");

  // Campos que trae AFIP → SIEMPRE de solo-lectura (AFIP es la fuente única,
  // no se tipean a mano). Si AFIP no trae uno puntual (o falla la consulta
  // entera), ese campo queda vacío/read-only — nunca un input editable. Cada
  // uno resuelto se puede desbloquear con "editar" por si AFIP tiene un dato
  // mal cargado.
  const [afip, setAfip] = useState<{
    razon_social: boolean;
    domicilio: boolean;
    condicion_iva: boolean;
  }>({ razon_social: false, domicilio: false, condicion_iva: false });

  // 3 campos nuevos + impuestos — puramente informativos (no se persisten,
  // no tienen "editar": no hay nada que corregir a mano).
  const [tipoPersona, setTipoPersona] = useState("");
  const [categoriaMonotributo, setCategoriaMonotributo] = useState("");
  const [actividades, setActividades] = useState<string[]>([]);
  const [impuestos, setImpuestos] = useState<PadronImpuesto[]>([]);

  const padron = usePadronLookup((datos) => {
    if (datos.razon_social) setRazonSocial(datos.razon_social);
    if (datos.domicilio) setDomicilio(datos.domicilio);
    if (datos.condicion_iva) setCondicion(datos.condicion_iva);
    setTipoPersona(datos.tipo_persona);
    setCategoriaMonotributo(datos.categoria_monotributo);
    setActividades(datos.actividades);
    setImpuestos(datos.impuestos);
    // Bloquea solo lo que AFIP realmente devolvió; lo que no vino queda vacío.
    setAfip({
      razon_social: !!datos.razon_social,
      domicilio: !!datos.domicilio,
      condicion_iva: !!datos.condicion_iva,
    });
  });

  // Auto-búsqueda: apenas el CUIT tiene 11 dígitos se consulta AFIP solo
  // (debounce para no disparar en cada tecla). En "Editar" el CUIT ya viene
  // cargado → se refresca desde AFIP al abrir. `buscarAfip` es estable
  // (useCallback en el hook), así el efecto no se re-dispara en cada render.
  const buscarAfip = padron.buscar;
  const ultimoBuscadoRef = useRef<string>("");
  useEffect(() => {
    const digits = cuit.replace(/\D/g, "");
    if (digits.length !== 11 || digits === ultimoBuscadoRef.current) return;
    const t = setTimeout(() => {
      ultimoBuscadoRef.current = digits;
      buscarAfip(cuit);
    }, 500);
    return () => clearTimeout(t);
  }, [cuit, buscarAfip]);

  const certOk = cert.includes("BEGIN CERTIFICATE");
  const keyOk = key.includes("PRIVATE KEY");
  const withCert = isNew && (cert.length > 0 || key.length > 0);

  const puntosVenta = useMutation({
    mutationFn: () => facturacionApi.consultarPuntosVenta(emisor!.id),
    onError: (e: Error) => toast.error(e.message),
  });

  // Si se crea el emisor CON cert, ya se puede detectar el punto de venta en
  // ARCA — se muestra el resolver antes de cerrar en vez de que el usuario lo
  // tipeé a mano (mismo patrón que CertFormModal).
  const [creadoConCert, setCreadoConCert] = useState<EmisorArca | null>(null);

  const qc = useQueryClient();
  const save = useMutation({
    mutationFn: async () => {
      const body = {
        nombre,
        razon_social: razonSocial || null,
        cuit,
        pto_vta: parseInt(ptoVta, 10),
        condicion_iva: condicion as EmisorArca["condicion_iva"],
        domicilio: domicilio || null,
        iibb: iibb || null,
        inicio_actividades: inicioActividades || null,
        notas: notas || null,
        activo: emisor?.activo ?? true,
      };
      if (emisor) return facturacionApi.updateEmisor(emisor.id, body);
      const created = await facturacionApi.createEmisor(body);
      if (certOk && keyOk) await facturacionApi.cargarCert(created.id, cert, key);
      return created;
    },
    onSuccess: (result) => {
      const msg = emisor
        ? "Emisor actualizado"
        : certOk && keyOk
          ? "Emisor creado con certificado"
          : "Emisor creado";
      toast.success(msg);
      qc.invalidateQueries({ queryKey: ["admin", "emisores-arca"] });
      onSaved();
      if (!emisor && certOk && keyOk) {
        setCreadoConCert(result);
      } else {
        onClose();
      }
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const asignarPtoVta = useMutation({
    mutationFn: (nro: number) => facturacionApi.updateEmisor(creadoConCert!.id, { pto_vta: nro }),
    onSuccess: (_data, nro) => {
      toast.success(`Punto de venta ${String(nro).padStart(5, "0")} detectado y asignado`);
      qc.invalidateQueries({ queryKey: ["admin", "emisores-arca"] });
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (creadoConCert) {
    return (
      <Overlay onClose={onClose}>
        <h2 className="font-display text-xl text-ink mb-1">{creadoConCert.nombre}</h2>
        <p className="text-sm text-verde-ink mb-4">Emisor creado con certificado ✓</p>
        <PuntoVentaResolver
          emisorId={creadoConCert.id}
          onResolved={(nro) => asignarPtoVta.mutate(nro)}
        />
        <div className="flex justify-end gap-2 mt-5">
          <button
            type="button"
            onClick={onClose}
            disabled={asignarPtoVta.isPending}
            className="h-9 px-4 rounded-md bg-ink text-background text-sm font-medium disabled:opacity-50"
          >
            Listo
          </button>
        </div>
      </Overlay>
    );
  }

  return (
    <Overlay onClose={onClose}>
      <h2 className="font-display text-xl text-ink mb-4">
        {emisor ? "Editar emisor" : "Nuevo emisor"}
      </h2>
      <div className="space-y-3">
        {/* 1. Nombre interno (nuestro, no de AFIP) — primero para identificar el emisor */}
        <Field
          label="Nombre interno"
          hint="Identificador corto para este sistema (no el nombre legal)"
        >
          {/* eslint-disable-next-line no-restricted-syntax -- input nativo en modal de baja complejidad; DS Input no soporta estilos custom hairline */}
          <input
            type="text"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            placeholder="pablo, santini, empresa_xyz…"
            className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm"
          />
        </Field>

        {/* 2. CUIT — dispara el autocompletado de AFIP solo */}
        <Field
          label="CUIT"
          hint="Poné el CUIT y AFIP completa razón social, condición IVA y domicilio."
        >
          <div className="flex items-center gap-1.5">
            {/* eslint-disable-next-line no-restricted-syntax -- input nativo en modal de baja complejidad */}
            <input
              type="text"
              inputMode="numeric"
              value={cuit}
              onChange={(e) => setCuit(formatCuit(e.target.value))}
              placeholder="20-30000000-0"
              className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm font-mono"
            />
            {padron.buscando ? (
              <span className="shrink-0 text-xs text-muted-foreground flex items-center gap-1.5">
                <Search className="h-3.5 w-3.5 animate-pulse" />
                Consultando AFIP…
              </span>
            ) : (
              cuit.replace(/\D/g, "").length === 11 && (
                <button
                  type="button"
                  onClick={() => padron.buscar(cuit)}
                  title="Volver a consultar AFIP para este CUIT"
                  className="shrink-0 h-9 px-3 rounded-md border hairline text-xs text-muted-foreground hover:text-ink flex items-center gap-1.5"
                >
                  <Search className="h-3.5 w-3.5" />
                  Actualizar
                </button>
              )
            )}
          </div>
          {padron.motivo && <ErrorBanner>{padron.motivo}</ErrorBanner>}
          {!padron.motivo && padron.inactivo && (
            <ErrorBanner>Este CUIT figura inactivo en AFIP.</ErrorBanner>
          )}
          {!padron.motivo && !padron.inactivo && padron.noEncontrado && (
            <p className="text-xs text-muted-foreground/70 mt-1">
              AFIP no trajo datos para este CUIT — completá los campos a mano.
            </p>
          )}
        </Field>

        {/* 3. Datos de AFIP — SIEMPRE de solo lectura, nunca un input editable
        (el dueño: si podemos traer el dato de AFIP, completarlo a mano no
        tiene sentido). Mientras la consulta está en vuelo se ve "esperando";
        si AFIP no lo trajo (falló o no vino ese campo puntual), se ve vacío
        — nunca editable. El banner de error de `padron.motivo` ya explica
        el motivo real cuando corresponde. */}
        <Field label="Razón social" hint="Nombre legal que aparece en el PDF de la factura">
          {padron.buscando && !afip.razon_social ? (
            <PendingAfip />
          ) : afip.razon_social ? (
            <ReadOnlyAfip
              value={razonSocial}
              onEdit={() => setAfip((a) => ({ ...a, razon_social: false }))}
            />
          ) : (
            <VacioAfip />
          )}
        </Field>
        <Field label="Condición IVA del emisor">
          {padron.buscando && !afip.condicion_iva ? (
            <PendingAfip />
          ) : afip.condicion_iva ? (
            <ReadOnlyAfip
              value={CONDICIONES.find((c) => c.value === condicion)?.label ?? condicion}
              onEdit={() => setAfip((a) => ({ ...a, condicion_iva: false }))}
            />
          ) : (
            <VacioAfip />
          )}
        </Field>
        <Field label="Domicilio comercial" hint="Aparece en el PDF de la factura">
          {padron.buscando && !afip.domicilio ? (
            <PendingAfip />
          ) : afip.domicilio ? (
            <ReadOnlyAfip
              value={domicilio}
              onEdit={() => setAfip((a) => ({ ...a, domicilio: false }))}
            />
          ) : (
            <VacioAfip />
          )}
        </Field>

        {/* 3b. Datos informativos de AFIP — solo lectura, sin persistir, sin
        "editar" (no hay nada que corregir a mano). Se completan junto con
        los 3 de arriba. */}
        <Field label="Tipo de persona">
          {padron.buscando && !tipoPersona ? (
            <PendingAfip />
          ) : tipoPersona ? (
            <InfoAfip value={tipoPersona === "FISICA" ? "Física" : "Jurídica"} />
          ) : (
            <VacioAfip />
          )}
        </Field>
        <Field label="Categoría de monotributo" hint="Vacío si el emisor es Responsable Inscripto">
          {padron.buscando && !categoriaMonotributo ? (
            <PendingAfip />
          ) : categoriaMonotributo ? (
            <InfoAfip value={categoriaMonotributo} />
          ) : (
            <VacioAfip />
          )}
        </Field>
        <Field label="Actividad económica">
          {padron.buscando && actividades.length === 0 ? (
            <PendingAfip />
          ) : actividades.length > 0 ? (
            <InfoAfip value={actividades.join(", ")} />
          ) : (
            <VacioAfip />
          )}
        </Field>
        <Field
          label="Impuestos registrados en AFIP"
          hint="Para ver si la relación de IVA está realmente activa en AFIP, no solo inferirla"
        >
          {padron.buscando && impuestos.length === 0 ? (
            <PendingAfip />
          ) : impuestos.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {impuestos.map((i) => (
                <span
                  key={i.id_impuesto}
                  className="inline-flex items-center gap-1 text-2xs font-mono font-medium rounded-full px-2 py-0.5 border hairline bg-surface-elevated text-muted-foreground"
                >
                  {i.descripcion} ({i.estado})
                </span>
              ))}
            </div>
          ) : (
            <VacioAfip />
          )}
        </Field>

        {/* 4. Punto de venta (AFIP no lo lista confiable — se carga/consulta) */}
        <Field label="Punto de Venta">
          <div className="flex gap-1.5">
            {/* eslint-disable-next-line no-restricted-syntax -- input nativo type="number"; DS Input no soporta este tipo */}
            <input
              type="number"
              value={ptoVta}
              onChange={(e) => setPtoVta(e.target.value)}
              placeholder="1"
              min={1}
              className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm font-mono"
            />
            {!isNew && emisor?.cert_cargado && (
              <button
                type="button"
                onClick={() => puntosVenta.mutate()}
                disabled={puntosVenta.isPending}
                title="Consultar los puntos de venta habilitados en ARCA para este emisor"
                className="shrink-0 h-9 px-3 rounded-md border hairline text-xs text-muted-foreground hover:text-ink flex items-center gap-1.5 disabled:opacity-40"
              >
                <Search className="h-3.5 w-3.5" />
                {puntosVenta.isPending ? "Consultando…" : "Consultar en ARCA"}
              </button>
            )}
          </div>
          {puntosVenta.isError && (
            <ErrorBanner>
              No se pudo consultar ARCA: {(puntosVenta.error as Error).message}
            </ErrorBanner>
          )}
          {puntosVenta.data && (
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {puntosVenta.data.puntos_venta.length === 0 ? (
                <span className="text-xs text-muted-foreground">
                  {mensajeSinPuntosVenta(puntosVenta.data.excluidos)}
                </span>
              ) : (
                puntosVenta.data.puntos_venta.map((p) => (
                  <button
                    key={p.nro}
                    type="button"
                    onClick={() => setPtoVta(String(p.nro))}
                    className={cn(
                      "h-7 px-2.5 rounded-md border hairline text-xs font-mono",
                      String(p.nro) === ptoVta
                        ? "bg-ink text-background border-ink"
                        : "bg-surface-elevated text-muted-foreground hover:text-ink",
                    )}
                  >
                    {String(p.nro).padStart(5, "0")}
                  </button>
                ))
              )}
            </div>
          )}
        </Field>
        <Field
          label="Ingresos Brutos (opcional)"
          hint="Sin configurar, el renglón se omite del PDF (no es obligatorio para la validez fiscal)"
        >
          {/* eslint-disable-next-line no-restricted-syntax -- input nativo en modal de baja complejidad */}
          <input
            type="text"
            value={iibb}
            onChange={(e) => setIibb(e.target.value)}
            placeholder="901-123456-7"
            className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm font-mono"
          />
        </Field>
        <Field
          label="Fecha de Inicio de Actividades (opcional)"
          hint="Sin configurar, el renglón se omite del PDF"
        >
          {/* eslint-disable-next-line no-restricted-syntax -- input nativo en modal de baja complejidad */}
          <input
            type="text"
            value={inicioActividades}
            onChange={(e) => setInicioActividades(e.target.value)}
            placeholder="01/03/2018"
            className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm font-mono"
          />
        </Field>
        <Field label="Notas (opcional)">
          {/* eslint-disable-next-line no-restricted-syntax -- input nativo en modal de baja complejidad */}
          <input
            type="text"
            value={notas}
            onChange={(e) => setNotas(e.target.value)}
            placeholder="Persona física, período vigencia cert, etc."
            className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm"
          />
        </Field>

        {/* Cert opcional al crear */}
        {isNew && (
          <>
            <div className="border-t hairline pt-3">
              <p className="text-xs text-muted-foreground mb-3">
                Certificado ARCA{" "}
                <span className="text-muted-foreground/60">
                  (opcional — podés cargarlo después)
                </span>
              </p>
              <div className="space-y-3">
                <PemFileField
                  label="Certificado PEM"
                  value={cert}
                  onChange={setCert}
                  placeholder={"-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----"}
                  isValid={certOk}
                />
                <PemFileField
                  label="Clave privada PEM"
                  value={key}
                  onChange={setKey}
                  placeholder={"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"}
                  isValid={keyOk}
                />
                {withCert && !certOk && (
                  <p className="text-xs text-destructive">
                    El certificado debe incluir los encabezados BEGIN / END CERTIFICATE.
                  </p>
                )}
                {withCert && !keyOk && (
                  <p className="text-xs text-destructive">
                    La clave debe incluir los encabezados BEGIN / END PRIVATE KEY.
                  </p>
                )}
              </div>
            </div>
          </>
        )}
      </div>
      <div className="flex justify-end gap-2 mt-5">
        <button
          type="button"
          onClick={onClose}
          className="h-9 px-4 rounded-md border hairline text-sm text-muted-foreground hover:text-ink"
        >
          Cancelar
        </button>
        <button
          type="button"
          onClick={() => save.mutate()}
          disabled={
            save.isPending ||
            !nombre ||
            !cuit ||
            !ptoVta ||
            !razonSocial ||
            (withCert && (!certOk || !keyOk))
          }
          className="h-9 px-4 rounded-md bg-ink text-background text-sm font-medium disabled:opacity-50"
        >
          {save.isPending ? "Guardando…" : "Guardar"}
        </button>
      </div>
    </Overlay>
  );
}

// ── Punto de venta: auto-detección tras cargar un certificado ──────────────────
//
// Ni bien hay cert cargado, ya se puede consultar ARCA (WSFE `FEParamGetPtosVenta`)
// sin que el usuario tenga que tipear el número a mano y descubrir recién al pedir
// el primer CAE que estaba mal. Un solo punto de venta válido → se asigna solo;
// varios → se deja la lista para elegir (mismo patrón de botones que ya usaba
// "Consultar en ARCA" en el campo Punto de Venta).

const MOTIVO_LABEL: Record<string, string> = {
  bloqueado: "bloqueado",
  dado_de_baja: "dado de baja",
  no_electronico: "no es electrónico",
};

// Fuente única del mensaje cuando la lista de habilitados viene vacía — la
// usan tanto el bloque inline de Punto de Venta como `PuntoVentaResolver`.
// Distingue "ARCA no tiene NINGÚN punto creado" de "ARCA tiene puntos, pero
// ninguno sirve para facturar electrónicamente" — antes ambos casos mostraban
// el mismo mensaje genérico.
function mensajeSinPuntosVenta(
  excluidos: { nro: number; motivo: string; raw_emision_tipo?: string | null }[],
): string {
  if (excluidos.length === 0) {
    return "ARCA no tiene ningún punto de venta registrado para este CUIT — hay que crear uno en el portal de ARCA (Puntos de Venta y Domicilios).";
  }
  const detalle = excluidos
    .map((e) => {
      const label = MOTIVO_LABEL[e.motivo] ?? e.motivo;
      // El valor crudo de `EmisionTipo` viaja para "no_electronico" — si ARCA
      // devuelve un valor inesperado (mismo tipo de quirk que "FchBaja=NULL"),
      // se ve acá tal cual en vez de un motivo genérico sin poder confirmarlo.
      const raw =
        e.motivo === "no_electronico" && e.raw_emision_tipo
          ? ` [ARCA dice EmisionTipo="${e.raw_emision_tipo}"]`
          : "";
      return `${String(e.nro).padStart(5, "0")} (${label}${raw})`;
    })
    .join(", ");
  return `ARCA tiene ${excluidos.length} punto${excluidos.length === 1 ? "" : "s"} de venta pero ninguno está habilitado para facturar electrónicamente: ${detalle}.`;
}

function PuntoVentaResolver({
  emisorId,
  onResolved,
}: {
  emisorId: number;
  onResolved: (ptoVta: number) => void;
}) {
  const q = useQuery({
    queryKey: ["admin", "puntos-venta-autodetect", emisorId],
    queryFn: () => facturacionApi.consultarPuntosVenta(emisorId),
  });
  const yaResuelto = useRef(false);
  const habilitados = q.data?.puntos_venta;

  useEffect(() => {
    if (habilitados && habilitados.length === 1 && !yaResuelto.current) {
      yaResuelto.current = true;
      onResolved(habilitados[0].nro);
    }
  }, [habilitados, onResolved]);

  if (q.isLoading) {
    return <p className="text-xs text-muted-foreground">Detectando punto de venta en ARCA…</p>;
  }
  if (q.isError) {
    return (
      <ErrorBanner>
        No se pudo detectar el punto de venta automáticamente: {(q.error as Error).message} —
        cargalo a mano.
      </ErrorBanner>
    );
  }
  if (!habilitados || habilitados.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        {mensajeSinPuntosVenta(q.data?.excluidos ?? [])} Cargalo a mano.
      </p>
    );
  }
  if (habilitados.length === 1) {
    // Se resuelve solo (useEffect de arriba) — nada que mostrar acá.
    return null;
  }
  return (
    <div className="space-y-1.5">
      <p className="text-xs text-muted-foreground">
        ARCA tiene varios puntos de venta habilitados — elegí uno:
      </p>
      <div className="flex flex-wrap gap-1.5">
        {habilitados.map((p) => (
          <button
            key={p.nro}
            type="button"
            onClick={() => onResolved(p.nro)}
            className="h-7 px-2.5 rounded-md border hairline text-xs font-mono bg-surface-elevated text-muted-foreground hover:text-ink"
          >
            {String(p.nro).padStart(5, "0")}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Modal cargar cert ──────────────────────────────────────────────────────────

function CertFormModal({
  emisor,
  onClose,
  onSaved,
}: {
  emisor: EmisorArca;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [cert, setCert] = useState("");
  const [key, setKey] = useState("");
  const [certGuardado, setCertGuardado] = useState(false);
  const qc = useQueryClient();

  const finalizar = () => {
    onSaved();
    onClose();
  };

  const save = useMutation({
    mutationFn: () => facturacionApi.cargarCert(emisor.id, cert, key),
    onSuccess: () => {
      toast.success("Certificado cargado y cifrado");
      qc.invalidateQueries({ queryKey: ["admin", "emisores-arca"] });
      // No cierra todavía: ahora que hay cert, ya se puede detectar el punto
      // de venta en ARCA sin que el usuario lo tenga que tipear a mano.
      setCertGuardado(true);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const asignarPtoVta = useMutation({
    mutationFn: (nro: number) => facturacionApi.updateEmisor(emisor.id, { pto_vta: nro }),
    onSuccess: (_data, nro) => {
      toast.success(`Punto de venta ${String(nro).padStart(5, "0")} detectado y asignado`);
      qc.invalidateQueries({ queryKey: ["admin", "emisores-arca"] });
      finalizar();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const certOk = cert.includes("BEGIN CERTIFICATE");
  const keyOk = key.includes("PRIVATE KEY");

  if (certGuardado) {
    return (
      <Overlay onClose={finalizar}>
        <h2 className="font-display text-xl text-ink mb-1">Cert · {emisor.nombre}</h2>
        <p className="text-sm text-verde-ink mb-4">Certificado cargado y cifrado ✓</p>
        <PuntoVentaResolver emisorId={emisor.id} onResolved={(nro) => asignarPtoVta.mutate(nro)} />
        <div className="flex justify-end gap-2 mt-5">
          <button
            type="button"
            onClick={finalizar}
            disabled={asignarPtoVta.isPending}
            className="h-9 px-4 rounded-md bg-ink text-background text-sm font-medium disabled:opacity-50"
          >
            Listo
          </button>
        </div>
      </Overlay>
    );
  }

  return (
    <Overlay onClose={onClose}>
      <h2 className="font-display text-xl text-ink mb-1">Cert · {emisor.nombre}</h2>
      <p className="text-xs text-muted-foreground mb-4">
        Pegá el contenido PEM completo (con encabezados BEGIN / END). Se cifra antes de guardarse —
        nunca se expone en texto.
      </p>
      <div className="space-y-3">
        <PemFileField
          label="Certificado"
          value={cert}
          onChange={setCert}
          placeholder={"-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----"}
          isValid={certOk}
        />
        <PemFileField
          label="Clave privada"
          value={key}
          onChange={setKey}
          placeholder={"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"}
          isValid={keyOk}
        />
      </div>
      <div className="flex justify-end gap-2 mt-5">
        <button
          type="button"
          onClick={onClose}
          className="h-9 px-4 rounded-md border hairline text-sm text-muted-foreground hover:text-ink"
        >
          Cancelar
        </button>
        <button
          type="button"
          onClick={() => save.mutate()}
          disabled={save.isPending || !certOk || !keyOk}
          className="h-9 px-4 rounded-md bg-ink text-background text-sm font-medium disabled:opacity-50"
        >
          {save.isPending ? "Guardando…" : "Guardar y cifrar"}
        </button>
      </div>
    </Overlay>
  );
}

// ── Helpers UI ─────────────────────────────────────────────────────────────────

function Overlay({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative z-10 w-full max-w-lg max-h-[85vh] overflow-y-auto rounded-2xl bg-background border hairline shadow-xl p-6">
        {children}
      </div>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <div className="font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground">
        {label}
      </div>
      {hint && <p className="text-xs text-muted-foreground/70 -mt-0.5">{hint}</p>}
      {children}
    </div>
  );
}

// Mismo tratamiento que el error de Factura ARCA en el rail del pedido —
// una sola forma de mostrar un error real de ARCA, con el texto tal cual
// (nunca genérico) en vez de un simple hint gris.
function ErrorBanner({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-1.5 rounded border border-destructive/20 bg-destructive/5 px-2 py-1.5 text-xs text-destructive">
      {children}
    </div>
  );
}

// Campo traído de AFIP, mostrado de solo-lectura (AFIP es la fuente de verdad,
// no se tipea a mano). Chip "AFIP" + un "editar" para desbloquearlo por si AFIP
// se equivocó o hay que ajustarlo — nunca deja al usuario trabado.
function ReadOnlyAfip({ value, onEdit }: { value: string; onEdit: () => void }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 min-w-0 h-9 rounded-md border hairline bg-muted/40 px-3 text-sm flex items-center text-ink">
        <span className="truncate">{value}</span>
      </div>
      <span className="shrink-0 inline-flex items-center gap-1 text-2xs font-mono font-medium text-verde-ink">
        <CheckCircle2 className="h-3 w-3" /> AFIP
      </span>
      <button
        type="button"
        onClick={onEdit}
        className="shrink-0 text-xs text-muted-foreground hover:text-ink underline"
      >
        editar
      </button>
    </div>
  );
}

// Estado "consultando AFIP" de un campo que todavía no se resolvió — distinto
// de un input editable normal, para que no parezca que el campo "se quedó
// editable para siempre" mientras la consulta a AFIP (que puede tardar unos
// segundos) sigue en vuelo.
function PendingAfip() {
  return (
    <div className="h-9 rounded-md border hairline bg-muted/20 px-3 text-sm flex items-center gap-1.5 text-muted-foreground">
      <Search className="h-3.5 w-3.5 animate-pulse" />
      Esperando a AFIP…
    </div>
  );
}

// Campo de AFIP sin dato — nunca un input editable: si AFIP no lo trajo (no
// se buscó todavía, no vino ese campo puntual, o la consulta falló — el
// motivo real ya se ve en el banner de `padron.motivo`), se ve vacío.
function VacioAfip() {
  return (
    <div className="h-9 rounded-md border hairline bg-muted/10 px-3 text-sm flex items-center text-muted-foreground/40">
      —
    </div>
  );
}

// Dato informativo de AFIP (categoría/actividad/tipo de persona) — de solo
// lectura, sin "editar": no se persiste, no hay nada que corregir a mano.
function InfoAfip({ value }: { value: string }) {
  return (
    <div className="h-9 rounded-md border hairline bg-muted/40 px-3 text-sm flex items-center text-ink">
      <span className="truncate">{value}</span>
    </div>
  );
}

function PemFileField({
  label,
  value,
  onChange,
  placeholder,
  isValid,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  isValid: boolean;
}) {
  const [fileName, setFileName] = useState<string | null>(null);

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = (ev) => onChange((ev.target?.result as string) ?? "");
    reader.readAsText(file);
    // reset so same file can be re-picked
    e.target.value = "";
  };

  const displayLabel = isValid ? `${label} ✓` : label;

  return (
    <Field label={displayLabel}>
      <div className="space-y-1.5">
        {/* File picker */}
        <label className="flex items-center gap-2 h-9 px-3 rounded-md border hairline bg-surface-elevated text-sm cursor-pointer hover:bg-muted/20 w-full">
          <Upload className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <span className={cn("truncate text-sm", fileName ? "text-ink" : "text-muted-foreground")}>
            {fileName ?? "Elegir archivo .pem / .crt / .key"}
          </span>
          {/* eslint-disable-next-line no-restricted-syntax -- input[type=file] nativo para file picker; no hay DS equivalente */}
          <input
            type="file"
            accept=".pem,.crt,.key,.cer"
            onChange={handleFile}
            className="sr-only"
          />
        </label>
        {/* Paste fallback */}
        {/* eslint-disable-next-line no-restricted-syntax -- textarea para PEM multilínea */}
        <textarea
          rows={3}
          value={value}
          onChange={(e) => {
            setFileName(null);
            onChange(e.target.value);
          }}
          placeholder={placeholder}
          className="w-full rounded-md border hairline bg-surface-elevated px-3 py-2 text-xs font-mono resize-none text-muted-foreground"
          spellCheck={false}
        />
      </div>
    </Field>
  );
}
