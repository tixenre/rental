---
name: limpieza
description: Flujo completo de mantenimiento del repo y el proyecto, en 4 frentes con la misma disciplina — (A) código muerto / imports / archivos / deps / duplicación (DRY) / modularización / optimización; (B) auditoría de seguridad + bugs; (C) ramas (borrar las mergeadas); (D) issues (triagear, cerrar lo hecho con evidencia, consolidar trackers/umbrellas solapados). Úsalo cuando el dueño pida "limpiar", "seguir limpiando", "housekeeping", "sacar lo que no se usa", "código muerto", "hay legacy dando vueltas", "revisá seguridad/bugs", "está todo seguro?", "limpiá ramas", "ordená/cerrá los issues", o cuando detectes cruft/drift mientras trabajás. El corazón NO es una lista de ítems, sino el MÉTODO seguro: verificar antes de ACTUAR (borrar/cerrar/afirmar — las herramientas Y la intuición mienten) → red de tests → no perder tracking → commits atómicos → supervisor. NO es para refactors de arquitectura ni tocar el core sagrado de reservas/plata en un barrido (eso va como iniciativa propia).
---

# limpieza — mantenimiento del repo, sin romper nada

Codifica **cómo** se mantiene Rambla sano: no la lista de lo ya hecho, sino la **lógica, el cuidado
y los tests** para que cada pasada futura sea segura. Es el flujo completo de housekeeping en **4
frentes** con la misma disciplina. Materializa la _Barra de calidad_ (MEMORIA *2026-05-25*):
modularidad a prueba de balas, nada de hotfixes, y **el core de reservas es sagrado**.

| Frente | Qué barre | Acción que arriesga | Verificación antes de actuar |
|---|---|---|---|
| **A · Código** | muerto / imports / archivos / deps / DRY / modularizar / optimizar | borrar | grep repo-wide + suite verde |
| **B · Seguridad + bugs** | authz/IDOR, injection, SSRF/XSS, overlap de reservas, plata | afirmar "está OK" / parchar | reproducir el exploit + test de regresión |
| **C · Ramas** | ramas que no son `dev`/`main` ya mergeadas | borrar la rama | confirmar que su PR está mergeado |
| **D · Issues** | triagear, cerrar lo hecho, consolidar trackers/umbrellas | cerrar el issue | evidencia (PR/commit) de que está hecho |

