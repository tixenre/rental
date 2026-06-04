// src/components/admin/PedidosBackoffice.tsx
// Back-office de Pedidos (alquileres) — Rambla Rental
//
// HANDOFF: este archivo es un scaffold de partida.
// La referencia visual canónica está en `Pedidos Back-Office.html` del mismo paquete
// (sources en `proto/`). Todos los `TODO:` requieren implementación real con los
// datos / hooks / mutations del repo.
//
// Stack: React 19 + TanStack Router/Query + Tailwind v4 + lucide-react + shadcn/Radix
//
// Estructura de la feature (espeja el prototipo):
//   PedidosBackoffice            ← shell: sidebar + topbar + ruteo interno list⇄editor
//   ├── ListView                 ← split master/detail, tabs, smart-chips, búsqueda  (proto/list.jsx)
//   ├── EditorView               ← superficie de trabajo 2 col: cliente/fechas/equipos + rail  (proto/editor.jsx)
//   ├── PagoModal                ← registrar seña / saldo  (proto/app.jsx)
//   └── CommsModal               ← plantillas de WhatsApp / Email + adjuntar PDFs  (proto/comms.jsx)

"use client"

import { useState, useEffect, useMemo } from "react"
import {
  LayoutGrid, Calendar, Box, Users, Camera, Settings, LogOut, Menu,
  ChevronLeft, ChevronRight, ChevronDown, Check, Plus, Minus, Trash2,
  Search, Mail, MessageCircle, Coins, FileText, Pencil, Bell, X,
  PanelLeft, Truck, RotateCcw, AlertTriangle, Lock, ArrowRight,
} from "lucide-react"

// TODO: reemplazar con los componentes / hooks reales del repo
// import { EstadoBadge } from "@/components/kit/EstadoBadge"        // ← ÚNICA fuente de chips de estado
// import { StepperPill } from "@/components/rental/StepperPill"     // ← ÚNICO stepper de la app
// import { PriceBlock } from "@/components/kit/PriceBlock"
// import { StatCard, EmptyState, SearchInput, FieldLabel } from "@/components/kit"
// import { Button } from "@/components/ui/button"
// import { TopBar } from "@/components/rental/TopBar"
// import { formatARS, formatRentalRange, jornadaLabel } from "@/lib/formatters"
// import { usePedidos, useUpdatePedido, useRegistrarPago, useResolverSolicitud } from "@/hooks/pedidos"

// ─── Tipos (solo campos que existen en el modelo de alquileres del repo) ─────

export type Estado =
  | "borrador" | "presupuesto" | "confirmado"
  | "retirado" | "devuelto" | "finalizado" | "cancelado"

interface Cliente {
  nombre: string
  email: string
  telefono: string
  perfil: "consumidor_final" | "responsable_inscripto"
  tipo?: string                       // etiqueta libre (freelance, productora…) — display only
}

interface Item {
  equipo_id: number
  nombre: string
  marca: string
  precio_jornada: number
  cantidad: number
  kit?: boolean
  componentes?: string[]              // TODO: en el repo puede venir como contenido_incluido_json (string)
}

interface Pago { monto: number; concepto: string; fecha: string }

interface Solicitud {                 // cambio pedido por el cliente desde el portal
  tipo: "fechas" | "items" | "otro"
  mensaje: string
  was: string
  now: string
}

interface Pedido {
  id: number
  numero_pedido: number | null        // null = registro manual / borrador sin número
  estado: Estado
  cliente: Cliente
  fecha_desde: Date | null
  fecha_hasta: Date | null
  descuento_pct: number
  items: Item[]
  pagos: Pago[]
  notas: string
  solicitud?: Solicitud | null
  // flags derivadas (calculadas en cliente o que ya provee el backend)
  retiraHoy?: boolean
  devuelveHoy?: boolean
  tiene_solicitud_pendiente?: boolean
  createdAgo?: string
  isNew?: boolean
}

// ─── Máquina de estados (ESPEJA backend: ESTADOS_VALIDOS + reglas) ───────────
// Mantener sincronizado con el backend. El back-office NO debe permitir
// transiciones que el backend rechazaría. Ver proto/ui.jsx.

