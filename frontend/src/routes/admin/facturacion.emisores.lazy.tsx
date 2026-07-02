/**
 * facturacion.emisores.lazy.tsx — Gestión de emisores ARCA.
 *
 * Permite agregar, editar, subir certs y activar/desactivar los
 * emisores (CUITs habilitados ante ARCA) sin tocar Railway.
 */
import { createLazyFileRoute } from "@tanstack/react-router";
import { useState } from "react";
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
} from "lucide-react";

import { facturacionApi, type EmisorArca } from "@/lib/admin/api";
import { usePadronLookup } from "@/lib/admin/usePadronLookup";
import { useDocumentTitle } from "@/lib/use-document-title";
import { cn } from "@/lib/utils";

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
        <button
          type="button"
          onClick={() => {
            setEditId(null);
            setShowForm(true);
          }}
          className="shrink-0 flex items-center gap-1.5 h-9 px-3 rounded-md bg-ink text-background text-sm font-medium"
        >
          <Plus className="h-3.5 w-3.5" />
          Nuevo emisor
        </button>
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
    </div>
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
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            type="button"
            onClick={onCert}
            className="h-8 px-2.5 rounded-md border hairline text-xs text-muted-foreground hover:text-ink flex items-center gap-1.5"
          >
            <KeyRound className="h-3.5 w-3.5" />
            {emisor.cert_cargado ? "Renovar cert" : "Cargar cert"}
          </button>
          <button
            type="button"
            onClick={onEdit}
            className="h-8 px-2.5 rounded-md border hairline text-xs text-muted-foreground hover:text-ink flex items-center gap-1.5"
          >
            <Pencil className="h-3.5 w-3.5" />
            Editar
          </button>
          <button
            type="button"
            onClick={() => toggle.mutate()}
            disabled={toggle.isPending}
            className="h-8 px-2.5 rounded-md border hairline text-xs text-muted-foreground hover:text-ink"
          >
            {emisor.activo ? "Desactivar" : "Activar"}
          </button>
        </div>
      </div>
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

  const padron = usePadronLookup((datos) => {
    if (datos.razon_social) setRazonSocial(datos.razon_social);
    if (datos.domicilio) setDomicilio(datos.domicilio);
    if (datos.condicion_iva) setCondicion(datos.condicion_iva);
  });

  const certOk = cert.includes("BEGIN CERTIFICATE");
  const keyOk = key.includes("PRIVATE KEY");
  const withCert = isNew && (cert.length > 0 || key.length > 0);

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
    onSuccess: () => {
      const msg = emisor
        ? "Emisor actualizado"
        : certOk && keyOk
          ? "Emisor creado con certificado"
          : "Emisor creado";
      toast.success(msg);
      qc.invalidateQueries({ queryKey: ["admin", "emisores-arca"] });
      onSaved();
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <Overlay onClose={onClose}>
      <h2 className="font-display text-xl text-ink mb-4">
        {emisor ? "Editar emisor" : "Nuevo emisor"}
      </h2>
      <div className="space-y-3">
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
        <Field label="Razón social" hint="Nombre legal que aparece en el PDF de la factura">
          {/* eslint-disable-next-line no-restricted-syntax -- input nativo en modal de baja complejidad */}
          <input
            type="text"
            value={razonSocial}
            onChange={(e) => setRazonSocial(e.target.value)}
            placeholder="Martín Javier Santini Calarco"
            className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm"
          />
        </Field>
        <Field
          label="CUIT"
          hint={
            padron.noEncontrado ? "ARCA no tiene datos para este CUIT — cargá a mano." : undefined
          }
        >
          <div className="flex gap-1.5">
            {/* eslint-disable-next-line no-restricted-syntax -- input nativo en modal de baja complejidad */}
            <input
              type="text"
              inputMode="numeric"
              value={cuit}
              onChange={(e) => setCuit(formatCuit(e.target.value))}
              placeholder="20-30000000-0"
              className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm font-mono"
            />
            <button
              type="button"
              onClick={() => padron.buscar(cuit)}
              disabled={padron.buscando || cuit.replace(/\D/g, "").length !== 11}
              title="Autocompletar razón social/domicilio/condición IVA desde ARCA"
              className="shrink-0 h-9 px-3 rounded-md border hairline text-xs text-muted-foreground hover:text-ink flex items-center gap-1.5 disabled:opacity-40"
            >
              <Search className="h-3.5 w-3.5" />
              {padron.buscando ? "Buscando…" : "Buscar"}
            </button>
          </div>
        </Field>
        <Field label="Punto de Venta">
          {/* eslint-disable-next-line no-restricted-syntax -- input nativo type="number"; DS Input no soporta este tipo */}
          <input
            type="number"
            value={ptoVta}
            onChange={(e) => setPtoVta(e.target.value)}
            placeholder="1"
            min={1}
            className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm font-mono"
          />
        </Field>
        <Field label="Condición IVA del emisor">
          <div className="relative">
            <select
              value={condicion}
              onChange={(e) => setCondicion(e.target.value)}
              className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm appearance-none pr-8"
            >
              {CONDICIONES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-2.5 top-2.5 h-4 w-4 text-muted-foreground pointer-events-none" />
          </div>
        </Field>
        <Field label="Domicilio comercial" hint="Aparece en el PDF de la factura">
          {/* eslint-disable-next-line no-restricted-syntax -- input nativo en modal de baja complejidad */}
          <input
            type="text"
            value={domicilio}
            onChange={(e) => setDomicilio(e.target.value)}
            placeholder="Falucho 4625, Mar del Plata"
            className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm"
          />
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
            save.isPending || !nombre || !cuit || !ptoVta || (withCert && (!certOk || !keyOk))
          }
          className="h-9 px-4 rounded-md bg-ink text-background text-sm font-medium disabled:opacity-50"
        >
          {save.isPending ? "Guardando…" : "Guardar"}
        </button>
      </div>
    </Overlay>
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
  const qc = useQueryClient();

  const save = useMutation({
    mutationFn: () => facturacionApi.cargarCert(emisor.id, cert, key),
    onSuccess: () => {
      toast.success("Certificado cargado y cifrado");
      qc.invalidateQueries({ queryKey: ["admin", "emisores-arca"] });
      onSaved();
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const certOk = cert.includes("BEGIN CERTIFICATE");
  const keyOk = key.includes("PRIVATE KEY");

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
      <div className="relative z-10 w-full max-w-lg rounded-2xl bg-background border hairline shadow-xl p-6">
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