> ## Regla de oro (vale para los 4 frentes)
>
> **Verificá antes de ACTUAR — y "actuar" es borrar, cerrar o afirmar.** Las tres acciones son
> irreversibles en la práctica (un issue cerrado se entierra, una rama borrada se olvida, un "está
> todo seguro" tranquiliza de más). Nada se ejecuta sin evidencia: las **herramientas dan candidatos,
> nunca sentencias** (knip/ruff/vulture mienten); **la intuición del dueño también se equivoca**
> ("casi todos los issues se pueden cerrar" → varios eran backlog real; "¿está todo seguro?" → había
> un agujero de authz crítico). El gate del dueño es *probar en staging*, no leer diffs → **"no
> romper nada / no enterrar nada" pesa más que "cuánto limpiamos"**. Ante la duda, se **deja, se deja
> abierto y se reporta** — nunca se borra/cierra a ciegas. **Honestidad > actividad:** si está limpio,
> la respuesta correcta es decirlo, no fabricar churn.

Casos testigo (de por qué la regla existe):

- **knip mintió:** marcó `categories`/`brands` como exports sin usar — tienen **30+ usos reales**; y
  `trackEvent` (uso dinámico desde cart-store/orders).
- **ruff mintió:** marcó `reservas.ESTADOS_RESERVADO` en `routes/alquileres.py` como import sin usar
  → es un **re-export canónico que un test exige** (`test_reservas_sql_safety`). Lo cazó el suite.
- **La intuición mintió:** "casi todos los issues se pueden cerrar" — al triagear con evidencia,
  varios eran trabajo pendiente real (ej. #476, lint promovible a bloqueante) → se dejaron abiertos.
- **El "todo OK" mintió:** ante "¿está todo seguro?", la auditoría destapó **escrituras de `/api/equipos`
  sin `require_admin`** (cualquier anónimo creaba/borraba equipos) → fix #795. No era cosmético.

La moraleja: la herramienta (o la corazonada) arranca el trabajo, **el suite, el grep y la evidencia
lo terminan**.

---

## Frente A — Código (el método, 6 fases)

### 1 · Inventario con herramientas (no grep ciego)

Las herramientas no están en CI (no hay linter de Python en CI; knip no corre solo) → se instalan
para el barrido. Dan una **lista de candidatos**.

| Capa | Herramienta | Qué caza | Comando |
|---|---|---|---|
| Backend (Python) | **ruff** | imports / redefiniciones / variables sin usar | `ruff check . --select F401,F811,F841 --no-cache --exclude "migrations,tests"` |
| Backend (Python) | **vulture** | funciones / clases / atributos muertos | `vulture . --min-confidence 80 --exclude "tests/,migrations/"` |
| Frontend (TS/TSX) | **knip** | archivos, exports y dependencias sin usar | `npx --yes knip --no-progress` |

```bash
# Setup del barrido (efímero, no se commitea):
python -m venv /tmp/venv && . /tmp/venv/bin/activate
pip install -q -r backend/requirements-dev.txt vulture ruff
# (knip se baja con npx; el front necesita `npm ci` para tsc/eslint/build)
# ruff/vulture NO están pineados: una versión nueva puede traer reglas distintas →
# si querés reproducir un barrido viejo, fijá la versión (ruff==X, vulture==Y).
```

> **`migrations/` se excluye SIEMPRE.** Es historia congelada (decisión _esquema en dos capas_,
> MEMORIA *2026-06-03*); sus "imports sin usar" (`op`, `sa`) son convención de Alembic, no cruft.

> **vulture: quedate en `--min-confidence 80`.** A 60 **inunda** de falsos positivos: marca todos
> los handlers de ruta FastAPI y los validators Pydantic (no ve los decoradores). Más ruido que señal.

> **No confíes en RUF100** ("unused noqa directive") corriendo ruff **ad-hoc**: como el repo no tiene
> config de ruff, RUF100 marca como "sin usar" `# noqa` que SÍ hacen falta cuando se corre el ruleset
> real (`E402` de scripts con path-setup antes del import, `E501`, y los `# noqa: F401` que protegen
> re-exports como `ESTADOS_RESERVADO`). **No saques noqas** basándote en un run ad-hoc.

> **Señales extra de ruff** (corré `--select F` para verlas además de las tres de arriba): **F541**
> (f-string sin placeholder) = micro-limpieza segura (`--fix`). **F601** (clave de dict repetida) =
> **bug smell, NO limpieza**: si los dos valores **coinciden** es una dup inocua (cleanup); si
> **difieren** es un bug de conducta (una clave pisa a la otra) → **reportar**, no "arreglar" a
> ciegas. Caso testigo: `"lens mount"` mapeaba a `"Montura"` y una dup lo pisaba con `"Lens mount"`
> (inglés sin traducir) — la "limpieza" de la dup es en realidad una decisión de qué label se muestra.

> **Ángulos extra cuando las herramientas principales ya no encuentran nada:** (1) **comentarios
> huérfanos** — tras una tanda de borrados, grepeá los símbolos eliminados en comentarios (`grep -rn
> WhatsappPill`) y actualizalos (caso testigo: un docstring seguía nombrando `WhatsappPill` ya borrado);
> (2) **código duplicado** con `npx jscpd src backend --min-tokens 80 --min-lines 15` → un % bajo
> (≤0.5) es sano; solo vale extraer un clon **grande e idéntico** (refactor DRY, no borrado). Cuando
> estos ángulos tampoco dan nada, el repo está limpio: **parar es la respuesta correcta**, no forzar.

### 2 · Triage — separar muerto real de falso positivo

Por cada candidato, preguntarse **por qué la herramienta lo marcó** y si es legítimo. Falsos
positivos típicos (**NO borrar**):

- **Re-exports** intencionales: barrels (`index.ts`), `__all__`, constantes canónicas re-expuestas.
  Si un **test** los exige, se conservan con `# noqa: F401` + comentario que apunte al test.
- **Uso dinámico / por string:** eventos de analytics, registries, factories, rutas lazy.
- **Funciones registradas por decorador:** las herramientas Python NO ven los decoradores → marcan
  como muertos los **handlers de ruta** (`@router.get`/`@app.get`) y los **validators Pydantic**
  (`@field_validator`/`@classmethod`). Es la fuente #1 de falsos positivos de vulture. Un handler,
  además, puede ser consumido por el front por **string de URL** (`fetch('/api/...')`) → grepear la
  **ruta** (`/api/...`) en el front, no el nombre de la función.
- **`__init__.py` vacíos:** son markers de paquete obligatorios, no archivos a borrar.
- **Helper que se autodescribe "fuente única"/canónico pero con 0 consumidores** (caso testigo:
  `pdf._a4_page`): es la baranda del barrel a menor escala → **reportar**, no borrar (suele ser
  intención sin cablear; borrarlo pierde el diseño, cablearlo es un refactor aparte).
- **Miembro suelto de una API simétrica / compound-component / toolkit curado:** un export sin usar
  que es parte de una familia coherente cuya mayoría sí se usa → dejar (borrar el miembro suelto
  rompe la simetría y empeora la legibilidad). Casos testigo: `refresh`/`refresh_equipos` en la
  familia `refresh_*`; `AdminCardActions` en el compound `AdminCard.*` (Header/Meta/Footer/Price/
  Actions); `PageHeader` en el barrel de primitivos mobile (`components/mobile/`: FAB, BottomSheet,
  ActionMenu…). Si dudás si es toolkit deliberado o muerto → **reportar**, no borrar.
- **Export con marcador de intención:** un `// eslint-disable-next-line react-refresh/only-export-components`
  con comentario ("a propósito", "coexiste con el componente") marca un export **deliberado** → dejar
  (casos testigo: `PLANTILLAS_MAIL`, `Illustrations`). El marcador ES la decisión registrada en el código.
- **Assets referenciados por string:** imágenes/íconos/templates cargados por path armado en runtime
  (no `import` estático) → knip no los ve. Grepear el nombre del archivo en TODO el repo. Y ojo: un
  asset de `public/` puede estar apuntado por un **setting administrable en la BD de prod** (ej.
  `app_settings.email_logo_url` → `/email-logo.png`) que NO podés inspeccionar → con 0 refs en código
  pero "seteable desde el back-office", **reportá, no borres** (caso testigo: `public/email-logo.png`).
- **Código de un job/cron:** una función llamada solo desde un scheduled job de Railway (ej. los
  slots fijos del estudio que generan pedidos mensuales, MEMORIA *2026-05-27*) parece muerta y no lo está.
- **Feature flags / settings administrables:** código detrás de un flag de `app_settings` apagado
  hoy NO es muerto (se enciende desde el back-office).
- **Parámetros de interfaz:** firmas que un framework exige (ej. `attrs` en `HTMLParser.handle_starttag`,
  params con default usados por keyword). Quitar un parámetro **cambia la firma** → no es limpieza.
- **Imports/llamadas con efecto secundario:** `client.fetch_token(...)` guarda estado; `import x`
  que registra algo. La **llamada se queda**; en F841 se tira solo la **asignación** sin usar.
- **Tooling / scripts CLI:** skills (`.claude/skills/**`), `scripts/*.mjs`, migraciones de imports.
  No los importa nadie a propósito (se corren a mano) → knip los marca, pero **se quedan**.
- **Librería mantenida a propósito:** primitivos shadcn (`src/components/ui/*`) y sus deps `radix`
  son la caja de herramientas del design system → se conservan aunque estén sin consumir hoy.

> **Respetar la MEMORIA.** Antes de borrar, chequear que no contradiga una decisión registrada.
> **Nunca** se borra: el barrel documentado `equipment/index.ts` (*2026-05-29*), los motores únicos
> `backend/{reservas,reportes,busqueda,services/branding}/` ni el sistema de analytics (*2026-06-02*).
> Si algo "parece muerto" pero está documentado como vivo → se **deja y se reporta** (baranda de
> "mirar el target antes de borrar").

### 3 · Verificar cada candidato (grep en TODO el repo)

La herramienta mira su dominio; vos mirás el repo entero. Antes de tocar:

```bash
# ¿Se usa en CUALQUIER lado? (no solo src/ o routes/ — incluir .mjs, tests, public, index.html)
grep -rn "NOMBRE" src packages backend .claude --include=*.ts --include=*.tsx --include=*.py --include=*.mjs
# Para un endpoint backend: grepeá la RUTA, no la función (el front la llama por string):
grep -rn "/api/la-ruta" src
```

Distinguir tres situaciones (cambian qué se borra):

- **Archivo huérfano:** 0 imports en todo el repo → se borra el archivo (`git rm`).
- **Export sin usar pero usado adentro de su módulo:** se quita solo la palabra `export` (o se deja);
  borrar la función rompería su uso interno.
- **Cascada:** borrar `X` deja huérfano a su helper privado o su import (ej. quitar `fuzzySameLabel`
  dejó muerta a su `normalize` privada; quitar `businessWhatsappLink` dejó sin uso el `import
  whatsappLink`). Hay que seguir la cascada hasta el fondo — `eslint`/`ruff` la confirman.

⚠️ **Cuidado con nombres comunes.** `grep` sobre-cuenta palabras genéricas (`categories`, `brands`,
`token`). Para esos, ni knip ni grep alcanzan: confiar en el **suite** y en `tsc` (que resuelven
bindings reales), o dejarlos.

### 4 · Clasificar el tipo de cambio (cuidado proporcional)

| Tipo | Qué es | Red mínima | Riesgo |
|---|---|---|---|
| **Borrado puro** | archivo / import / var muerta | tsc + eslint + build / pytest | bajo |
| **Refactor DRY** | unificar duplicación vía helper (ej. `MARCA_SUBQUERY`) | **salida byte-idéntica** (verificada) + suite + Postgres real | medio |
| **Cambio de conducta** | migrar a otra implementación (ej. normalizers a otro motor) | NO es limpieza pura → análisis de impacto + plan de prueba + **avisar antes** | alto |
| **Core sagrado** | reservas / plata (`backend/reservas`, `reportes`) | **NO se toca en un barrido** → iniciativa propia, Opus | máximo |

> **Refactor DRY = byte-idéntico.** Si extraés un helper, probá que genera **exactamente** la misma
> salida que el código viejo (ej. imprimir el SQL resultante y comparar carácter por carácter). Un
> refactor de limpieza no debe cambiar ninguna conducta.

> **Conditional siempre-verdadero** (`if True:` envolviendo un bloque grande; vulture lo marca como
> _redundant if-condition_): se elimina dedentando el bloque, pero **nunca a mano** si son muchas
> líneas → **script de dedent uniforme** (-4 espacios) **después** de verificar que TODA línea no-vacía
> del bloque tiene ≥ ese indent (si una no, el dedent rompe la estructura). Red: `py_compile` + suite
> + **ejecutar la función real** (caso testigo: `compute_estadisticas`, 175 líneas de SQL, dedentadas
> por script y verificadas contra Postgres real).

### 5 · La red de tests (esto es el "cuidado")

**Nada se da por bueno sin verlo verde.** El suite es la red que caza lo que el ojo no ve
(el re-export `ESTADOS_RESERVADO` lo cazó un test, no la revisión).

**Backend:**
```bash
. /tmp/venv/bin/activate
export SECRET_KEY=ci-test-secret-not-for-production ADMIN_EMAILS=admin@test.com
unset DATABASE_URL
cd backend && python -m pytest tests/ -q     # corré DESDE backend/ (toma pytest.ini: asyncio_mode, markers)
```
> Los tests de DB se saltan **solos**: cada archivo exige su opt-in (`RESERVAS_DB_TEST=1` /
> `ALEMBIC_DB_TEST=1` + `DATABASE_URL` a una base con `test` en el nombre) vía `skipif`. Sin eso no
> corren — **no** es un marker por default. Por eso este comando es paridad real con el job de CI.

**SQL / refactors de DB → Postgres REAL.** CI corre contra Postgres real **solo** las migraciones
(`test_alembic_upgrade_db.py`) y el SQL de liquidación (`test_reportes_liquidacion_db.py`); el resto
de las queries de rutas **no** tiene cobertura DB en CI → si tu refactor toca SQL de otra ruta,
**ejercelo a mano**. Receta:
```bash
pg_ctlcluster 16 main start
su - postgres -c "psql -c \"ALTER USER postgres WITH PASSWORD 'postgres';\""
su - postgres -c "psql -c 'CREATE DATABASE rambla_rental_test;'"
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rambla_rental_test
# bootstrap (init_db() + alembic upgrade head + base limpia) YA está escrito como harness copiable
# en backend/tests/test_alembic_upgrade_db.py (fixture clean_db) → usalo de base.
# Después: sembrar datos mínimos y EJECUTAR los caminos reales (TestClient sobre endpoints públicos
# + llamadas directas a helpers).
```
El objetivo: que **cada forma distinta de query** y cada **alias** se ejecute contra Postgres y
devuelva lo esperado (no solo que compile).

**Frontend:**
```bash
npx prettier --check <archivos>     # gate BLOQUEANTE de CI
npx tsc --noEmit -p tsconfig.json   # tipos (caza imports/exports rotos y cascadas)
npx eslint <archivos>               # unused tras cascada
npm run build                       # job `build` de CI
```

**Dependencias:** sacar con `npm uninstall <dep>` (sincroniza `package-lock.json`); si hay
`bun.lock`, además `bun install`. Nunca editar `package.json` a mano sin actualizar los lockfiles
(rompe `npm ci` de CI).

### 6 · Empaquetar + revisar

- **Commits atómicos por categoría**, Conventional Commits en español: `chore(backend): …`,
  `chore(frontend): …`, `refactor(scope): …`, `fix(scope): …`.
- En el body, **documentar qué se dejó a propósito y por qué** (params, código sensible, falsos
  positivos, documentado en MEMORIA). El "se dejó a propósito" es parte del valor.
- **Despachar el `supervisor`** antes de abrir/mergear la PR (instrucción de `CLAUDE.md`).
- Acompañar con **plan de prueba en lenguaje claro** para que el dueño verifique conducta en staging
  (foco: los lugares que más código perdieron).

---

## Qué NO tocar (lista negra)

1. `backend/migrations/` — historia congelada.
2. Core sagrado: `backend/reservas/`, `backend/reportes/` (y todo cálculo de stock/overlap/plata).
3. Motores únicos: `backend/busqueda/`, `backend/services/branding/`.
4. Barrel documentado `src/components/rental/equipment/index.ts` (MEMORIA *2026-05-29*).
5. Primitivos shadcn `src/components/ui/*` + sus deps `@radix-ui/*` (librería del DS).
6. Analytics (`src/lib/analytics.ts`) — eventos dinámicos (MEMORIA *2026-06-02*).
7. Parámetros de funciones, imports/llamadas con efecto, scripts de tooling/skills.

## Más allá del código muerto: modularizar y optimizar

Cuando el código muerto ya está barrido, el dueño suele pedir "¿y modularizar? ¿optimizar?".
Son lentes distintos: **no es borrado puro, cambia estructura/comportamiento** → red de tests sí o sí,
y clasificá por riesgo (tabla de la fase 4). Reglas:

- **Distinguí duplicación real-y-peligrosa de trivial/intencional.** Vale extraer cuando el patrón es
  largo, copiado en muchos lados y propenso a fallar (caso testigo: `MARCA_SUBQUERY`, una subquery de
  60 chars copiada 37× que ya había causado 500s en prod, #499). **NO** vale "DRY-ear" un one-liner
  (ej. el chequeo de rango `0 ≤ descuento ≤ 100`, repetido 3× pero con manejo de `None`/mensaje
  **distintos a propósito** por sitio) → forzarlo es over-engineering y arriesga pisar la diferencia
  intencional. La herramienta de detección de clones (`jscpd`) ayuda; un % bajo es sano.
- **N+1 de escritura** (`for x: conn.execute(INSERT …)`) → `conn.executemany(sql, [tuplas])`
  (behavior-idéntico; lista vacía = no-op; mismo orden de filas). Caso testigo: `duplicate_equipo`
  (categorías/etiquetas/kit) y `bulk_action` (insert anidado equipo×categoría). Verificá con suite +
  **ejercicio real contra Postgres** (forjá sesión admin con `signer.dumps({"email": <ADMIN_EMAILS>})`
  y pegale a la ruta con TestClient). **Pero ojo:** a veces el N+1 caro no es el INSERT sino una
  **llamada adentro del loop** (ej. `regenerate_auto_tags(conn, eid)` por equipo) → batchear eso toca
  el helper interno = refactor propio, no sweep.
- **Optimización sin problema medido = no tocar.** Memoización de React sin lag reportado, índices sin
  un `EXPLAIN` que muestre el cuello → es optimización prematura (deuda, no calidad). Reportá el
  candidato, no lo fuerces.
- **Boilerplate cross-cutting** (ej. `conn = get_db(); try/finally: close()` en ~37 rutas) → unificarlo
  (context-manager / FastAPI `Depends`) toca el manejo transaccional de **cada** endpoint = alto radio
  de explosión → **iniciativa propia con plan + supervisor**, jamás en un barrido.
- **Honestidad > actividad.** Si tras el análisis el código ya está bien modularizado (motores únicos
  presentes, clones ≤0.5%), la respuesta correcta es **decirlo**, no fabricar churn de bajo valor.

---

## Frente B — Seguridad + bugs

Se dispara con "¿está todo seguro?", "¿no hay ningún bug posta?", "revisá seguridad", o como pasada
propia. **La misma regla de oro: no se AFIRMA "está OK" ni se parcha sin verificar.** Un "todo bien"
sin auditar es la mentira más cara — tranquiliza al dueño sobre un agujero real.

**Cómo se barre:**

1. **Auditar con un agente read-only** (`Explore`/`general-purpose`) en paralelo a la revisión a mano
   — fan-out por superficie, sin tocar nada. El barrido cubre estas superficies:
   - **Authz / IDOR:** ¿toda escritura sensible tiene su guard (`require_admin`/`require_cliente`)?
     ¿un endpoint lee/edita un recurso de **otro** cliente por id sin chequear dueño? Caso testigo
     **#795**: 12 handlers de escritura de `/api/equipos` (create/update/delete/ficha/mantenimiento/
     kit/etiquetas/categorías) **sin `require_admin`** → anónimo total. El gate de público vivía en
     `middleware.PUBLIC_API`; se partió en `PUBLIC_API_READONLY` (GET/HEAD) vs `PUBLIC_API_ANY`.
   - **Injection:** SQL siempre parametrizado (`?`→`%s` vía el wrapper PGCursor), nunca f-strings con
     input. Command/template injection en lo que toque shell o render.
   - **SSRF:** todo `fetch`/descarga de URL externa (media, webhooks) con allowlist + `follow_redirects=False`
     (caso testigo: `services/media/security.py`). Un redirect a `169.254.169.254` roba credenciales de cloud.
   - **XSS / open-redirect:** todo lo que vuelva al DOM o a `Location`. Caso testigo: `_safe_next_path`
     en `auth.py` endurecido para rechazar `<>"'`\``, whitespace y control chars en el `?next=`.
   - **Core sagrado:** overlap de reservas (cero doble-booking) y cálculos de plata — un bug acá es
     de severidad máxima aunque no sea "seguridad" clásica.
2. **Triage por severidad** (crítico / alto / medio / bajo). El crítico se arregla ya; lo medio/bajo
   puede ir a issue con label si no es urgente.
3. **Verificar explotabilidad antes de tocar.** No parchar lo que no se reprodujo: confirmá el
   exploit (ej. `TestClient` haciendo la escritura anónima → debe dar 401 después del fix; GET sigue
   200; admin pasa). Un "fix" de algo no explotable puede romper conducta legítima.
4. **Test de regresión sí o sí.** Cada hallazgo arreglado deja un test que falla sin el fix (caso
   testigo: `test_auth_guards.py` parametrizado por los 12 endpoints + el test XSS de `_safe_next_path`).
   Sin el test, el agujero vuelve en el próximo refactor.

> **El core de reservas/plata sigue sagrado.** Un bug **se reporta** y se arregla con plan + Opus +
> test; no se parcha de apuro dentro de un barrido. Lo demás (la fase 4 de Frente A) aplica igual.

## Frente C — Ramas

"Limpiá las ramas que no sean `dev` ni `main`." El riesgo es **borrar trabajo no mergeado**.

1. **Mapear rama → PR.** Por cada rama remota, buscá su PR (`mcp__github__list_pull_requests` por
   `head`). Una rama es segura de borrar **solo si su PR está MERGED** (o el trabajo llegó a `dev` por
   otra vía verificable). Una rama **sin PR o con PR abierto/cerrado-sin-merge = se deja** y se reporta.
2. **`git branch --merged` NO alcanza:** el flujo mergea con **squash** a `dev` (MEMORIA *2026-06-01*),
   así que la rama squasheada **no aparece** como merged por ancestría aunque su contenido ya esté en
   `dev`. La verdad es el **estado del PR** (MERGED), no el grafo de commits.
3. **Limitación del entorno:** en el sandbox `git push origin --delete <rama>` da **HTTP 403** y no hay
   tool MCP de delete-ref → **no se pueden borrar ramas remotas desde acá**. Acción correcta: **reportar
   la lista** de ramas borrables (con su PR mergeado como evidencia) y recomendar al dueño activar
   **"Automatically delete head branches"** en Settings del repo (las borra solas al mergear, de ahí
   en más). Nunca afirmar "borré las ramas" si el entorno no lo permitió.

## Frente D — Issues

"Hacé housekeeping de los issues, casi todos se pueden cerrar." El riesgo es **enterrar backlog real**
porque la corazonada dice "ya está". Acá la regla de oro pesa doble: **cerrar es afirmar "esto está hecho".**

1. **Listar + agrupar por tópico.** `mcp__github__list_issues` (devuelve `{issues, totalCount, pageInfo}`
   — es un dict, no una lista) → mapear cada uno a su tema para ver solapamientos.
2. **Cerrar SOLO con evidencia.** Un issue se cierra cuando hay un PR/commit que lo resuelve, o el dueño
   lo confirma explícitamente. Cerrar = `mcp__github__issue_write` con `state:closed` + `state_reason`
   (`completed`/`not_planned`) **+ un comentario** que linkee la evidencia (PR/commit/decisión). Sin
   comentario, el "por qué se cerró" se pierde.
3. **No cerrar backlog real.** Si el issue describe trabajo pendiente que **no** se hizo, queda abierto
   aunque "suene viejo" (caso testigo: **#476**, promover reglas de lint a bloqueante — pendiente real,
   se dejó abierto y se flageó). Parciales = abiertos.
4. **Consolidar trackers/umbrellas solapados.** Cuando N issues cubren la misma iniciativa (caso testigo:
   DS #612/#605/#479 → #612; specs #526/#528/#535 → #526), **rescatá primero los ítems únicos** de cada
   uno hacia el tracker que sobrevive, **después** cerrá los redundantes apuntando al consolidador. Un
   **umbrella** se cierra cuando su pasada está completa; si quedan sub-tareas, sobrevive con el checklist
   actualizado.
5. **El dueño dirige, la sesión recomienda.** Proponé la lista de cierres con su razón; el dueño da la
   orden ("borrá 234 476 764…" — ojo a los typos: "476" era probablemente "477"). Ante un número dudoso,
   **confirmá** antes de cerrar.

## Anti-objetivos (cuándo NO es este skill)

- **Refactor de arquitectura** o consolidación del core sagrado → iniciativa propia con plan + Opus,
  no un barrido (`_check_stock_hipotetico` que reimplementa el gate es el caso típico: se reporta como
  follow-up, no se toca acá).
- **Cambios de conducta** disfrazados de limpieza → requieren plan de prueba y aviso.
- **Borrar a ciegas** lo que diga la herramienta → la herramienta da candidatos, no sentencias.

## Cheatsheet (el flow — 4 frentes)

```
A · CÓDIGO (6 fases)                      B · SEGURIDAD + BUGS
1. setup venv + deps + npm ci            1. agente read-only por superficie (authz/inject/SSRF/XSS/core)
2. ruff + vulture + knip → candidatos    2. triage por severidad
3. triage: cazar falsos positivos        3. reproducir el exploit (no parchar lo no explotable)
4. grep repo-wide por cada candidato     4. fix + test de regresión que falla sin él
5. clasificar (puro/DRY/conducta/sagrado)
6. red de tests (pytest[+PG real] / prettier+tsc+eslint+build)

C · RAMAS                                 D · ISSUES
1. mapear rama → PR                       1. listar + agrupar por tópico
2. borrable solo si PR=MERGED             2. cerrar SOLO con evidencia (state_reason + comentario)
   (squash ≠ git branch --merged)        3. no enterrar backlog real (parciales = abiertos)
3. sandbox no borra (403) →              4. consolidar trackers/umbrellas (rescatar únicos primero)
   reportar lista + auto-delete           5. el dueño dirige, la sesión recomienda

CIERRE (todos los frentes): commits atómicos + body con "lo que se dejó" → supervisor → plan de prueba
```
