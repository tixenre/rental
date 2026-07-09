/**
 * IdentificacionSection — foto (create mode) + nombre interno/público +
 * marca/modelo + grid de candidatos de foto.
 *
 * Extraído verbatim de `EquipoFormDialogV2.tsx` (split de god-module, Frente E
 * del skill `mantenimiento`, F2a #1263). Cero cambio de comportamiento —
 * `draft` cubre nombre público/auto-gen; el resto (fotos, marca/modelo) son
 * props puntuales porque no viven en el hook de hidratación.
 */
import type { UseFormReturn } from "react-hook-form";
import { Spinner } from "@/design-system/ui/spinner";
import { Input } from "@/design-system/ui/input";
import { Label } from "@/design-system/ui/label";
import { Switch } from "@/design-system/ui/switch";
import { Button } from "@/design-system/ui/button";
import { Field, PhotoCard } from "./form-helpers";
import type { FormValues } from "./equipo-form-schema";
import type { EquipoFormDraft } from "./useEquipoFormDraft";

export function IdentificacionSection({
  isEdit,
  form,
  draft,
  marcasOptions,
  fotoActual,
  pendingFile,
  onClearPendingFile,
  onUpload,
  onSubirAR2,
  uploadingPending,
  uploadingToR2Pending,
  photoCands,
  lastEnrichPhotoCands,
  onAgregarTodasLasFotos,
  agregarTodasPending,
  onElegirFoto,
  elegirFotoPending,
  elegirFotoVariable,
}: {
  isEdit: boolean;
  form: UseFormReturn<FormValues>;
  draft: EquipoFormDraft;
  marcasOptions: { id: number; nombre: string }[];
  fotoActual: string | undefined;
  pendingFile: File | null;
  onClearPendingFile: () => void;
  onUpload: (file: File) => void;
  onSubirAR2: () => void;
  uploadingPending: boolean;
  uploadingToR2Pending: boolean;
  photoCands: string[];
  lastEnrichPhotoCands: string[];
  onAgregarTodasLasFotos: () => void;
  agregarTodasPending: boolean;
  onElegirFoto: (url: string) => void;
  elegirFotoPending: boolean;
  elegirFotoVariable: string | undefined;
}) {
  const {
    nombrePublico,
    setNombrePublico,
    nombrePublicoAuto,
    setNombrePublicoAuto,
    autoGenDisponible,
    categoriaRoot,
  } = draft;

  return (
    <section className="space-y-3">
      <div className={`grid grid-cols-1 ${!isEdit ? "sm:grid-cols-[160px_1fr]" : ""} gap-3`}>
        {/* Foto card — solo en CREATE mode; en EDIT la galería toma el mando */}
        {!isEdit && (
          <div className="space-y-1">
            <PhotoCard
              url={fotoActual}
              pendingFile={pendingFile}
              hasInitial={false}
              onClear={onClearPendingFile}
              onUpload={onUpload}
              onSubirAR2={onSubirAR2}
              uploading={uploadingPending}
              uploadingToR2={uploadingToR2Pending}
            />
          </div>
        )}

        <div className="space-y-3">
          <Field
            label="Nombre interno (técnico, para vos)"
            error={form.formState.errors.nombre?.message}
          >
            <Input
              {...form.register("nombre")}
              placeholder="Ej: Sony ILME-FX30B Cuerpo"
              autoFocus
            />
          </Field>

          <Field label="Nombre público (cómo se ve en el catálogo)">
            <div className="space-y-1.5">
              <Input
                value={nombrePublico}
                onChange={(e) => {
                  // Tipear a mano es la señal de "esto es mío" — apaga el
                  // auto-gen. Sin esto, `nombrePublicoAuto` (default true)
                  // queda armado en silencio mientras no hay molde (el
                  // toggle para verlo/apagarlo está oculto), y el texto
                  // tipeado se borra apenas se elige una categoría de specs
                  // que sí tiene molde — confirmado en vivo (Angulo 5).
                  setNombrePublico(e.target.value);
                  setNombrePublicoAuto(false);
                }}
                placeholder={
                  autoGenDisponible
                    ? "Generado automático según el molde de la categoría"
                    : "Ej: Cable HDMI 2.0 50cm"
                }
              />
              {autoGenDisponible && (
                <label className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Switch checked={nombrePublicoAuto} onCheckedChange={setNombrePublicoAuto} />
                  Generar automático desde el molde de {categoriaRoot}
                  {!nombrePublicoAuto && (
                    <span className="opacity-60">(off — se guarda como nombre fijo)</span>
                  )}
                </label>
              )}
              {autoGenDisponible && nombrePublicoAuto && (
                <p className="text-2xs text-muted-foreground italic">
                  Molde vivo de la categoría — si el dueño lo cambia desde /admin/equipos/specs,
                  este nombre se actualiza solo (toggle OFF para fijarlo a mano).
                </p>
              )}
              {!nombrePublicoAuto && (
                <p className="text-2xs text-muted-foreground italic">
                  Nombre fijo: gana siempre, aunque cambie el molde de la categoría.
                </p>
              )}
              {!autoGenDisponible && categoriaRoot && (
                <p className="text-xs text-muted-foreground italic">
                  "{categoriaRoot}" todavía no tiene molde configurado. Escribilo a mano — se guarda
                  como nombre fijo (o configurá el molde en /admin/equipos/specs).
                </p>
              )}
            </div>
          </Field>

          <div className="grid grid-cols-2 gap-2">
            <Field label="Marca">
              <Input
                {...form.register("marca")}
                placeholder="Sony"
                list="marca-options"
                autoComplete="off"
              />
              <datalist id="marca-options">
                {marcasOptions.map((m) => (
                  <option key={m.id} value={m.nombre} />
                ))}
              </datalist>
            </Field>
            <Field label="Modelo">
              <Input {...form.register("modelo")} placeholder="FX30" />
            </Field>
          </div>
        </div>
      </div>

      {/* Candidatos de foto (si hay) */}
      {photoCands.length > 0 && (
        <div>
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <Label className="text-xs uppercase tracking-wide text-muted-foreground">
              Fotos encontradas ({photoCands.length}) · click para elegir
            </Label>
            {lastEnrichPhotoCands.length > 0 && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={onAgregarTodasLasFotos}
                disabled={agregarTodasPending}
                title="Sube de un saque las fotos que trajo el último HTML pegado"
              >
                {agregarTodasPending ? (
                  <>
                    <Spinner size="xs" className="mr-1" /> Agregando…
                  </>
                ) : (
                  `Agregar las ${lastEnrichPhotoCands.length} del HTML`
                )}
              </Button>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            {photoCands.map((u) => {
              const isPicking = elegirFotoPending && elegirFotoVariable === u;
              // `fotoActual` (no `form.watch("foto_url")` crudo): en EDIT
              // mode, elegir un candidato sube directo a la galería sin
              // tocar el campo del form (mismo bug ya arreglado en el
              // preview grande del costado) — comparar contra el mismo
              // valor derivado mantiene el aro de "seleccionada" correcto
              // en los dos modos.
              const isSelected = fotoActual === u;
              return (
                <button
                  key={u}
                  type="button"
                  onClick={() => onElegirFoto(u)}
                  disabled={isPicking}
                  className={`relative h-14 w-14 rounded border bg-background overflow-hidden ${isSelected ? "ring-2 ring-amber" : ""}`}
                >
                  <img
                    loading="lazy"
                    decoding="async"
                    src={u}
                    alt=""
                    className="h-full w-full object-contain"
                  />
                  {isPicking && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                      <Spinner size="sm" className="text-white" />
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
