/**
 * TerminosModal — Términos y Condiciones en un modal, sin salir del checkout.
 *
 * El link de T&C del resumen abría /terminos en otra pestaña — cortaba el
 * flujo. Reusa el mismo contenido de la página pública (`data/legal.ts`,
 * fuente única), solo cambia la presentación: mismo criterio que
 * `FacturacionModal`.
 */
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/design-system/ui/dialog";
import { LAST_UPDATED, TERMS_SECTIONS } from "@/data/legal";

export function TerminosModal({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-full sm:max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Términos y condiciones</DialogTitle>
          <DialogDescription>Última actualización: {LAST_UPDATED}</DialogDescription>
        </DialogHeader>
        <article className="space-y-5 text-sm leading-relaxed text-foreground/90">
          {TERMS_SECTIONS.map((s) => (
            <section key={s.id} id={s.id}>
              <h2 className="font-display text-base text-ink mb-1.5">{s.title}</h2>
              <p className="whitespace-pre-line">{s.content}</p>
            </section>
          ))}
        </article>
      </DialogContent>
    </Dialog>
  );
}
