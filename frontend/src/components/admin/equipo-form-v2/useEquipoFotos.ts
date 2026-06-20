/**
 * useEquipoFotos — concern de la galería multi-foto del form de equipos (edit mode).
 *
 * Extraído verbatim de `EquipoFormDialogV2.tsx` (split de god-module, Frente E del
 * skill `mantenimiento`). Encapsula query + mutaciones + handlers de la galería,
 * decoupled del estado del form (react-hook-form). Cero cambio de comportamiento.
 */
import { useState } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getEquipoFotos,
  uploadEquipoFoto,
  deleteEquipoFoto,
  reorderEquipoFotos,
  type EquipoFoto,
  type EquipoFotoOrdenItem,
} from "@/lib/equipment/equipoFotos";
import { type GalleryFoto } from "@/components/common/PhotoGallery";
import type { Equipo } from "@/lib/admin/api";

export function useEquipoFotos(initial: Equipo | null | undefined, open: boolean) {
  const qc = useQueryClient();
  const [galleryUploading, setGalleryUploading] = useState(false);

  const fotosQ = useQuery({
    queryKey: ["admin", "equipo-fotos", initial?.id],
    queryFn: () => getEquipoFotos(initial!.id),
    enabled: !!initial?.id && open,
  });
  const fotos: GalleryFoto[] = (fotosQ.data ?? []).map((f: EquipoFoto) => ({
    id: f.id,
    url: f.url,
    orden: f.orden,
    es_principal: f.es_principal,
  }));

  const deleteFotoMut = useMutation({
    mutationFn: (fotoId: number) => deleteEquipoFoto(initial!.id, fotoId),
    onSuccess: () => {
      toast.success("Foto eliminada");
      void qc.invalidateQueries({ queryKey: ["admin", "equipo-fotos", initial?.id] });
      void qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
    },
    onError: (e) => toast.error("Error eliminando foto", { description: (e as Error).message }),
  });

  const reorderFotoMut = useMutation({
    mutationFn: (items: EquipoFotoOrdenItem[]) => reorderEquipoFotos(initial!.id, items),
    onSuccess: (data) => {
      qc.setQueryData(["admin", "equipo-fotos", initial?.id], data.fotos);
    },
    onError: (e) => toast.error("Error reordenando fotos", { description: (e as Error).message }),
  });

  async function handleGalleryUpload(files: FileList) {
    if (!initial?.id) return;
    setGalleryUploading(true);
    try {
      await Promise.all(Array.from(files).map((f) => uploadEquipoFoto(initial.id, f)));
      toast.success(files.length === 1 ? "Foto subida" : `${files.length} fotos subidas`);
      await qc.invalidateQueries({ queryKey: ["admin", "equipo-fotos", initial.id] });
      void qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
    } catch (e) {
      toast.error("Error subiendo foto", { description: (e as Error).message });
    } finally {
      setGalleryUploading(false);
    }
  }

  function handleGalleryReorder(reordered: GalleryFoto[]) {
    reorderFotoMut.mutate(
      reordered.map((f) => ({ id: f.id, orden: f.orden, es_principal: f.es_principal })),
    );
  }

  function handleGallerySetPrincipal(id: number) {
    const updated = fotos.map((f) => ({ id: f.id, orden: f.orden, es_principal: f.id === id }));
    reorderFotoMut.mutate(updated);
  }

  return {
    fotos,
    galleryUploading,
    handleGalleryUpload,
    handleGalleryReorder,
    handleGallerySetPrincipal,
    onDelete: (id: number) => deleteFotoMut.mutate(id),
    mutating: deleteFotoMut.isPending || reorderFotoMut.isPending,
  };
}
