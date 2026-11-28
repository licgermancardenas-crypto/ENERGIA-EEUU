"""Optimiza las fotos del scrollytelling de la portada (AVIF + WebP en 3 anchos y un placeholder
borroso). La web es un export estático: next/image no optimiza en build, así que se hace acá.

    python -I scripts/optimizar_imagenes_historia.py data/descargas/historia web/public/historia

Entrada: <origen>/<clave>/original.jpg (descargas de Wikimedia Commons, ver IMAGE_CREDITS.md).
Salida: <destino>/<clave>-<ancho>.avif|.webp y <destino>/placeholders.json (data URI 24 px).
"""

import base64
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageFilter

ANCHOS = (640, 1280, 1920)
CALIDAD = {"avif": 50, "webp": 72}


def main(origen: Path, destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    placeholders = {}
    for carpeta in sorted(p for p in origen.iterdir() if p.is_dir()):
        src = next(carpeta.glob("original.*"))
        img = Image.open(src).convert("RGB")
        clave = carpeta.name
        for w in ANCHOS:
            if w > img.width:
                w = img.width
            h = round(img.height * w / img.width)
            r = img.resize((w, h), Image.LANCZOS)
            for fmt, q in CALIDAD.items():
                r.save(destino / f"{clave}-{w}.{fmt}", fmt.upper(), quality=q)
        chica = img.resize((24, round(img.height * 24 / img.width)), Image.LANCZOS).filter(ImageFilter.GaussianBlur(1))
        b = io.BytesIO()
        chica.save(b, "WEBP", quality=40)
        placeholders[clave] = {"blur": "data:image/webp;base64," + base64.b64encode(b.getvalue()).decode(),
                               "ancho": img.width, "alto": img.height,
                               "anchos": sorted({min(w, img.width) for w in ANCHOS})}
        print(clave, img.size)
    (destino / "placeholders.json").write_text(json.dumps(placeholders, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
