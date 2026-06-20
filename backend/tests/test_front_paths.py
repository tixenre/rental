"""Regresión: FRONT_NEW (dist del SPA) debe apuntar a `frontend/dist` en la RAÍZ.

El Dockerfile copia el build del frontend a `/app/frontend/dist`. `_serve_frontend`
busca `FRONT_NEW / index.html`; si FRONT_NEW apunta mal, el backend devuelve
`{"error":"Frontend not built"}` (503) y el sitio público queda caído.

El split de `database.py` → paquete `database/` (#501) bajó `core.py` un nivel, y
las paths relativas a `__file__` quedaron apuntando a `backend/dist` en vez de
la raíz. Más tarde el frontend se mudó de la raíz a `frontend/` (simétrico a
`backend/`), así que el `dist` ahora vive en `frontend/dist`. Railway sirve el SPA
tanto en staging como en prod, así que la regresión sería fatal en ambos. Este
test es hermético y falla con la regresión.
"""
import pytest

pytestmark = pytest.mark.unit


def test_front_new_apunta_a_frontend_dist_en_la_raiz():
    from database import FRONT_NEW

    assert FRONT_NEW.name == "dist"
    # `dist` vive en `frontend/` (FRONT_NEW.parent), y `frontend/` es hermano de
    # `backend/` en la raíz (/app en Docker). Si FRONT_NEW apuntara a backend/dist
    # o a la raíz/dist, esta cadena de padres no encontraría backend/.
    assert FRONT_NEW.parent.name == "frontend", (
        f"FRONT_NEW={FRONT_NEW} no cuelga de frontend/"
    )
    assert (FRONT_NEW.parent.parent / "backend").is_dir(), (
        f"FRONT_NEW={FRONT_NEW} no está en frontend/ de la raíz del repo "
        f"(el Dockerfile pone el dist en /app/frontend/dist) → 'Frontend not built'"
    )


def test_front_clasico_apunta_a_la_raiz():
    from database import FRONT

    assert FRONT.parts[-2:] == ("frontend", "public")
    assert (FRONT.parent.parent / "backend").is_dir(), (
        f"FRONT={FRONT} no está en la raíz del repo"
    )
