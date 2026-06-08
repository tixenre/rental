---
name: auditar-flujos
description: Audita Y mejora los FLUJOS de navegación de la app real recorriéndolos como un agente de navegación (un browser de verdad vía Playwright) sobre una copia local con datos de ejemplo. Úsalo cuando el dueño pida "auditá los flujos", "revisá que la navegación funcione", "qué bugs hay en el recorrido", "mejorá el flujo de X", "probá el carrito/checkout/portal/back-office de punta a punta", "está todo bien la experiencia", o cuando quieras verificar de verdad (no solo leer código) que un recorrido multi-paso funciona. El corazón NO es una lista de pantallas, sino el MÉTODO: levantar el stack local con seed + bypass → recorrer cada flujo capturando screenshots + errores de consola + 4xx + tap targets → juzgar contra criterios de UX → arreglar lo seguro (reusando el design system) → re-recorrer para verificar. NO es para rediseño visual de una pantalla (eso es `importar-diseno`) ni para tocar el core sagrado de reservas/plata (eso va como iniciativa propia con plan + Opus).
---

# auditar-flujos — recorrer la app de verdad, encontrar lo que falla, mejorarlo

Codifica **cómo** se audita y mejora la experiencia de navegación de Rambla sin
romper nada: no la lista de pantallas, sino el **método, el cuidado y la red de
verificación**. Es hermano de `limpieza` (mismo espíritu: verificar antes de
afirmar/actuar) pero aplicado a los **flujos** que ve y camina el usuario.
Materializa la _Barra de calidad_ (MEMORIA *2026-05-25*): mobile-first, sin
hotfixes, modularidad, y **el core de reservas es sagrado**.

> ## Por qué un skill aparte (y no dentro de `importar-diseno`)
>
> `importar-diseno` **implementa un diseño** ya hecho (loop render-compare contra
> un mockup). Esto es lo opuesto y complementario: **descubre** qué anda mal
> recorriendo la app real, sin un mockup de referencia. Es un **método de
> auditoría** (como `limpieza`), no un skill de design system. **Cuando un
> hallazgo se arregla con piezas visuales, se consume la librería del DS por las
> reglas de `importar-diseno`** (reuse-first; no se recrea ni duplica). La regla
> "un solo skill de UI" (MEMORIA *2026-06-06*) se respeta: este skill **no posee
> patrones de UI**, posee el método de recorrer+auditar+mejorar flujos.
>
> _Pendiente de ratificación del dueño: sumar una entrada a `docs/MEMORIA.md` que
> sancione este skill (si no, el supervisor lo marca como "segundo skill de UI")._

---

## La regla de oro (igual que `limpieza`)

**Verificá antes de afirmar.** No se dice "el flujo funciona" sin haberlo
**recorrido y visto**. La intuición y la lectura de código mienten: un botón
puede llevar a una ruta pausada, una pantalla pública puede tirar 401 en
silencio y caer a un fallback (caso testigo real: el catálogo público recibía
401 en `/api/settings/*` y `/api/marcas` → las settings del dueño nunca llegaban
al visitante). **El walk con screenshots + consola + red es la evidencia.**
Honestidad > actividad: si un flujo está bien, se dice; no se fabrica churn.

---

## 0 · Levantar el stack local (la base de todo)

El audit corre contra la app **local**, NUNCA contra prod/staging (prod es
sagrado). El bypass de admin y el dev-login de cliente **solo funcionan fuera de
Railway** (gate `dev_bypass_enabled` / `settings.is_railway`).

```bash
# Postgres
pg_ctlcluster 16 main start
su - postgres -c "psql -c \"ALTER USER postgres WITH PASSWORD 'postgres';\""
su - postgres -c "psql -c 'CREATE DATABASE rambla_rental;'"

# Backend (con bypass de admin; dev@local como admin para que /auth/me lo acepte)
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rambla_rental \
       SECRET_KEY=dev-local ADMIN_EMAILS="dev@local" ADMIN_BYPASS_AUTH=1 \
       EMAIL_PROVIDER=test FRONTEND_BASE_URL=http://localhost:3000
uvicorn main:app --port 8000 &        # arranca y corre init_db + migraciones

# Datos de ejemplo (idempotente; NO corre en Railway)
python -m seeds.demo_data             # equipos, clientes y pedidos en varios estados

# Frontend (proxyea /api y /auth a :8000)
cd .. && npm ci && npm run dev &      # http://localhost:3000
```

- **Auth en local:** admin → el browser navega `/auth/dev-login` (sesión
  `dev@local`, que debe estar en `ADMIN_EMAILS`). Cliente → `/auth/dev-login-cliente`
  (sesión del primer cliente del seed). `walk.mjs` lo hace solo con `--as`.
- **`pkill` traicionero:** matar uvicorn desde un comando cuyo cmdline contiene
  `uvicorn main:app` **se autodestruye** (pkill -f matchea su propio wrapper).
  Matá por **PID exacto** (de "Started server process [PID]") o por puerto.
- **`get_db()` NO auto-commitea:** su `__exit__` solo cierra. Todo seed/script
  con `with get_db() as conn:` necesita `conn.commit()` explícito antes de salir.

## 1 · Recorrer (el agente de navegación)

`walk.mjs` recorre rutas o un flujo guionado y captura, por paso:
screenshot desktop+mobile, **errores de consola**, **4xx**, y **tap targets < 44px**
(HIG, MEMORIA *2026-06-05*).

