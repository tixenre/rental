import { Search, X } from "lucide-react";

type Props = {
  selectedCategories: Set<string>;
  onToggleCategory: (c: string) => void;
  selectedBrand: string | null;
  onBrand: (b: string | null) => void;
  query: string;
  onQuery: (q: string) => void;
  onClear: () => void;
};

export function ActiveFiltersChips({
  selectedCategories,
  onToggleCategory,
  selectedBrand,
  onBrand,
  query,
  onQuery,
  onClear,
}: Props) {
  const trimmed = query.trim();
  const total = selectedCategories.size + (selectedBrand ? 1 : 0) + (trimmed ? 1 : 0);
  if (total === 0) return null;

  return (
    <div className="-mx-3 mb-3 flex items-center gap-1.5 overflow-x-auto px-3 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0">
      <span className="shrink-0 text-2xs uppercase tracking-wider text-muted-foreground hidden sm:inline">
        Filtros:
      </span>
      {trimmed && (
        <Chip
          onRemove={() => onQuery("")}
          label={`"${trimmed}"`}
          icon={<Search className="h-3 w-3" />}
        />
      )}
      {selectedBrand && <Chip onRemove={() => onBrand(null)} label={selectedBrand} />}
      {[...selectedCategories].map((c) => (
        <Chip key={c} onRemove={() => onToggleCategory(c)} label={c} />
      ))}
      {total >= 2 && (
        <button
          onClick={onClear}
          className="shrink-0 rounded-full border hairline px-3 py-1 text-xs text-muted-foreground hover:border-ink hover:text-ink"
        >
          Limpiar
        </button>
      )}
    </div>
  );
}

function Chip({
  label,
  onRemove,
  icon,
}: {
  label: string;
  onRemove: () => void;
  icon?: React.ReactNode;
}) {
  return (
    <button
      onClick={onRemove}
      className="shrink-0 inline-flex items-center gap-1.5 rounded-full bg-ink px-3 py-1 text-xs text-amber hover:opacity-90"
      aria-label={`Quitar filtro ${label}`}
    >
      {icon}
      <span className="max-w-[40vw] truncate">{label}</span>
      <X className="h-3 w-3" />
    </button>
  );
}
