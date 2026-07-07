import { SearchX } from "lucide-react";

export function SearchEmptyState({
  query,
  categories,
  onSuggestCategory,
}: {
  query: string;
  categories: string[];
  onSuggestCategory: (c: string) => void;
}) {
  return (
    <div className="px-4 lg:px-12">
      <div className="flex flex-col items-center gap-3 py-20 text-center">
        <div className="opacity-20">
          <SearchX className="h-16 w-16 text-ink" strokeWidth={1.2} />
        </div>
        <div className="font-display text-3xl font-black text-ink">Sin resultados</div>
        <div className="font-sans text-sm text-muted-foreground max-w-md">
          Ningún equipo coincide con "{query}". Probá con otro término o explorá las categorías
          populares:
        </div>
        {categories.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5 justify-center">
            {categories.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => onSuggestCategory(c)}
                className="rounded-full border border-[var(--hairline)] bg-surface px-3 py-1 text-xs font-medium text-ink hover:border-ink hover:bg-muted transition"
              >
                {c}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
