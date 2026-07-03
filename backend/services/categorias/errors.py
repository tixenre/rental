class ErrorValidacion(ValueError):
    """Error de validación de negocio. HTTP 400."""


class CategoriaNoExiste(ErrorValidacion):
    """La categoría referenciada no existe. HTTP 404."""


class NombreDuplicado(ErrorValidacion):
    """Ya existe otra categoría con el mismo nombre. HTTP 409."""
