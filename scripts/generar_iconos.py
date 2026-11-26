"""Fuente única de los íconos del informe: escribe assets/icons/*.svg, su índice y dax/iconos.dax.

Un solo estilo: grilla 24×24, trazo 2, extremos y uniones redondeados, sin relleno (salvo
detalles puntuales). El color lo pone cada uso según la familia (petróleo, gas, estado).

Uso:  python scripts/generar_iconos.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

RAIZ = Path(__file__).resolve().parents[1]
DIR_ICONOS = RAIZ / "assets" / "icons"
DAX = RAIZ / "dax" / "iconos.dax"
TABLA = "dim_serie"

# Familias de color (paleta del proyecto)
PETROLEO, GAS, OK, ALERTA, ERROR = "#C4531A", "#1F6FD1", "#1D7A3B", "#A35400", "#B42318"
TINTA_3, BLANCO, NAVY = "#7A8394", "#FFFFFF", "#0B1F3A"

# ---------------------------------------------------------------- íconos (cuerpo SVG)
ICONOS: dict[str, tuple[str, str]] = {
    # nombre: (cuerpo, descripción)
    "pulso": ('<polyline points="3 12 7 12 10 5 14 19 17 12 21 12"/>', "Pulso (Resumen)"),
    "gota": ('<path d="M12 3c0 0-6.5 7.2-6.5 11.5a6.5 6.5 0 0 0 13 0C18.5 10.2 12 3 12 3z"/>',
             "Gota de petróleo"),
    "llama": ('<path d="M12 2.5c.6 3.6 6.5 5.8 6.5 11.7a6.5 6.5 0 0 1-13 0c0-3 1.5-4.9 3-6'
              ' .3 2.4 1.3 3.6 2.8 3.6 0-3.5-1-6.2.7-9.3z"/>', "Llama de gas"),
    "reloj": ('<circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15.5 14"/>',
              "Reloj (rezago, atraso)"),
    "escudo-check": ('<path d="M12 3l7 3v5c0 4.6-3 8.3-7 10-4-1.7-7-5.4-7-10V6z"/>'
                     '<polyline points="9 12 11.2 14.2 15.5 9.8"/>', "Escudo con check (Calidad)"),
    "tendencia-sube": ('<polyline points="3 17 9 11 13 15 21 7"/>'
                       '<polyline points="15 7 21 7 21 13"/>',
                       "Tendencia en alza"),
    "tendencia-baja": ('<polyline points="3 7 9 13 13 9 21 17"/>'
                       '<polyline points="15 17 21 17 21 11"/>',
                       "Tendencia en baja"),
    "flechas-opuestas": ('<path d="M4 8h14M14 4l4 4-4 4"/><path d="M20 16H6M10 12l-4 4 4 4"/>',
                         "Flechas opuestas (diferencial)"),
    "tanque": ('<ellipse cx="12" cy="6.5" rx="7" ry="2.5"/><path d="M5 6.5v11c0 1.4 3.1 2.5 7 '
               '2.5s7-1.1 7-2.5v-11"/><path d="M5 12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5"/>',
               "Tanque de crudo"),
    "cilindro": ('<rect x="7" y="4" width="10" height="17" rx="5"/><path d="M10 4V2.5h4V4"/>'
                 '<path d="M7 11h10"/>', "Cilindro de gas"),
    "flecha-sube": ('<path d="M12 19V5"/><polyline points="6 11 12 5 18 11"/>', "Flecha arriba"),
    "flecha-baja": ('<path d="M12 5v14"/><polyline points="6 13 12 19 18 13"/>', "Flecha abajo"),
    "rayo": ('<path d="M13 2L4.5 13.5H12L11 22l8.5-11.5H12z"/>', "Rayo (generación eléctrica)"),
    "boveda": ('<path d="M12 3l7 3v5c0 4.6-3 8.3-7 10-4-1.7-7-5.4-7-10V6z"/>'
               '<circle cx="12" cy="10.5" r="1.8"/><path d="M12 12.3V15.5"/>',
               "Escudo con cerradura (reserva estratégica)"),
    "surtidor": ('<path d="M4 21V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v16"/><path d="M3 21h12"/>'
                 '<path d="M4 10h10"/><path d="M14 8h1.5a2 2 0 0 1 2 2v6a1.5 1.5 0 0 0 3 0V8.5'
                 'L17.5 5.5"/>', "Surtidor de combustible"),
    "alerta": ('<path d="M10.3 4.2L2.6 18a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 '
               '0-3.4 0z"/><path d="M12 9.5v4"/><path d="M12 17h.01"/>', "Alerta"),
    "copo": ('<path d="M12 2v20M3.3 7l17.4 10M3.3 17L20.7 7"/><path d="M9.5 3.5L12 6l2.5-2.5'
             'M9.5 20.5L12 18l2.5 2.5"/>', "Copo de nieve (invierno, extracción)"),
    "sol": ('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 '
            '17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
            "Sol (verano, inyección)"),
    "casa": ('<path d="M3 11l9-8 9 8"/><path d="M5 9.5V21h14V9.5"/><path d="M10 21v-6h4v6"/>',
             "Casa (residencial)"),
    "edificio": ('<rect x="5" y="3" width="14" height="18" rx="1"/><path d="M9 7h1M14 7h1M9 11h1'
                 'M14 11h1M9 15h1M14 15h1M11 21v-3h2v3"/>', "Edificio (comercial)"),
    "fabrica": ('<path d="M3 21V10l5 3v-3l5 3v-3l5 3V4h3v17z"/><path d="M7 17h1M11 17h1M15 17h1"/>',
                "Fábrica (industrial)"),
    "auto": ('<path d="M5 16v-3.5L7 8h10l2 4.5V16"/><path d="M3.5 16h17"/><circle cx="8" '
             'cy="17.5" r="1.5"/><circle cx="16" cy="17.5" r="1.5"/>', "Auto (vehicular)"),
    "info": ('<circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8h.01"/>',
             "Información"),
    "torre": ('<path d="M6.5 21L12 3l5.5 18"/><path d="M8.3 15h7.4M9.8 9.5h4.4"/>'
              '<path d="M3.5 21h17"/><path d="M8.3 15l5.9 6M15.7 15l-5.9 6"/>',
              "Torre de perforación (producción)"),
    "calendario": ('<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4'
                   'M16 3v4"/>', "Calendario (frecuencia)"),
    "check-circulo": ('<circle cx="12" cy="12" r="9"/><polyline points="8 12.3 10.8 15 16 9.5"/>',
                      "Check (al día)"),
    "x-circulo": ('<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
                  "X (atrasada)"),
}

# Dónde se usa cada ícono (para el índice)
USOS: dict[str, str] = {
    "pulso": "Encabezado de Resumen; botón Resumen",
    "gota": "Encabezado de Petróleo; botón Petróleo; sección PETRÓLEO; KPI WTI; diagrama de Rezago",
    "llama": "Encabezado de Gas; botón Gas; sección GAS NATURAL; KPI Henry Hub",
    "reloj": "Encabezado de Rezago; botón Rezago; KPI rezago óptimo; diagrama; estado ámbar",
    "escudo-check": "Encabezado de Calidad; botón Calidad",
    "tendencia-sube": "KPIs de variación (signo +)",
    "tendencia-baja": "KPIs de variación (signo −)",
    "flechas-opuestas": "KPI Brent − WTI",
    "tanque": "KPI crudo comercial",
    "cilindro": "KPI gas almacenado",
    "flecha-sube": "KPI inyección neta (positiva)",
    "flecha-baja": "KPI inyección neta (negativa)",
    "rayo": "KPI generación eléctrica; leyenda de consumo",
    "boveda": "KPI reserva estratégica (SPR)",
    "surtidor": "Título de Precio en surtidor",
    "alerta": "Nota de la reserva estratégica 2026; KPI fuentes atrasadas; aviso de causalidad",
    "copo": "Nota de picos de invierno del Henry Hub; ciclo de almacenamiento (extracción)",
    "sol": "Ciclo de almacenamiento (inyección)",
    "casa": "Leyenda de consumo: residencial",
    "edificio": "Leyenda de consumo: comercial",
    "fabrica": "Leyenda de consumo: industrial",
    "auto": "Leyenda de consumo: vehicular",
    "info": "Caja Cómo leerlo; nota de COVID 2020",
    "torre": "Diagrama de Rezago (producción)",
    "calendario": "Tabla de frescura: frecuencia",
    "check-circulo": "Tabla de frescura: al día; KPI fuentes al día",
    "x-circulo": "Tabla de frescura: atrasada",
}


def svg(nombre: str, color: str = "currentColor", tam: int = 24) -> str:
    """SVG completo de un ícono, con comillas simples (apto para data URI y DAX)."""
    cuerpo = ICONOS[nombre][0].replace('"', "'")
    return (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='{tam}' "
            f"height='{tam}' fill='none' stroke='{color}' stroke-width='2' "
            f"stroke-linecap='round' stroke-linejoin='round'>{cuerpo}</svg>")


def data_uri(svg_texto: str) -> str:
    """data:image/svg+xml;utf8 con los caracteres conflictivos escapados (#, %, <, >)."""
    return "data:image/svg+xml;utf8," + quote(svg_texto, safe=" '=:/;,.-()_")


def dax_str(s: str) -> str:
    return '"' + s.replace('"', '""') + '"'


# ---------------------------------------------------------------- medidas DAX
@dataclass
class MedidaIcono:
    nombre: str
    expresion: str
    comentario: str


def _icono_fijo(nombre_medida: str, icono: str, color: str, comentario: str) -> MedidaIcono:
    return MedidaIcono(nombre_medida, dax_str(data_uri(svg(icono, color, 20))), comentario)


def _uri_dax(svg_dax: str) -> str:
    """Envuelve una expresión DAX que arma SVG (texto) en un data URI escapado en DAX."""
    return ('"data:image/svg+xml;utf8," & SUBSTITUTE ( SUBSTITUTE ( SUBSTITUTE ( '
            f'{svg_dax}, "%", "%25" ), "#", "%23" ), "<", "%3C" )')


def _flecha(nombre: str, medida: str, color: str, comentario: str) -> MedidaIcono:
    sube, baja = (dax_str(data_uri(svg(n, color, 20))) for n in ("tendencia-sube",
                                                                  "tendencia-baja"))
    expr = (f"VAR v = [{medida}]\nRETURN\n    SWITCH ( TRUE (), ISBLANK ( v ), BLANK (), "
            f"v >= 0, {sube}, {baja} )")
    return MedidaIcono(nombre, expr, comentario)


def medidas() -> list[MedidaIcono]:
    ms: list[MedidaIcono] = []
    # Encabezados de página (blanco sobre la banda navy)
    for icono, pag in [("pulso", "Resumen"), ("gota", "Petróleo"), ("llama", "Gas"),
                       ("reloj", "Rezago"), ("escudo-check", "Calidad")]:
        ms.append(_icono_fijo(f"Ícono página {pag}", icono, BLANCO,
                              f"Ícono del encabezado de la página {pag}"))
    # Secciones y KPIs fijos
    fijos = [
        ("Ícono sección petróleo", "gota", PETROLEO, "Encabezado de sección PETRÓLEO"),
        ("Ícono sección gas", "llama", GAS, "Encabezado de sección GAS NATURAL"),
        ("Ícono WTI", "gota", PETROLEO, "KPI Último WTI"),
        ("Ícono Brent-WTI", "flechas-opuestas", PETROLEO, "KPI Diferencial Brent-WTI"),
        ("Ícono crudo comercial", "tanque", PETROLEO, "KPI Stock crudo comercial"),
        ("Ícono reserva estratégica", "boveda", PETROLEO, "KPI Stock SPR"),
        ("Ícono surtidor", "surtidor", PETROLEO, "Título de Precio en surtidor"),
        ("Ícono Henry Hub", "llama", GAS, "KPI Último Henry Hub"),
        ("Ícono gas almacenado", "cilindro", GAS, "KPI Gas almacenado Lower 48"),
        ("Ícono generación eléctrica", "rayo", GAS, "KPI Participación generación eléctrica %"),
        ("Ícono reloj rezago", "reloj", PETROLEO, "KPI Rezago óptimo (meses)"),
        ("Ícono info", "info", GAS, "Caja Cómo leerlo"),
        ("Ícono alerta", "alerta", ALERTA, "Notas de alerta (SPR 2026, causalidad)"),
        ("Ícono invierno", "copo", GAS, "Nota de picos de invierno / extracción"),
        ("Ícono verano", "sol", ALERTA, "Nota de inyección en verano"),
        ("Ícono fuentes al día", "check-circulo", OK, "KPI Fuentes al día"),
    ]
    ms += [_icono_fijo(*f) for f in fijos]
    # Flechas de tendencia según el signo
    for nombre, medida, color in [
        ("Flecha WTI vs promedio 12 meses", "WTI vs promedio 12 meses %", PETROLEO),
        ("Flecha crudo vs año anterior", "Crudo comercial vs año anterior %", PETROLEO),
        ("Flecha variación semanal crudo", "Variación semanal crudo comercial", PETROLEO),
        ("Flecha Henry Hub vs promedio 12 meses", "Henry Hub vs promedio 12 meses %", GAS),
        ("Flecha almacenamiento vs año anterior", "Almacenamiento vs año anterior %", GAS),
    ]:
        ms.append(_flecha(nombre, medida, color, f"▲/▼ según el signo de [{medida}]"))
    # Inyección neta: flecha arriba/abajo
    arriba, abajo = (dax_str(data_uri(svg(n, GAS, 20))) for n in ("flecha-sube", "flecha-baja"))
    ms.append(MedidaIcono(
        "Ícono inyección neta",
        f"VAR v = [Inyección neta semanal]\nRETURN\n    SWITCH ( TRUE (), ISBLANK ( v ), BLANK (), "
        f"v >= 0, {arriba}, {abajo} )",
        "Flecha arriba si se inyectó gas en la semana, abajo si se extrajo"))
    # Fuentes atrasadas: alerta gris si 0, roja si > 0
    gris, rojo = (dax_str(data_uri(svg("alerta", c, 20))) for c in (TINTA_3, ERROR))
    ms.append(MedidaIcono("Ícono fuentes atrasadas",
                          f"IF ( [Fuentes atrasadas] > 0, {rojo}, {gris} )",
                          "Alerta roja si hay fuentes atrasadas; gris si no"))
    # Semáforo de frescura (fila de la tabla)
    ok_, amb, err = (dax_str(data_uri(svg(n, c, 20))) for n, c in
                     (("check-circulo", OK), ("reloj", ALERTA), ("x-circulo", ERROR)))
    ms.append(MedidaIcono(
        "Semáforo de frescura",
        "VAR a = SELECTEDVALUE ( frescura[dias_atraso] )\n"
        "VAR u = SELECTEDVALUE ( frescura[umbral_dias] )\nRETURN\n    SWITCH (\n        TRUE (),\n"
        "        ISBLANK ( a ) || ISBLANK ( u ), BLANK (),\n"
        f"        a > u, {err},\n        a >= 0.8 * u, {amb},\n        {ok_}\n    )",
        "Check verde (al día), reloj ámbar (≥ 80 % del umbral) o X roja (supera el umbral)"))
    # Calendario por frecuencia
    cal = ("VAR f = SELECTEDVALUE ( frescura[frecuencia] )\n"
           "VAR letra = SWITCH ( f, \"daily\", \"D\", \"weekly\", \"S\", \"monthly\", \"M\" )\n"
           "VAR s =\n    \"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='20' "
           f"height='20' fill='none' stroke='{TINTA_3}' stroke-width='2' stroke-linecap='round' "
           "stroke-linejoin='round'>"
           + ICONOS["calendario"][0].replace('"', "'")
           + f"<text x='12' y='18.5' text-anchor='middle' font-family='Segoe UI' font-size='8' "
             f"font-weight='700' fill='{TINTA_3}' stroke='none'>\" & letra & \"</text></svg>\"\n"
           "RETURN\n    IF ( ISBLANK ( letra ), BLANK (), " + _uri_dax("s") + " )")
    ms.append(MedidaIcono("Ícono frecuencia", cal,
                          "Calendario con D (diaria), S (semanal) o M (mensual)"))
    # Barra de atraso vs umbral
    barra = (
        "VAR a = SELECTEDVALUE ( frescura[dias_atraso] )\n"
        "VAR u = SELECTEDVALUE ( frescura[umbral_dias] )\n"
        "VAR r = MIN ( DIVIDE ( a, u ), 1.25 )\n"
        "VAR ancho = 120\n"
        "-- FORMAT con en-US: el modelo es es-AR y el SVG necesita punto decimal\n"
        "VAR w = FORMAT ( r / 1.25 * ancho, \"0.0\", \"en-US\" )\n"
        "VAR xu = FORMAT ( 1 / 1.25 * ancho, \"0.0\", \"en-US\" )\n"
        f"VAR c = SWITCH ( TRUE (), a > u, \"{ERROR}\", a >= 0.8 * u, \"{ALERTA}\", \"{OK}\" )\n"
        "VAR s =\n    \"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 14' width='120' "
        "height='14'><rect x='0' y='3' width='120' height='8' rx='4' fill='#ECE7DD'/>\"\n"
        "        & \"<rect x='0' y='3' width='\" & w & \"' "
        "height='8' rx='4' fill='\" & c & \"'/>\"\n"
        "        & \"<line x1='\" & xu & \"' y1='0' x2='\" & xu & \"' y2='14' stroke='#1B1F24' "
        "stroke-width='1.5'/></svg>\"\n"
        "RETURN\n    IF ( ISBLANK ( a ) || ISBLANK ( u ), BLANK (), " + _uri_dax("s") + " )")
    ms.append(MedidaIcono("Barra de atraso", barra,
                          "Barra de días de atraso con una marca vertical en el umbral"))
    ms.append(_mapa())
    ms.append(_diagrama_rezago())
    ms.append(_textura())
    ms.append(_leyenda_consumo())
    return ms


def _estatica(nombre: str, svg_texto: str, comentario: str) -> MedidaIcono:
    return MedidaIcono(nombre, dax_str(data_uri(svg_texto)), comentario)


def _textura() -> MedidaIcono:
    """Líneas topográficas blancas al 7 % para el fondo de la banda del encabezado."""
    curvas = []
    for i, y in enumerate(range(-10, 110, 14)):
        a = 18 + (i % 3) * 6
        curvas.append(f"<path d='M-20 {y} C 180 {y - a}, 360 {y + a}, 560 {y} S 940 {y - a}, "
                      f"1140 {y + a / 2} S 1300 {y}, 1320 {y - 4}'/>")
    s = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1280 92' width='1280' height='92' "
         "preserveAspectRatio='none' fill='none' stroke='#FFFFFF' stroke-opacity='0.07' "
         "stroke-width='1.2'>" + "".join(curvas) + "</svg>")
    return _estatica("Textura encabezado", s, "Líneas topográficas al 7 % (banda del encabezado)")


