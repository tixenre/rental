import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AlertCircle } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { cn } from "@/lib/utils";
import { useUsdRate, calcularPrecioJornada } from "@/hooks/useSettings";

import { adminApi, type Equipo, type EquipoInput, type FaltaField } from "@/lib/admin/api";

/**
 * Editor inline del stock (cantidad). Click → input numérico → Enter/blur guarda.
 * Esc descarta. Vacío = 0 (no permite null).
 */
export function StockInline({ equipo, onSaved }: { equipo: Equipo; onSaved: () => void }) {
  const [value, setValue] = useState<string>(String(equipo.cantidad));
  const initialRef = useRef(equipo.cantidad);

  useEffect(() => {
    setValue(String(equipo.cantidad));
    initialRef.current = equipo.cantidad;
  }, [equipo.id, equipo.cantidad]);

  const saveMut = useMutation({
    mutationFn: (n: number) => adminApi.updateEquipo(equipo.id, { cantidad: n }),
    onSuccess: () => onSaved(),
    onError: (e: Error) => {
      toast.error(`No se pudo actualizar stock: ${e.message}`);
      setValue(String(initialRef.current));
    },
  });

  const commit = () => {
    const n = Math.max(0, Math.floor(Number(value.trim() || "0")));
    if (!Number.isFinite(n)) {
      setValue(String(initialRef.current));
      return;
    }
    if (n === initialRef.current) return;
    saveMut.mutate(n);
  };

  return (
    <Input
      type="number"
      min={0}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        else if (e.key === "Escape") {
          setValue(String(initialRef.current));
          (e.target as HTMLInputElement).blur();
        }
      }}
      disabled={saveMut.isPending}
      className="h-7 w-14 ml-auto text-right text-xs tabular-nums px-2 py-0"
    />
  );
}

/**
 * Editor inline del ROI %. Al cambiar:
 *  - Calcula el nuevo precio_jornada con el USD rate actual.
 *  - PATCHea ambos campos al backend.
 *  - Optimistic UI: actualiza el state local al toque, revierte si falla.
 *
 * No commitea hasta blur o Enter (evita una request por cada keystroke).
 */
export function RoiInline({ equipo, onSaved }: { equipo: Equipo; onSaved: () => void }) {
  const { rate: usdRate } = useUsdRate();
  const [value, setValue] = useState<string>(equipo.roi_pct != null ? String(equipo.roi_pct) : "");
  const initialRef = useRef(equipo.roi_pct);

  // Si el equipo cambia (ej. recarga), sincronizar el input.
  useEffect(() => {
    setValue(equipo.roi_pct != null ? String(equipo.roi_pct) : "");
    initialRef.current = equipo.roi_pct;
  }, [equipo.id, equipo.roi_pct]);

  const saveMut = useMutation({
    mutationFn: async (newRoi: number) => {
      // Actualiza ROI; si tenemos USD, también recalcula precio_jornada
      // y lo manda en el mismo PATCH para que ambos cambien atómicamente.
      // Editar el ROI = volver a la fórmula → marcar precio como AUTO
      // (precio_jornada_manual = false). Esto deja el equipo elegible
      // para futuros recálculos masivos.
      const patch: Partial<EquipoInput> = { roi_pct: newRoi };
      if (equipo.precio_usd) {
        const nuevoPrecio = calcularPrecioJornada(equipo.precio_usd, usdRate, newRoi);
        if (nuevoPrecio !== null) {
          patch.precio_jornada = nuevoPrecio;
          patch.precio_jornada_manual = false;
        }
      }
      return adminApi.updateEquipo(equipo.id, patch);
    },
    onSuccess: () => {
      onSaved();
    },
    onError: (e: Error) => {
      toast.error(`No se pudo actualizar % día: ${e.message}`);
      // Revertir al valor original.
      setValue(initialRef.current != null ? String(initialRef.current) : "");
    },
  });

  const commit = () => {
    const trimmed = value.trim();
    if (trimmed === "") {
      // Vacío → null (saca el ROI). Lo permitimos pero no recalcula precio.
      if (initialRef.current != null) {
        adminApi
          .updateEquipo(equipo.id, { roi_pct: null })
          .then(onSaved)
          .catch((e) => {
            toast.error(`No se pudo limpiar % día: ${e instanceof Error ? e.message : ""}`);
          });
      }
      return;
    }
    const num = Number(trimmed);
    if (!Number.isFinite(num) || num < 0) {
      toast.error("% día debe ser un número >= 0");
      setValue(initialRef.current != null ? String(initialRef.current) : "");
      return;
    }
    if (num === initialRef.current) return; // sin cambio, evitar request
    saveMut.mutate(num);
  };

  return (
    <Input
      type="number"
      min={0}
      step="0.1"
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          (e.target as HTMLInputElement).blur();
        } else if (e.key === "Escape") {
          setValue(initialRef.current != null ? String(initialRef.current) : "");
          (e.target as HTMLInputElement).blur();
        }
      }}
      placeholder="—"
      disabled={saveMut.isPending}
      className="h-7 w-16 ml-auto text-right text-xs tabular-nums px-2 py-0"
    />
  );
}

/**
 * Editor inline del precio de jornada en pesos. Espejo de RoiInline:
 *  - Editás precio → calcula nuevo ROI = precio / (precio_usd × usd_rate) × 100
 *  - PATCHea ambos campos atómicamente
 *  - Optimistic UI con rollback si falla
 *
 * No fuerza redondeo a múltiplos de 100 al tipear (es input MANUAL — el
 * admin manda). El redondeo a 100 solo aplica al cálculo automático
 * desde ROI o al recálculo masivo desde Settings.
 *
 * Si el equipo no tiene `precio_usd`, el ROI no se puede calcular: se
 * guarda solo el precio.
 */
