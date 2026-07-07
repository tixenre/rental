import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { PhotoGallery, type GalleryFoto } from "@/components/common/PhotoGallery";
import { uploadStudioFile } from "@/lib/studio/photos";
import { estudioAdminApi, type EstudioConfig, type FotoOrdenItem } from "@/lib/admin/api";
import { Section } from "./shared";

export function GaleriaSection({
  fotos,
  onChanged,
}: {
  fotos: Array<{ id: number; url: string; orden: number; es_principal: boolean }>;
  onChanged: () => void;
}) {
  const qc = useQueryClient();
  const [uploading, setUploading] = useState(false);

  async function handleUpload(files: FileList) {
    setUploading(true);
    try {
      const uploads = Array.from(files).map((f) => uploadStudioFile(f));
      await Promise.all(uploads);
      toast.success(files.length === 1 ? "Foto subida" : `${files.length} fotos subidas`);
      onChanged();
    } catch (e) {
      toast.error("Error subiendo foto", { description: (e as Error).message });
    } finally {
      setUploading(false);
    }
  }

  const deleteMut = useMutation({
    mutationFn: (id: number) => estudioAdminApi.deleteFoto(id),
    onSuccess: () => {
      toast.success("Foto eliminada");
      onChanged();
    },
    onError: (e) => toast.error("Error eliminando", { description: (e as Error).message }),
  });

  const reorderMut = useMutation({
    mutationFn: (items: FotoOrdenItem[]) => estudioAdminApi.reorderFotos(items),
    onSuccess: (data) => {
      qc.setQueryData(["admin", "estudio"], (old: EstudioConfig | undefined) =>
        old ? { ...old, fotos: data.fotos } : old,
      );
    },
    onError: (e) => toast.error("Error reordenando", { description: (e as Error).message }),
  });

  function handleReorder(reordered: GalleryFoto[]) {
    reorderMut.mutate(
      reordered.map((f) => ({ id: f.id, orden: f.orden, es_principal: f.es_principal })),
    );
  }

  function handleSetPrincipal(id: number) {
    const updated = fotos.map((f) => ({ id: f.id, orden: f.orden, es_principal: f.id === id }));
    reorderMut.mutate(updated);
  }

  return (
    <Section title="Galería de fotos">
      <p className="text-xs text-muted-foreground mb-4">
        La primera foto marcada como principal aparece en el hero de la página pública.
      </p>
      <PhotoGallery
        fotos={fotos}
        onUpload={handleUpload}
        onDelete={(id) => deleteMut.mutate(id)}
        onReorder={handleReorder}
        onSetPrincipal={handleSetPrincipal}
        uploading={uploading}
        disabled={deleteMut.isPending || reorderMut.isPending}
      />
    </Section>
  );
}
