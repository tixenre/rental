/**
 * PrecioYStockSection — stock (o sentinel de combo) + precio USD/ROI/jornada
 * (manual override) + tipo de producto + dueño.
 *
 * Extraído verbatim de `EquipoFormDialogV2.tsx` (split de god-module, Frente E
 * del skill `mantenimiento`, F2b #1263). Cero cambio de comportamiento.
 */
import type { UseFormReturn } from "react-hook-form";
import { Input } from "@/design-system/ui/input";
import { Button } from "@/design-system/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import { DUENOS, isCanonicalDueno } from "@/lib/admin/duenos";
import { Field, TipoGlosario } from "./form-helpers";
import type { FormValues } from "./equipo-form-schema";

export function PrecioYStockSection({
  form,
  esCombo,
  precioJornadaManual,
  setPrecioJornadaManual,
}: {
  form: UseFormReturn<FormValues>;
  esCombo: boolean;
  precioJornadaManual: boolean;
  setPrecioJornadaManual: (v: boolean) => void;
}) {
  return (
    <section className="space-y-3 pt-2 border-t hairline">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <Field label="Stock">
          {esCombo ? (
            <div className="flex items-center h-9 px-3 rounded-md border hairline bg-muted/30 text-sm text-muted-foreground">
              Sentinel (9999) — derivado de componentes
            </div>
          ) : (
            <div className="flex gap-1">
              <Button
                type="button"
                size="icon"
                variant="outline"
                className="h-9 w-9 shrink-0"
                onClick={() => {
                  const raw = Number(form.getValues("cantidad") ?? 0);
                  const current = Number.isFinite(raw) ? raw : 0;
                  form.setValue("cantidad", Math.max(0, current - 1), { shouldDirty: true });
                }}
                aria-label="Restar 1 al stock"
              >
                −
              </Button>
              <Input type="number" min={0} className="text-center" {...form.register("cantidad")} />
              <Button
                type="button"
                size="icon"
                variant="outline"
                className="h-9 w-9 shrink-0"
                onClick={() => {
                  const raw = Number(form.getValues("cantidad") ?? 0);
                  const current = Number.isFinite(raw) ? raw : 0;
                  form.setValue("cantidad", current + 1, { shouldDirty: true });
                }}
                aria-label="Sumar 1 al stock"
              >
                +
              </Button>
            </div>
          )}
        </Field>
        <Field label="Valor USD">
          <Input type="number" step="0.01" {...form.register("precio_usd")} />
        </Field>
        <Field label="% día">
          <Input type="number" step="0.1" {...form.register("roi_pct")} />
        </Field>
        <Field label={precioJornadaManual ? "Precio/jornada (manual)" : "Precio/jornada (auto)"}>
          <div className="flex gap-1">
            <Input
              type="number"
              {...form.register("precio_jornada", {
                onChange: () => setPrecioJornadaManual(true),
              })}
            />
            {precioJornadaManual && (
              <Button
                type="button"
                size="icon"
                variant="ghost"
                title="Recalcular automático"
                onClick={() => setPrecioJornadaManual(false)}
              >
                ↺
              </Button>
            )}
          </div>
        </Field>
      </div>

      <div className="space-y-2">
        <Field label="Tipo de producto">
          <Select
            value={form.watch("tipo")}
            onValueChange={(v) =>
              form.setValue("tipo", v as FormValues["tipo"], { shouldDirty: true })
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="simple">Equipo</SelectItem>
              <SelectItem value="kit">Kit</SelectItem>
              <SelectItem value="combo">Combo</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <TipoGlosario tipo={form.watch("tipo")} />
      </div>

      <Field label="Dueño">
        <Select
          value={form.watch("dueno") ?? ""}
          onValueChange={(v) => form.setValue("dueno", v, { shouldDirty: true })}
        >
          <SelectTrigger>
            <SelectValue placeholder="Seleccionar…" />
          </SelectTrigger>
          <SelectContent>
            {DUENOS.map((d) => (
              <SelectItem key={d} value={d}>
                {d}
              </SelectItem>
            ))}
            {form.watch("dueno") && !isCanonicalDueno(form.watch("dueno") ?? "") && (
              <SelectItem value={form.watch("dueno") ?? ""}>
                {form.watch("dueno")} (custom)
              </SelectItem>
            )}
          </SelectContent>
        </Select>
      </Field>
    </section>
  );
}
