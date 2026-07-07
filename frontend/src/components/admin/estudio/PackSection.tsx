import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Package, Plus, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Input } from "@/design-system/ui/input";
import { EmptyState } from "@/design-system/composites/EmptyState";
import { ListSkeleton } from "@/components/admin/skeletons";
import { adminApi, estudioAdminApi } from "@/lib/admin/api";
import { Section } from "./shared";

export function PackSection() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<{ id: number; nombre: string; marca: string | null }[]>(
    [],
  );
  const [searching, setSearching] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "estudio", "pack"],
    queryFn: () => estudioAdminApi.listPack(),
  });

  const pack = data?.pack ?? [];
  const packIds = new Set(pack.map((p) => p.id));

  const addMut = useMutation({
    mutationFn: (id: number) => estudioAdminApi.addPackEquipo(id),
    onSuccess: (res) => {
      qc.setQueryData(["admin", "estudio", "pack"], res);
    },
    onError: (e) => toast.error("No se pudo agregar", { description: (e as Error).message }),
  });

  const removeMut = useMutation({
    mutationFn: (id: number) => estudioAdminApi.removePackEquipo(id),
    onSuccess: (res) => {
      qc.setQueryData(["admin", "estudio", "pack"], res);
    },
    onError: (e) => toast.error("No se pudo quitar", { description: (e as Error).message }),
  });

  useEffect(() => {
    const q = search.trim();
    if (q.length < 2) {
      setResults([]);
      return;
    }
    let cancelado = false;
    setSearching(true);
    const t = setTimeout(() => {
      adminApi
        .listEquipos({ q, per_page: 15 })
        .then((r) => {
          if (!cancelado)
            setResults(r.items.map((e) => ({ id: e.id, nombre: e.nombre, marca: e.marca })));
        })
        .catch(() => {
          if (!cancelado) setResults([]);
        })
        .finally(() => {
          if (!cancelado) setSearching(false);
        });
    }, 250);
    return () => {
      cancelado = true;
      clearTimeout(t);
    };
  }, [search]);

  return (
    <Section title="Pack (equipos incluidos)">
      <p className="-mt-2 mb-3 text-sm text-muted-foreground">
        Elegí a mano qué equipos integran el pack. En cada franja se ofrecen solo los que estén
        disponibles — un equipo ocupado no se ofrece, pero no bloquea la reserva.
      </p>

      {/* Buscador */}
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar equipo para agregar…"
          className="pl-9"
        />
      </div>
      {search.trim().length >= 2 && (
        <div className="mt-2 max-h-60 space-y-1 overflow-y-auto rounded-lg border hairline p-1">
          {searching && <div className="px-2 py-1.5 text-sm text-muted-foreground">Buscando…</div>}
          {!searching && results.length === 0 && (
            <div className="px-2 py-1.5 text-sm text-muted-foreground">Sin resultados.</div>
          )}
          {results.map((e) => {
            const yaEsta = packIds.has(e.id);
            return (
              <button
                key={e.id}
                type="button"
                disabled={yaEsta || addMut.isPending}
                onClick={() => addMut.mutate(e.id)}
                className="flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted disabled:opacity-50"
              >
                <span>
                  {e.marca && <span className="text-muted-foreground">{e.marca} · </span>}
                  {e.nombre}
                </span>
                {yaEsta ? (
                  <span className="text-xs text-muted-foreground">Ya está</span>
                ) : (
                  <Plus className="h-4 w-4 shrink-0" />
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Lista actual */}
      <div className="mt-4 space-y-2">
        {isLoading ? (
          <ListSkeleton rows={3} />
        ) : pack.length === 0 ? (
          <EmptyState
            icon={<Package className="h-6 w-6" />}
            title="Sin equipos en el pack"
            sub="Buscá un equipo arriba para sumarlo al pack."
          />
        ) : (
          pack.map((p) => (
            <div
              key={p.id}
              className="flex items-center gap-3 rounded-lg border hairline px-3 py-2 text-sm"
            >
              <div className="relative aspect-square w-10 shrink-0 overflow-hidden rounded bg-muted/40">
                {p.foto_url ? (
                  <img
                    loading="lazy"
                    decoding="async"
                    src={p.foto_url}
                    alt={p.nombre}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="grid h-full w-full place-items-center">
                    <Package className="h-4 w-4 text-muted-foreground" />
                  </div>
                )}
              </div>
              <div className="min-w-0 flex-1">
                {p.marca && <div className="t-eyebrow">{p.marca}</div>}
                <div className="truncate text-ink">{p.nombre}</div>
              </div>
              <button
                type="button"
                disabled={removeMut.isPending}
                onClick={() => removeMut.mutate(p.id)}
                className="text-muted-foreground hover:text-destructive disabled:opacity-50"
                aria-label={`Quitar ${p.nombre}`}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))
        )}
      </div>
    </Section>
  );
}
