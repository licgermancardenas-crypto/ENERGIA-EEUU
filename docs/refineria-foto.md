# Modo "Refinería real": foto aérea de las refinerías del país (`/planta`)

En `/planta`, el botón **Refinería real** muestra la foto aérea verdadera de cualquiera de las
refinerías de crudo de EE. UU. La maqueta esquemática sigue siendo el modo principal.

Reemplaza a la versión anterior (geometría 3D desde OpenStreetMap para 18 refinerías), que se
retiró el 2026-11-28 a pedido del autor: cubría pocas refinerías y la cobertura de OSM era
despareja. Queda en el historial de git (commits `bfcbcda`, `b4a0eb1`, `189051d`, `2cb8175`).

## Fuentes

| Dato | Fuente | Vintage |
|---|---|---|
| Límites de estados | U.S. Census (`mapa_estados.geojson`) | 2024 |
| Nombres de estados y ciudades | OpenFreeMap (vector tiles de OpenStreetMap, © colaboradores de OSM, ODbL) | vigente |
| Foto aérea | USGS The National Map, servicio `USGSImageryOnly` (ortoimágenes, sobre todo USDA NAIP). Dominio público, sin clave. URL de teselas: `https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}` | "Data refreshed June, 2024" según el servicio; cada zona puede ser de un vuelo anterior |
| Refinerías (124) y ubicación | EIA, capa *Petroleum Refineries* (copia pública en ArcGIS Online) | 1/1/2024 |
| Capacidad | EIA, Refinery Capacity Report 2026 (`refcap26.xlsx`, EIA-820) | 1/1/2026 |

Las refinerías y la capacidad salen de `web/public/data/geo/refinerias.json`, el mismo archivo que
usan el mapa de gas, el de petróleo y Análisis (ver `src/eia_pulso/geo/refinerias.py` y
`docs/mapa.md`).

## Cómo funciona

- Mapa MapLibre con un único fondo raster: la foto del USGS (servicio con detalle hasta el nivel de
  zoom 16; más cerca se amplía la misma imagen).
- A escala país, cada refinería es un punto amarillo (tamaño = capacidad). Al elegirla en la lista
  (agrupada por estado) o tocar su punto, la cámara vuela hasta ella y se ve la foto real.
- La tarjeta muestra empresa, sitio, estado, capacidad (y capacidad en operación si hay ociosa).
- Atribución visible: "Foto: USGS The National Map, ortoimágenes USDA NAIP (dominio público) ·
  Ubicación y capacidad: EIA".

## Limitaciones

- Es una foto vertical (2D), no un modelo 3D. La foto 3D realista requiere Google Photorealistic
  3D Tiles, con facturación (ver [fase2-foto-3d.md](fase2-foto-3d.md)).
- La foto puede ser de un vuelo de años anteriores: no muestra el estado actual de la planta.
- El punto de la EIA marca la refinería aproximadamente; el predio se ve alrededor.
- El servicio del USGS es externo: si no responde, el mapa queda sin foto (los puntos y la
  tarjeta siguen funcionando).

## Cómo actualizar

No hay datos propios que regenerar: la foto la sirve el USGS y la lista de refinerías se actualiza
con el pipeline geo (`python -m eia_pulso geo --stage all` y `export-web --solo-geo`).
