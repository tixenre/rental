---
name: limpieza
description: Barrido de mantenimiento del repo — encontrar y eliminar código muerto, imports/variables sin usar, archivos huérfanos, dependencias sin uso y duplicación (DRY) con la lógica, el cuidado y la red de tests pertinentes. Úsalo cuando el dueño pida "limpiar", "seguir limpiando", "sacar lo que no se usa", "código muerto / dead code", "housekeeping", "hay cosas legacy dando vueltas", "imports sin usar", "unificar lo duplicado", o cuando vos detectes cruft mientras trabajás. El corazón del skill NO es una lista de ítems a borrar, sino el MÉTODO seguro: herramientas dan candidatos → triage con criterio (cazar falsos positivos) → verificar cada uno → clasificar el tipo de cambio → red de tests (incluido Postgres real para SQL) → commits atómicos → supervisor. NO es para refactors de arquitectura, ni para tocar el core sagrado de reservas/plata en un barrido (eso va como iniciativa propia), ni para "borrar todo lo que la herramienta diga".
---

# limpieza — housekeeping del repo, sin romper nada

Codifica **cómo** se limpia Rambla: no la lista de lo ya limpiado, sino la **lógica, el cuidado y
los tests** para que cada barrido futuro sea seguro. Materializa la _Barra de calidad_ (MEMORIA
*2026-05-25*): modularidad a prueba de balas, nada de hotfixes, y **el core de reservas es sagrado**.

> ## Regla de oro
>
> **Las herramientas dan CANDIDATOS, nunca una lista de borrado.** Nada se elimina sin (1) verificar
> a mano que está realmente muerto y (2) que la **red de tests queda verde**. El gate del dueño es
> *probar en staging*, no leer diffs → **"no romper nada" pesa más que "cuánto limpiamos"**. Ante la
> duda, se **deja y se reporta**, no se borra.

Casos testigo (de por qué la regla existe):

- **knip mintió:** marcó `categories`/`brands` como exports sin usar — tienen **30+ usos reales**; y
  `trackEvent` (uso dinámico desde cart-store/orders).
- **ruff mintió:** marcó `reservas.ESTADOS_RESERVADO` en `routes/alquileres.py` como import sin usar
  → es un **re-export canónico que un test exige** (`test_reservas_sql_safety`). Lo cazó el suite.

La moraleja: la herramienta arranca el trabajo, **el suite y el grep lo terminan**.

---

## El método (6 fases)

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

## Anti-objetivos (cuándo NO es este skill)

- **Refactor de arquitectura** o consolidación del core sagrado → iniciativa propia con plan + Opus,
  no un barrido (`_check_stock_hipotetico` que reimplementa el gate es el caso típico: se reporta como
  follow-up, no se toca acá).
- **Cambios de conducta** disfrazados de limpieza → requieren plan de prueba y aviso.
- **Borrar a ciegas** lo que diga la herramienta → la herramienta da candidatos, no sentencias.

## Cheatsheet (orden de un barrido)

```
1. setup venv + deps + npm ci          5. clasificar (puro / DRY / conducta / sagrado)
2. ruff + vulture + knip → candidatos  6. red de tests (pytest [+Postgres real] / prettier+tsc+eslint+build)
3. triage: cazar falsos positivos      7. commits atómicos + body con "lo que se dejó"
4. grep repo-wide por cada candidato    8. supervisor + plan de prueba
```
