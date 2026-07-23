import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";

import type { TallerConcepto } from "@/lib/admin/api/types";
import { Button } from "@/design-system/ui/button";
import { ContenidoSection, FotoSection } from "./ConceptoTabs";
import { EdicionSubRow } from "./EdicionSubRow";
import { FaqSection } from "./FaqSection";
import { InstructoresSection } from "./InstructoresSection";
import { InteresadosSection } from "./InteresadosSection";
import { TrabajosSection } from "./TrabajosSection";

export function TallerConceptoRow({
  concepto,
  expanded,
  onToggle,
  onNuevaEdicion,
}: {
  concepto: TallerConcepto;
  expanded: boolean;
  onToggle: () => void;
  onNuevaEdicion: (c: TallerConcepto) => void;
}) {
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<
    "ediciones" | "taller" | "instructores" | "interesados" | "trabajos" | "faq"
  >("ediciones");

  const totalConfirmados = concepto.ediciones.reduce((s, e) => s + e.cupos_confirmados, 0);
  const activeEdiciones = concepto.ediciones.filter((e) => e.activo);

  function handleDeleteEdicion(edicionId: number) {
    qc.setQueryData(["admin", "talleres"], (prev: TallerConcepto[] | undefined) =>
      prev?.map((c) =>
        c.id === concepto.id
          ? { ...c, ediciones: c.ediciones.filter((e) => e.id !== edicionId) }
          : c,
      ),
    );
  }

  return (
    <div
      className={`rounded-xl border transition-colors ${
        expanded ? "border-ink/30 bg-ink/5" : "border-border/60"
      }`}
    >
      {/* Concept header */}
      <div
        className="flex items-center gap-3 px-4 py-3.5 cursor-pointer select-none"
        onClick={onToggle}
      >
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-ink text-sm truncate leading-tight">{concepto.nombre}</p>
          <p className="text-xs text-muted-foreground truncate mt-0.5">
            {concepto.instructor_nombre}
          </p>
        </div>

        <span className="hidden md:block shrink-0 text-2xs font-mono text-muted-foreground bg-muted/40 rounded-full px-2 py-0.5">
          {concepto.ediciones.length === 1 ? "1 edición" : `${concepto.ediciones.length} ediciones`}
          {activeEdiciones.length !== concepto.ediciones.length &&
            ` · ${activeEdiciones.length} activa${activeEdiciones.length !== 1 ? "s" : ""}`}
        </span>

        {totalConfirmados > 0 && (
          <span className="shrink-0 text-2xs font-mono text-muted-foreground bg-muted/40 rounded-full px-2 py-0.5 tabular-nums">
            {totalConfirmados} inscripto{totalConfirmados !== 1 ? "s" : ""}
          </span>
        )}

        <svg
          className={`h-4 w-4 text-muted-foreground/60 shrink-0 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {/* Detail */}
      {expanded && (
        <div className="border-t border-border/40">
          <div className="flex border-b border-border/60 overflow-x-auto">
            {(
              [
                { id: "ediciones", label: "Ediciones" },
                { id: "taller", label: "El taller" },
                { id: "instructores", label: "Instructores" },
                { id: "interesados", label: "Interesados" },
                { id: "trabajos", label: "Trabajos" },
                { id: "faq", label: "FAQ" },
              ] as {
                id: "ediciones" | "taller" | "instructores" | "interesados" | "trabajos" | "faq";
                label: string;
              }[]
            ).map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`shrink-0 px-4 py-2.5 text-sm border-b-2 -mb-[1px] transition-colors ${
                  activeTab === tab.id
                    ? "border-ink text-ink font-medium"
                    : "border-transparent text-muted-foreground hover:text-ink"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="px-4 pb-6 pt-5">
            {activeTab === "ediciones" && (
              <div className="flex flex-col gap-3">
                {concepto.ediciones.map((edicion) => (
                  <EdicionSubRow
                    key={edicion.id}
                    edicion={edicion}
                    concepto={concepto}
                    onDelete={handleDeleteEdicion}
                  />
                ))}
                {concepto.ediciones.length === 0 && (
                  <p className="text-sm text-muted-foreground italic">Sin ediciones.</p>
                )}
                <div className="flex justify-end pt-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onNuevaEdicion(concepto)}
                    className="gap-1.5"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Nueva edición
                  </Button>
                </div>
              </div>
            )}

            {activeTab === "taller" && (
              <div className="flex flex-col gap-0">
                <FotoSection concepto={concepto} />
                <div className="border-t border-border/40 mt-6 pt-6">
                  <ContenidoSection concepto={concepto} />
                </div>
              </div>
            )}

            {activeTab === "instructores" && <InstructoresSection concepto={concepto} />}
            {activeTab === "interesados" && <InteresadosSection concepto={concepto} />}
            {activeTab === "trabajos" && <TrabajosSection concepto={concepto} />}
            {activeTab === "faq" && <FaqSection concepto={concepto} />}
          </div>
        </div>
      )}
    </div>
  );
}
