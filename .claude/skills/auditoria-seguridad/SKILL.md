---
name: auditoria-seguridad
description: Auditor de seguridad — evalúa sistemáticamente la postura de seguridad de la app (OWASP Top 10, auth/sesiones, CORS/headers, validación de inputs, secretos, dependencias vulnerables). Lee y razona; nunca toca código. Disparadores: "auditá la seguridad", "hay vulnerabilidades?", "está seguro el auth?", "revisá CORS y headers", "qué tan vulnerable está?", "OWASP", "revisá las dependencias". NO busca bugs de negocio (→ auditoria-profunda), NO audita performance (→ performance), NO revisa código muerto (→ mantenimiento).
model: opus
last-reviewed: 2026-06-23
version: 1.0
---

# auditoria-seguridad — auditor de seguridad de la app

Rambla maneja datos de clientes, pagos y sesiones autenticadas. Este skill evalúa la **postura de
seguridad** de forma sistemática: busca vulnerabilidades reales antes de que las encuentre alguien
que no debería. Read-only — propone issues con severidad; el dueño aprueba; la sesión aplica.

## Dónde encaja (no dupliques: delegá)

| Skill | Pregunta que responde | Zona |
|---|---|---|
| **`auditoria-seguridad`** (este) | "¿está seguro?" | OWASP, auth, headers, inputs, secretos, deps |
| `mantenimiento` | "¿hay deuda?" | Frente B: scan superficial de seguridad básica |
| `auditoria-profunda` | "¿tiene fallas?" | Bugs de flujo de negocio, edge cases |
| `calidad-codigo` | "¿bien escrito?" | Patterns de código, tipado, complejidad |
| `performance` | "¿está rápido?" | Bundle, DB, Core Web Vitals |

`mantenimiento` (Frente B) hace un sweep superficial — este skill profundiza con el método OWASP.

## El método: leer → evaluar → proponer

### 1 · Auth & sesiones

Leer `backend/auth.py` (o el módulo de auth) y verificar:

- **Cookie firmada**: ¿usa `itsdangerous`/`cryptography` o similar? ¿la clave es `SECRET_KEY` de env?
- **Expiración**: ¿las cookies/tokens tienen expiración razonable (no "never")?
- **HttpOnly + Secure + SameSite**: ¿la cookie de sesión tiene los tres atributos?
- **Logout**: ¿el logout invalida el token/cookie en el servidor (no solo en el cliente)?
- **Staging-login** (`/auth/staging-login`): ¿el doble gate (`is_production` + `STAGING_LOGIN_SECRET`) está intacto?

```bash
grep -rn 'set_cookie\|httponly\|samesite\|secure' backend/ --include="*.py" -i
grep -rn 'SECRET_KEY\|STAGING_LOGIN_SECRET' backend/ --include="*.py"
grep -rn 'expires\|max_age\|SESSION_EXPIRE' backend/ --include="*.py"
```

### 2 · CORS

```bash
grep -rn 'CORSMiddleware\|allow_origins\|allow_credentials' backend/ --include="*.py"
```

Verificar: ¿`allow_origins` es lista explícita o `["*"]`? ¿`allow_credentials=True` con `allow_origins=["*"]`
(combinación inválida y peligrosa)? ¿los dominios permitidos son solo los de prod/staging?

### 3 · Headers de seguridad HTTP

Verificar en `backend/middleware.py` o similar:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY` (o CSP `frame-ancestors`)
- `Referrer-Policy`
- `Content-Security-Policy` (CSP) — al menos bloquear `object-src 'none'`
- `Strict-Transport-Security` (HSTS) — solo relevante en prod/Railway

```bash
grep -rn 'X-Content-Type\|X-Frame\|Content-Security-Policy\|Strict-Transport\|Referrer-Policy' backend/ --include="*.py"
```

Si no hay un middleware de headers de seguridad → proponer agregar uno.

### 4 · Validación de inputs (SQL injection / XSS / IDOR)

**SQL injection:**
```bash
# Queries con f-string o concatenación (señal de riesgo)
grep -rn 'f"SELECT\|f"INSERT\|f"UPDATE\|f"DELETE\|" + table\|% table' backend/ --include="*.py"
# Verificar que todas las queries vayan por parámetros ORM o `text()` con bind params
grep -rn 'execute.*f"\|execute.*%.*%' backend/ --include="*.py"
```

**IDOR (Insecure Direct Object Reference):** ¿los endpoints que reciben un `id` verifican que
pertenezca al usuario autenticado antes de responder/modificar?

```bash
# Endpoints que reciben pedido_id / equipo_id y no verifican ownership
grep -rn 'pedido_id\|equipo_id\|cliente_id' backend/ --include="*.py" -A3 | grep -v 'WHERE.*cliente\|is_admin\|check_owner'
```

**XSS en React:** React escapa por defecto. Revisar `dangerouslySetInnerHTML`:
```bash
grep -rn 'dangerouslySetInnerHTML' frontend/src/ --include="*.tsx" --include="*.ts"
```

### 5 · Secretos y configuración

```bash
# Secretos hardcodeados en código (no en .env)
grep -rn 'password\s*=\s*"\|secret\s*=\s*"\|api_key\s*=\s*"' backend/ --include="*.py" | grep -v 'os.getenv\|os.environ\|settings\.'

