"""Prepara la foto de fondo de la portada: recorte 16:9, velo navy y JPG liviano.

Foto: "Oil Refinery" (Porvoo, Finlandia), de Carlos "Grury" Santos, publicada en Unsplash
(https://unsplash.com/photos/Z8rvuexdWJU) bajo la Unsplash License (uso libre, también
comercial). El original queda fuera del repo, en data/geo/entrada/portada/.

Uso:  python scripts/preparar_foto_portada.py [ruta_original]
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
ORIGEN = RAIZ / "data" / "geo" / "entrada" / "portada" / "porvoo_unsplash.jpg"
SALIDA = RAIZ / "assets" / "portada" / "portada.jpg"
W, H = 1280, 720
NAVY = (11, 31, 58)
CREDITO = 'Foto: Carlos "Grury" Santos · Unsplash'


def _velo(w: int, h: int) -> Image.Image:
    """Capa navy semitransparente: más densa arriba a la izquierda (título) y abajo (paneles)."""
    alfa = Image.new("L", (w, h))
    px = alfa.load()
    for y in range(h):
        fy = y / (h - 1)
        vertical = 0.55 * max(0.0, 1 - fy / 0.45) + 0.80 * max(0.0, (fy - 0.62) / 0.38)
        for x in range(w):
            fx = x / (w - 1)
            izquierda = 0.35 * max(0.0, 1 - fx / 0.6)
            px[x, y] = int(255 * min(0.9, 0.12 + vertical + izquierda))
    capa = Image.new("RGBA", (w, h), (*NAVY, 0))
    capa.putalpha(alfa)
    return capa


def preparar(origen: Path = ORIGEN, salida: Path = SALIDA, ancla_x: float = 1.0) -> Path:
    img = Image.open(origen).convert("RGB")
    # recorte 16:9 anclado a la derecha (ahí está la refinería)
    ancho = min(img.width, round(img.height * W / H))
    alto = round(ancho * H / W)
    x0 = round((img.width - ancho) * ancla_x)
    y0 = (img.height - alto) // 2
    img = img.crop((x0, y0, x0 + ancho, y0 + alto)).resize((W, H), Image.LANCZOS)
    img = Image.alpha_composite(img.convert("RGBA"), _velo(W, H)).convert("RGB")
    salida.parent.mkdir(parents=True, exist_ok=True)
    img.save(salida, "JPEG", quality=82, optimize=True, progressive=True)
    return salida


if __name__ == "__main__":
    s = preparar(Path(sys.argv[1]) if len(sys.argv) > 1 else ORIGEN)
    print(f"portada -> {s.relative_to(RAIZ)} ({s.stat().st_size // 1024} KB)")
