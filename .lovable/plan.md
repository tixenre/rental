No, no estás pidiendo algo raro. Se guardó pensando en el modal de detalle, pero vos estás mirando la fila expandida del catálogo, donde el componente que dice “Sin información adicional” no está usando la info enriquecida de forma clara; además la foto puede estar fallando por guardado/invalidación/cache.

Plan:

1. Hacer visible la ficha enriquecida en la fila pública
   - En `EquipmentRow`, cuando se despliega una fila, reemplazar el estado “Sin información adicional” por una sección real con:
     - 3 o 4 specs/selling points destacados primero.
     - Descripción breve si existe.
     - “Incluye” debajo si es combo/kit.
   - Si no hay ficha, recién ahí mostrar “Sin información adicional”.

2. Unificar la presentación de “selling points”
   - Ajustar `IncludedList` para que no trate las specs como una tabla técnica larga en ese contexto.
   - Mostrar specs importantes como chips/pares cortos, aptos para catálogo: `6K`, `Global Shutter`, `Canon RF`, `Full Frame`, etc.
   - Mantener el acordeón completo de especificaciones en el modal de detalle para quien quiera ver todo.

3. Corregir refresco después de enriquecer
   - Al aplicar enriquecimiento, invalidar también el query público `equipos`, no solo el query admin.
   - Así, si estás en el catálogo o volvés a él, se ve la nueva foto/ficha sin esperar cache ni recargar manualmente.

4. Robustecer guardado de fotos
   - Mantener la subida al bucket interno, pero hacer que si la subida externa falla quede claro con un error útil.
   - Asegurar que `foto_url` actualizado vuelva en `/api/equipos` y se mapee a `fotoUrl` para cards, filas y ficha pública.
   - Evitar que una URL externa rota quede como “guardada” si no se pudo copiar al storage.

5. Verificar el flujo completo
   - Probar conceptualmente: enriquecer equipo → aplicar → catálogo público → fila expandida muestra specs/descripcion → thumbnail/foto aparece.
   - Si el backend devuelve ficha/foto pero el frontend no lo refleja, corregir el mapeo; si no lo devuelve, corregir el endpoint.