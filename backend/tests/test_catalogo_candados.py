"""Motor de catálogo — candados estáticos (sin opt-in de BD).

Inspección de fuente: verifican que los invariantes de delegación se cumplen
en el código, sin levantar servidor ni conexión. Corren en el suite default.

Candado C1: main._get_initial_catalog no hace FROM equipos (delega en proyectar_seed).
"""
import inspect

import pytest

pytestmark = pytest.mark.unit


class TestSeedShape:
    def test_main_no_query_equipos(self):
        """Candado C1: main._get_initial_catalog delega en proyectar_seed
        y no arma su propio SQL contra equipos.

        Si este test falla, main volvió a tener SQL inline contra equipos
        en vez de delegar al motor (puerta única del catálogo).
        """
        import main as main_module

        src = inspect.getsource(main_module._get_initial_catalog).lower()
        assert "from equipos" not in src, (
            "main._get_initial_catalog arma SQL directo contra equipos — "
            "debe delegar en proyectar_seed (puerta única del motor de catálogo)"
        )