const ESTADO_LABEL: Record<Estado, string> = {
  borrador: "Borrador", presupuesto: "Presupuesto", confirmado: "Confirmado",
  retirado: "Retirado", devuelto: "Devuelto", finalizado: "Finalizado", cancelado: "Cancelado",
}

// Flujo lineal feliz (el chip de progreso del editor)
export const FLOW: Estado[] = ["presupuesto", "confirmado", "retirado", "devuelto", "finalizado"]

// Transiciones permitidas por estado de origen
const TRANSICIONES: Record<Estado, Estado[]> = {
  borrador:    ["presupuesto", "cancelado"],
  presupuesto: ["confirmado", "cancelado"],
  confirmado:  ["retirado", "cancelado"],
  retirado:    ["devuelto", "cancelado"],
  devuelto:    ["finalizado"],
  finalizado:  [],
  cancelado:   [],
}

export function transiciones(o: Pedido): Estado[] {
  return TRANSICIONES[o.estado] ?? []
}

// Motivo por el que un estado destino está bloqueado (validación de fechas / items).
// Devuelve null si la transición es válida. Espeja la validación del backend.
export function blockReason(o: Pedido, target: Estado): string | null {
  const needsDates: Estado[] = ["confirmado", "retirado", "devuelto", "finalizado"]
  if (needsDates.includes(target)) {
    if (!o.fecha_desde || !o.fecha_hasta) return "faltan fechas"
    if (!o.items?.length) return "sin equipos"
  }
  return null
}

// Acción "siguiente paso" sugerida en la UI (botón ámbar primario)
export function nextStep(o: Pedido) {
  const t = transiciones(o).filter(x => x !== "cancelado")
  if (!t.length) return null
  const target = t[0]
  const labels: Partial<Record<Estado, string>> = {
    presupuesto: "Confirmar pedido", confirmado: "Marcar retirado",
    retirado: "Registrar devolución", devuelto: "Cobrar saldo y finalizar",
  }
  return { target, label: labels[o.estado] ?? "Avanzar", blocked: blockReason(o, target) }
}

// ─── Helpers de precio / cobranza (el backend es la fuente de verdad real) ───
// En producción el desglose lo calcula `services.precios`. Acá se replica solo
// para preview en la UI; al integrar, usar los montos persistidos del pedido.

export function pagado(o: Pedido): number {
  return (o.pagos ?? []).reduce((s, p) => s + p.monto, 0)
}

export function jornadas(a: Date | null, b: Date | null): number {
  if (!a || !b) return 1
  return Math.max(1, Math.ceil((+b - +a) / 86_400_000))
}

export function breakdown(o: Pedido) {
  const J = jornadas(o.fecha_desde, o.fecha_hasta)
  const bruto = o.items.reduce((s, it) => s + it.precio_jornada * it.cantidad, 0) * J
  const desc = Math.round(bruto * (o.descuento_pct || 0) / 100)
  const neto = bruto - desc
  const conIva = o.cliente.perfil === "responsable_inscripto"   // RI → IVA 21%
  const iva = conIva ? Math.round(neto * 0.21) : 0
  return { J, bruto, desc, neto, conIva, iva, total: neto + iva }
}

// TODO: importar desde @/lib/formatters
function formatARS(n: number | null): string {
  if (n == null) return "consultar"
  return "$ " + Math.round(n).toLocaleString("es-AR").replace(/,/g, ".")
}

// ─── Datos: hooks reales a implementar ───────────────────────────────────────
// | Hook / endpoint            | Qué trae / hace                         |
// |----------------------------|-----------------------------------------|
// | usePedidos(filtros)        | GET lista de alquileres (+ flags)       |
// | useUpdatePedido(id)        | PATCH estado / cliente / items / notas  |
// | useRegistrarPago(id)       | POST pago (seña / saldo)                |
// | useResolverSolicitud(id)   | aprobar / contraproponer / rechazar     |
// | useCatalogo()              | catálogo para "agregar equipo"          |
// | useEnviarComms(id)         | WhatsApp link / email + adjuntar PDFs   |
//
// El prototipo usa `RAMBLA.orders` (mock en proto/data.js) — reemplazar por
// `usePedidos()`. Las mutaciones del prototipo viven en proto/app.jsx (upd,
// setEstado, patch, addItem, removeItem, setQty, savePago, resolveSolicitud).

