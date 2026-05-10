-- Bucket público para fotos de equipos
INSERT INTO storage.buckets (id, name, public)
VALUES ('equipos-fotos', 'equipos-fotos', true)
ON CONFLICT (id) DO UPDATE SET public = true;

-- Lectura pública
DROP POLICY IF EXISTS "equipos_fotos_public_read" ON storage.objects;
CREATE POLICY "equipos_fotos_public_read"
ON storage.objects FOR SELECT
USING (bucket_id = 'equipos-fotos');

-- Insert / update / delete sólo para usuarios autenticados (la validación de admin
-- se hace a nivel app vía ADMIN_EMAILS).
DROP POLICY IF EXISTS "equipos_fotos_authenticated_write" ON storage.objects;
CREATE POLICY "equipos_fotos_authenticated_write"
ON storage.objects FOR INSERT TO authenticated
WITH CHECK (bucket_id = 'equipos-fotos');

DROP POLICY IF EXISTS "equipos_fotos_authenticated_update" ON storage.objects;
CREATE POLICY "equipos_fotos_authenticated_update"
ON storage.objects FOR UPDATE TO authenticated
USING (bucket_id = 'equipos-fotos');

DROP POLICY IF EXISTS "equipos_fotos_authenticated_delete" ON storage.objects;
CREATE POLICY "equipos_fotos_authenticated_delete"
ON storage.objects FOR DELETE TO authenticated
USING (bucket_id = 'equipos-fotos');