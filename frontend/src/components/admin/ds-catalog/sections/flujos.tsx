/**
 * Sección Módulos con flujo — los módulos compuestos con estado e interacción
 * real (no átomos: el carrito, el selector de fechas, etc.). Patrón shell+container:
 * la pieza presentacional es la fuente de verdad; el TopBar/app le pasan el store,
 * la vitrina le pasa estado MOCK local → se prueba clickeable, sin tocar el carrito
 * real. Se construye por fases: 1) DatePill · 2) modal de fechas · 3-4) carrito.
 */
import { useState } from "react";

import { type CatalogSection } from "../types";
import { Caption, Stack } from "../catalog-kit";
import { DatePill } from "@/components/rental/DatePill";

// Demo funcional del DatePill: estado mock local, cero contacto con el carrito real.
function DatePillDemo() {
  const [range, setRange] = useState<{ start?: Date; end?: Date }>({});
  const hasDates = !!(range.start && range.end);

  const pick = () => {
    const start = new Date();
    const end = new Date();
    end.setDate(end.getDate() + 3);
    setRange({ start, end });
  };

  return (
    <Stack className="gap-3">
      {/* Sobre una barra de área (amber) para que se lea como en el topbar real. */}
      <div className="flex justify-center rounded-lg bg-amber p-4">
        <DatePill
          startDate={range.start}
          endDate={range.end}
          startTime="09:00"
          endTime="09:00"
          jornadas={4}
          onClick={hasDates ? () => setRange({}) : pick}
        />
      </div>
      <Caption>
        {hasDates
          ? 'clic → limpia (simula "cambiar fechas")'
          : "clic → elige un rango mock · en la app abre el selector real"}
      </Caption>
    </Stack>
  );
}

export const flujosSection: CatalogSection = {
  id: "flujos",
  title: "Módulos con flujo",
  hint: "Los módulos compuestos con estado e interacción. Acá los probás con data mock; la app usa la MISMA pieza desde el store del carrito — una sola fuente de verdad del diseño. (En construcción por fases.)",
  specimens: [
    {
      name: "DatePill",
      files: ["components/rental/DatePill.tsx"],
      blurb:
        "El pill central de fechas del rental. Shell presentacional: el TopBar le pasa el store; acá, estado mock. Cliqueá para alternar vacío ↔ con fechas.",
      render: () => <DatePillDemo />,
    },
  ],
};
