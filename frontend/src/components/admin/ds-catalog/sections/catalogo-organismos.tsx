/**
 * Organismos del catálogo público — las piezas ENSAMBLADAS que ve el visitante
 * (el card del equipo, la fila de lista, el mosaico de categorías, el buscador,
 * el drawer del carrito, el selector de fechas). No son primitivos: combinan
 * varios del cluster equipment/shared + datos del dominio.
 *
 * Los overlays (buscador, carrito, fechas) se muestran con un botón que los
 * abre — es el patrón honesto para un componente fixed/portaled en la vitrina:
 * se ve el componente REAL, no una maqueta.
 */
import { useRef, useState } from "react";

import { Button } from "@/design-system/ui/button";
import { type CatalogSection } from "../types";
import { Caption, Row, Sample, Stack } from "../catalog-kit";

import { EquipmentCard } from "@/components/rental/EquipmentCard";
import { EquipmentRow } from "@/components/rental/EquipmentRow";
import { CategoryMosaic } from "@/components/rental/CategoryMosaic";
import { DiscoverySheet } from "@/components/rental/DiscoverySheet";
import { CartDrawerView } from "@/components/rental/CartDrawerView";
import { RentalDateModal } from "@/components/rental/RentalDateModal";

import { equipment, categories, brands } from "@/data/equipment";
import { equipoSimple, equipoKit, equipoCombo, noop } from "../fixtures";

// ── Demo del selector de fechas ───────────────────────────────────────────────
function RentalDateModalDemo() {
  const [open, setOpen] = useState(false);
  return (
    <Stack>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        Abrir selector de fechas
      </Button>
      <Caption>Cableado al carrito real (useCart) — elegir fechas las guarda en el store.</Caption>
      <RentalDateModal open={open} onOpenChange={setOpen} />
    </Stack>
  );
}

// ── Demo del buscador (DiscoverySheet, mobile) ────────────────────────────────
function DiscoverySheetDemo() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(new Set());
  const [selectedBrand, setSelectedBrand] = useState<string | null>(null);
  const brandObjs = brands.map((b, i) => ({ id: i, nombre: b }));
  return (
    <Stack>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        Abrir buscador (mobile)
      </Button>
      <Caption>Busca y filtra en una sola superficie fullscreen — datos del catálogo demo.</Caption>
      <DiscoverySheet
        open={open}
        onOpenChange={setOpen}
        defaultTab="search"
        query={query}
        setQuery={setQuery}
        allEquipos={equipment}
        categories={categories}
        brands={brandObjs}
        selectedCategories={selectedCategories}
        onToggleCategory={(c) =>
          setSelectedCategories((prev) => {
            const next = new Set(prev);
            if (next.has(c)) next.delete(c);
            else next.add(c);
            return next;
          })
        }
        selectedBrand={selectedBrand}
        onBrand={setSelectedBrand}
        onClear={() => {
          setSelectedCategories(new Set());
          setSelectedBrand(null);
          setQuery("");
        }}
        resultCount={equipment.length}
      />
    </Stack>
  );
}

// ── Demo del drawer del carrito (CartDrawerView, shell presentacional) ────────
function CartDrawerDemo() {
  const [open, setOpen] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const list = [
    { it: equipoKit, qty: 1 },
    { it: equipoCombo, qty: 1 },
  ];
  const jornadas = 3;
  const subtotalTotal = (equipoKit.pricePerDay + equipoCombo.pricePerDay) * jornadas;
  const descuentoPct = 10;
  const descuentoMonto = Math.round((subtotalTotal * descuentoPct) / 100);
  const totalNeto = subtotalTotal - descuentoMonto;
  return (
    <Stack>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        Abrir carrito
      </Button>
      <Caption>
        Shell presentacional del checkout — recibe todo por props (estado demo + callbacks no-op),
        sin tocar el carrito real.
      </Caption>
      <CartDrawerView
        drawerOpen={open}
        isBottom={false}
        dialogRef={dialogRef}
        closeBtnRef={closeBtnRef}
        titleId="ds-cart-demo-title"
        onClose={() => setOpen(false)}
        onExplore={noop}
        step="carrito"
        pedidoEnviado={null}
        sessionId="ds-demo-session"
        onVolverAlCarrito={noop}
        onCrearPedido={async () => {}}
        startDate={new Date("2026-07-10T10:00:00")}
        endDate={new Date("2026-07-12T18:00:00")}
        startTime="10:00"
        endTime="18:00"
        d={jornadas}
        hayFechas
        onOpenDateModal={noop}
        dateModalOpen={false}
        onDateModalChange={noop}
        list={list}
        getDisponible={() => 5}
        openKits={{}}
        onToggleKit={noop}
        onAdd={noop}
        onRemove={noop}
        onSetQty={noop}
        subtotalTotal={subtotalTotal}
        descuentoPct={descuentoPct}
        descuentoOrigen="jornadas"
        descuentoMonto={descuentoMonto}
        totalNeto={totalNeto}
        conIva={false}
        notas=""
        showNotas={false}
        onNotasChange={noop}
        onShowNotas={noop}
        onSubmit={noop}
        hayNoDisponible={false}
        nombresSinDisp={[]}
        dentroDeLeadTime={false}
        leadTimeHoras={0}
        urgenciaWhatsappUrl={null}
        needsLogin={false}
        onLogin={noop}
        onRegister={noop}
        clienteSession={{ nombre: "Estudio Demo" }}
        onClear={noop}
      />
    </Stack>
  );
}