# .env en gitignore
cat .gitignore | grep -E '\.env|\.secret'
```

Verificar que `backend/config.py` (o settings) cargue todo desde env vars, no defaults hardcodeados
en prod (los defaults para dev son ok si hay una guard de `is_production`).

### 6 · Dependencias vulnerables

```bash
# Frontend
cd frontend && npm audit --json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
vulns = data.get('vulnerabilities', {})
for name, v in vulns.items():
    sev = v.get('severity', 'unknown')
    if sev in ('high', 'critical'):
        print(f'  [{sev.upper()}] {name}: {v.get(\"title\", \"\")}')
" 2>/dev/null || npm audit 2>&1 | grep -E 'high|critical|moderate'

# Backend
cd backend && pip-audit --json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
for v in data.get('dependencies', []):
    for vuln in v.get('vulns', []):
        print(f'  [{v[\"name\"]}] {vuln[\"id\"]}: {vuln[\"description\"][:80]}')
" 2>/dev/null || pip-audit 2>&1 | head -30
```

### 7 · Rate limiting

```bash
grep -rn 'slowapi\|limiter\|rate_limit\|RateLimiter' backend/ --include="*.py"
```

¿Hay rate limiting en endpoints sensibles (`/auth/login`, `/auth/staging-login`, reset de contraseña)?
Sin rate limiting → fuerza bruta es trivial.

### 8 · Reporte con severidad CVSS-lite

```
SEGURIDAD — <fecha>
────────────────────
Auth: <ok / hallazgos>
CORS: <ok / hallazgos>
Headers HTTP: <N faltantes>
SQL injection: <ok / hallazgos>
IDOR: <ok / hallazgos>
XSS: <ok / hallazgos>
Secretos: <ok / hallazgos>
Deps: <N high, M critical>
Rate limiting: <ok / ausente en N endpoints>

🔴 Crítico (exploitable ahora):
  - ...

🟡 Medio (riesgo real, menos probable):
  - ...

🟢 Info / bajo:
  - ...

✅ OK:
  - ...

Propuestas (esperando aprobación):
  1. "Seguridad: agregar headers HTTP (X-Frame, CSP, nosniff)" → middleware único
  2. "Seguridad: rate limiting en /auth/login" → N intentos / min
  ...
```

**No crea issues sin confirmación** — muestra los drafts, el dueño aprueba.

## Regla de oro

**Confirmar antes de reportar.** Un grep de `execute(f"` puede ser una query parametrizada mal
formateada en el log. Leer el código completo antes de elevar a 🔴. Un falso positivo de seguridad
erosiona la confianza más que uno perdido.

**Staging-login está documentado y guardado**: la decisión 2026-06-19 lo blinda con doble gate.
No reportarlo como vulnerabilidad — es intencional y tiene guardas.

## Anti-objetivos

- **Bugs de negocio** → `auditoria-profunda`.
- **Código mal escrito** → `calidad-codigo`.
- **Performance** → `performance`.
- **Aplicar los fixes** → la sesión aplica tras aprobación del dueño.

## Auto-mejora (correr al cerrar cada uso)

¿Aparecieron vectores de ataque que no están cubiertos en el método? ¿Cambió el stack (nueva dep,
nuevo endpoint, nuevo auth flow)? ¿Algún hallazgo fue falso positivo porque el código tenía una
guarda que los greps no cacharon?

Si **SÍ** → anotar en [`docs/PROPUESTAS_SKILLS.md`](../../../docs/PROPUESTAS_SKILLS.md).
Si **NO** → no fabriques churn. **Honestidad > actividad.**

## Cheatsheet

```
Disparadores: "auditá la seguridad", "hay vulnerabilidades?", "seguro el auth?",
              "CORS/headers", "qué tan vulnerable?", "OWASP", "dependencias"

8 frentes:
  1. Auth: cookie attrs, expiración, logout, staging-login gate
  2. CORS: origins explícitos, no * con credentials
  3. Headers HTTP: nosniff, X-Frame, CSP, HSTS, Referrer-Policy
  4. Inputs: SQL inject (f-string queries), IDOR, XSS (dangerouslySetInnerHTML)
  5. Secretos: nada hardcodeado, .env gitignored
  6. Deps: npm audit + pip-audit high/critical
  7. Rate limiting: login + endpoints sensibles
  8. Reporte 🔴/🟡/🟢/✅ + draft issues → dueño aprueba
```