```bash
# Superficie entera (rutas sueltas):
node .claude/skills/auditar-flujos/walk.mjs --as none    --both --out /tmp/audit/public \
  --routes "/,/catalogo,/equipo/<slug>-<id>,/estudio,/preguntas-frecuentes"
node .claude/skills/auditar-flujos/walk.mjs --as cliente --both --out /tmp/audit/portal \
  --routes "/cliente/portal,/cliente/perfil"
node .claude/skills/auditar-flujos/walk.mjs --as admin   --desktop --out /tmp/audit/admin \
  --routes "/admin/pedidos,/admin/pedidos/<id>,/admin/clientes,/admin/contabilidad,..."

# Flujo multi-paso guionado (clicks/fills/evals entre capturas):
node .claude/skills/auditar-flujos/walk.mjs --as none --flow flows/carrito.json --out /tmp/audit/carrito
```

Cada paso del `--flow` es `{name, goto?, fill?:[[sel,val]], click?, eval?, waitFor?}`
→ permite reproducir el recorrido real (abrir el modal de fechas, agregar al
carrito, solicitar) y ver **estados intermedios**, no solo rutas. Salida:
PNGs + `report.json` con los hallazgos por paso. Leé los PNG con la tool de
imágenes y `report.json` para los errores. (Hereda el motor de Playwright del
repo, igual que `render.mjs`.)

## 2 · Auditar cada paso (el corazón — qué se mira)

Por cada pantalla/transición, juzgá contra estos criterios. Un hallazgo es
"funciona / no funciona / se puede mejorar", con su evidencia (screenshot + log):

| Eje | Pregunta | Señal en el report |
|---|---|---|
| **Funciona** | ¿la pantalla carga y hace lo que promete? ¿el botón lleva a donde dice? | `console_errors`, `http_errors`, redirect inesperado en `url` |
| **Próximo paso claro** | ¿se ve qué hacer después? ¿hay un CTA, no un dead-end? | screenshot |
| **Estados** | vacío / cargando / error / sin-resultados, ¿están diseñados? | recorrer con datos Y sin datos |
| **Feedback** | tras una acción, ¿el sistema confirma? (pedido → redirect al portal + toast, ver `docs/FLUJO_PEDIDOS.md`) | screenshot del después |
| **Mobile-first** | tap targets ≥ 44×44 (HIG), inputs ≥ 16px (no zoom iOS), sin overflow horizontal | `small_tap_targets` |
| **Consistencia** | ¿usa los componentes/tokens del DS o hay estilo ad-hoc? | screenshot |
| **Vuelta atrás** | ¿hay forma clara de volver/cancelar sin perder trabajo? | recorrer el "atrás" |
| **Core sagrado** | si el flujo toca reservas/plata, ¿la disponibilidad y los montos son correctos? | NO se valida tocando el motor; se observa la conducta |

> **Distinguí bug de decisión.** Antes de marcar algo como bug, leé el código y la
> MEMORIA: una ruta puede **rebotar a propósito** (`/admin/email-templates` →
> `/admin/settings` es redirect de compat; el editor del cliente está **pausado**
> #750), un 404 de una setting pública puede ser **fallback correcto** (sin valor
> seteado), un nombre raro puede ser **dato de seed**, no la app. Reproducí y leé
> antes de afirmar.

## 3 · Triage por tipo (cuidado proporcional, como `limpieza`)

| Tipo de mejora | Qué es | Cómo se aplica |
|---|---|---|
| **Bug de red/authz** | 4xx en algo público-por-diseño, guard faltante/de más | fix + **test de regresión** que falla sin él (caso testigo: `test_public_settings.py`) |
| **Lógica de flujo** | dead-end, paso de más, feedback ausente, vuelta-atrás rota | fix acotado + re-walk; reusa hooks/data-layer existentes |
| **Visual / DS** | tap target chico, estilo ad-hoc, inconsistencia | **se delega a las reglas de `importar-diseno`** (reusar la librería del DS), no se recrea |
| **Core sagrado** | reservas / plata | **NO se toca acá** → iniciativa propia, plan + Opus + test |

Lo grande / sensible / que toca lo que ve el usuario → **se reporta como propuesta,
no se ramea de prepo**. El dueño prueba la conducta en staging; un PR gigante e
inreviewable es lo contrario de lo que sirve. Mejor: un fix seguro y verificado +
una lista clara de propuestas con su evidencia.

## 4 · Verificar (re-walk) y empaquetar

- **Re-recorré el flujo arreglado** y compará el `report.json` antes/después (los
  errores deben caer; la conducta esperada debe aparecer). Para backend, **suite
  verde** (`pytest tests/ -q` desde `backend/`) — un fix de authz lleva su test.
- **Commits atómicos** (Conventional Commits en español). En el body, documentá
  qué se dejó como propuesta y por qué.
- **Despachá el `supervisor`** antes de abrir/mergear el PR.
- **Plan de prueba en lenguaje claro** para el dueño (qué tocar en staging para
  ver cada cambio). El dueño testea conducta, no lee diffs.

## Anti-objetivos (cuándo NO es este skill)

- **Rediseñar una pantalla** contra un mockup → `importar-diseno`.
- **Tocar el core de reservas/plata** en un barrido → iniciativa propia (Opus + plan + test).
- **Barrer código muerto / deps / ramas / issues** → `limpieza`.
- **Afirmar "todo funciona" sin recorrer** → prohibido (regla de oro).

## Cheatsheet

```
0. stack local: pg + backend (bypass) + seed demo + npm run dev
1. walk.mjs --as none|admin|cliente  (--routes o --flow) → PNGs + report.json
2. auditar: funciona / próximo-paso / estados / feedback / mobile / consistencia / atrás / core
3. triage: red(+test) · lógica(re-walk) · visual(→DS/importar-diseno) · core(NO, iniciativa)
4. re-walk + suite verde + commits atómicos + supervisor + plan de prueba
   honestidad > actividad · bug ≠ decisión (leé MEMORIA/código antes de afirmar)
```
