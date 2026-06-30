"""Dataclasses del módulo media."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DeriveSpec:
    """Especificación para derivar una variante a partir del original."""
    name: str    # 'display' | 'square' | 'display-sm' | 'nobg' | 'og' | 'bg:#hex' …
    square: bool  # pasado a _optimize_image
    fmt: str = "webp"  # formato de salida: 'webp' (default) | 'jpeg' (ej. OG para WhatsApp)
    # Ancho/lado máximo de la variante. None = default del pipeline (1200 square /
    # 1600 keep-aspect). Para srcset: variantes más chicas (ej. 'display-sm' a 600).
    max_width: Optional[int] = None


@dataclass
class MediaVariant:
    id: int
    asset_id: int
    name: str
    key: str
    url: str
    content_type: str
    width: int
    height: int
    bytes: int


@dataclass
class MediaAsset:
    id: int
    kind: str
    original_key: Optional[str]
    original_ct: Optional[str]
    width: Optional[int]
    height: Optional[int]
    bytes: Optional[int]
    content_hash: Optional[str] = None
    # LQIP (Low Quality Image Placeholder, F0e): data URI de 4×4px en base64.
    # Se usa como fondo inmediato mientras carga la variante CDN (blur-up en CSS).
    # None si no fue generado (assets pre-F0e o si PIL falló silenciosamente).
    lqip: Optional[str] = None
    # Estado de derivación: 'ready' (variantes OK) | 'pending' (derivando en BG)
    # | 'failed' (derivación falló). Default 'ready' para assets pre-F0g.
    status: str = "ready"
    variants: list[MediaVariant] = field(default_factory=list)

    def variant(self, name: str) -> Optional[MediaVariant]:
        """Devuelve la variante con `name`, o None si no existe."""
        return next((v for v in self.variants if v.name == name), None)