// ─── Shell ───────────────────────────────────────────────────────────────────

export function PedidosBackoffice() {
  // TODO: const { data: orders = [] } = usePedidos()
  const [orders] = useState<Pedido[]>([])       // ← usePedidos()
  const [view, setView] = useState<"list" | "editor">("list")
  const [selectedId, setSelectedId] = useState<number | null>(orders[0]?.id ?? null)
  const [drawer, setDrawer] = useState(false)

  // Modales
  const [pagoFor, setPagoFor] = useState<number | null>(null)
  const [comms, setComms] = useState<{ channel: "wa" | "mail"; id: number } | null>(null)

  // Acciones — TODO: cablear a las mutations reales y mostrar toasts
  const setEstado = (id: number, estado: Estado) => {
    const o = orders.find(x => x.id === id)
    if (!o) return
    const reason = blockReason(o, estado)
    if (reason) {/* toast: No se puede pasar a … : reason */ return }
    // TODO: useUpdatePedido(id).mutate({ estado })
    // Reglas de auto-avance del prototipo:
    //  - confirmado sin número → asignar numero_pedido
    //  - devuelto && saldo == 0 → auto-finalizar
  }
  const openEditor = (id: number) => { setSelectedId(id); setView("editor"); setDrawer(false) }

  const sel = orders.find(o => o.id === selectedId) ?? null
  const pendientes = orders.filter(o => o.tiene_solicitud_pendiente).length
  const activos = orders.filter(o => o.estado !== "finalizado" && o.estado !== "cancelado").length

  return (
    <div className="flex min-h-[100dvh] bg-[var(--background)] text-[var(--ink)]">
      {/* ── Sidebar (drawer en mobile) ──
          Logo wordmark + nav (Pedidos activo) + footer de usuario.
          Ver proto/app.jsx → <aside className="sidebar">.
          TODO: usar el layout admin existente del repo si ya hay uno. */}
      <aside className="hidden md:flex w-[232px] shrink-0 flex-col border-r border-[var(--hairline)] bg-[var(--surface)]">
        {/* logo · nav (Pedidos·{activos}, Calendario, Equipo, Clientes, Estudio, Config) · avatar */}
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        {/* ── Topbar ──
            list:   breadcrumb "admin / pedidos" + campana (badge si pendientes>0) + avatar
            editor: ‹ volver + breadcrumb #NNNN + nombre + EstadoBadge + "Guardado" + Mail/WhatsApp
            Ver proto/app.jsx → <div className="topbar">. */}
        <header className="h-[58px] shrink-0 flex items-center gap-3 px-4 border-b border-[var(--hairline)] bg-[var(--surface-elevated)]">
          <button className="md:hidden" onClick={() => setDrawer(true)} aria-label="Menú"><Menu size={18} /></button>
          {/* … */}
        </header>

        {/* ── Contenido: lista ⇄ editor ── */}
        <main className="flex-1 min-h-0">
          {view === "list"
            ? (
              <ListView
                orders={orders}
                selectedId={selectedId}
                onSelect={setSelectedId}
                onOpen={openEditor}
                onSetEstado={setEstado}
                onPago={setPagoFor}
                onWhatsApp={o => setComms({ channel: "wa", id: o.id })}
                onEmail={o => setComms({ channel: "mail", id: o.id })}
              />
            ) : (
              <EditorView
                o={sel}
                onBack={() => setView("list")}
                onSetEstado={setEstado}
                onPago={setPagoFor}
                onWhatsApp={o => setComms({ channel: "wa", id: o.id })}
                onEmail={o => setComms({ channel: "mail", id: o.id })}
              />
            )}
        </main>
      </div>

      {/* ── Overlays ── */}
      {pagoFor != null && (
        <PagoModal o={orders.find(o => o.id === pagoFor)!} onClose={() => setPagoFor(null)} />
      )}
      {comms && (
        <CommsModal channel={comms.channel} order={orders.find(o => o.id === comms.id)!} onClose={() => setComms(null)} />
      )}
    </div>
  )
}

