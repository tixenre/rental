import { createLazyFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  GitMerge, Loader2, ArrowRight, ShieldCheck, CheckCircle2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

import { adminApi } from "@/lib/admin/api";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/specs/dedup")({
  component: DedupPage,
});

function DedupPage() {
  useDocumentTitle("Dedup de specs · Back Office");
  const qc = useQueryClient();
  const candidatosQ = useQuery({
    queryKey: ["admin", "specs-dedup"],
    queryFn: () => adminApi.listDedupCandidatos(),
    staleTime: 30_000,
  });

  const mergeMut = useMutation({
    mutationFn: (input: { keep_id: number; drop_id: number }) =>
      adminApi.mergeSpecs(input),
    onSuccess: () => {
      toast.success("Merge aplicado");
      qc.invalidateQueries({ queryKey: ["admin", "specs-dedup"] });
      qc.invalidateQueries({ queryKey: ["admin", "spec-definitions"] });
      qc.invalidateQueries({ queryKey: ["admin", "spec-templates"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const items = candidatosQ.data?.items ?? [];

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-5xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office › Specs
        </div>
        <h1 className="font-display text-3xl text-ink flex items-center gap-2">
          <GitMerge className="h-6 w-6 text-amber" />
          Dedup de specs
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          Detecta pares de specs con label similar (distancia Levenshtein
          ≤ 2) y mismo tipo. Sugerí cuál mantener basado en uso + validado.
          El merge migra todas las asignaciones y valores cargados, y
          unifica enum_options si aplica. Operación destructiva — restore
          desde backup si necesitás revertir.
        </p>
      </header>

      {candidatosQ.isLoading && (
        <div className="rounded-md border hairline px-4 py-6 text-center text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin mx-auto mb-1" />
          Analizando catálogo…
        </div>
      )}

      {!candidatosQ.isLoading && items.length === 0 && (
        <div className="rounded-md border hairline border-dashed p-6 text-center text-sm text-muted-foreground">
          <CheckCircle2 className="h-5 w-5 text-emerald-700 mx-auto mb-2" />
          Sin candidatos. El catálogo ya no tiene specs con labels similares
          de mismo tipo.
        </div>
      )}

      {items.length > 0 && (
        <div className="space-y-2">
          {items.map((c) => (
            <DedupCard
              key={`${c.keep.id}-${c.drop.id}`}
              candidato={c}
              onMerge={() => mergeMut.mutate({ keep_id: c.keep.id, drop_id: c.drop.id })}
              onMergeInverso={() => mergeMut.mutate({ keep_id: c.drop.id, drop_id: c.keep.id })}
              busy={mergeMut.isPending}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function DedupCard({
  candidato, onMerge, onMergeInverso, busy,
}: {
  candidato: NonNullable<Awaited<ReturnType<typeof adminApi.listDedupCandidatos>>>["items"][number];
  onMerge: () => void;
  onMergeInverso: () => void;
  busy: boolean;
}) {
  const { keep, drop, label_distance } = candidato;
  return (
    <div className="rounded-md border hairline overflow-hidden">
      <header className="bg-muted/30 px-3 py-2 border-b hairline flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[10px]">{keep.tipo}</Badge>
          <span className="text-muted-foreground">
            distancia: {label_distance}
            {label_distance === 0 && " (mismo label)"}
          </span>
        </div>
      </header>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 p-3 text-sm">
        <SpecInfo info={keep} role="keep" />
        <ArrowRight className="h-5 w-5 text-muted-foreground shrink-0" />
        <SpecInfo info={drop} role="drop" />
      </div>
      <footer className="border-t hairline bg-muted/10 px-3 py-2 flex flex-wrap items-center gap-2">
        <div className="text-[11px] text-muted-foreground flex-1 min-w-[200px]">
          Sugerencia: <strong>mantener "{keep.label}"</strong>
          {keep.validado && " (validada)"}
          {keep.uso_eq > drop.uso_eq && ` · más usada (${keep.uso_eq} vs ${drop.uso_eq} equipos)`}
        </div>
        <Button
          size="sm" variant="outline"
          onClick={onMergeInverso}
          disabled={busy}
          className="h-7 px-2 text-[11px]"
        >
          Invertir (mantener "{drop.label}")
        </Button>
        <Button
          size="sm"
          onClick={onMerge}
          disabled={busy}
          className="h-7 px-2"
        >
          {busy
            ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
            : <GitMerge className="h-3 w-3 mr-1" />}
          Mergear
        </Button>
      </footer>
    </div>
  );
}

function SpecInfo({
  info, role,
}: {
  info: {
    id: number; spec_key: string; label: string; tipo: string;
    unidad: string | null; validado: boolean;
    uso_cat: number; uso_eq: number;
  };
  role: "keep" | "drop";
}) {
  return (
    <div className="min-w-0 space-y-0.5">
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className={"font-medium truncate " + (role === "keep" ? "text-emerald-700" : "text-amber-700")}>
          {info.label}
        </span>
        {info.validado && <ShieldCheck className="h-3 w-3 text-emerald-700 shrink-0" />}
      </div>
      <code className="font-mono text-[10px] text-muted-foreground block truncate">
        {info.spec_key}
        {info.unidad && ` · ${info.unidad}`}
      </code>
      <div className="text-[10px] text-muted-foreground flex gap-2">
        <span>{info.uso_cat} cat</span>
        <span>·</span>
        <span>{info.uso_eq} eq</span>
      </div>
    </div>
  );
}
