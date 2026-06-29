/**
 * Sección Formularios — los controles de entrada del DS.
 *
 * Field es la molécula label+control+hint/error para forms con useState (la
 * mayoría del back-office); Form (react-hook-form) es para forms validados.
 * Select y Calendar son críticos en el flujo de reserva.
 */
import { useState } from "react";
import { SegmentedControl } from "@/design-system/ui/segmented-control";
import { QtyInput } from "@/design-system/ui/qty-input";
import { useForm } from "react-hook-form";
import { type DateRange } from "react-day-picker";

import { type CatalogSection } from "../types";
import { Caption, Row, Sample, Stack } from "../catalog-kit";
import { Field } from "@/design-system/kit/Field";
import { Label } from "@/design-system/ui/label";
import { Input } from "@/design-system/ui/input";
import { Textarea } from "@/design-system/ui/textarea";
import { Checkbox } from "@/design-system/ui/checkbox";
import { Switch } from "@/design-system/ui/switch";
import { RadioGroup, RadioGroupItem } from "@/design-system/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import { Slider } from "@/design-system/ui/slider";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/design-system/ui/form";
import { Calendar } from "@/design-system/ui/calendar";

/**
 * FormDemo — react-hook-form en vivo: un campo normal (válido) y otro con
 * error. El error se cablea por defecto en errors → FormMessage lo pinta en
 * destructive sin escribir el texto a mano.
 *
 * `DEFAULTS`/`ERRORS` son constantes a nivel módulo (referencia estable): la prop
 * `errors` de useForm re-sincroniza por un efecto keyeado en esa referencia, así
 * que un objeto literal nuevo por render dispararía un loop infinito de updates.
 */
const FORM_DEFAULTS = { nombre: "Pablo", email: "" };
const FORM_ERRORS = {
  email: { type: "required", message: "El email es obligatorio." },
} as const;

function FormDemo() {
  const form = useForm({ defaultValues: FORM_DEFAULTS, errors: FORM_ERRORS });

  return (
    <Form {...form}>
      <form className="max-w-xs space-y-4" onSubmit={(e) => e.preventDefault()}>
        <FormField
          control={form.control}
          name="nombre"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Nombre</FormLabel>
              <FormControl>
                <Input placeholder="Nombre del cliente" {...field} />
              </FormControl>
              <FormDescription>Como aparece en el remito.</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input placeholder="cliente@correo.com" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      </form>
    </Form>
  );
}

/**
 * CalendarDemo — el date-picker del flujo de reserva. `mode="single"` (un día)
 * y `mode="range"` (retiro→devolución) necesitan estado → useState acá, no en
 * el render() del specimen (que no puede tener hooks).
 */
function CalendarDemo() {
  const [single, setSingle] = useState<Date | undefined>(new Date());
  const [range, setRange] = useState<DateRange | undefined>(() => {
    const desde = new Date();
    const hasta = new Date();
    hasta.setDate(hasta.getDate() + 3);
    return { from: desde, to: hasta };
  });

  return (
    <Row className="items-start gap-6">
      <Stack className="gap-1.5">
        <Calendar
          mode="single"
          selected={single}
          onSelect={setSingle}
          className="rounded-lg border hairline"
        />
        <Caption>mode=&quot;single&quot; — un día</Caption>
      </Stack>
      <Stack className="gap-1.5">
        <Calendar
          mode="range"
          selected={range}
          onSelect={setRange}
          className="rounded-lg border hairline"
        />
        <Caption>mode=&quot;range&quot; — retiro → devolución</Caption>
      </Stack>
    </Row>
  );
}

