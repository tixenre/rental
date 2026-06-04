// src/routes/admin/pedidos.tsx
// TanStack Router — Back-office: lista + editor de Pedidos (alquileres)
//
// NOTAS DE HANDOFF:
// - Este archivo es un scaffold. Ajustá los imports a los paths reales del repo.
// - La referencia visual canónica está en `Pedidos Back-Office.html` (raíz del handoff).
// - Los `TODO:` marcados necesitan implementación real (queries + mutations).
// - Confirmá el path real de la ruta: el back-office vive en `/admin/*`. Si el
//   entity en el repo se llama `alquileres`, esta ruta puede ser `/admin/alquileres`.

import { createFileRoute } from "@tanstack/react-router"
import { PedidosBackoffice } from "@/components/admin/PedidosBackoffice"

// TODO: pre-fetch de la lista de pedidos en el loader
// import { pedidosQueryOptions } from "@/lib/queries/pedidos"

export const Route = createFileRoute("/admin/pedidos")({
  // TODO: loader para pre-fetch de la lista
  // loader: ({ context: { queryClient } }) =>
  //   queryClient.ensureQueryData(pedidosQueryOptions()),

  // TODO: guard de auth admin (el resto de /admin/* ya lo tiene)
  // beforeLoad: requireAdmin,

  component: PedidosBackoffice,
})
