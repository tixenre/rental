# Mejoras — roadmap de funcionalidades

> Ideas de mejora ordenadas por **impacto / esfuerzo**. No son bugs (eso está en `BUGS.md`), son features o pulidas que suman.

---

## QUICK WINS — alto impacto, bajo esfuerzo (un par de horas)

- [ ] **Skeleton loaders en el catálogo público** — hoy mientras carga `useEquipos` no hay nada. Un grid de cards grises con `animate-pulse` mejora la percepción de velocidad.

- [ ] **Persistir filtros en la URL del admin** — `q` y `etiqueta` en `routes/admin/equipos.tsx` viven solo en estado React. Si recargás, se pierden. Mover a search params (TanStack Router lo soporta nativo).

- [ ] **Confirmación al cerrar el form con cambios sin guardar** — hoy si tocás "Cancelar" en `EquipoFormDialog` con datos importados, perdés todo en silencio. Detectar `form.formState.isDirty` y pedir confirmación.

- [ ] **Atajo de teclado para abrir "Nuevo equipo"** — `n` en la página de equipos. Para flujos rápidos al cargar muchos.

- [ ] **Botón "duplicar equipo"** — útil cuando tenés varios cuerpos del mismo modelo. Copia todo menos `serie` y `id`, deja editar antes de guardar.

- [ ] **Toggle bulk de visibilidad** — checkbox en cada fila + acción masiva "ocultar / mostrar seleccionados". Hoy hay que hacer click uno por uno.

- [ ] **Storage diag visible en Settings** — el endpoint `/api/admin/storage/diag` ya existe; ponerle UI en `/admin/settings` con un botón "test R2" que muestre OK/error.

---

## MEDIO — más esfuerzo, vale la pena

- [ ] **Histórico de fotos por equipo** — hoy reemplazás la foto y la anterior queda en R2 huérfana. Mantener un array `fotos: string[]` y permitir elegir cuál es la principal. Ventaja: si la nueva foto sale fea, podés volver a la anterior con un click.

- [ ] **Versiones de la ficha técnica** — cada vez que enriquecemos un equipo se sobrescribe la ficha. Si el dato nuevo es peor, no hay vuelta atrás. Guardar versiones en `equipo_ficha_historial` con `created_at` y `fuente`.

- [ ] **Crear desde URL sin abrir el form** — botón en `/admin/equipos` que abre un modal mini con un input de URL, hace `enriquecer`, crea el equipo en un solo paso, y abre el form para editar. Acelera mucho el data entry.

- [ ] **Merge de "buscar fotos" en el form de edición** — hoy en el form ya hay un botón "Buscar fotos" pero no hay preview grande. Mostrar la foto seleccionada en grande con un botón "X otras opciones" colapsable, en vez del row de thumbs.

- [ ] **Búsqueda full-text en el catálogo público** — hoy el filtro busca en `nombre`, `marca`, `modelo`. Extender a `descripcion`, `keywords`, `specs`. Postgres tiene `tsvector` nativo.

- [ ] **Auto-sugerencia de categoría desde el enriquecimiento** — Firecrawl ya devuelve `categoria_sugerida` pero no se usa. Mostrarla como hint en el form ("¿Asignar a 'Cámaras'?") con un click.

- [ ] **Disponibilidad real en backend** — hoy el `disponible` que muestra el card se calcula en el frontend a partir de los pedidos. Mover el cálculo al backend (`GET /api/equipos?desde=X&hasta=Y` devuelve `disponible` por equipo) — más fiable y permite cachear.

- [ ] **Carrito persistente** — `cart-store.ts` usa Zustand sin persistencia. Si el cliente refresca, pierde todo. Agregar `persist` middleware a localStorage.

---

## GRANDES — features con peso, planificar antes

- [ ] **Multi-tenant / múltiples empresas** — hoy todo asume "Rambla". Si querés vender la app a otra rental, tenés que duplicar la base. Agregar `tenant_id` a las tablas y un middleware que lo filtre por subdominio.

- [ ] **Notificaciones por email** — al cliente cuando confirmás un pedido, al admin cuando entra una solicitud nueva. Postmark o Resend, plantillas en MJML.

- [ ] **Calendar view de pedidos** — ver el mes con todos los alquileres como bloques en un calendario. Útil para ver disponibilidad de un vistazo.

- [ ] **Stripe / Mercado Pago para pagos** — hoy los pagos son por fuera. Cobrar señas online te ahorra el ida y vuelta de "te paso CBU".

- [ ] **App pública del cliente** — hoy `/cliente` es básico. Agregar: ver pedidos pasados, descargar facturas, subir DNI desde el celu, firmar contrato digital.

- [ ] **Reportes / dashboard** — `dashboard.py` ya tiene algunos KPIs. Expandir: equipos más alquilados, ROI por equipo, ingresos por mes, clientes top.

- [ ] **Sistema de mantenimiento** — cuando un equipo entra a "en_mantenimiento", registrar fecha, motivo, costo, técnico. Reporte de costos de mantenimiento por equipo.

---

## POLISH — detalles que hacen sentir profesional

- [ ] **Loading states consistentes** — usar el mismo `<Skeleton />` en todas las páginas en vez de "Cargando…" con texto.

- [ ] **Empty states con dibujito + CTA** — hoy "Sin equipos" es un texto gris. Una ilustración + "Crear el primero" suma mucho.

- [ ] **Dark mode** — el design system ya parece pensado para esto (`bg-ink`, `bg-background`, etc.). Falta el toggle.

- [ ] **Microinteracciones en el carrito** — cuando agregás un equipo desde el card, animar el "+1" volando hacia el ícono del carrito (Framer Motion).

- [ ] **Compartir equipo (link directo)** — botón "compartir" en el card del catálogo que copia un URL con anchor a ese equipo.

- [ ] **Mejor manejo de imágenes rotas** — hoy con `onError` se baja la opacidad. Reemplazar con un placeholder real (categoría + nombre) cuando falla.

- [ ] **Sticky header en el catálogo** — el filtro y carrito siempre visibles cuando scrolleás.

---

## TÉCNICO / DX — para vos como dev, no se ve pero ayuda

- [ ] **Tests unitarios mínimos del backend** — al menos `enriquecer`, `upload-foto-from-url`, `aplicar-enriquecimiento`. Hoy un cambio en `_scrape` puede romper sin avisar.

- [ ] **CI con typecheck + lint** — GitHub Actions que corra `tsc --noEmit` y `ruff` en cada PR. 5 min de setup, mucho ojo evitado.

- [ ] **Migrations versionadas** — hoy los `ALTER TABLE IF NOT EXISTS` están sueltos en `database.py`. Pasar a Alembic o migraciones numeradas.

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