export const formsSection: CatalogSection = {
  id: "formularios",
  title: "Formularios",
  hint: "Controles de entrada. Field envuelve label+hint+error para forms con useState; Form es la integración react-hook-form.",
  specimens: [
    {
      name: "Field",
      files: ["design-system/kit/Field.tsx"],
      blurb:
        "Molécula label+control+hint/error. Una sola forma del campo en forms controlados — el error tiene prioridad sobre el hint.",
      render: () => (
        <Stack className="max-w-xs gap-4">
          <Field label="Nombre" htmlFor="demo-field-ok" hint="Como aparece en el remito.">
            <Input id="demo-field-ok" placeholder="Nombre del cliente" />
          </Field>
          <Field label="Email" htmlFor="demo-field-err" required error="El email es obligatorio.">
            <Input id="demo-field-err" placeholder="cliente@correo.com" />
          </Field>
        </Stack>
      ),
    },
    {
      name: "Label",
      files: ["design-system/ui/label.tsx"],
      blurb:
        "Etiqueta de control (Radix Label). Asociar con htmlFor / id; refleja disabled del control peer.",
      render: () => (
        <Stack className="max-w-xs gap-1.5">
          <Label htmlFor="demo-label-input">Razón social</Label>
          <Input id="demo-label-input" placeholder="Ej: Rambla Rental SRL" />
        </Stack>
      ),
    },
    {
      name: "Input",
      files: ["design-system/ui/input.tsx"],
      blurb:
        "Campo de texto base. Soporta cualquier type nativo; ≥16px en mobile para no zoomear (HIG).",
      render: () => (
        <Stack className="max-w-xs gap-3">
          <Sample label="normal">
            <Input defaultValue="Pablo Ferrari" />
          </Sample>
          <Sample label="placeholder">
            <Input placeholder="Buscar equipo…" />
          </Sample>
          <Sample label="disabled">
            <Input disabled defaultValue="No editable" />
          </Sample>
          <Sample label='type="file"'>
            <Input type="file" />
          </Sample>
        </Stack>
      ),
    },
    {
      name: "Textarea",
      files: ["design-system/ui/textarea.tsx"],
      blurb: "Texto multilínea (notas del pedido, descripción del equipo). Crece desde min-h.",
      render: () => (
        <Textarea
          className="max-w-xs"
          placeholder="Notas internas del pedido…"
          defaultValue="Retira el cliente en moto, llevar bolso acolchado."
        />
      ),
    },
    {
      name: "Checkbox",
      files: ["design-system/ui/checkbox.tsx"],
      blurb:
        "Casilla on/off para una opción aislada (Radix). Para varias opciones excluyentes usar RadioGroup.",
      render: () => (
        <Stack className="gap-3">
          <label className="flex items-center gap-2 text-sm">
            <Checkbox id="demo-cb-off" />
            <span>Sin marcar</span>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox id="demo-cb-on" defaultChecked />
            <span>Marcado (defaultChecked)</span>
          </label>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <Checkbox id="demo-cb-disabled" disabled />
            <span>Deshabilitado</span>
          </label>
        </Stack>
      ),
    },
    {
      name: "Switch",
      files: ["design-system/ui/switch.tsx"],
      blurb:
        "Toggle para activar/desactivar algo al instante (no necesita confirmar). Ej: visibilidad de un equipo.",
      render: () => (
        <Row className="gap-6">
          <label className="flex items-center gap-2 text-sm">
            <Switch id="demo-sw-off" />
            <span>Apagado</span>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <Switch id="demo-sw-on" defaultChecked />
            <span>Encendido</span>
          </label>
        </Row>
      ),
    },
    {
      name: "RadioGroup",
      files: ["design-system/ui/radio-group.tsx"],
      blurb: "Una opción entre varias excluyentes (Radix). defaultValue marca la inicial.",
      render: () => (
        <RadioGroup defaultValue="diaria" className="gap-3">
          <label className="flex items-center gap-2 text-sm">
            <RadioGroupItem value="diaria" id="demo-r-diaria" />
            <span>Tarifa diaria</span>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <RadioGroupItem value="fin-de-semana" id="demo-r-finde" />
            <span>Fin de semana</span>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <RadioGroupItem value="semanal" id="demo-r-semanal" />
            <span>Semanal</span>
          </label>
        </RadioGroup>
      ),
    },
    {
      name: "Select",
      files: ["design-system/ui/select.tsx"],
      blurb:
        "Desplegable de opción única (Radix). Crítico en el flujo de reserva — categoría, marca, estado del pedido.",
      render: () => (
        <Select defaultValue="camaras">
          <SelectTrigger className="max-w-xs">
            <SelectValue placeholder="Elegí una categoría" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="camaras">Cámaras</SelectItem>
            <SelectItem value="lentes">Lentes</SelectItem>
            <SelectItem value="iluminacion">Iluminación</SelectItem>
            <SelectItem value="audio">Audio</SelectItem>
          </SelectContent>
        </Select>
      ),
    },
    {
      name: "Slider",
      files: ["design-system/ui/slider.tsx"],
      blurb: "Selección de un valor en un rango continuo (Radix). defaultValue es un array.",
      render: () => (
        <div className="max-w-xs pt-2">
          <Slider defaultValue={[40]} max={100} step={1} />
        </div>
      ),
    },
    {
      name: "Form",
      files: ["design-system/ui/form.tsx"],
      blurb:
        "Integración react-hook-form: FormItem/FormLabel/FormControl/FormDescription/FormMessage. El error se pinta solo en destructive.",
      render: () => <FormDemo />,
    },
    {
      name: "Calendar",
      files: ["design-system/ui/calendar.tsx"],
      blurb:
        "Date-picker del flujo de reserva (react-day-picker). mode single (un día) y range (retiro → devolución).",
      render: () => <CalendarDemo />,
    },
    {
      name: "SegmentedControl",
      files: ["design-system/ui/segmented-control.tsx"],
      blurb:
        'Toggle de opciones mutuamente exclusivas. variant="default" = botones separados (back-office). variant="pill" = track conectado (CalendarioWidget).',
      render: () => {
        // eslint-disable-next-line react-hooks/rules-of-hooks
        const [v1, setV1] = useState("sena");
        // eslint-disable-next-line react-hooks/rules-of-hooks
        const [v2, setV2] = useState("mes");
        return (
          <Stack>
            <Sample label="default">
              <SegmentedControl
                value={v1}
                onChange={setV1}
                options={[
                  { value: "sena", label: "Seña 50%" },
                  { value: "saldo", label: "Saldo total" },
                  { value: "otro", label: "Otro" },
                ]}
              />
            </Sample>
            <Sample label="pill">
              <SegmentedControl
                variant="pill"
                value={v2}
                onChange={setV2}
                options={[
                  { value: "mes", label: "Mes" },
                  { value: "semana", label: "Semana" },
                ]}
              />
            </Sample>
          </Stack>
        );
      },
    },
    {
      name: "QtyInput",
      files: ["design-system/ui/qty-input.tsx"],
      blurb:
        "Stepper editable: − / input / +. Controla min/max y muestra estado de error (overstock).",
      render: () => {
        // eslint-disable-next-line react-hooks/rules-of-hooks
        const [qty, setQty] = useState(1);
        // eslint-disable-next-line react-hooks/rules-of-hooks
        const [qtyErr, setQtyErr] = useState(3);
        return (
          <Row className="gap-6">
            <Sample label="default (min 1)">
              <QtyInput value={qty} onChange={setQty} min={1} />
            </Sample>
            <Sample label="error / overstock (max 2)">
              <QtyInput value={qtyErr} onChange={setQtyErr} min={1} max={2} error={qtyErr > 2} />
            </Sample>
            <Sample label="size sm">
              <QtyInput value={qty} onChange={setQty} size="sm" />
            </Sample>
          </Row>
        );
      },
    },
  ],
};