# Series de consumo de gas en el orden de dim_serie[orden] y con los colores del tema
SECTORES = [("Residencial", "casa", "#1F6FD1"), ("Comercial", "edificio", "#C4531A"),
            ("Industrial", "fabrica", "#7A45C2"), ("Generación eléctrica", "rayo", "#A87D00"),
            ("Vehicular", "auto", "#5B6770")]


def _leyenda_consumo() -> MedidaIcono:
    """Leyenda con íconos para el gráfico de consumo por sector (reemplaza la nativa)."""
    x, partes = 0, []
    for nombre, icono, color in SECTORES:
        cuerpo = ICONOS[icono][0].replace('"', "'")
        partes.append(f"<g transform='translate({x} 2) scale(0.75)' fill='none' stroke='{color}' "
                      f"stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'>"
                      f"{cuerpo}</g><text x='{x + 23}' y='15' font-size='12' "
                      f"fill='#4A5260'>{nombre}</text>")
        x += 30 + int(len(nombre) * 6.6)
    s = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {x} 22' width='{x}' height='22' "
         f"font-family='Segoe UI'>" + "".join(partes) + "</svg>")
    return _estatica("Leyenda consumo por sector", s,
                     "Leyenda con ícono por sector: casa, edificio, fábrica, rayo y auto")


