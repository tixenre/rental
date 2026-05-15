# Changelog

> Historial de cambios de Rambla Rental.
> Actualizado automáticamente — fuente: `src/data/changelog.ts`.

## Mayo de 2026

### ✨ Novedades

- **Crear equipo: campos mínimos obligatorios + invitación a completar lo recomendado** *(15 de mayo de 2026)*
  Al crear un equipo nuevo, ahora son obligatorios: nombre, marca, categoría, cantidad, precio por jornada y dueño. Si falta alguno, el form no deja guardar. Cuando el equipo se crea OK, si quedaron campos recomendados vacíos (foto, descripción, número de serie, valor de reposición), aparece un toast diciendo cuáles faltan con un botón "Completar →" que reabre el form en modo edición. En edición los campos siguen siendo todos opcionales — no romper flujos legacy.
- **Dashboard de calidad: cada fila es ahora un CTA que filtra equipos directamente** *(15 de mayo de 2026)*
  Las filas del dashboard /admin/equipos/calidad pasaron de ser solo lectura a ser links. Click en "5 sin foto principal" → te lleva a /admin/equipos filtrado a esos 5 equipos, con un banner ámbar arriba que dice "Filtrando equipos sin foto principal · 5 resultados · Quitar filtro". Cada campo faltante (foto, categoría, nombre público, descripción, serie, valor de reposición) tiene su filtro propio compartible vía URL.
- **Dashboard de calidad del inventario — qué equipos tienen datos faltantes** *(15 de mayo de 2026)*
  Nueva sección en /admin/equipos/calidad que muestra de un vistazo cuántos equipos están al 100% y cuántos tienen datos faltantes por campo (foto, categoría, nombre público, descripción, serie, valor de reposición). Es solo lectura — los botones para completar directamente desde acá llegan en una segunda iteración. Sirve para saber dónde poner el foco al limpiar el inventario.
- **Microinteracción "+1" volando al carrito al agregar un equipo** *(15 de mayo de 2026)*
  Al tocar 'Agregar' en una tarjeta del catálogo, ahora aparece un chip '+1' amarillo que sale del botón con una curva animada hacia el ícono del carrito en la barra inferior. Cuando llega, el ícono hace un pequeño pop (escala) que refuerza visualmente que el item se sumó. Es feedback inmediato típico de e-commerce mobile — sirve para no perderse el cambio del contador cuando estás scrolleando rápido.
- **Calendario embebido en el dashboard + vista semanal** *(11 de mayo de 2026)*
  El calendario ahora aparece directamente en /admin, debajo de las tarjetas de 'salen/devuelven hoy', con todo a la vista sin tener que navegar a otra página. Bonus: ahora se puede alternar entre vista 'Mes' y vista 'Semana' (útil para producciones con pedidos densos). La página /admin/calendario sigue existiendo para una vista a pantalla completa. Click en un pedido del calendario abre el detalle.
- **Páginas de Privacidad y Términos** *(11 de mayo de 2026)*
  Se publicaron dos páginas legales: /privacidad (cómo recolectamos, usamos y protegemos los datos personales, cumpliendo Ley 25.326 de Argentina) y /terminos (proceso de reserva, precios, depósito, daños, cancelación, jurisdicción Mar del Plata). Links agregados al footer. Los textos son un borrador inicial — antes de hacer el sitio 100% público conviene que un abogado los revise.
- **Cliente puede previsualizar documentos antes de descargar** *(11 de mayo de 2026)*
  En el portal del cliente, cada documento (remito, contrato, albarán) ahora tiene dos botones: 'Ver' abre el documento en un modal (mejor UX en mobile, no abre apps externas), 'PDF' descarga la versión final. Útil para revisar datos antes de mandarle el PDF a alguien, y para ahorrar datos en mobile.
- **Albarán PDF: 'valor por unidad' aclarado + cálculo por línea** *(11 de mayo de 2026)*
  Cuando un equipo tiene cantidad > 1, el albarán ahora muestra explícitamente 'valor unitario × cantidad = subtotal' (antes solo aparecía el valor unitario y era confuso para el cliente). El header de la columna aclara '(por unidad)' debajo. Total al pie incluye los componentes de kits y dice claro de qué está compuesto.
