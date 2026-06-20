"""Regresión: FRONT_NEW (dist del SPA) debe apuntar a la RAÍZ del repo.

El Dockerfile copia el build del frontend a `/app/dist` (raíz). `_serve_frontend`
busca `FRONT_NEW / index.html`; si FRONT_NEW apunta mal, el backend devuelve
`{"error":"Frontend not built"}` (503) y el sitio público queda caído.

El split de `database.py` → paquete `database/` (#501) bajó `core.py` un nivel, y
las paths relativas a `__file__` quedaron apuntando a `backend/dist` en vez de
`<raíz>/dist`. Dormido en staging (el frontend de dev lo sirve Vercel), fatal en
prod (Railway sirve el SPA). Este test es hermético y falla con la regresión.
"""
import pytest

pytestmark = pytest.mark.unit


def test_front_new_apunta_a_la_raiz_del_repo():
    from database import FRONT_NEW

    assert FRONT_NEW.name == "dist"
    # `dist` es hermano de `backend/` en la raíz (/app en Docker). Si FRONT_NEW
    # apuntara a backend/dist, su padre sería backend/ y no tendría un backend/ dentro.
    assert (FRONT_NEW.parent / "backend").is_dir(), (
        f"FRONT_NEW={FRONT_NEW} no está en la raíz del repo "
        f"(el Dockerfile pone el dist en /app/dist) → 'Frontend not built'"
    )


def test_front_clasico_apunta_a_la_raiz():
    from database import FRONT

    assert FRONT.parts[-2:] == ("frontend", "public")
    assert (FRONT.parent.parent / "backend").is_dir(), (
        f"FRONT={FRONT} no está en la raíz del repo"
    )