# Regiones de almacenamiento de la EIA (esquema simplificado, no a escala)
REGIONES = [
    # (region_key, etiqueta, polígono en una grilla de 400×240, posición de la etiqueta)
    ("R35", "Pacífico", "20,30 80,26 86,70 98,150 72,196 46,200 24,150 14,90", (52, 112)),
    ("R34", "Montaña", "80,26 196,32 194,120 150,124 150,150 98,150 86,70", (140, 82)),
    ("R32", "Medio Oeste", "196,32 300,30 312,64 300,124 194,120", (252, 72)),
    ("R33", "Centro Sur", "98,150 150,150 150,124 194,120 300,124 296,180 270,196 236,220 "
     "210,236 190,214 160,206 120,196", (224, 162)),
    ("R31", "Este", "300,30 368,20 392,40 372,90 350,130 330,170 336,226 322,232 300,196 "
     "296,180 300,124 312,64", (332, 100)),
]


def _mapa() -> MedidaIcono:
    """Mapa esquemático de las 5 regiones coloreadas por Gas almacenado por región."""
    lineas: list[str] = []
    for k, _, _, _ in REGIONES:
        lineas.append(f"VAR v{k} = CALCULATE ( [Gas almacenado por región], "
                      f"dim_region[region_key] = \"{k}\" )")
    vals = ", ".join(f"v{k}" for k, *_ in REGIONES)
    lineas += [f"VAR vmin = MINX ( {{ {vals} }}, [Value] )",
               f"VAR vmax = MAXX ( {{ {vals} }}, [Value] )"]
    for k, *_ in REGIONES:
        lineas.append(
            f"VAR c{k} = VAR i = IF ( vmax = vmin, 3, INT ( DIVIDE ( v{k} - vmin, vmax - vmin ) "
            f"* 4.999 ) + 1 ) RETURN SWITCH ( i, 1, \"#DCE8F8\", 2, \"#A9C7EE\", 3, \"#6FA0E0\", "
            f"4, \"#3478D2\", \"#164E9C\" )")
    partes = ["\"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 260' width='400' "
              "height='260' font-family='Segoe UI'>\""]
    for k, nombre, pts, (lx, ly) in REGIONES:
        oscuro = f"IF ( c{k} IN {{ \"#3478D2\", \"#164E9C\" }}, \"#FFFFFF\", \"#1B1F24\" )"
        partes.append(f"\"<polygon points='{pts}' fill='\" & c{k} & \"' stroke='#FFFFFF' "
                      f"stroke-width='3' stroke-linejoin='round'/>\"")
        partes.append(f"\"<text x='{lx}' y='{ly}' text-anchor='middle' font-size='12' "
                      f"font-weight='600' fill='\" & {oscuro} & \"'>{nombre}</text>\"")
        partes.append(f"\"<text x='{lx}' y='{ly + 16}' text-anchor='middle' font-size='12' "
                      f"fill='\" & {oscuro} & \"'>\" & FORMAT ( v{k}, \"#,0\" ) & \" Bcf</text>\"")
    partes.append("\"<text x='8' y='254' font-size='10' fill='#7A8394'>Esquema de las regiones "
                  "de almacenamiento de la EIA · no a escala</text></svg>\"")
    lineas.append("VAR s =\n        " + "\n        & ".join(partes))
    expr = "\n".join(lineas) + "\nRETURN\n    " + _uri_dax("s")
    return MedidaIcono("Mapa almacenamiento por región", expr,
                       "Mapa esquemático (no a escala) de las 5 regiones de la EIA, coloreado "
                       "por [Gas almacenado por región] en 5 tonos de azul")