export function PrecioJornadaInline({ equipo, onSaved }: { equipo: Equipo; onSaved: () => void }) {
  const { rate: usdRate } = useUsdRate();
  const [value, setValue] = useState<string>(
    equipo.precio_jornada != null ? String(equipo.precio_jornada) : "",
  );
  const initialRef = useRef(equipo.precio_jornada);

  useEffect(() => {
    setValue(equipo.precio_jornada != null ? String(equipo.precio_jornada) : "");
    initialRef.current = equipo.precio_jornada;
  }, [equipo.id, equipo.precio_jornada]);

  const saveMut = useMutation({
    mutationFn: async (newPrecio: number | null) => {
      // Editar el precio directo = override manual → flag = TRUE.
      // Esto evita que el próximo recálculo masivo (al cambiar el USD)
      // pise el precio que el admin acaba de definir a mano.
      const patch: Partial<EquipoInput> = {
        precio_jornada: newPrecio,
        precio_jornada_manual: true,
      };
      // Si tenemos USD y el nuevo precio no es null, derivamos el ROI
      // implícito y lo persistimos también para que la fórmula quede
      // coherente. Si el equipo no tiene USD, no podemos calcular ROI.
      if (newPrecio !== null && equipo.precio_usd && usdRate > 0) {
        const newRoi = (newPrecio / (equipo.precio_usd * usdRate)) * 100;
        // Redondear a 2 decimales para evitar 3.0399999999...
        patch.roi_pct = Math.round(newRoi * 100) / 100;
      }
      return adminApi.updateEquipo(equipo.id, patch);
    },
    onSuccess: () => {
      onSaved();
    },
    onError: (e: Error) => {
      toast.error(`No se pudo actualizar precio: ${e.message}`);
      setValue(initialRef.current != null ? String(initialRef.current) : "");
    },
  });

  const commit = () => {
    const trimmed = value.trim();
    if (trimmed === "") {
      // Vacío → null (saca el precio). Permitido pero no toca ROI.
      if (initialRef.current != null) saveMut.mutate(null);
      return;
    }
    const num = Number(trimmed);
    if (!Number.isFinite(num) || num < 0) {
      toast.error("Precio debe ser un número >= 0");
      setValue(initialRef.current != null ? String(initialRef.current) : "");
      return;
    }
    if (num === initialRef.current) return;
    saveMut.mutate(num);
  };

  const isManual = !!equipo.precio_jornada_manual;

  return (
    <div className="relative ml-auto w-28">
      <span className="absolute left-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground pointer-events-none">
        $
      </span>
      <Input
        type="number"
        min={0}
        step="100"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            (e.target as HTMLInputElement).blur();
          } else if (e.key === "Escape") {
            setValue(initialRef.current != null ? String(initialRef.current) : "");
            (e.target as HTMLInputElement).blur();
          }
        }}
        placeholder="—"
        disabled={saveMut.isPending}
        title={
          isManual
            ? "Precio fijado manualmente — no se actualiza al recalcular masivo"
            : "Precio automático (calculado desde USD × % día)"
        }
        className={
          "h-7 text-right text-xs tabular-nums pl-5 pr-2 py-0 " +
          (isManual ? "border-amber/60 bg-amber-soft/30" : "")
        }
      />
      {isManual && (
        <span
          className="absolute -top-1.5 -right-1 rounded-full bg-amber px-1 text-2xs font-mono uppercase tracking-wide text-ink"
          title="Manual"
        >
          M
        </span>
      )}
    </div>
  );
}

const FALTA_LABELS: Record<FaltaField, string> = {
  foto: "sin foto principal",
  categoria: "sin categoría asignada",
  nombre_publico: "sin nombre público",
  descripcion: "sin descripción extendida",
  serie: "sin número de serie",
  valor_reposicion: "sin valor de reposición",
};

export function KpiCard({
  label,
  value,
  meta,
  warn = false,
}: {
  label: string;
  value: number;
  meta: string;
  warn?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-card px-3.5 py-3 sm:px-4 sm:py-3.5",
        warn
          ? "border-[color-mix(in_oklch,var(--amber)_45%,transparent)] bg-amber-soft/40"
          : "hairline",
      )}
    >
      <div className="font-mono text-2xs uppercase tracking-[0.22em] text-muted-foreground">
        {label}
      </div>
      <div className="font-display text-2xl sm:text-3xl font-black text-ink tabular-nums leading-none mt-1">
        {value}
      </div>
      <div className="font-sans text-xs text-muted-foreground mt-1">{meta}</div>
    </div>
  );
}

export function FaltaBanner({
  falta,
  total,
  loading,
  onClear,
}: {
  falta: FaltaField;
  total: number;
  loading: boolean;
  onClear: () => void;
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-amber/40 bg-amber-soft px-4 py-2.5">
      <AlertCircle className="h-4 w-4 shrink-0 text-ink" />
      <div className="flex-1 min-w-0 text-sm">
        <span className="font-medium text-ink">Filtrando equipos {FALTA_LABELS[falta]}</span>
        <span className="text-muted-foreground">
          {" · "}
          {loading ? "cargando…" : `${total} ${total === 1 ? "resultado" : "resultados"}`}
        </span>
      </div>
      <Button variant="ghost" size="sm" onClick={onClear}>
        Quitar filtro
      </Button>
    </div>
  );
}