- **Ranking automático extendido a marcas y categorías** *(11 de mayo de 2026)*
  Antes el sistema solo rankeaba equipos. Ahora también marcas y categorías se ordenan automáticamente por uso real (cantidad de pedidos + ingresos generados en los últimos 6 meses). Cuando corrés 'Recalcular ranking' en /admin/settings, las marcas más alquiladas suben en el carrusel y las categorías más activas suben en el mosaico. El orden manual (campo 'orden' o 'prioridad') sigue siendo override — el admin puede forzar marcas específicas arriba bajándole el número.
- **Ranking automático del catálogo: prioridad calculada por uso real** *(11 de mayo de 2026)*
  El sistema ya existía pero estaba escondido. Ahora en /admin/settings hay un botón 'Ranking automático' que calcula la prioridad de cada equipo según cuántas veces se alquiló y cuánto generó en los últimos 6 meses, normalizado por categoría (un equipo no compite contra todo el inventario, solo contra otros de su tipo). Tiene modo preview (dry-run) para ver qué cambiaría antes de aplicar. Esto reemplaza la idea de asignar prioridades a mano. Más parámetros vendrán pronto (issue #129).
- **Fecha de compra del equipo: ahora se elige mes + año (no día)** *(11 de mayo de 2026)*
  Antes era un input de fecha completo. Cambiamos a dos selectores (mes + año) — solo importa la época en que se compró, no el día exacto. Se guarda como 'YYYY-MM' (compatible con la columna actual). Los valores legacy con fecha completa siguen funcionando.
- **Series de equipos: botón N/A + banner de cuántos faltan cargar** *(11 de mayo de 2026)*
  En el form del equipo aparece un botón 'N/A' al lado del número de serie — útil para equipos como reflectores o cables que no tienen serie. La lista de equipos en el admin muestra un banner amarillo cuando hay equipos sin serie cargada, ordenados por valor de reposición (los caros primero). Te ayuda a priorizar qué completar.
- **Dueño de equipo ahora es un dropdown (Rambla / Pablo / Tincho)** *(11 de mayo de 2026)*
  Antes el campo dueño era texto libre — generaba inconsistencias por capitalización ("Pablo" vs "pablo" vs "PABLO") que fragmentaban los reportes. Ahora es un selector con las 3 opciones fijas. Los valores existentes se normalizaron automáticamente via migración Alembic. Si algún equipo tiene un dueño legacy (raro), aparece como '(legacy: X)' en el form y al guardar se reemplaza por la opción elegida del dropdown.
- **URLs de equipos con nombre legible — /equipo/sony-fx3-cuerpo-47** *(11 de mayo de 2026)*
  Antes los links eran /equipo/47 — números crípticos sin información. Ahora son /equipo/sony-fx3-cuerpo-47, con la marca y el nombre del equipo. Google posiciona mejor URLs con keywords, y compartir un link es más confiable (al ver la URL ya se sabe qué hay). Los links viejos /equipo/47 siguen funcionando y redirigen automáticamente al nuevo formato.
- **Cada equipo tiene su propia página: /equipo/{id}** *(11 de mayo de 2026)*
  El detalle del equipo dejó de ser un modal y pasó a ser una página real con URL única. Esto desbloquea: (1) Google indexa cada equipo como producto único con su foto, precio y marca; (2) compartir el link de un equipo muestra preview con título y foto; (3) bookmark + back/forward del navegador funcionan; (4) mejor experiencia en mobile. Datos estructurados Product agregados — Google puede mostrar rich snippets con precio y disponibilidad en resultados.
- **WhatsApp click-to-chat con plantillas en el back-office** *(11 de mayo de 2026)*
  Botón de WhatsApp en cada pedido (lista + detalle) que abre la app con mensaje pre-cargado. 7 plantillas según el estado: saludo, cotización lista, confirmación, recordatorios de retiro/devolución, pago, mensaje libre. El admin elige y envía con 2 clicks. Si el cliente no tiene teléfono cargado, el botón aparece deshabilitado.
- **SEO: meta tags, sitemap, structured data para Google** *(11 de mayo de 2026)*
  Ahora cuando Google indexa el sitio aparece con título, descripción e imagen propios (antes era genérico). Al compartir un link en WhatsApp/Instagram/Facebook se ve una preview con logo y texto. Agregado sitemap.xml para que Google encuentre todas las páginas, robots.txt para bloquear el back-office del indexado, y datos estructurados (LocalBusiness + FAQPage) para que aparezca con rich snippets en los resultados.
- **Carga más rápida — bundle JavaScript -34%** *(11 de mayo de 2026)*
  Optimización del bundle del frontend: el código del back-office se separa en chunks que solo bajan cuando el admin navega ahí. Visitors del catálogo público bajan 126 KB menos (de 375 KB a 249 KB gzipped). Mejora visible en redes lentas y móviles.
- **Migraciones de base de datos versionadas (Alembic)** *(11 de mayo de 2026)*
  Los cambios al schema ahora se trackean como migraciones versionadas. Cada vez que se modifica una tabla queda registrado y aplicado en orden — antes era "ALTER TABLE IF NOT EXISTS" suelto sin trazabilidad. Las migraciones corren automáticamente al arrancar la app.
- **Tests automatizados del backend (83 tests)** *(11 de mayo de 2026)*
  Red de seguridad para refactors futuros. Cubre regresiones de seguridad (allowlist anti-SSRF, separación admin/cliente), validaciones de fechas y stock, formato de precios y fechas. Cada PR ahora corre los tests automáticamente.
- **Precios discriminados por jornada y por período** *(11 de mayo de 2026)*
  En el catálogo, listas y modal de detalle ahora se ve el precio por jornada Y el total del período cuando hay fechas seleccionadas. Preparado para mostrar descuentos por cantidad de jornadas cuando se implementen.
- **Footer renovado + página de preguntas frecuentes** *(11 de mayo de 2026)*
  Footer público completo con logo, contacto, WhatsApp, navegación e Instagram. Nueva página /preguntas-frecuentes con 12 FAQs en 4 grupos (Reservas, Pago, Retiro y devolución, Seguros). Removidos el link a /admin y los iconos no clickeables.
- **Sección Novedades en el panel de administración** *(10 de mayo de 2026)*
  Nueva página en el back-office que muestra los cambios recientes del sistema.
- **Reordenamiento de specs con drag & drop y mejoras de UX** *(10 de mayo de 2026)*
  Sistema de specs con Kit DnD para reordenar por arrastre. Scroll restaurado al cerrar modal de producto, login funcional en portal cliente, link en Enriquecer con IA.
- **Sistema de specs robusto + imágenes PNG con fondo correcto** *(10 de mayo de 2026)*
  Gestión completa de especificaciones técnicas. Imágenes PNG ya no muestran fondo negro. Cambios en categorías ahora se guardan correctamente.
- **Mejoras en la barra superior (TopBar)** *(10 de mayo de 2026)*
  Logo centrado en mobile, pill con día de semana y jornadas en texto completo, barra de búsqueda alineada, toggle de vista bajo el logo.
- **Carrusel de marcas y precios editables** *(10 de mayo de 2026)*
  Nuevo carrusel de marcas en el catálogo. Precios editables inline en el panel de administración. Flag para marcar precios manuales.

### 🐛 Correcciones

- **Batch de cierres rápidos: rate limit, cleanup BD, rename 'Enriquecer'** *(11 de mayo de 2026)*
  Tres mejoras chicas que cierran issues abiertos: (1) protección básica contra abuso/bots (rate limit 200 req/min por IP, sin Redis ni costos); (2) limpieza de tabla 'usuarios' legacy del auth viejo (ya no se usaba); (3) 'Enriquecer con IA' renombrado a 'Auto-completar info' en el form del equipo (menos jerga, más claro).
- **Catálogo: el ranking automático ahora SÍ se aplica** *(11 de mayo de 2026)*
  Dos bugs que hacían que el ranking pareciera no funcionar: (1) el frontend re-ordenaba categorías y equipos perdiendo la popularidad que calculaba el backend — ahora respeta el orden completo. (2) Si nunca se había corrido el cálculo, todos los scores quedaban en 0 y el orden caía a alfabético — ahora se corre automáticamente la primera vez que arranca la app. Resultado: los equipos, marcas y categorías más alquilados aparecen primero, sin que el admin tenga que hacer nada.
- **Carrusel de marcas: click ahora filtra el catálogo** *(11 de mayo de 2026)*
  Bug en desktop: hacer click en una marca del carrusel no filtraba nada. El carrusel pasaba el ID numérico pero el filtro espera el nombre. Ahora se pasa el nombre y al hacer click se filtran solo los equipos de esa marca. Re-click deselecciona (toggle).
- **Logo: subir uno nuevo se ve en todos lados (sin recorte ni grosor extra)** *(11 de mayo de 2026)*
  Tres problemas resueltos: (1) Antes el logo se guardaba con un nombre nuevo cada vez (logo-1234567890.png), entonces quedaban versiones viejas en el storage como basura. Ahora se guarda en un path fijo y se sobreescribe. (2) El logo se procesaba con el mismo helper de las fotos de equipos, que recortaba al ras y hacía cuadrado — eso engrosaba el top bar mobile porque los wordmarks horizontales pasaban a cuadrados con mucho padding. Ahora se preserva el aspect ratio original. (3) Si subías un logo nuevo, tardaba hasta 5 min en aparecer — ahora se ve en menos de 30s.
- **Validación de stock más estricta: equipos duplicados en pedido** *(11 de mayo de 2026)*
  Bug latente arreglado: si un pedido tenía dos items separados del mismo equipo (raro pero posible vía API directa o bug del frontend), la validación de stock los chequeaba por separado y podía pasar cuando no debía. Ahora se suman las cantidades del mismo equipo antes de validar contra el stock. 5 tests de regresión agregados.
- **Footer en mobile más compacto** *(11 de mayo de 2026)*
  Antes el footer en celular era gigante con todos los datos en 3 bloques verticales. Ahora es chico: logo + botón WhatsApp en una fila, links navegación en chips horizontales, contacto comprimido a ciudad + email, copyright. Si necesitás más info (horarios, dirección completa, Instagram), todo eso queda en desktop intacto.
- **Mini-ficha más limpia: sin descripción, solo lo importante** *(11 de mayo de 2026)*
  En la mini-ficha que aparece al hacer click en un equipo del catálogo, se sacó la descripción corta. Quedan solo los datos clave (quick facts) + los componentes del kit (lo más útil para decidir rápido) + el botón 'Ver ficha completa'. Pronto los quick facts van a poder definirse por categoría desde el back-office (issue #116).
- **Mobile: vuelve la mini-ficha inline + scroll se mantiene al volver** *(11 de mayo de 2026)*
  Regresión del PR de ficha de equipo (#111): en mobile click expandía inline una mini ficha con kit y datos clave para navegar rápido. Ahora vuelve eso, y para ir al detalle completo hay un botón 'Ver ficha completa →' dentro. Bonus: al hacer back desde la ficha el catálogo vuelve al mismo punto del scroll donde estabas (scrollRestoration de TanStack Router).
- **Mobile fixes + checklist de auditoría** *(11 de mayo de 2026)*
  Mejoras para la experiencia en celulares: (1) los inputs ya no hacen zoom al hacer focus en iOS (era el problema más molesto en formularios); (2) el botón de usuario en el top bar es más grande y fácil de tocar; (3) las imágenes del catálogo y lista de pedidos cargan en forma diferida (perf). Más un documento docs/MOBILE_AUDIT.md con el checklist de revisión para mantener todo en orden.
- **Quick wins: logo PNG en mobile, favicon, títulos de tab, orden de pedidos manuales** *(11 de mayo de 2026)*
  Cuatro fixes chicos que suman: (1) el logo del top bar en mobile ahora usa el PNG real (antes era texto); (2) favicon agregado (el ícono que aparece en la pestaña del navegador); (3) títulos de tab diferenciados — 'Back Office · Rambla' vs 'Rambla Rental' para distinguir desde la tab; (4) los pedidos manuales viejos (sin número) ahora aparecen al final del listado, no arriba.
- **Editar categorías ya no tira error 500** *(11 de mayo de 2026)*
  Al renombrar una categoría a un nombre que ya existía, el servidor devolvía 'Internal Server Error' sin explicación. Ahora detecta el duplicado antes de intentar guardar y muestra un mensaje claro: 'Ya existe una categoría llamada X'.
- **Edición de categorías: ahora con feedback visual al guardar** *(11 de mayo de 2026)*
  El editor de categorías guardaba los cambios sin avisar (el campo se 'auto-guardaba' al perder el foco, sin botón ni confirmación). Ahora cuando se modifica un nombre aparece un botón verde ✓ para confirmar y uno gris ✗ para cancelar, con toast de éxito. También se pueden usar Enter (guardar) y Esc (cancelar). Resuelve la queja de 'no puedo editar las categorías'.
- **Reparada la descarga de PDFs (cotizaciones, remitos, contratos, albaranes)** *(11 de mayo de 2026)*
  Los botones 'Descargar PDF' del portal cliente y del back-office no funcionaban — el generador de PDFs estaba deshabilitado. Reactivado, todos los documentos se descargan de nuevo.
- **Performance de queries en la BD** *(11 de mayo de 2026)*
  Agregados 5 índices que faltaban en la base (pedidos por cliente, login por email, categorías y etiquetas reverse, solicitudes). Mejora la velocidad de operaciones frecuentes del portal cliente y admin.
- **Logging estructurado en producción + orden de pedidos del cliente** *(11 de mayo de 2026)*
  Backend: logs JSON estructurados con request_id, listos para Railway/Sentry. Bug fix: el listado de pedidos del cliente ahora ordena por fecha de creación (más reciente primero), antes podía aparecer fuera de orden con pedidos importados del histórico.
- **Bugs críticos pre-producción: stock, fechas, errores 500 silenciosos** *(11 de mayo de 2026)*
  (1) Race condition en stock al crear pedidos: dos clientes simultáneos ya no pueden reservar el mismo equipo. (2) Validación backend de fechas: rechaza fechas en el pasado y fecha_hasta menor a fecha_desde. (3) Errores 500 en handlers críticos ahora se loguean con traceback. (4) Admin /pedidos se auto-refresca cada 5s.
- **Seguridad: acceso restringido a endpoints de admin** *(11 de mayo de 2026)*
  22 endpoints del backend que no tenían autenticación ahora requieren rol admin. Cerraba una escalada de privilegios donde un cliente podía acceder a rutas de back-office.
- **Marcas, preview de documentos y perfil del cliente** *(10 de mayo de 2026)*
  Fusión de marcas duplicadas, preview de PDFs en cotizaciones y nueva sección de Perfil en el portal del cliente.
- **Calidad de fotos, calendario, logos de marcas y branding** *(10 de mayo de 2026)*
  Mejora en la calidad de búsqueda de fotos, integración de calendario en el dashboard, logos correctos por marca y mejoras de branding general.
- **Slugs de foto y ranking en carruseles** *(10 de mayo de 2026)*
  Corrección en la detección de URLs hospedadas y mejora en el ordenamiento de carruseles por relevancia.
- **UX: grilla, estados y categorías expandibles** *(10 de mayo de 2026)*
  Eliminación de gaps visuales en la grilla, colores de estado corregidos, categorías expandibles en la sidebar y link al catálogo arreglado.
- **Carrusel de marcas y fechas inválidas en pedidos** *(10 de mayo de 2026)*
  Carrusel de marcas mostraba 0 equipos. Fechas inválidas ("Invalid Date") en la sección Mis Pedidos del portal cliente.

### 🔧 Mantenimiento

- **CI automático: typecheck + build en cada PR** *(11 de mayo de 2026)*
  GitHub Actions corre verificaciones automáticas en cada cambio. Detecta errores de tipos y de build antes de que lleguen a producción.
- **Limpieza del repo** *(11 de mayo de 2026)*
  Borrados residuos de la migración SQLite→Postgres y de un intento abandonado con Supabase. 26k líneas menos. El cliente Supabase JS para auth sigue intacto.

### 📝 Documentación

- **Issues ahora se clasifican también por complejidad** *(11 de mayo de 2026)*
  Además de la prioridad (urgencia), ahora cada bug/feature tiene una etiqueta de complejidad (trivial, small, medium, large, epic) según el tiempo estimado. Útil para elegir qué hacer según el tiempo disponible — sesiones cortas tackle trivial+small, sprints epic. Aplicado a los 28 issues abiertos.
- **README real + estructura de docs/** *(11 de mayo de 2026)*
  Documentación del proyecto reorganizada: README con quick start y arquitectura, docs/ con todos los .md (PROTOCOLO, DISEÑO_SPECS, DEPLOY_RAILWAY, MEJORAS, BUGS) e índice navegable.
