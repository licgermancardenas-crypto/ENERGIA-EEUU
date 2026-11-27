# Capa geoespacial: red de gas natural de EE. UU.

**Autor:** Germán Cárdenas · Páginas del informe: **Red** (mapa de la red) y **Análisis** (análisis geoespacial).

Este documento cubre las fuentes y su vintage, la metodología de cada métrica, las limitaciones y cómo refrescar los datos. El código está en `src/eia_pulso/geo/` (Bronze → Silver → Gold, la misma convención del pipeline principal) y la configuración en la sección `geo` de `config/pipeline.yaml`.

---

## 1. Fuentes y vintage

Verificadas el 2026-11-26. Los servicios ArcGIS oficiales de la EIA ([cuenta del Energy Atlas](https://services7.arcgis.com/FGr1D95XCGALKXqM/arcgis/rest/services)) **ahora piden token** para gasoductos, GNL y reserva estratégica, y HIFLD Open parece fuera de línea (sus capas sobreviven en el archivo de rescate de [DataLumos](https://www.datalumos.org/datalumos/project/239743), que requiere iniciar sesión). Por eso, las capas estáticas salen de **copias públicas de terceros** de esas mismas capas de la EIA. Se rotulan así en el informe y en la página Calidad.

| Capa | Fuente | Vintage (año de atributos) | Registros |
|---|---|---|---|
| Gasoductos interestatales e intraestatales | EIA, copia pública en ArcGIS Online ([servicio](https://services2.arcgis.com/vHeD2bHG1G3sW5YZ/ArcGIS/rest/services/NaturalGas_InterIntrastate_Pipelines_US_EIA_ExportFeatures/FeatureServer/0)); una segunda copia independiente tiene la misma cantidad de tramos | 2020-01 ("updated January 2020") | 32.892 tramos |
| Hubs de mercado | EIA, copia pública ([servicio](https://services.arcgis.com/jDGuO8tYggdCCnUJ/arcgis/rest/services/Natural_Gas_Market_Hubs/FeatureServer/0)) | 2020-02 (campo `Period`) | 32 |
| Terminales de GNL | EIA, copia pública ([servicio](https://services.arcgis.com/kbDdtKcFi2adamXa/arcgis/rest/services/Lng_ImportExportTerminals_US_EIA/FeatureServer/0)) | 2023-08 | 9 |
| Reserva estratégica de petróleo | DOE vía EIA, copia pública ([servicio](https://services.arcgis.com/jDGuO8tYggdCCnUJ/arcgis/rest/services/Strategic_Petroleum_Reserves/FeatureServer/0)) | 2022-04 | 4 |
| Regiones de almacenamiento | EIA, **servicio oficial** ([Natural_Gas_Storage_Regions](https://services7.arcgis.com/FGr1D95XCGALKXqM/ArcGIS/rest/services/Natural_Gas_Storage_Regions/FeatureServer/0)) | 2020-10 | 5 |
| Límites de estados | U.S. Census Bureau, Cartographic Boundary Files 2024, 1:20.000.000 | 2024 | 49 (Lower 48 + DC) |
| Flujos interestatales | EIA API v2 `natural-gas/move/ist` (anual; procesos `MIR` recibe, `MID` entrega, `MIN` neto) | último año publicado | — |
| Centrales a gas | EIA API v2 `electricity/operating-generator-capacity` (EIA-860M, `energy_source_code = NG`) | último mes publicado | — |
| Conexiones del Henry Hub | [Sabine Pipe Line LLC](https://sabinepipeline.enlink.com/?p=25): 9 interestatales y 3 intraestatales | consultado 2026-11-26 | 11 filas en `config/henry_hub_conexiones.csv` |

Lo que ya estaba en el modelo **no se vuelve a descargar**: el gas almacenado por región, el consumo por sector y el precio Henry Hub se reutilizan con las medidas existentes.

Cada descarga queda en `data/bronze_geo/<capa>/` con un manifiesto (URL, registros, SHA-256, vintage y fecha). El vintage de cada capa también figura en la tabla `frescura_geo` (página Calidad).

## 2. Decisiones

- **CRS:** las longitudes y áreas se calculan en **EPSG:5070** (NAD83 / Conus Albers, de área equivalente). Lo que se muestra vuelve a **WGS84** (EPSG:4326).
- **Alaska, Hawái y Puerto Rico:** se **excluyen**, con una nota visible en el mapa. Las regiones de almacenamiento y la red analizada son del Lower 48. Un recuadro aparte sumaría peso y complejidad sin responder ninguna de las preguntas del informe.
- **Simplificación:** Douglas-Peucker con **1,5 km** de tolerancia sobre EPSG:5070 (6 km para las regiones), sin romper la topología. Las coordenadas se redondean a 3 decimales (~100 m). Los tramos se unen por (tipo, operador). Resultado: **1,4 MB** en total (red 1,2 MB, estados 77 KB, regiones 73 KB). Las métricas se calculan **sobre la geometría completa**, no sobre la simplificada.
- **Umbral de proximidad: 25 km.** Una central a esa distancia o menos puede conectarse con un ramal corto; más allá, lo más probable es que dependa de un ramal que la capa de la EIA no dibuja, porque la capa cubre la red troncal y no los ramales de conexión. Es un supuesto de diseño, no un dato de la EIA. Se cambia en `geo.umbral_proximidad_km`.
- **Visual del mapa:** Deneb (Vega-Lite), con la geometría embebida en la spec. Deneb no carga URLs externas. Se probó en Power BI Service del tenant antes de usarlo.

## 3. Metodología de cada métrica

| Métrica | Cálculo | Tabla / medida |
|---|---|---|
| km de gasoducto por estado y tipo | intersección de líneas con polígonos en EPSG:5070; largo de cada pedazo | `geo_km_estado_operador`, `geo_estado_metricas` |
| Densidad | km del estado ÷ superficie del estado (EPSG:5070) × 1.000 | `[Densidad de red]` |
| Operadores | operadores distintos con al menos un tramo en el estado (no se suman entre estados) | `[Operadores en el estado]` |
| Balance interestatal neto | `MIN` de la EIA (recepciones netas). Se verifica que `MIN = MIR − MID` en cada estado. > 0: importador neto; < 0: exportador neto | `geo_flujos_estado`, `[Balance neto interestatal]` |
| Huella del Henry Hub | km y estados de los operadores listados en `config/henry_hub_conexiones.csv`. **Mide huella de red, no flujo físico** | `[Km huella Henry Hub]`, `[Estados conectados al Henry Hub]` |
| Distancia GNL → Henry Hub | distancia geodésica sobre el elipsoide WGS84 (pyproj) | `geo_gnl` |
| Distancia central → red | distancia al gasoducto más cercano en EPSG:5070 (`sjoin_nearest`). Los generadores se suman por planta | `geo_centrales` |
| % de capacidad cerca de la red | MW de centrales a ≤ 25 km ÷ MW totales | `[Capacidad cerca de la red %]` |
| Región de almacenamiento del estado | punto interior del estado dentro de las regiones de la EIA | `geo_dim_estado[region_key]` → `dim_region` |

## 4. Validaciones (corrida del 2026-11-26)

- **Red total:** 360.239 km (239.408 interestatales y 120.831 intraestatales).
- **Dentro de estados:** 345.480 km. Quedan **fuera** 14.760 km (4,1 %): son tramos marinos del Golfo de México. Por ejemplo, Sea Robin tiene solo 35 km en tierra.
- **Consistencia:** la suma de las métricas por estado coincide con el total intersectado.
- **Estados con 0 km:** solo **DC**, y es real: el gasoducto más cercano está a 15,8 km de su límite.
- **Henry Hub:** 10 de las 11 conexiones de Sabine figuran en la capa. Jefferson Island no está (es sobre todo almacenamiento). La huella de esos operadores toca **20 estados** y suma 36.088 km.
- **Flujos:** en cada estado se verifica `MIN = MIR − MID` (columna `cierre_ok`).

## 5. Limitaciones

- **Huella ≠ flujo:** que un estado esté "conectado" al Henry Hub significa que algún operador conectado al hub tiene red ahí, no que reciba gas del hub.
- **Copias de terceros:** las capas estáticas son copias públicas de capas de la EIA. Se verificó que los campos (`TYPEPIPE`, `Operator`, `Status`) y la descripción coincidan con los metadatos de la EIA, pero no se puede garantizar que estén completas ni que sean idénticas al original.
- **Sin recolección:** la capa de la EIA solo distingue interestatal e intraestatal. Los gasoductos de recolección figuran como "no disponible".
- **Sin corredores origen-destino:** la ruta `ist` publica totales por estado, no pares origen-destino. Por eso el mapa no dibuja flechas de corredores.
- **Vintage viejo:** los gasoductos son de 2020 y los hubs de febrero de 2020. Proyectos posteriores pueden faltar.
- **Aviso de la EIA:** la EIA aclara que estos datos no garantizan precisión ni exhaustividad.
- **Geometría simplificada:** sirve para ver el país, no para medir un tramo puntual.

## 6. Cómo refrescar

```bash
pip install -e ".[geo]"
python -m eia_pulso geo --stage all          # bronze + bronze-api + silver + gold
python scripts/publicar_geo_fabric.py --workspace "Pulso Energetico EEUU"   # al Lakehouse
```

Después de publicar, regenerá el informe con `scripts/generar_informe.py`, que embebe la geometría nueva en el mapa.

- Si la API de la EIA no responde, Gold igual corre: los flujos y las centrales quedan vacíos y el informe los muestra como **"No disponible"**.
- Para sumar o corregir una conexión del Henry Hub, editá `config/henry_hub_conexiones.csv` y volvé a correr `--stage gold`.
