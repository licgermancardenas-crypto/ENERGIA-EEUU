# Mapa animado de la red de gas (`/mapa`)

Sección de la web con un mapa interactivo y animado de la red de gasoductos de EE. UU., con el
Henry Hub como protagonista. Usa los mismos datos geoespaciales que las páginas Red y Análisis
(y que el informe de Power BI): no hay un procesamiento aparte.

## Cómo está armado

- **Mapa base:** estilo oscuro de [OpenFreeMap](https://openfreemap.org) (datos © OpenMapTiles y
  colaboradores de OpenStreetMap). No pide clave. Se evaluó Carto Dark Matter, pero hoy exige
  una clave de API (términos en https://carto.com/legal/basemap-terms/), así que no se usó.
- **Motor:** MapLibre GL JS con deck.gl encima (`MapboxOverlay`). Los dos se cargan con import
  dinámico y solo en el navegador (`components/mapa-animado/index.tsx`), así no pesan en el resto
  de la web ni rompen el export estático.
- **Proyección:** Web Mercator (la del mapa base). Agranda el norte: para comparar superficies,
  las páginas Análisis y el informe de Power BI usan Albers (áreas iguales). Alaska y Hawái no
  van en recuadros: la vista arranca en los 48 estados contiguos y hay botones para volar a ellos.

## Capas, fuentes y vintage

| Capa | Fuente | Vintage | Archivo web |
|---|---|---|---|
| Gasoductos (interestatal / intraestatal) | EIA, Natural Gas Interstate and Intrastate Pipelines (copia pública en ArcGIS Online, origen HIFLD) | 2020-01 | `data/geo/mapa_red_detalle.geojson` |
| Pulsos desde el Henry Hub | Derivado de la capa de gasoductos (ver cálculo) | — | `data/geo/pulsos.json` |
| Flujos entre estados | EIA API v2 `natural-gas/move/ist`, entregas (MID) por par de estados | anual, 2015–2024 | `data/geo/flujos.json` |
| Almacenamiento por región | EIA, Weekly Natural Gas Storage Report (series `NW2_EPG0_SWO_R3x_BCF_W`) sobre la capa de regiones de almacenamiento de la EIA (2020-10) | semanal | `data/semanales.json`, `data/geo/mapa_regiones.geojson` |
| Hubs de gas | EIA, Natural Gas Market Hubs (copia pública) | 2020-02 | `data/geo/puntos.json` |
| Terminales de GNL | EIA, LNG Import/Export Terminals (copia pública) | 2023-08 | `data/geo/puntos.json` |
| Estados | U.S. Census, Cartographic Boundary Files 2024 (1:20.000.000) | 2024 | `data/geo/mapa_estados.geojson` |
| Precio Henry Hub | EIA API v2, serie `RNGWHHD_D` (la misma de la página Gas) | diario | `data/ultimo_dato.json` |
| Conexiones del Henry Hub | `config/henry_hub_conexiones.csv`; fuente en `config/pipeline.yaml` (`henry_hub.fuente_conexiones`) | 2026-11-26 | `data/geo/henry_hub.json`, `data/geo/fuentes_mapa.json` |

## Cómo se calculan

- **Pulsos (ilustrativos).** Se arma un grafo con los tramos de gasoductos simplificados a 3 km
  (nodos redondeados a ~1 km para unir tramos de distintos operadores que se tocan) y se calcula
  la distancia más corta por la red desde el nodo más cercano al Henry Hub (Dijkstra). Cada tramo
  recibe como "tiempo" los km recorridos y se corta donde la distancia deja de crecer. La
  animación recorre esos km a velocidad constante: **no representa caudal, velocidad ni
  volumen real** (la EIA no publica volúmenes por gasoducto). La interfaz lo dice en pantalla.
  Código: `pulsos_desde_henry_hub` en `src/eia_pulso/web/export_geo.py`.
- **Flujos entre estados (datos reales).** La API v2 publica los pares como `SXX-SYY`. Se usan las
  entregas (`MID`): `SIN-SKY` con `MID` = Indiana entrega a Kentucky. La recepción del otro lado
  es el mismo volumen, así que no se suma dos veces. Se descartan áreas que no son estados
  (offshore federal `R3FM`, Canadá, México, totales). El mapa muestra los 80 pares más grandes
  del año elegido (40 en equipos chicos) para que no sea una maraña. El grosor es proporcional al
  volumen. Los arcos van de un punto interior de cada estado al otro: no siguen el trazado real.
  Código: `flujos_pares` en `src/eia_pulso/geo/gold.py`.
- **Balance neto por estado:** recibe − entrega, de los totales `SXX-Z0S` de la misma API. Se
  valida que neto = recibe − entrega. Las únicas filas que no se pueden validar son Alaska 2016 y
  DC y Hawái 2015–2016, porque la EIA no publica entregas para esos casos.
- **Almacenamiento en 3D:** la altura es proporcional a los Bcf almacenados la última semana en la
  región de la EIA (110 m por Bcf). Es un dato regional: todos los estados de una región comparten
  el mismo valor.

## Rendimiento (medido en el build de producción)

- Carga inicial de `/mapa`: ~195 KB comprimidos (HTML + JS común de la web).
- Después, en segundo plano: MapLibre + deck.gl (~550 KB comprimidos) y datos (~830 KB
  comprimidos: red 501, pulsos 259, estados 32, regiones 19, flujos 18).
- Equipos chicos (≤ 4 núcleos, ≤ 4 GB o pantalla ≤ 640 px): una sola onda de pulsos, sin el
  halo de los gasoductos y 40 arcos.
- `prefers-reduced-motion`: sin pulsos, sin cometas en los arcos, sin vuelo de entrada, sin
  conteo de KPIs y con el anillo del Henry Hub fijo. El mapa sigue funcionando completo.
- Sin WebGL: aviso y un mapa fijo de la red (SVG), con link a la página Red.

## Limitaciones

- Las capas de la EIA vienen de copias públicas de terceros porque los servicios oficiales piden
  token. La EIA no garantiza la exactitud de sus datos geoespaciales.
- La capa de gasoductos solo distingue interestatal e intraestatal (no hay recolección).
- La lista de conexiones del Henry Hub es un esquema: según la fuente son entre 8 y 13. Jefferson
  Island no aparece en la capa de la EIA.
- Los flujos son anuales y llegan hasta 2024, con el rezago de publicación de la EIA.

## Cómo refrescar

```bash
python -m eia_pulso geo --stage all          # o bronze-api + silver + gold si solo cambió la API
python -m eia_pulso export-web --solo-geo    # regenera web/public/data/geo/
```

El precio del Henry Hub y el almacenamiento se actualizan solos con la Action diaria
(`export-web` sin `--solo-geo`), que no toca la carpeta `geo/`.

## Modo grabación

`/mapa/?record=1` oculta la interfaz y corre un recorrido de ~20 s. Con `&formato=4x5` o
`&formato=1x1` encuadra el mapa en esa proporción. El guion está en
[guion-video.md](guion-video.md).

## Fase futura (no implementada)

- Census tracts como vector tiles (PMTiles) con zoom progresivo: el detalle aparece al acercarse
  sin bajar todo el país de entrada.
- Cruce con calefacción a gas por condado (ACS B25040, ya calculado para la página Análisis) en
  el mapa animado: por ejemplo, resaltar los condados que dependen del gas de red y quedan lejos.