def _diagrama_rezago() -> MedidaIcono:
    """Infografía: gota (WTI) → reloj con N meses → torre (producción)."""
    def grupo(icono: str, x: int, color: str) -> str:
        cuerpo = ICONOS[icono][0].replace('"', "'")
        return (f"<g transform='translate({x} 14) scale(1.6)' fill='none' stroke='{color}' "
                f"stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'>{cuerpo}</g>")
    flecha = ("<path d='M{a} 34 H{b}' stroke='#B9B3A8' stroke-width='2'/>"
              "<path d='M{c} 29 L{b} 34 L{c} 39' fill='none' stroke='#B9B3A8' stroke-width='2' "
              "stroke-linecap='round' stroke-linejoin='round'/>")
    s = ("\"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 420 92' width='420' height='92' "
         "font-family='Segoe UI'>"
         + grupo("gota", 28, PETROLEO)
         + flecha.format(a=90, b=150, c=144)
         + grupo("reloj", 190, GAS)
         + flecha.format(a=252, b=312, c=306)
         + grupo("torre", 352, PETROLEO)
         + "<text x='47' y='84' text-anchor='middle' font-size='12' fill='#4A5260'>"
           "Precio WTI</text>"
         + "<text x='209' y='84' text-anchor='middle' font-size='13' font-weight='700' "
           "fill='#1B1F24'>\" & k & IF ( k = 1, \" mes\", \" meses\" ) & \"</text>"
         + "<text x='371' y='84' text-anchor='middle' font-size='12' fill='#4A5260'>Producción"
           "</text></svg>\"")
    expr = ("VAR k = [Rezago óptimo (meses)]\nVAR s =\n    " + s + "\nRETURN\n    "
            "IF ( ISBLANK ( k ), BLANK (), " + _uri_dax("s") + " )")
    return MedidaIcono("Diagrama rezago", expr,
                       "Infografía precio WTI → N meses (rezago óptimo) → producción")


