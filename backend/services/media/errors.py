"""Error de dominio del módulo media — sin acople a ningún framework HTTP."""


class MediaError(Exception):
    """Representa un error recuperable con un código HTTP y mensaje para el usuario.

    El adapter FastAPI (services/media_fastapi.py) lo mapea 1:1 a HTTPException
    con los mismos status/detail que la lógica legacy en image_upload.py.
    """

    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(detail)
