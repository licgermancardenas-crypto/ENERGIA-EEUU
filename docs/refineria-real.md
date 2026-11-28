# Modo "Refinería real" (`/planta`)

En la página `/planta`, el botón **Refinería real** muestra la geometría verdadera de una
refinería existente (posición y tamaño de sus tanques, edificios, chimeneas, antorchas y
tuberías) tomada de OpenStreetMap. La maqueta esquemática sigue siendo el modo principal.

## Fuentes

| Dato | Fuente | Vintage |
|---|---|---|
| Geometría (tanques, chimeneas, antorchas, torres, edificios, tuberías, predio) | OpenStreetMap vía Overpass API (`overpass-api.de`) | fecha de extracción en cada archivo (`extraido`) |
| Ubicación de la refinería (punto de referencia) | EIA, capa *Petroleum Refineries* (copia pública en ArcGIS Online; campos `Company`, `Corp`, `Site`, `State`, `Latitude`, `Longitude`, `Period`) | 1/1/2024 |
| Capacidad | EIA, Refinery Capacity Report 2026 (`refcap26.xlsx`, EIA-820): `PRODUCT = TOTAL OPERABLE CAPACITY`, barriles por día calendario | 1/1/2026 |
| Utilización (antorchas) | EIA API v2, serie `WPULEUS3` (semanal, **nacional**) | última semana publicada |

## Cómo se cruzan

1. La EIA (capa + informe) ya está unida en `web/public/data/geo/refinerias.json` por estado +
   sitio (+ empresa si hay más de una en el mismo sitio). Ver `src/eia_pulso/geo/refinerias.py`.
2. Para cada refinería de la lista curada se busca en OSM, a 3 km del punto de la EIA:
   - primero un área `industrial=refinery` (con `landuse=industrial`, como indica la wiki de OSM)
     de al menos 0,2 km²; se elige la que contiene el punto o, si ninguna, la más cercana;
   - si no hay, un área `landuse=industrial` que contenga el punto o esté a menos de 500 m;
   - si tampoco hay, un círculo de 3 km alrededor del punto (y se descartan edificios que no son
     de la refinería: viviendas, comercios, escuelas, iglesias, etc.).

   Áreas más chicas que 0,2 km² se ignoran: en Baytown, el único `industrial=refinery` cercano es
   un edificio de 60 m mal etiquetado.
3. Dentro de esa área (con 60 m de margen) se toman los elementos con estas etiquetas, verificadas
   en la wiki de OSM: `man_made=storage_tank` (y `building=storage_tank`), `man_made=chimney`,
   `man_made=flare`, `man_made=tower` con `tower:type=cooling|flare`, `man_made=pipeline` y
   `building=*`.

## Cómo se arma la geometría

- Proyección local en metros alrededor del punto de la EIA (equirectangular; error < 0,1 % a 5 km).
  En la escena, 1 unidad = 10 m, igual en horizontal y en vertical: no se exageran alturas.
- **Tanques:** cilindro en el centro de su huella; radio = √(área ÷ π). Si el tanque está mapeado
  como punto (sin huella), radio estimado de 10 m (marcado en el archivo). Techo naranja si OSM
  dice `content=oil`/`crude_oil`, celeste si gas, gris si no informa. Instanciados.
- **Edificios:** contorno simplificado a 2 m y extruido a su altura; se unen en una sola malla. Tope
  de 1.500 por refinería (se priorizan los más grandes).
- **Chimeneas, antorchas y torres:** en su posición real.
- **Tuberías:** recortadas al área y simplificadas a 4 m (tope 600 tramos).

### Regla de estimación de alturas

Se usa `height` de OSM (metros; se aceptan pies). Si falta, se estima y el archivo lo marca:

| Elemento | Altura estimada |
|---|---|
| Tanque | 0,6 × diámetro, máximo 20 m |
| Edificio | `building:levels` × 3,5 m; sin niveles, 8 m |
| Chimenea | 45 m |
| Antorcha | 60 m |
| Torre de enfriamiento | 15 m |

La interfaz dice cuántos tanques tienen altura estimada.

### Cobertura

Estructuras = tanques + chimeneas + antorchas + torres. **Buena** con 40 o más, **parcial** con 8 a
39 y **pobre** con menos de 8. Con cobertura pobre la tarjeta lo avisa, no se inventa nada para
rellenar y se ofrece volver a la maqueta.

## Lista curada (18)

Las 15 de mayor capacidad según la EIA (Motiva Port Arthur, Marathon Galveston Bay, Marathon
Garyville, ExxonMobil Beaumont, ExxonMobil Baytown, ExxonMobil Baton Rouge, Citgo Lake Charles,
BP Whiting, Premcor/Valero Port Arthur, Tesoro Carson, Chevron Pascagoula, WRB Wood River,
Flint Hills Saint Paul, Deer Park, Marathon Catlettsburg) más tres chicas para mostrar cobertura
pobre: Silver Eagle (Evanston, WY), Foreland (Ely, NV) y Talley Asphalt (Kern, CA).

## Archivos

- `scripts/preparar_refinerias_osm.py`: script con todos los parámetros arriba (lista, radios,
  tolerancias, alturas).
- `web/public/data/refinerias-osm/<id>.json`: uno por refinería (ver `RefineriaOSM` en
  `web/src/components/planta/refineria-real.tsx`).
- `web/public/data/refinerias-osm/indice.json`: lista con cobertura.
- Respuestas crudas de Overpass: `data/osm/crudo/` (fuera del repo; no se publican).

## Licencia ODbL y cómo se cumple

Los datos de OpenStreetMap están bajo la Open Database License (ODbL 1.0). Lo que se hace acá:

- **Atribución visible:** en la escena, mientras se ve una refinería real, se muestra
  "Geometría de OpenStreetMap (© colaboradores de OpenStreetMap, licencia ODbL)" con link a
  https://www.openstreetmap.org/copyright.
- **Base de datos derivada:** los JSON de `web/public/data/refinerias-osm/` son una base derivada
  de OSM y se publican junto con el sitio. Cada archivo indica en el campo `licencia`
  "ODbL 1.0 · © colaboradores de OpenStreetMap" y el link a la licencia. Esos archivos se
  distribuyen bajo ODbL (share-alike), aunque el resto del repositorio tenga otra licencia.
- No se usa ningún mapa ni imagen de terceros en este modo.

## Limitaciones

- La cobertura de OSM varía mucho de una refinería a otra y no es oficial: puede haber tanques
  sin mapear, desactualizados o mal etiquetados.
- La mayoría de las alturas son estimadas.
- Las columnas de destilación casi nunca están mapeadas en OSM como tales: no aparecen.
- El punto de la EIA es de 2024 y la capacidad de 2026.
- La animación de la antorcha usa la utilización de refinerías de todo EE. UU., no la de esa
  refinería (la EIA no la publica por refinería).

## Cómo regenerar

```bash
python scripts/preparar_refinerias_osm.py              # usa la caché de data/osm/crudo/
python scripts/preparar_refinerias_osm.py --refrescar  # vuelve a consultar Overpass
```

El script manda un User-Agent que identifica al proyecto, hace una consulta por vez con 5 s de
pausa y espera 30 s (o más) si Overpass responde 429, 502, 503 o 504. Son unas 2 consultas por
refinería, muy por debajo del límite de uso de la instancia pública.
