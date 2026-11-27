"""Ilustración propia para la portada del informe: refinería en silueta al atardecer.

Se dibuja con formas simples (sin fotos ni recursos de terceros) y se guarda en
assets/portada/portada.svg (1280×720). La disposición es determinística (semilla fija) para
que el archivo no cambie entre corridas.

Uso:  python scripts/generar_portada.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "assets" / "portada" / "portada.svg"
W, H = 1280, 720
SUELO = 560  # línea del horizonte de la planta
SIL, SIL_2 = "#0A1426", "#111E36"  # siluetas (más oscura adelante)
LUZ = "#FFC66B"


def _columna(x: float, ancho: float, alto: float, color: str) -> list[str]:
    """Columna de destilación: cilindro con plataformas y escalera."""
    y = SUELO - alto
    out = [f'<rect x="{x:.1f}" y="{y:.1f}" width="{ancho:.1f}" height="{alto:.1f}" '
           f'rx="{ancho / 2.6:.1f}" fill="{color}"/>']
    for k in range(1, int(alto // 38)):
        yp = y + k * 38
        out.append(f'<rect x="{x - 6:.1f}" y="{yp:.1f}" width="{ancho + 12:.1f}" height="2.2" '
                   f'fill="{color}"/>')
    out.append(f'<rect x="{x + ancho + 3:.1f}" y="{y + 10:.1f}" width="1.6" '
               f'height="{alto - 10:.1f}" fill="{color}"/>')
    return out


def _chimenea(x: float, alto: float, color: str, llama: bool = False) -> list[str]:
    y = SUELO - alto
    out = [f'<path d="M{x - 5:.1f} {SUELO} L{x - 2.5:.1f} {y:.1f} L{x + 2.5:.1f} {y:.1f} '
           f'L{x + 5:.1f} {SUELO} Z" fill="{color}"/>']
    if llama:
        out.append(f'<ellipse cx="{x:.1f}" cy="{y - 9:.1f}" rx="4.5" ry="10" fill="#FF9F43" '
                   f'opacity="0.9"/><ellipse cx="{x:.1f}" cy="{y - 6:.1f}" rx="2.2" ry="5.5" '
                   f'fill="#FFE29A"/>')
        out.append(f'<circle cx="{x:.1f}" cy="{y - 8:.1f}" r="26" fill="url(#halo)"/>')
    return out


def _torre_reticulada(x: float, alto: float, color: str) -> list[str]:
    y = SUELO - alto
    out = [f'<path d="M{x - 14:.1f} {SUELO} L{x:.1f} {y:.1f} L{x + 14:.1f} {SUELO}" '
           f'fill="none" stroke="{color}" stroke-width="2.4"/>']
    for k in range(1, 9):
        yy = y + (SUELO - y) * k / 9
        dx = 14 * k / 9
        out.append(f'<path d="M{x - dx:.1f} {yy:.1f} L{x + dx:.1f} {yy:.1f}" stroke="{color}" '
                   f'stroke-width="1.4"/>')
    return out


def _tanque(x: float, ancho: float, alto: float, color: str) -> str:
    return (f'<path d="M{x:.1f} {SUELO} V{SUELO - alto:.1f} Q{x + ancho / 2:.1f} '
            f'{SUELO - alto - 10:.1f} {x + ancho:.1f} {SUELO - alto:.1f} V{SUELO} Z" '
            f'fill="{color}"/>')


def _esfera(x: float, r: float, color: str) -> str:
    return (f'<circle cx="{x:.1f}" cy="{SUELO - r - 14:.1f}" r="{r:.1f}" fill="{color}"/>'
            f'<rect x="{x - r * 0.7:.1f}" y="{SUELO - 16:.1f}" width="2.5" height="16" '
            f'fill="{color}"/><rect x="{x + r * 0.7 - 2.5:.1f}" y="{SUELO - 16:.1f}" '
            f'width="2.5" height="16" fill="{color}"/>')


def svg() -> str:
    rnd = random.Random(2026)
    p: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
        f'height="{H}" preserveAspectRatio="xMidYMid slice">',
        "<defs>",
        '<linearGradient id="cielo" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#0B1F3A"/><stop offset="0.38" stop-color="#2B2E5A"/>'
        '<stop offset="0.6" stop-color="#7A3E5E"/><stop offset="0.74" stop-color="#D2683C"/>'
        '<stop offset="0.8" stop-color="#F29B4C"/><stop offset="1" stop-color="#F7C27A"/>'
        "</linearGradient>",
        '<radialGradient id="sol" cx="0.62" cy="0.78" r="0.35">'
        '<stop offset="0" stop-color="#FFD9A0" stop-opacity="0.85"/>'
        '<stop offset="1" stop-color="#FFD9A0" stop-opacity="0"/></radialGradient>',
        '<radialGradient id="halo"><stop offset="0" stop-color="#FFB45C" stop-opacity="0.55"/>'
        '<stop offset="1" stop-color="#FFB45C" stop-opacity="0"/></radialGradient>',
        '<linearGradient id="suelo" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#0A1426"/><stop offset="1" stop-color="#050B16"/>'
        "</linearGradient>",
        '<linearGradient id="velo" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#0B1F3A" stop-opacity="0.55"/>'
        '<stop offset="0.45" stop-color="#0B1F3A" stop-opacity="0.05"/>'
        '<stop offset="0.8" stop-color="#0B1F3A" stop-opacity="0.15"/>'
        '<stop offset="1" stop-color="#0B1F3A" stop-opacity="0.85"/></linearGradient>',
        "</defs>",
        f'<rect width="{W}" height="{H}" fill="url(#cielo)"/>',
        f'<rect width="{W}" height="{H}" fill="url(#sol)"/>',
    ]
    # estrellas tenues arriba
    for _ in range(70):
        x, y = rnd.uniform(0, W), rnd.uniform(0, 230)
        p.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rnd.uniform(0.4, 1.1):.1f}" '
                 f'fill="#FFFFFF" opacity="{rnd.uniform(0.2, 0.6):.2f}"/>')
    # vetas de nubes
    for _ in range(9):
        x, y = rnd.uniform(-100, W), rnd.uniform(250, 420)
        p.append(f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{rnd.uniform(120, 300):.0f}" '
                 f'ry="{rnd.uniform(4, 9):.0f}" fill="#FFB98A" opacity="0.16"/>')
    # colinas lejanas
    p.append(f'<path d="M0 {SUELO - 40} C 200 {SUELO - 70}, 380 {SUELO - 30}, 560 {SUELO - 52} '
             f'S 940 {SUELO - 28}, 1280 {SUELO - 60} V{SUELO} H0 Z" fill="#3A3557" '
             f'opacity="0.6"/>')
    # planta: fila de fondo (más clara) y fila de adelante (más oscura)
    for fila, color, escala in ((0, SIL_2, 0.72), (1, SIL, 1.0)):
        x = -20 + fila * 30
        while x < W + 40:
            tipo = rnd.choices(["col", "chim", "tanque", "esfera", "torre", "nada"],
                               [0.3, 0.18, 0.22, 0.1, 0.06, 0.14])[0]
            if tipo == "col":
                a = rnd.uniform(26, 40) * escala
                p += _columna(x, a, rnd.uniform(140, 300) * escala, color)
                x += a + rnd.uniform(18, 46)
            elif tipo == "chim":
                p += _chimenea(x, rnd.uniform(180, 330) * escala, color,
                               llama=fila == 1 and rnd.random() < 0.35)
                x += rnd.uniform(24, 50)
            elif tipo == "tanque":
                a = rnd.uniform(60, 110) * escala
                p.append(_tanque(x, a, rnd.uniform(40, 70) * escala, color))
                x += a + rnd.uniform(10, 30)
            elif tipo == "esfera":
                r = rnd.uniform(18, 30) * escala
                p.append(_esfera(x + r, r, color))
                x += 2 * r + rnd.uniform(14, 30)
            elif tipo == "torre":
                p += _torre_reticulada(x + 14, rnd.uniform(200, 300) * escala, color)
                x += 40
            else:
                x += rnd.uniform(20, 60)
    # rack de cañerías y suelo
    p.append(f'<rect x="0" y="{SUELO - 22}" width="{W}" height="4" fill="{SIL}"/>')
    p.append(f'<rect x="0" y="{SUELO - 12}" width="{W}" height="3" fill="{SIL}"/>')
    p.append(f'<rect x="0" y="{SUELO}" width="{W}" height="{H - SUELO}" fill="url(#suelo)"/>')
    # luces de la planta
    for _ in range(260):
        x, y = rnd.uniform(0, W), rnd.uniform(SUELO - 300, SUELO + 6)
        p.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rnd.uniform(0.7, 1.7):.1f}" '
                 f'fill="{LUZ}" opacity="{rnd.uniform(0.35, 0.95):.2f}"/>')
    # reflejos y líneas de perspectiva en el suelo
    for k in range(12):
        x0 = W * k / 11
        p.append(f'<path d="M{x0:.0f} {SUELO} L{W / 2 + (x0 - W / 2) * 3:.0f} {H}" '
                 f'stroke="#1F6FD1" stroke-width="1" opacity="0.18"/>')
    for k in range(1, 6):
        y = SUELO + (H - SUELO) * (k / 6) ** 1.6
        p.append(f'<path d="M0 {y:.0f} H{W}" stroke="#1F6FD1" stroke-width="1" opacity="0.14"/>')
    # velo navy para que se lea el texto encima
    p.append(f'<rect width="{W}" height="{H}" fill="url(#velo)"/>')
    p.append("</svg>")
    return "".join(p)


def generar() -> Path:
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(svg(), encoding="utf-8")
    return SALIDA


if __name__ == "__main__":
    s = generar()
    print(f"portada -> {s.relative_to(RAIZ)} ({s.stat().st_size // 1024} KB)")
    sys.exit(0)
