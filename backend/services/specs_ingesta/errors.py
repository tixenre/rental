class ErrorIngesta(ValueError):
    """Error de negocio del embudo de ingesta. HTTP 400."""


class HtmlNoParseable(ErrorIngesta):
    """El HTML no tiene ninguna estructura reconocible (ni JSON-LD ni tablas
    DOM) — no de ninguna fuente conocida. HTTP 422."""
