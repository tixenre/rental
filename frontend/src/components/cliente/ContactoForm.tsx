/**
 * ContactoForm.tsx — datos de contacto editables del cliente (mail de
 * comunicación read-only + teléfono + apodo). Extraído de
 * ClientePortalHelpers.tsx; solo lo consume PerfilSection.
 */
import { useState } from "react";
import { toast } from "sonner";
import { Field, SaveButton } from "./primitives";
import { patchPerfil } from "./patchPerfil";
import type { Perfil } from "./ClientePortalTypes";

export function ContactoForm({
  perfil,
  onPerfilChange,
}: {
  perfil: Perfil;
  onPerfilChange: (p: Perfil) => void;
}) {
  const [saving, setSaving] = useState(false);
  const [telefono, setTelefono] = useState(perfil.telefono ?? "");
  const [apodo, setApodo] = useState(perfil.apodo ?? "");
  const dirty = telefono !== (perfil.telefono ?? "") || apodo !== (perfil.apodo ?? "");

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (saving || !dirty) return;
    setSaving(true);
    try {
      await patchPerfil(perfil, onPerfilChange, {
        telefono: telefono.trim(),
        apodo: apodo.trim() || null,
      });
      toast.success("Contacto actualizado");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error al guardar");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSave} className="space-y-5">
      <Field
        label="Mail de comunicación"
        hint="Tu mail de Google — te escribimos acá. No se edita."
      >
        <input
          type="email"
          value={perfil.email ?? ""}
          disabled
          className="w-full rounded-md border hairline bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
        />
      </Field>

      <Field label="Teléfono" hint="Para coordinar el retiro y los avisos por WhatsApp">
        <input
          type="tel"
          value={telefono}
          onChange={(e) => setTelefono(e.target.value)}
          placeholder="+54 9 223 ..."
          className="w-full rounded-md border hairline bg-background px-3 py-2 text-base sm:text-sm text-ink"
        />
      </Field>

      <Field
        label="Apodo"
        hint={
          'Cómo te saludamos en los mails ("Hola Nacho"). Tu nombre oficial sigue siendo el del DNI.'
        }
      >
        <input
          type="text"
          value={apodo}
          onChange={(e) => setApodo(e.target.value)}
          placeholder="Ej: Nacho, Sofi, Toto…"
          maxLength={40}
          className="w-full rounded-md border hairline bg-background px-3 py-2 text-base sm:text-sm text-ink"
        />
      </Field>

      <SaveButton saving={saving} disabled={!dirty} />
    </form>
  );
}
