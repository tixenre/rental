import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Spinner } from "@/design-system/ui/spinner";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/design-system/ui/alert-dialog";

import { adminApi } from "@/lib/admin/api";

export function CalendarFeedSection() {
  const qc = useQueryClient();
  const [confirmReset, setConfirmReset] = useState(false);

  const feedQ = useQuery({
    queryKey: ["calendar-feed"],
    queryFn: () => adminApi.getCalendarFeed(),
    staleTime: 0,
    retry: false,
  });

  const regenMut = useMutation({
    mutationFn: () => adminApi.regenerateCalendarFeed(),
    onSuccess: (data) => {
      qc.setQueryData(["calendar-feed"], data);
      toast.success("Generamos una URL nueva. La anterior dejó de funcionar.");
    },
    onError: (e: Error) => toast.error(e.message),
    onSettled: () => setConfirmReset(false),
  });

  const url = feedQ.data?.url ?? "";
  // webcal:// abre directo el diálogo de suscripción del calendario (un clic),
  // sin copiar-pegar. Mismo enlace, solo cambia el esquema.
  const webcalUrl = url.replace(/^https?:\/\//, "webcal://");

  const copiar = async () => {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      toast.success("URL copiada");
    } catch {
      toast.error("No se pudo copiar — copiala a mano");
    }
  };

  return (
    <section className="card p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink">Calendario de reservas</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Suscribí esta URL en tu calendario para ver las reservas <strong>confirmadas</strong> como
          eventos (los alquileres ocupan el día completo; las reservas del Estudio van con su
          horario). Se actualiza solo cada algunas horas y es <strong>solo lectura</strong>: editás
          las reservas en Rambla, el calendario las refleja.
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          En Google Calendar: <em>Otros calendarios → Suscribirse con URL</em> → pegá el enlace.
          También funciona en Apple Calendar y Outlook.
        </p>
      </div>

      <div className="border-t hairline pt-3 space-y-2">
        <div className="text-2xs uppercase tracking-wide text-muted-foreground">URL del feed</div>
        {feedQ.isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner size="sm" /> Cargando…
          </div>
        ) : feedQ.isError ? (
          <p className="text-sm text-destructive">
            No se pudo cargar la URL del feed. Reintentá recargando la página.
          </p>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <Input
              readOnly
              value={url}
              onFocus={(e) => e.currentTarget.select()}
              className="w-full sm:w-[28rem] font-mono text-xs"
            />
            <Button size="sm" onClick={copiar} disabled={!url}>
              Copiar
            </Button>
            <Button size="sm" variant="outline" asChild>
              <a href={webcalUrl}>Suscribir</a>
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setConfirmReset(true)}
              disabled={regenMut.isPending}
            >
              Regenerar
            </Button>
          </div>
        )}
        <p className="text-xs text-muted-foreground">
          <strong>Suscribir</strong> abre tu app de calendario directo; o copiá la URL y pegala a
          mano (Google Calendar: <em>Otros calendarios → Suscribirse con URL</em>).
        </p>
        <p className="text-xs text-muted-foreground">
          La URL es secreta: cualquiera que la tenga puede ver tus reservas. Si se filtró,
          regenerala (se corta el acceso anterior y hay que volver a suscribir el calendario).
        </p>
      </div>

      <AlertDialog open={confirmReset} onOpenChange={setConfirmReset}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Regenerar la URL del feed?</AlertDialogTitle>
            <AlertDialogDescription>
              La URL actual dejará de funcionar al instante. Los calendarios ya suscritos con la URL
              vieja van a dejar de actualizarse hasta que los vuelvas a suscribir con la nueva.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={regenMut.isPending}>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                regenMut.mutate();
              }}
              disabled={regenMut.isPending}
            >
              {regenMut.isPending ? "Regenerando…" : "Regenerar"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