export const catalogoOrganismosSection: CatalogSection = {
  id: "catalogo-organismos",
  title: "Catálogo público (organismos)",
  hint: "Las piezas ensambladas que ve el visitante. El card del equipo, la lista, el mosaico de categorías y el buscador/carrito — armados con datos demo de las tres formas (simple · kit · combo).",
  specimens: [
    {
      name: "EquipmentCard",
      files: ["components/rental/EquipmentCard.tsx"],
      blurb:
        "Card de grilla del catálogo: foto (o EmptyImage), nombre, precio, stepper y favorito. Las tres formas + un caso sin stock.",
      // La card está afinada para la grilla ANGOSTA del catálogo (foto aspect-square
      // + content-visibility con un intrinsic-size de 280px): en columnas anchas la
      // foto se dispara y las cards se pisan. Espejamos las proporciones reales
      // (grid-cols-2 → md:4, igual que categoria.$slug.tsx) y capamos el ancho para
      // que rinda a tamaño catálogo, no estiradas.
      render: () => (
        <div className="mx-auto grid max-w-5xl grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 md:grid-cols-4">
          <Sample label="kit — destacado">
            <EquipmentCard item={equipoKit} index={0} />
          </Sample>
          <Sample label="combo">
            <EquipmentCard item={equipoCombo} index={1} />
          </Sample>
          <Sample label="simple — sin foto (EmptyImage)">
            <EquipmentCard item={equipoSimple} index={2} />
          </Sample>
          <Sample label="sin stock — badge no disponible">
            <EquipmentCard item={equipoSimple} index={3} disponible={0} />
          </Sample>
        </div>
      ),
    },
    {
      name: "EquipmentRow",
      files: ["components/rental/EquipmentRow.tsx"],
      blurb:
        "Vista de lista (desktop + mobile): thumb, nombre, specs clave, precio alineado a la derecha, stepper. Click expande la mini-ficha.",
      render: () => (
        <div className="mx-auto max-w-2xl divide-y divide-hairline rounded-xl border hairline">
          <EquipmentRow item={equipoKit} index={0} />
          <EquipmentRow item={equipoCombo} index={1} />
          <EquipmentRow item={equipoSimple} index={2} disponible={0} />
        </div>
      ),
    },
    {
      name: "CategoryMosaic",
      files: ["components/rental/CategoryMosaic.tsx"],
      blurb:
        "Fila scrolleable de categorías con ilustración + conteo. Es el primer gesto de descubrimiento en la home del catálogo.",
      render: () => (
        <div className="-mx-4">
          <CategoryMosaic allEquipos={equipment} categories={categories} onSelect={noop} />
        </div>
      ),
    },
    {
      name: "DiscoverySheet",
      files: ["components/rental/DiscoverySheet.tsx"],
      blurb:
        "El buscador mobile: búsqueda + filtros (categoría / marca) en una sola superficie con tabs. Reemplazó a los dos sheets separados.",
      render: () => <DiscoverySheetDemo />,
    },
    {
      name: "CartDrawerView",
      files: ["components/rental/CartDrawerView.tsx"],
      blurb:
        "El drawer del carrito / checkout. Shell presentacional puro: la lógica vive en CartDrawer; este recibe estado por props (ideal para la vitrina).",
      render: () => <CartDrawerDemo />,
    },
    {
      name: "RentalDateModal",
      files: ["components/rental/RentalDateModal.tsx"],
      blurb:
        "El selector de fechas único del carrito (desktop + mobile). Wrapper fino sobre DateRangePickerModal cableado al useCart.",
      render: () => <RentalDateModalDemo />,
    },
  ],
};
