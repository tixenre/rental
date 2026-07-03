class ErrorSpec(ValueError):
    """Error de validación de negocio. HTTP 400."""


class SpecNoExiste(ErrorSpec):
    """El spec_definition referenciado no existe. HTTP 404."""


class ValorNoCanonico(ErrorSpec):
    """El value no matchea enum_options ni un alias conocido en
    spec_value_aliases. HTTP 400. Ver docs/PLAN_SPECS_REDISENO.md — Fase 3
    (el embudo) antes de que esto se levante en la práctica."""
