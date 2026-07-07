/**
 * Sección Módulos con flujo — los módulos compuestos con estado e interacción
 * real (no átomos: el carrito, el selector de fechas, etc.). Patrón shell+container:
 * la pieza presentacional es la fuente de verdad; el TopBar/app le pasan el store,
 * la vitrina le pasa estado MOCK local → se prueba clickeable, sin tocar el carrito
 * real. Cubre: fechas (pill + selector), carrito mini-bar, carrito drawer, guardar lista.
 */
import { useId, useRef, useState } from "react";
import { toast } from "sonner";

import { type CatalogSection } from "../types";
import { Caption, Row, Stack } from "../catalog-kit";
import { Button } from "@/design-system/ui/button";
import { DatePill } from "@/components/rental/dates/DatePill";
import { DateRangePickerModal } from "@/components/rental/dates/DateRangePickerModal";
import { CartMiniBarView, type CartPreviewItem } from "@/components/rental/cart/CartMiniBarView";
import { CartDrawerView } from "@/components/rental/cart/CartDrawerView";
import { GuardarComoListaView } from "@/components/rental/GuardarComoListaView";
import { type Equipment } from "@/data/equipment";
import { computeJornadas } from "@/lib/rental-dates";

// ── Fechas: pill + selector (flujo completo) ─────────────────────────────────────
// El DatePill abre el DateRangePickerModal REAL (el core controlado por props que
// la app cablea a useCart vía RentalDateModal). Acá lo manejamos con estado mock:
// elegís fechas en el selector y el pill se actualiza — flujo end-to-end, sin carrito.
function DateFlowDemo() {
  const [range, setRange] = useState<{ start?: Date; end?: Date }>({});
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("09:00");
  const [open, setOpen] = useState(false);
  const hasDates = !!(range.start && range.end);
  const jornadas = hasDates ? computeJornadas(range.start, range.end, startTime, endTime) : 0;

  return (
    <Stack className="gap-3">
      {/* Sobre una barra de área (amber) para que se lea como en el topbar real. */}
      <div className="flex justify-center rounded-lg bg-amber p-4">
        <DatePill
          startDate={range.start}
          endDate={range.end}
          startTime={startTime}
          endTime={endTime}
          jornadas={jornadas}
          onClick={() => setOpen(true)}
        />
      </div>
      <Caption>clic en el pill → abre el selector real · elegí fechas y mirá actualizarse</Caption>
      <DateRangePickerModal
        open={open}
        onOpenChange={setOpen}
        startDate={range.start}
        endDate={range.end}
        startTime={startTime}
        endTime={endTime}
        onDatesChange={(start, end) => setRange({ start, end })}
        onStartTimeChange={setStartTime}
        onEndTimeChange={setEndTime}
        options={{ respectHorarios: false, allowPast: true, itemsParam: "" }}
      />
    </Stack>
  );
}

// ── Carrito (mini-bar mobile) ────────────────────────────────────────────────────
// Equipos mock (solo los campos que usa la View). category/brand alimentan el
// placeholder de EmptyImage; sin fotoUrl no se hace fetch de imágenes reales.
const MOCK_EQUIPOS: Equipment[] = [
  {
    id: "1",
    slug: "sony-a7iii",
    name: "Alpha A7 III",
    brand: "Sony",
    category: "camaras",
    pricePerDay: 12000,
    description: "",
    specs: [],
  },
  {
    id: "2",
    slug: "canon-rf-2470",
    name: "RF 24-70 f/2.8",
    brand: "Canon",
    category: "opticas",
    pricePerDay: 8000,
    description: "",
    specs: [],
  },
  {
    id: "3",
    slug: "aputure-600d",
    name: "600d Pro",
    brand: "Aputure",
    category: "iluminacion",
    pricePerDay: 9000,
    description: "",
    specs: [],
  },
];

const DEMO_DAYS = 4;

function CartMiniBarDemo() {
  const [qtys, setQtys] = useState<Record<string, number>>({ "1": 1 });
  const [popKey, setPopKey] = useState(0);

  const previewItems: CartPreviewItem[] = MOCK_EQUIPOS.filter((e) => qtys[e.id]).map((e) => ({
    equipo: e,
    qty: qtys[e.id],
  }));
  const count = previewItems.reduce((a, i) => a + i.qty, 0);
  const isEmpty = count === 0;
  const totalNeto = previewItems.reduce((a, i) => a + i.equipo.pricePerDay * i.qty * DEMO_DAYS, 0);

  const add = (id: string) => {
    setQtys((q) => ({ ...q, [id]: (q[id] ?? 0) + 1 }));
    setPopKey((k) => k + 1);
  };
  const clear = () => setQtys({});

  return (
    <Stack className="gap-3">
      <Row>
        {MOCK_EQUIPOS.map((e) => (
          <Button key={e.id} size="sm" variant="outline" onClick={() => add(e.id)}>
            + {e.brand}
          </Button>
        ))}
        <Button size="sm" variant="ghost" onClick={clear} disabled={isEmpty}>
          Vaciar
        </Button>
      </Row>
      {/* `transform` crea el containing block → el mini-bar `fixed` se ancla a esta
          caja en vez del viewport. Así se muestra embebido sin tocar el componente. */}
      <div className="relative h-36 overflow-hidden card" style={{ transform: "translateZ(0)" }}>
        <CartMiniBarView
          count={count}
          days={DEMO_DAYS}
          isEmpty={isEmpty}
          previewItems={previewItems}
          totalNeto={totalNeto}
          conIva={false}
          hayFechas
          popKey={popKey}
          onOpen={() => toast("En la app abre el CartDrawer (acá abajo, en su propio specimen)")}
        />
      </div>
      <Caption>agregá ítems → la barra actualiza count, total y el bump del ícono</Caption>
    </Stack>
  );
}

