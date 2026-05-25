import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function FieldRow({
  label,
  value,
  onChange,
  checked,
  onCheckedChange,
  current,
  mono,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  current?: string | null;
  mono?: boolean;
}) {
  // Comparar normalizando: backend a veces devuelve null/undefined, el form
  // siempre tiene string. Trim también, así "FX3" no se marca como cambiado
  // si el actual es " FX3 ". Sin esto, casi todos los campos aparecen como
  // "cambia" aunque el valor sea idéntico — confunde al review.
  const changed = ((current ?? "") as string).trim() !== (value ?? "").trim();
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2">
        <Label className="text-xs uppercase tracking-wide text-muted-foreground">{label}</Label>
        <label className="flex items-center gap-1.5 text-xs cursor-pointer">
          <Checkbox checked={checked} onCheckedChange={(v) => onCheckedChange(!!v)} />
          Aplicar
          {changed && (
            <Badge variant="secondary" className="text-[9px] px-1 py-0">
              cambia
            </Badge>
          )}
        </label>
      </div>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={mono ? "font-mono text-xs" : ""}
      />
      {current && current !== value && (
        <div className="text-[11px] text-muted-foreground truncate">Actual: {current}</div>
      )}
    </div>
  );
}

export function FichaCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border hairline px-2 py-1">
      <div className="text-muted-foreground">{label}</div>
      <div className="font-medium truncate">{value}</div>
    </div>
  );
}

export function FichaList({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="mt-2">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground mb-1">{label}</div>
      <div className="flex flex-wrap gap-1">
        {items.map((item, i) => (
          <span
            key={`${label}-${i}`}
            className="inline-flex items-center rounded-full border hairline bg-muted/40 px-2 py-0.5 text-[11px]"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}
