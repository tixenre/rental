import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { Textarea } from "@/design-system/ui/textarea";

import { adminApi } from "@/lib/admin/api";
import { FAQ_GROUPS, parseFaq, type FaqGroup } from "@/data/faq";

export function FaqSection() {
  const qc = useQueryClient();
  const [groups, setGroups] = useState<FaqGroup[] | null>(null);

  const settingQ = useQuery({
    queryKey: ["settings", "faq_json"],
    queryFn: () => adminApi.getSetting("faq_json"),
    retry: false,
    staleTime: 0,
  });

  // Arranca del setting guardado, o de las FAQ por defecto (hardcodeadas).
  useEffect(() => {
    if (groups !== null || !settingQ.isFetched) return;
    const parsed = parseFaq(settingQ.data?.value);
    // Clonamos para no mutar el default importado.
    setGroups(
      parsed ?? FAQ_GROUPS.map((g) => ({ title: g.title, items: g.items.map((i) => ({ ...i })) })),
    );
  }, [settingQ.data, settingQ.isFetched, groups]);

  const updateMut = useMutation({
    mutationFn: (v: string) => adminApi.updateSetting("faq_json", v),
    onSuccess: () => {
      toast.success("Preguntas frecuentes actualizadas");
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const setGroup = (gi: number, patch: Partial<FaqGroup>) =>
    setGroups((prev) => prev && prev.map((g, i) => (i === gi ? { ...g, ...patch } : g)));
  const setItem = (gi: number, ii: number, patch: Partial<{ q: string; a: string }>) =>
    setGroups(
      (prev) =>
        prev &&
        prev.map((g, i) =>
          i === gi
            ? { ...g, items: g.items.map((it, j) => (j === ii ? { ...it, ...patch } : it)) }
            : g,
        ),
    );
  const addItem = (gi: number) =>
    setGroups(
      (prev) =>
        prev &&
        prev.map((g, i) => (i === gi ? { ...g, items: [...g.items, { q: "", a: "" }] } : g)),
    );
  const removeItem = (gi: number, ii: number) =>
    setGroups(
      (prev) =>
        prev &&
        prev.map((g, i) => (i === gi ? { ...g, items: g.items.filter((_, j) => j !== ii) } : g)),
    );
  const addGroup = () =>
    setGroups((prev) => [...(prev ?? []), { title: "Nueva sección", items: [] }]);
  const removeGroup = (gi: number) => setGroups((prev) => prev && prev.filter((_, i) => i !== gi));

  const save = () => {
    if (!groups) return;
    const clean = groups
      .map((g) => ({
        title: g.title.trim(),
        items: g.items
          .map((it) => ({ q: it.q.trim(), a: it.a.trim() }))
          .filter((it) => it.q && it.a),
      }))
      .filter((g) => g.title && g.items.length > 0);
    updateMut.mutate(JSON.stringify(clean));
  };

  return (
    <section className="card p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink">Preguntas frecuentes</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Las que ve el cliente en <code className="text-ink">/preguntas-frecuentes</code>.
          Organizadas en secciones. Las preguntas o secciones vacías se descartan al guardar.
        </p>
      </div>

      <div className="border-t hairline pt-3 space-y-4">
        {groups?.map((g, gi) => (
          <div key={gi} className="rounded-md border hairline p-3 space-y-2">
            <div className="flex items-center gap-2">
              <Input
                value={g.title}
                onChange={(e) => setGroup(gi, { title: e.target.value })}
                placeholder="Título de la sección (ej. Reservas)"
                className="font-medium"
              />
              <Button
                type="button"
                size="icon"
                variant="ghost"
                onClick={() => removeGroup(gi)}
                title="Eliminar sección"
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </div>

            {g.items.map((it, ii) => (
              <div key={ii} className="flex items-start gap-2 pl-3 border-l-2 border-muted">
                <div className="flex-1 space-y-1">
                  <Input
                    value={it.q}
                    onChange={(e) => setItem(gi, ii, { q: e.target.value })}
                    placeholder="Pregunta"
                    className="text-sm"
                  />
                  <Textarea
                    value={it.a}
                    onChange={(e) => setItem(gi, ii, { a: e.target.value })}
                    placeholder="Respuesta"
                    rows={2}
                    className="text-sm"
                  />
                </div>
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  onClick={() => removeItem(gi, ii)}
                  title="Eliminar pregunta"
                >
                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                </Button>
              </div>
            ))}

            <Button type="button" size="sm" variant="outline" onClick={() => addItem(gi)}>
              <Plus className="h-3.5 w-3.5 mr-1" /> Pregunta
            </Button>
          </div>
        ))}

        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" onClick={addGroup}>
            <Plus className="h-4 w-4 mr-1" /> Sección
          </Button>
          <Button onClick={save} disabled={!groups || updateMut.isPending}>
            {updateMut.isPending ? "Guardando…" : "Guardar FAQ"}
          </Button>
        </div>
      </div>
    </section>
  );
}