// ─── ListView ────────────────────────────────────────────────────────────────
// Split master/detail. Header con tabs (Todos · Cobranzas · Solicitudes),
// smart-chips (Retiran hoy / Devuelven hoy / Presupuestos nuevos / Con saldo),
// búsqueda y chips de estado. Desktop: lista 340px + PreviewPane. Mobile: cards.
// Referencia completa de layout/clases: Pedidos Back-Office.html + proto/list.jsx.

interface ListViewProps {
  orders: Pedido[]
  selectedId: number | null
  onSelect: (id: number) => void
  onOpen: (id: number) => void
  onSetEstado: (id: number, e: Estado) => void
  onPago: (id: number) => void
  onWhatsApp: (o: Pedido) => void
  onEmail: (o: Pedido) => void
}

function ListView(props: ListViewProps) {
  const { orders } = props
  const [tab, setTab] = useState<"todos" | "cobranzas" | "solicitudes">("todos")
  const [smart, setSmart] = useState<string | null>(null)
  const [estadoF, setEstadoF] = useState("activos")
  const [q, setQ] = useState("")

  // Conteos para chips / tabs
  const counts = useMemo(() => ({
    retiraHoy: orders.filter(o => o.retiraHoy).length,
    devuelveHoy: orders.filter(o => o.devuelveHoy).length,
    nuevos: orders.filter(o => o.isNew).length,
    saldo: orders.filter(o => ["confirmado", "retirado", "devuelto", "finalizado"].includes(o.estado) && pagado(o) < breakdown(o).neto).length,
    solicitudes: orders.filter(o => o.tiene_solicitud_pendiente).length,
    activos: orders.filter(o => o.estado !== "finalizado" && o.estado !== "cancelado").length,
  }), [orders])

  // Filtro combinado: tab → smart-chip → estado → búsqueda. Ver proto/list.jsx.
  const filtered = useMemo(() => {
    // … (mismo pipeline que el prototipo)
    return orders
  }, [orders, tab, smart, estadoF, q])

  // TODO: render — usar EstadoBadge del kit para los chips de estado.
  return <div /* … */ />
}

// ─── EditorView ──────────────────────────────────────────────────────────────
// 2 columnas: <ed-main> (banner de solicitud, Cliente, Fechas, Equipos, Notas)
// + <ed-rail> (EstadoDropdown + FlowStrip + Desglose + Cobranza + Documentos).
// Mobile: barra inferior sticky con total + acciones. Ver proto/editor.jsx.

interface EditorViewProps {
  o: Pedido | null
  onBack: () => void
  onSetEstado: (id: number, e: Estado) => void
  onPago: (id: number) => void
  onWhatsApp: (o: Pedido) => void
  onEmail: (o: Pedido) => void
}

function EditorView(props: EditorViewProps) {
  if (!props.o) return null
  // El dropdown de estado usa transiciones() + blockReason() para deshabilitar
  // opciones inválidas y mostrar el motivo. Stepper de cantidades = <StepperPill>.
  // TODO: render. Ver proto/editor.jsx para el detalle de cada sección y el rail.
  return <div /* … */ />
}

// ─── PagoModal ───────────────────────────────────────────────────────────────
// Registrar seña / saldo. Presets (Seña 50% / Saldo total / Otro) + barra de
// progreso de cobranza. Si cubre el saldo y el pedido está "devuelto" → finaliza.
function PagoModal({ o, onClose }: { o: Pedido; onClose: () => void }) {
  // TODO: useRegistrarPago(o.id). Ver proto/app.jsx → PagoModal.
  return <div /* … */ />
}

// ─── CommsModal ──────────────────────────────────────────────────────────────
// Selector de plantilla (sugerida según estado) para WhatsApp / Email, con
// adjuntos PDF (Remito / Contrato / Packing / Presupuesto) en email.
// Plantillas y lógica de sugerencia: proto/comms.jsx.
function CommsModal({ channel, order, onClose }: { channel: "wa" | "mail"; order: Pedido; onClose: () => void }) {
  // TODO: useEnviarComms(order.id). WhatsApp = abrir wa.me link; Email = enviar server-side.
  return <div /* … */ />
}
