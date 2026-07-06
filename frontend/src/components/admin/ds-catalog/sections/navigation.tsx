/**
 * Sección Navegación & Estructura — cómo se ordena el contenido en pantalla.
 * Tabs/Accordion/Collapsible reparten contenido; Separator/ScrollArea lo enmarcan;
 * Sidebar es el bloque de navegación entero del back-office.
 */
import { type CatalogSection } from "../types";
import { Caption, Sample, Stack } from "../catalog-kit";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/design-system/ui/tabs";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/design-system/ui/accordion";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/design-system/ui/collapsible";
import { Separator } from "@/design-system/ui/separator";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarSeparator,
} from "@/design-system/ui/sidebar";
import { Button } from "@/design-system/ui/button";
import { Calendar, ChevronDown, FileText, Package, Settings, Users } from "lucide-react";

/** Lista larga para mostrar el scroll real del ScrollArea. */
const EQUIPOS = [
  "Sony FX6",
  "Canon C70",
  "Blackmagic 6K Pro",
  "DJI RS3 Pro",
  "Aputure 600d",
  "Aputure 300x",
  "Nanlite PavoTube",
  "Sennheiser MKH 416",
  "Rode NTG5",
  "Tascam DR-70D",
  "Manfrotto 504X",
  "Tripode Sachtler FSB 8",
  "SmallHD Indie 7",
  "Atomos Ninja V",
  "Tarjeta CFexpress 512GB",
];

export const navigationSection: CatalogSection = {
  id: "navegacion",
  title: "Navegación & Estructura",
  hint: "Cómo se reparte y enmarca el contenido — pestañas, paneles plegables, separadores y el menú del back-office.",
  specimens: [
    {
      name: "Tabs",
      files: ["design-system/ui/tabs.tsx"],
      blurb:
        "Pestañas para repartir contenido afín en un mismo espacio. Uncontrolled con defaultValue.",
      render: () => (
        <Tabs defaultValue="datos" className="w-full max-w-md">
          <TabsList>
            <TabsTrigger value="datos">Datos</TabsTrigger>
            <TabsTrigger value="pagos">Pagos</TabsTrigger>
            <TabsTrigger value="historial">Historial</TabsTrigger>
          </TabsList>
          <TabsContent value="datos" className="text-sm text-muted-foreground">
            Nombre, contacto y perfil fiscal del cliente.
          </TabsContent>
          <TabsContent value="pagos" className="text-sm text-muted-foreground">
            Señas, saldos y movimientos de cobranza.
          </TabsContent>
          <TabsContent value="historial" className="text-sm text-muted-foreground">
            Pedidos anteriores y su estado.
          </TabsContent>
        </Tabs>
      ),
    },
    {
      name: "Accordion",
      files: ["design-system/ui/accordion.tsx"],
      blurb:
        "Paneles plegables single-collapsible (uno abierto a la vez, o todos cerrados). Acá el primero arranca abierto.",
      render: () => (
        <Accordion type="single" collapsible defaultValue="que-incluye" className="w-full max-w-md">
          <AccordionItem value="que-incluye">
            <AccordionTrigger>¿Qué incluye el kit?</AccordionTrigger>
            <AccordionContent className="text-muted-foreground">
              Cámara, óptica, batería y cargador. El detalle sale de la receta real del producto.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="entrega">
            <AccordionTrigger>¿Cómo es la entrega?</AccordionTrigger>
            <AccordionContent className="text-muted-foreground">
              Retiro en el local o envío coordinado. Se acuerda al confirmar el pedido.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="sena">
            <AccordionTrigger>¿Necesito seña?</AccordionTrigger>
            <AccordionContent className="text-muted-foreground">
              Sí: la reserva se confirma con una seña parcial del total.
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      ),
    },
    {
      name: "Collapsible",
      files: ["design-system/ui/collapsible.tsx"],
      blurb:
        "Primitivo de mostrar/ocultar un bloque suelto. Uncontrolled: el trigger maneja su propio estado.",
      render: () => (
        <Collapsible className="w-full max-w-md space-y-2">
          <CollapsibleTrigger asChild>
            <Button variant="outline" size="sm" className="gap-2">
              Ver detalle técnico
              <ChevronDown className="h-4 w-4" />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="card p-3 text-sm text-muted-foreground">
            Sensor full-frame, grabación 4K60, montura E. Specs derivadas del catálogo.
          </CollapsibleContent>
        </Collapsible>
      ),
    },
    {
      name: "Separator",
      files: ["design-system/ui/separator.tsx"],
      blurb:
        "Línea divisoria de 1px. Orientación horizontal (default) o vertical para separar en línea.",
      render: () => (
        <Stack className="gap-4">
          <Sample label="horizontal">
            <div className="w-full max-w-xs space-y-3">
              <span className="text-sm text-ink">Subtotal</span>
              <Separator />
              <span className="text-sm text-ink">Total</span>
            </div>
          </Sample>
          <Sample label="vertical">
            <div className="flex h-6 items-center gap-3 text-sm text-muted-foreground">
              <span>Catálogo</span>
              <Separator orientation="vertical" />
              <span>Estudio</span>
              <Separator orientation="vertical" />
              <span>Workshops</span>
            </div>
          </Sample>
        </Stack>
      ),
    },
    {
      name: "ScrollArea",
      files: ["design-system/ui/scroll-area.tsx"],
      blurb:
        "Contenedor de alto fijo con scrollbar estilizada propia. Para listas largas que no deben empujar el layout.",
      render: () => (
        <ScrollArea className="h-48 w-full max-w-xs card">
          <div className="p-3">
            <Caption>Equipos disponibles</Caption>
            <ul className="mt-2 space-y-2">
              {EQUIPOS.map((eq) => (
                <li key={eq} className="text-sm text-ink">
                  {eq}
                </li>
              ))}
            </ul>
          </div>
        </ScrollArea>
      ),
    },
    {
      name: "Sidebar",
      files: ["design-system/ui/sidebar.tsx"],
      blurb:
        "Bloque de navegación entero del AdminLayout (~20 subcomponentes). Acá un menú real con un item activo, embebido en alto fijo.",
      render: () => (
        <SidebarProvider className="min-h-0">
          <div className="h-72 w-64 overflow-hidden rounded-lg border hairline">
            <Sidebar collapsible="none" className="h-full">
              <SidebarHeader className="px-3 py-3 text-sm font-medium text-ink">
                Rambla · Back-office
              </SidebarHeader>
              <SidebarSeparator />
              <SidebarContent>
                <SidebarGroup>
                  <SidebarGroupLabel>Operación</SidebarGroupLabel>
                  <SidebarMenu>
                    <SidebarMenuItem>
                      <SidebarMenuButton isActive>
                        <Package />
                        <span>Pedidos</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                    <SidebarMenuItem>
                      <SidebarMenuButton>
                        <Calendar />
                        <span>Calendario</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                    <SidebarMenuItem>
                      <SidebarMenuButton>
                        <Users />
                        <span>Clientes</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  </SidebarMenu>
                </SidebarGroup>
                <SidebarGroup>
                  <SidebarGroupLabel>Gestión</SidebarGroupLabel>
                  <SidebarMenu>
                    <SidebarMenuItem>
                      <SidebarMenuButton>
                        <FileText />
                        <span>Reportes</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                    <SidebarMenuItem>
                      <SidebarMenuButton>
                        <Settings />
                        <span>Ajustes</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  </SidebarMenu>
                </SidebarGroup>
              </SidebarContent>
            </Sidebar>
          </div>
        </SidebarProvider>
      ),
    },
  ],
};
