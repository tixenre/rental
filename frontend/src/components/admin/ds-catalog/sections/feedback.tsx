/**
 * Sección Notificaciones — toasts efímeros (Sonner).
 *
 * El <Toaster> ya está montado a nivel app (tematizado con tokens del DS), así
 * que el demo es solo disparar toast() desde "sonner": no se monta nada acá.
 */
import { toast } from "sonner";

import { type CatalogSection } from "../types";
import { Row } from "../catalog-kit";
import { Button } from "@/design-system/ui/button";

export const feedbackSection: CatalogSection = {
  id: "notificaciones",
  title: "Notificaciones",
  hint: "Toasts efímeros. El <Toaster> ya está montado a nivel app (tematizado con tokens del DS); se disparan con toast() desde 'sonner'.",
  specimens: [
    {
      name: "Toaster (Sonner)",
      files: ["design-system/ui/sonner.tsx"],
      blurb:
        "Feedback efímero no bloqueante: éxito, error, info y un toast con descripción + acción. El Toaster vive una vez a nivel app.",
      render: () => (
        <Row>
          <Button variant="secondary" onClick={() => toast.success("Pedido confirmado")}>
            success
          </Button>
          <Button variant="secondary" onClick={() => toast.error("No se pudo guardar")}>
            error
          </Button>
          <Button variant="secondary" onClick={() => toast("Reserva actualizada")}>
            default
          </Button>
          <Button
            variant="secondary"
            onClick={() =>
              toast("Equipo agregado al carrito", {
                description: "Sony FX3 · 2 unidades",
                action: {
                  label: "Deshacer",
                  onClick: () => toast("Deshecho"),
                },
              })
            }
          >
            con acción
          </Button>
        </Row>
      ),
    },
  ],
};
