/**
 * Sección Overlays & Modales — todo lo que se abre por encima del contenido.
 * Casi todo es Radix (maneja su propio estado): se muestra con su Trigger, un
 * <Button> que abre. ModalBackdrop es la excepción: backdrop fuente-única para
 * los overlays hechos a mano (los que NO usan Radix).
 */
import { useState } from "react";
import { MoreHorizontal } from "lucide-react";

import { type CatalogSection } from "../types";
import { Stack } from "../catalog-kit";
import { Button } from "@/design-system/ui/button";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/design-system/ui/dialog";
import {
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogAction,
  AlertDialogCancel,
} from "@/design-system/ui/alert-dialog";
import {
  Sheet,
  SheetTrigger,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/design-system/ui/sheet";
import {
  Drawer,
  DrawerTrigger,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
  DrawerFooter,
  DrawerClose,
} from "@/design-system/ui/drawer";
import { Popover, PopoverTrigger, PopoverContent } from "@/design-system/ui/popover";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from "@/design-system/ui/tooltip";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuItem,
  DropdownMenuCheckboxItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuSubContent,
} from "@/design-system/ui/dropdown-menu";
import { ModalBackdrop } from "@/design-system/ui/modal-backdrop";

/**
 * Demo del ModalBackdrop: necesita estado para abrir/cerrar, así que va como
 * componente nombrado (no se pueden usar hooks dentro de `render`). Clic en el
 * panel NO cierra (el evento no es directo sobre el overlay); clic en el fondo SÍ.
 */
function ModalBackdropDemo() {
  const [abierto, setAbierto] = useState(false);
  return (
    <>
      <Button variant="outline" onClick={() => setAbierto(true)}>
        Abrir overlay a mano
      </Button>
      {abierto && (
        <ModalBackdrop
          onClose={() => setAbierto(false)}
          className="z-50 grid place-items-center bg-black/80 p-4"
        >
          <div className="w-full max-w-sm space-y-3 rounded-lg border bg-background p-6 shadow-lg">
            <h3 className="text-lg font-semibold leading-none tracking-tight text-ink">
              Panel a mano
            </h3>
            <p className="text-sm text-muted-foreground">
              Clic acá adentro no cierra. Clic en el fondo oscuro, sí.
            </p>
            <div className="flex justify-end">
              <Button variant="outline" onClick={() => setAbierto(false)}>
                Cerrar
              </Button>
            </div>
          </div>
        </ModalBackdrop>
      )}
    </>
  );
}

