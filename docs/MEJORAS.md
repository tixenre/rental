# Mejoras — roadmap de funcionalidades (DEPRECATED)

> **DEPRECATED — archivado**. El backlog activo ahora vive en [GitHub Issues](https://github.com/tixenre/rental/issues)
> (label `feature`). Ver [`MANIFIESTO.md`](../MANIFIESTO.md) para el workflow.
>
> Este archivo queda como referencia histórica con marca de qué se hizo en
> las sesiones 2026-05-10 y 2026-05-12. Items todavía `[ ]` son ideas que
> podrían ir a issues cuando haya decisión.
>
> Ideas de mejora ordenadas por **impacto / esfuerzo**. No son bugs (eso está en `BUGS.md`), son features o pulidas que suman.

---

## QUICK WINS — alto impacto, bajo esfuerzo (un par de horas)

- [ ] **Skeleton loaders en el catálogo público** `[mobile]` — hoy mientras carga `useEquipos` no hay nada. Un grid de cards grises con `animate-pulse` mejora la percepción de velocidad, especialmente en conexiones lentas (mobile).

- [ ] **Persistir filtros en la URL del admin** — `q` y `etiqueta` en `routes/admin/equipos.tsx` viven solo en estado React. Si recargás, se pierden. Mover a search params (TanStack Router lo soporta nativo).

- [ ] **Confirmación al cerrar el form con cambios sin guardar** — hoy si tocás "Cancelar" en `EquipoFormDialog` con datos importados, perdés todo en silencio. Detectar `form.formState.isDirty` y pedir confirmación.

- [ ] **Atajo de teclado para abrir "Nuevo equipo"** — `n` en la página de equipos. Para flujos rápidos al cargar muchos.

- [x] **Botón "duplicar equipo"** — _Hecho en PR #213 (2026-05-12). Clona equipo + ficha + categorías + kit; copia con serie vacía y `ficha_completa = false`._

- [x] **Toggle bulk de visibilidad** — _Hecho en PR #220 (2026-05-12) — generalizado a bulk actions (visible/incompleta/eliminar) con checkboxes + barra flotante._

- [ ] **Storage diag visible en Settings** — el endpoint `/api/admin/storage/diag` ya existe; ponerle UI en `/admin/settings` con un botón "test R2" que muestre OK/error.

---

## MEDIO — más esfuerzo, vale la pena

- [ ] **Histórico de fotos por equipo** — hoy reemplazás la foto y la anterior queda en R2 huérfana. Mantener un array `fotos: string[]` y permitir elegir cuál es la principal. Ventaja: si la nueva foto sale fea, podés volver a la anterior con un click.

- [ ] **Versiones de la ficha técnica** — cada vez que enriquecemos un equipo se sobrescribe la ficha. Si el dato nuevo es peor, no hay vuelta atrás. Guardar versiones en `equipo_ficha_historial` con `created_at` y `fuente`.

- [ ] **Crear desde URL sin abrir el form** — botón en `/admin/equipos` que abre un modal mini con un input de URL, hace `enriquecer`, crea el equipo en un solo paso, y abre el form para editar. Acelera mucho el data entry.

- [ ] **Merge de "buscar fotos" en el form de edición** — hoy en el form ya hay un botón "Buscar fotos" pero no hay preview grande. Mostrar la foto seleccionada en grande con un botón "X otras opciones" colapsable, en vez del row de thumbs.

- [x] **Búsqueda full-text en el catálogo público** — _Hecho en PR #214 (2026-05-12) — extiende `q` a serie + descripción + specs_json + keywords_json. ILIKE crudo (no `tsvector`), aceptable para inventario chico-mediano. Aplica a admin y catálogo público._

- [ ] **Auto-sugerencia de categoría desde el enriquecimiento** — Firecrawl ya devuelve `categoria_sugerida` pero no se usa. Mostrarla como hint en el form ("¿Asignar a 'Cámaras'?") con un click.

- [ ] **Disponibilidad real en backend** — hoy el `disponible` que muestra el card se calcula en el frontend a partir de los pedidos. Mover el cálculo al backend (`GET /api/equipos?desde=X&hasta=Y` devuelve `disponible` por equipo) — más fiable y permite cachear.

- [ ] **Carrito persistente** `[mobile]` — `cart-store.ts` usa Zustand sin persistencia. Si el cliente refresca (o vuelve al browser en el celu), pierde todo. Agregar `persist` middleware a localStorage.

---

## GRANDES — features con peso, planificar antes

- [ ] **Multi-tenant / múltiples empresas** — hoy todo asume "Rambla". Si querés vender la app a otra rental, tenés que duplicar la base. Agregar `tenant_id` a las tablas y un middleware que lo filtre por subdominio.

- [ ] **Notificaciones por email** — al cliente cuando confirmás un pedido, al admin cuando entra una solicitud nueva. Postmark o Resend, plantillas en MJML.

- [ ] **Calendar view de pedidos** — ver el mes con todos los alquileres como bloques en un calendario. Útil para ver disponibilidad de un vistazo.

- [ ] **Stripe / Mercado Pago para pagos** — hoy los pagos son por fuera. Cobrar señas online te ahorra el ida y vuelta de "te paso CBU".

- [ ] **App pública del cliente** — hoy `/cliente` es básico. Agregar: ver pedidos pasados, descargar facturas, subir DNI desde el celu, firmar contrato digital.

- [x] **Reportes / dashboard** — _Hecho en PRs #222 (dashboard de uso: top alquilados, sin uso, revenue por categoría) y #227 (cuentas por cobrar). ROI real por equipo todavía pendiente — issue separado para llevarlo a estadísticas._

- [x] **Sistema de mantenimiento** — _Hecho en PR #216 (2026-05-12). Tabla `equipo_mantenimiento` + CRUD + modal desde la lista con badge rojo si la próxima revisión está vencida._

---

## POLISH — detalles que hacen sentir profesional

- [ ] **Loading states consistentes** `[mobile]` — usar el mismo `<Skeleton />` en todas las páginas en vez de "Cargando…" con texto. En mobile los spinners de texto son particularmente feos.

- [ ] **Empty states con dibujito + CTA** — hoy "Sin equipos" es un texto gris. Una ilustración + "Crear el primero" suma mucho.

- [ ] **Dark mode** — el design system ya parece pensado para esto (`bg-ink`, `bg-background`, etc.). Falta el toggle.

- [ ] **Microinteracciones en el carrito** `[mobile]` — cuando agregás un equipo desde el card, animar el "+1" volando hacia el ícono del carrito (Framer Motion). El feedback táctil es especialmente importante en mobile.

- [ ] **Compartir equipo (link directo)** — botón "compartir" en el card del catálogo que copia un URL con anchor a ese equipo.

- [ ] **Mejor manejo de imágenes rotas** — hoy con `onError` se baja la opacidad. Reemplazar con un placeholder real (categoría + nombre) cuando falla.

- [ ] **Sticky header en el catálogo** `[mobile]` — el filtro y carrito siempre visibles cuando scrolleás. El `MobileStickyBar` ya es sticky; esto aplica a asegurar que se mantenga visible en todos los casos.

---

## TÉCNICO / DX — para vos como dev, no se ve pero ayuda

- [x] **Tests unitarios mínimos del backend** — _Parcial: existen tests SSRF, auth, pricing, validaciones de pedido. Tests E2E del form admin agregados en PR #224 (2026-05-12). Falta cobertura específica de `enriquecer/autocompletar` y `aplicar-autocompletado` — issue separado._

- [x] **CI con typecheck + lint** — _Hecho. CI corre Python tests, Python syntax check, TypeScript typecheck, Build frontend y mobile-smoke en cada PR (`.github/workflows/`)._

- [x] **Migrations versionadas** — _Hecho. Alembic configurado en `backend/migrations/`. Cambios incrementales en `versions/`. Schema base sigue en `init_db()` con `CREATE IF NOT EXISTS`._

- [ ] **`uv` para Python** — más rápido que pip, lockfile reproducible. Tu `requirements.txt` ya está, solo agregar `uv.lock`.

- [ ] **Logger estructurado** — hoy `print()` y excepciones sueltas. Pasar a `logging` con JSON output → más fácil de leer en Railway.

- [ ] **Pre-commit hook** — bloquear commits si tipo o lint falla. `husky` + `lint-staged`.

---

## ¿Por dónde empezarías?

Si tuviera que sugerir un orden:

1. **Quick wins** primero (skeletons, filtros en URL, confirmación al cerrar) — un día y mejora muchísimo el feel.
2. **Crear desde URL en un click** — alinea con tu objetivo de "no tener que buscar las specs yo mismo".
3. **Histórico de fotos** — barato y te salva de reemplazar la foto y arrepentirte.
4. **Disponibilidad en backend + carrito persistente** — fundamento para todo lo que venga después (notificaciones, pagos, etc.).
5. Después de eso, lo grande (pagos, multi-tenant, etc.) según lo que necesites.
