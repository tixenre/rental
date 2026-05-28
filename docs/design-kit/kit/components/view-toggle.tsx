import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "./lib/cn";

interface Option<T extends string> {
  value: T;
  label: string;
  icon?: ReactNode;
}

/**
 * ViewToggle — segmented control con pill deslizante.
 *
 * Usado en la sub-toolbar del catálogo (Grid / Lista) y donde sea que haya
 * 2–3 opciones mutuamente excluyentes. La pill se mueve con `transition`
 * cubic-bezier en 200ms.
 *
 * El label activo va en `text-amber` sobre el pill ink. Los inactivos en
 * `text-muted-foreground`, hover `text-ink`.
 *
 * @example
 *   <ViewToggle
 *     value={view}
 *     onChange={setView}
 *     options={[
 *       { value: "grid", label: "Grid",  icon: <LayoutGrid className="h-4 w-4" /> },
 *       { value: "list", label: "Lista", icon: <List       className="h-4 w-4" /> },
 *     ]}
 *   />
 *
 * @example  // Estado borrador/publicado en el admin
 *   <ViewToggle
 *     value={status}
 *     onChange={setStatus}
 *     options={[
 *       { value: "draft",     label: "Borrador" },
 *       { value: "published", label: "Publicado" },
 *     ]}
 *   />
 */
export function ViewToggle<T extends string>({
  options,
  value,
  onChange,
  className,
}: {
  options: Option<T>[];
  value: T;
  onChange: (v: T) => void;
  className?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [indicator, setIndicator] = useState({ left: 2, width: 0 });

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const idx = options.findIndex((o) => o.value === value);
    const btn = container.querySelectorAll("button")[idx] as HTMLElement | undefined;
    if (btn) setIndicator({ left: btn.offsetLeft, width: btn.offsetWidth });
  }, [value, options]);

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative inline-flex items-center rounded-full border border-hairline bg-surface p-0.5",
        className,
      )}
    >
      {/* Sliding indicator */}
      <span
        aria-hidden
        className="pointer-events-none absolute top-0.5 bottom-0.5 rounded-full bg-ink transition-all duration-200 ease-out"
        style={{ left: indicator.left, width: indicator.width }}
      />
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={cn(
            "relative z-10 inline-flex items-center gap-1.5 rounded-full px-5 py-2 font-sans text-sm font-bold transition-colors",
            value === opt.value
              ? "text-amber"
              : "text-muted-foreground hover:text-ink",
          )}
        >
          {opt.icon}
          <span>{opt.label}</span>
        </button>
      ))}
    </div>
  );
}