# ---------------------------------------------------------------- salida
def escribir_iconos() -> None:
    DIR_ICONOS.mkdir(parents=True, exist_ok=True)
    for viejo in DIR_ICONOS.glob("*.svg"):
        viejo.unlink()
    for n in ICONOS:
        (DIR_ICONOS / f"{n}.svg").write_text(svg(n).replace("'", '"') + "\n", encoding="utf-8")
    filas = ["# Íconos del informe Power BI", "",
             "Un solo set propio: grilla 24×24, trazo 2, extremos redondeados, sin relleno. "
             "El color (`currentColor` en el archivo) lo pone cada uso según la familia: "
             f"petróleo `{PETROLEO}`, gas `{GAS}`, OK `{OK}`, alerta `{ALERTA}`, error `{ERROR}`.",
             "", "Generados por `scripts/generar_iconos.py`: no los edites a mano.", "",
             "| Archivo | Qué representa | Dónde se usa |", "|---|---|---|"]
    filas += [f"| `{n}.svg` | {ICONOS[n][1]} | {USOS[n]} |" for n in ICONOS]
    (DIR_ICONOS / "index.md").write_text("\n".join(filas) + "\n", encoding="utf-8")


def a_dax(ms: list[MedidaIcono]) -> str:
    out = ["// Medidas de íconos e imágenes SVG del informe Pulso Energético de EE. UU.",
           "// Generado por scripts/generar_iconos.py: no editar a mano.",
           "// Todas devuelven un data URI (data:image/svg+xml;utf8,...) y en el modelo llevan",
           "// la categoría de datos 'Image URL'. Uso: Power BI Desktop → Vista de consultas DAX",
           f"// → pegar → 'Actualizar modelo con cambios'. Se alojan en la tabla '{TABLA}'.", "",
           "DEFINE"]
    for m in ms:
        out += ["", f"    // {m.comentario}", f"    MEASURE '{TABLA}'[{m.nombre}] ="]
        out += [f"        {linea}" for linea in m.expresion.splitlines()]
    out += ["", "EVALUATE", "ROW ("]
    out.append(",\n".join(f'    "{m.nombre}", LEN ( [{m.nombre}] )' for m in ms))
    out += [")", ""]
    return "\n".join(out)


def generar() -> list[MedidaIcono]:
    escribir_iconos()
    ms = medidas()
    DAX.parent.mkdir(parents=True, exist_ok=True)
    DAX.write_text(a_dax(ms), encoding="utf-8")
    return ms


if __name__ == "__main__":
    ms = generar()
    print(f"{len(ICONOS)} íconos -> {DIR_ICONOS.relative_to(RAIZ)}; "
          f"{len(ms)} medidas -> {DAX.relative_to(RAIZ)}")
    sys.exit(0)
