"""El backup operacional se descarga como `backup-<fecha>.zip`.

Contrato pedido por el dueño: un solo archivo, nombre `backup-fecha.zip`. Este
test blinda el formato del `Content-Disposition` que arma `_zip_response` sin
necesitar DB.
"""
import re

import pytest

from routes.dataio import _zip_response

pytestmark = pytest.mark.unit

_FECHA = re.compile(r"^attachment; filename=\"backup-\d{4}-\d{2}-\d{2}\.zip\"$")


class TestBackupFilename:
    def test_backup_se_llama_backup_fecha_zip(self):
        resp = _zip_response(b"PK\x05\x06", "backup")
        cd = resp.headers["Content-Disposition"]
        assert _FECHA.match(cd), cd

    def test_full_conserva_su_prefijo(self):
        resp = _zip_response(b"PK\x05\x06", "backup-full")
        cd = resp.headers["Content-Disposition"]
        assert re.match(r"^attachment; filename=\"backup-full-\d{4}-\d{2}-\d{2}\.zip\"$", cd), cd