// ── Carrito (drawer desktop / checkout) ──────────────────────────────────────────
function CartDrawerDemo() {
  const [qtys, setQtys] = useState<Record<string, number>>({ "1": 1, "2": 1 });
  const [open, setOpen] = useState(false);
  const [openKits, setOpenKits] = useState<Record<string, boolean>>({});
  const [notas, setNotas] = useState("");
  const [showNotas, setShowNotas] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();

  const list = MOCK_EQUIPOS.filter((e) => qtys[e.id]).map((e) => ({ it: e, qty: qtys[e.id] }));
  const subtotal = list.reduce((a, { it, qty }) => a + it.pricePerDay * qty * DEMO_DAYS, 0);

  const add = (id: string) => setQtys((q) => ({ ...q, [id]: (q[id] ?? 0) + 1 }));
  const remove = (id: string) =>
    setQtys((q) => {
      const n = (q[id] ?? 0) - 1;
      const next = { ...q };
      if (n <= 0) delete next[id];
      else next[id] = n;
      return next;
    });
  const setQty = (id: string, qty: number) =>
    setQtys((q) => {
      const next = { ...q };
      if (qty <= 0) delete next[id];
      else next[id] = qty;
      return next;
    });

  // Fechas mock (3 noches → 4 jornadas) para que el panel muestre un rango.
  const start = new Date();
  const end = new Date();
  end.setDate(end.getDate() + 3);

  return (
    <Stack className="gap-3">
      <Button variant="amber" shape="pill" onClick={() => setOpen(true)}>
        Abrir drawer (desktop)
      </Button>
      <Caption>
        abre el panel real · cambiá cantidades y mirá los totales · Confirmar/Compartir hacen toast
        (sin backend)
      </Caption>
      <CartDrawerView
        drawerOpen={open}
        isBottom={false}
        dialogRef={dialogRef}
        closeBtnRef={closeBtnRef}
        titleId={titleId}
        onClose={() => setOpen(false)}
        onExplore={() => setOpen(false)}
        step="carrito"
        pedidoEnviado={null}
        sessionId="ds-demo-session"
        onVolverAlCarrito={() => {}}
        onCrearPedido={async () => {}}
        startDate={start}
        endDate={end}
        startTime="09:00"
        endTime="09:00"
        d={DEMO_DAYS}
        hayFechas
        onOpenDateModal={() =>
          toast('El selector de fechas está en el specimen "Fechas" de arriba')
        }
        dateModalOpen={false}
        onDateModalChange={() => {}}
        list={list}
        getDisponible={undefined}
        openKits={openKits}
        onToggleKit={(id) => setOpenKits((p) => ({ ...p, [id]: !p[id] }))}
        onAdd={add}
        onRemove={remove}
        onSetQty={setQty}
        subtotalTotal={subtotal}
        descuentoPct={0}
        descuentoOrigen="ninguno"
        descuentoMonto={0}
        totalNeto={subtotal}
        conIva={false}
        notas={notas}
        showNotas={showNotas}
        onNotasChange={setNotas}
        onShowNotas={() => setShowNotas(true)}
        onSubmit={() => toast.success("Confirmar pedido (demo — en la app crea el pedido real)")}
        hayNoDisponible={false}
        nombresSinDisp={[]}
        dentroDeLeadTime={false}
        leadTimeHoras={0}
        urgenciaWhatsappUrl={null}
        needsLogin={false}
        onLogin={() => {}}
        onRegister={() => {}}
        clienteSession={null}
        onClear={() => setQtys({})}
      />
    </Stack>
  );
}

export const flujosSection: CatalogSection = {
  id: "flujos",
  title: "Módulos con flujo",
  hint: "Los módulos compuestos con estado e interacción. Acá los probás con data mock; la app usa la MISMA pieza desde el store del carrito — una sola fuente de verdad del diseño.",
  specimens: [
    {
      name: "Fechas (pill + selector)",
      files: ["components/rental/DatePill.tsx", "components/rental/DateRangePickerModal.tsx"],
      blurb:
        "El flujo de fechas del rental: el DatePill abre el DateRangePickerModal (el core controlado por props que la app cablea a useCart). Cliqueá el pill, elegí un rango y mirá el pill actualizarse.",
      render: () => <DateFlowDemo />,
    },
    {
      name: "CartMiniBar (mobile)",
      files: ["components/rental/CartMiniBarView.tsx"],
      blurb:
        "La barra del carrito mobile. View presentacional: la app le pasa store + cotización del backend; acá, ítems mock. Agregá equipos y mirá actualizarse.",
      render: () => <CartMiniBarDemo />,
    },
    {
      name: "CartDrawer (desktop · checkout)",
      files: ["components/rental/CartDrawerView.tsx"],
      blurb:
        "El panel completo del carrito: fechas, ítems con stepper, qué incluye, totales, notas y acciones. View presentacional; la app cablea store/cotización/creación de pedido. Acá: ítems mock, Confirmar/Compartir hacen toast.",
      render: () => <CartDrawerDemo />,
    },
    {
      name: "Guardar como lista",
      files: ["components/rental/GuardarComoListaView.tsx"],
      blurb:
        "El gesto botón ↔ input inline para guardar el carrito como lista. View presentacional (maneja el toggle/nombre); la app cablea el guardado al backend. Cliqueá, escribí un nombre y Enter (acá hace toast).",
      render: () => (
        <div className="max-w-sm">
          <GuardarComoListaView
            onSave={async (nombre) => {
              toast.success(`Guardamos “${nombre}” en tus listas (demo)`);
              return true;
            }}
          />
        </div>
      ),
    },
  ],
};
