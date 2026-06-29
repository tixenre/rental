/**
 * Sección Contenedores & Datos — superficies que envuelven y muestran datos.
 * Card (panel con header/footer), Table (el arquetipo dominante del back-office),
 * Alert (avisos inline) y Progress (barra determinada).
 */
import { type CatalogSection } from "../types";
import { Caption, Stack } from "../catalog-kit";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/design-system/ui/card";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  TableCaption,
  TableFooter,
} from "@/design-system/ui/table";
import { Alert, AlertTitle, AlertDescription } from "@/design-system/ui/alert";
import { Progress } from "@/design-system/ui/progress";
import { Button } from "@/design-system/ui/button";
import { Info, AlertTriangle } from "lucide-react";

const PEDIDOS = [
  { numero: "#1042", cliente: "Pablo Ferrari", estado: "Confirmado", monto: "$ 48.500" },
  { numero: "#1043", cliente: "María González", estado: "Presupuesto", monto: "$ 12.000" },
  { numero: "#1044", cliente: "Juan Pérez", estado: "Retirado", monto: "$ 31.200" },
];

export const containersSection: CatalogSection = {
  id: "contenedores",
  title: "Contenedores & Datos",
  hint: "Superficies que envuelven y muestran datos: panel, tabla, aviso y barra de progreso.",
  specimens: [
    {
      name: "Card",
      files: ["design-system/ui/card.tsx"],
      blurb: "Panel con header/contenido/footer. Para agrupar info en bloques con borde y sombra.",
      render: () => (
        <Card className="max-w-sm">
          <CardHeader>
            <CardTitle>Pedido #1042</CardTitle>
            <CardDescription>Confirmado · retira el 12/07</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              3 ítems · seña parcial cobrada. Falta el saldo antes del retiro.
            </p>
          </CardContent>
          <CardFooter className="gap-2">
            <Button variant="primary" size="sm">
              Ver pedido
            </Button>
            <Button variant="outline" size="sm">
              Cobrar saldo
            </Button>
          </CardFooter>
        </Card>
      ),
    },
    {
      name: "Table",
      files: ["design-system/ui/table.tsx"],
      blurb:
        "El arquetipo dominante del back-office: header + filas + caption + footer. Se scrollea sola en mobile.",
      render: () => (
        <Table>
          <TableCaption>Pedidos recientes</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>Nº</TableHead>
              <TableHead>Cliente</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead className="text-right">Monto</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {PEDIDOS.map((p) => (
              <TableRow key={p.numero}>
                <TableCell className="font-medium">{p.numero}</TableCell>
                <TableCell>{p.cliente}</TableCell>
                <TableCell>{p.estado}</TableCell>
                <TableCell className="text-right">{p.monto}</TableCell>
              </TableRow>
            ))}
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell colSpan={3}>Total</TableCell>
              <TableCell className="text-right">$ 91.700</TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      ),
    },
    {
      name: "Alert",
      files: ["design-system/ui/alert.tsx"],
      blurb: "Aviso inline con icono. variant default (neutro) y destructive (error/peligro).",
      render: () => (
        <Stack className="max-w-md">
          <Alert>
            <Info />
            <AlertTitle>Pedido en presupuesto</AlertTitle>
            <AlertDescription>
              Todavía no está confirmado. El stock se reserva recién al confirmar.
            </AlertDescription>
          </Alert>
          <Alert variant="destructive">
            <AlertTriangle />
            <AlertTitle>Saldo impago</AlertTitle>
            <AlertDescription>
              El cliente debe el saldo y el retiro es mañana. Cobrá antes de entregar.
            </AlertDescription>
          </Alert>
        </Stack>
      ),
    },
    {
      name: "Progress",
      files: ["design-system/ui/progress.tsx"],
      blurb: "Barra determinada por value 0–100. Para avances medibles (carga, cobrado vs. total).",
      render: () => (
        <Stack className="max-w-md">
          <div className="space-y-1.5">
            <Progress value={25} />
            <Caption>25%</Caption>
          </div>
          <div className="space-y-1.5">
            <Progress value={60} />
            <Caption>60%</Caption>
          </div>
          <div className="space-y-1.5">
            <Progress value={100} />
            <Caption>100%</Caption>
          </div>
        </Stack>
      ),
    },
  ],
};