export const overlaysSection: CatalogSection = {
  id: "overlays",
  title: "Overlays & Modales",
  hint: "Lo que se abre por encima. Radix maneja su estado — se muestra con su Trigger (un botón que abre).",
  specimens: [
    {
      name: "Dialog",
      files: ["design-system/ui/dialog.tsx"],
      blurb:
        "Modal centrado con header/footer. Trae su botón X — `hideClose` lo saca cuando el modal lleva su propio cierre.",
      render: () => (
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="outline">Abrir Dialog</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Confirmar reserva</DialogTitle>
              <DialogDescription>
                Revisá las fechas y el equipo antes de mandar la solicitud.
              </DialogDescription>
            </DialogHeader>
            <p className="text-sm text-muted-foreground">
              Acá va el contenido del modal: un formulario, un resumen, lo que haga falta.
            </p>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline">Cancelar</Button>
              </DialogClose>
              <DialogClose asChild>
                <Button variant="primary">Confirmar</Button>
              </DialogClose>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      ),
    },
    {
      name: "AlertDialog",
      files: ["design-system/ui/alert-dialog.tsx"],
      blurb:
        "Confirmación bloqueante para acciones destructivas: no se cierra al clickear afuera, exige Action o Cancel.",
      render: () => (
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="destructive">Eliminar pedido</Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>¿Eliminar este pedido?</AlertDialogTitle>
              <AlertDialogDescription>
                Esta acción no se puede deshacer. El pedido y sus líneas se borran para siempre.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancelar</AlertDialogCancel>
              <AlertDialogAction>Sí, eliminar</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      ),
    },
    {
      name: "Sheet",
      files: ["design-system/ui/sheet.tsx"],
      blurb:
        "Panel que entra desde un borde. 4 sides (`top` · `bottom` · `left` · `right`); default `right`. Para filtros, detalle lateral.",
      render: () => (
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="outline">Abrir Sheet (right)</Button>
          </SheetTrigger>
          <SheetContent side="right">
            <SheetHeader>
              <SheetTitle>Filtros</SheetTitle>
              <SheetDescription>
                Panel lateral. Cambiá `side` para que entre desde arriba, abajo o la izquierda.
              </SheetDescription>
            </SheetHeader>
          </SheetContent>
        </Sheet>
      ),
    },
    {
      name: "Drawer",
      files: ["design-system/ui/drawer.tsx"],
      blurb:
        "Panel que sube desde abajo (vaul), pensado para mobile. Trae su handle arrastrable arriba.",
      render: () => (
        <Drawer>
          <DrawerTrigger asChild>
            <Button variant="outline">Abrir Drawer</Button>
          </DrawerTrigger>
          <DrawerContent>
            <DrawerHeader>
              <DrawerTitle>Opciones del pedido</DrawerTitle>
              <DrawerDescription>
                Sube desde abajo y se arrastra con el handle. Ideal en pantallas chicas.
              </DrawerDescription>
            </DrawerHeader>
            <DrawerFooter>
              <DrawerClose asChild>
                <Button variant="outline">Cerrar</Button>
              </DrawerClose>
            </DrawerFooter>
          </DrawerContent>
        </Drawer>
      ),
    },
    {
      name: "Popover",
      files: ["design-system/ui/popover.tsx"],
      blurb:
        "Contenido flotante anclado al trigger, sin overlay bloqueante. Para ayuda contextual o mini-formularios.",
      render: () => (
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline">Abrir Popover</Button>
          </PopoverTrigger>
          <PopoverContent>
            <div className="space-y-1">
              <p className="text-sm font-medium text-ink">Anclado al botón</p>
              <p className="text-sm text-muted-foreground">
                Flota cerca del trigger y se cierra al clickear afuera. No bloquea el resto.
              </p>
            </div>
          </PopoverContent>
        </Popover>
      ),
    },
    {
      name: "Tooltip",
      files: ["design-system/ui/tooltip.tsx"],
      blurb:
        "Etiqueta breve al hover/focus. Necesita `TooltipProvider` envolviéndolo (uno por árbol alcanza).",
      render: () => (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="outline">Pasá el mouse</Button>
            </TooltipTrigger>
            <TooltipContent>Ayuda contextual breve</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      ),
    },
    {
      name: "DropdownMenu",
      files: ["design-system/ui/dropdown-menu.tsx"],
      blurb:
        "Menú de acciones anclado a un trigger: items, checkbox, radio-group, separador, label y submenú.",
      render: () => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="icon" aria-label="Acciones">
              <MoreHorizontal />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            <DropdownMenuLabel>Acciones</DropdownMenuLabel>
            <DropdownMenuItem>Editar</DropdownMenuItem>
            <DropdownMenuItem>Duplicar</DropdownMenuItem>
            <DropdownMenuSub>
              <DropdownMenuSubTrigger>Mover a…</DropdownMenuSubTrigger>
              <DropdownMenuSubContent>
                <DropdownMenuItem>Presupuestos</DropdownMenuItem>
                <DropdownMenuItem>Confirmados</DropdownMenuItem>
              </DropdownMenuSubContent>
            </DropdownMenuSub>
            <DropdownMenuSeparator />
            <DropdownMenuCheckboxItem defaultChecked>Mostrar archivados</DropdownMenuCheckboxItem>
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Ordenar por</DropdownMenuLabel>
            <DropdownMenuRadioGroup defaultValue="fecha">
              <DropdownMenuRadioItem value="fecha">Fecha</DropdownMenuRadioItem>
              <DropdownMenuRadioItem value="monto">Monto</DropdownMenuRadioItem>
            </DropdownMenuRadioGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-destructive">Eliminar</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
    {
      name: "ModalBackdrop",
      files: ["design-system/ui/modal-backdrop.tsx"],
      blurb:
        "Backdrop fuente-única para overlays hechos a mano (los que NO usan Radix). Cierra solo en pointer-down directo sobre el fondo, nunca al burbujear desde el panel (fix #761).",
      render: () => (
        <Stack>
          <ModalBackdropDemo />
        </Stack>
      ),
    },
  ],
};
