# Mapa de petróleo (`/petroleo-red`)

Hermano del mapa de gas (`/mapa`): mismo mapa base oscuro (OpenFreeMap), mismo overlay de
deck.gl y mismo marcador que late (`web/src/components/mapa-comun.ts`), mismo cálculo de pulsos
(`pulsos_desde` en `src/eia_pulso/web/export_geo.py`). Naranja = petróleo.

Datos: `scripts/preparar_mapa_petroleo.py` → `web/public/data/petroleo/` (con `meta.json`:
origen, URL, licencia, vintage, cantidad de elementos y fecha de descarga). Respuestas crudas en
`data/bronze_geo/petroleo/<fecha>/` (fuera del repo).

## Fase 0: verificación de fuentes (2026-11-28)

Todas las capas se probaron con consultas reales (acceso sin token, cantidad, campos y peso
simplificado y comprimido).

| # | Capa | Fuente | Disponible | Peso | Notas |
|---|---|---|---|---|---|
| 1 | Oleoductos de crudo | EIA, Crude Oil Trunk Pipelines (copia pública, Federal User Community) | Sí | 236 tramos · 74 KB (≈27 KB gz) | Operador y nombre. Vintage no informado en la copia. |
| 2 | Poliductos de derivados | EIA, Petroleum Products Pipelines (misma copia) | Sí | 329 tramos · 87 KB | Ídem. |
| 3 | Terminales de derivados | EIA-815, Petroleum Product Terminals (copia pública) | Sí | 1.464 puntos · 291 KB (≈61 KB gz) | Dato a junio de 2023. La copia de FEMA pide token. |
| 4 | Puertos | USACE / USDOT BTS, Principal Ports (NTAD) | Parcial | 150 · 33 KB | Toneladas 2023 de TODAS las cargas, no de crudo: se rotula así. |
| 5 | Cushing | Census TIGERweb (lugar 4018850) + EIA (área YCUOK) | Sí (punto) | — | No hay capa de "hub de crudo". El punto es el centro de la ciudad. |
| 6 | Refinerías | Capa existente (EIA, capacidad 2026) | Sí | ya cargada | Reutilizada. |
| 7 | Reserva Estratégica | Capa existente | Sí | ya cargada | Reutilizada. |
| 8 | Plays de shale | EIA, Tight Oil and Shale Gas Plays (cuenta EIA.gov) | Sí | 50 · 45 KB | Incluye plays de gas. Solo contorno de referencia. |
| 9 | Plataformas offshore | BOEM, OCS Platforms Golfo 2024 T4 (vía Esri US Federal Data) | Parcial | 1.280 · 183 KB (≈20 KB gz) | Solo fechas de instalación y retiro; sin profundidad de agua. 18 fechas de 1899 son marcadores vacíos (la primera plataforma del Golfo es de 1938): se toman como sin dato. |
| 9b | Pozos y ductos offshore | BOEM | No verificado | — | Fuera de alcance. |
| 10a | Producción por estado/PADD | API v2 `petroleum/crd/crpdn` (process FPF, product EPC0), anual y mensual | Sí | 10 KB | Texas 5.710 mil b/d (ago. 2026). |
| 10b | Producción offshore Golfo | `petroleum/crd/crpdn`, área R3FM | Sí | — | `petroleum/crd/gom` termina en 2007: no se usa. |
| 10c | Comercio de crudo | `petroleum/move/imp` (IM0) y `exp` (EEX), product EPC0 | Sí por PADD, no por puerto | — | La API v2 no publica comercio por puerto. |
| 10d | Producción por cuenca | `steo` (TOPRPM, TOPRBK, TOPREF…) | Parcial | — | Mezcla historia y pronóstico sin marcar: no se usa. |
| 11 | Rigs (Baker Hughes) | — | Descartado | — | Sin licencia pública clara. |

Licencias: todas las capas y series son datos del gobierno de EE. UU. (dominio público), servidos
desde copias públicas porque los servicios oficiales piden token. El mapa base es OpenFreeMap
(© OpenMapTiles, © colaboradores de OpenStreetMap).

## Decisiones

- Puertos: se muestran rotulados "toneladas de todas las cargas" (decisión del autor).
- Producción: por estado, nunca atribuida a la cuenca (decisión del autor). Los plays son solo
  contorno de referencia.
- Capas prendidas por defecto: oleoductos (con sus pulsos), Cushing y refinerías.
- Pulsos: misma función que el gas, desde Cushing. Los oleoductos troncales no comparten
  vértices exactos, así que se unen extremos a ~10 km (1 decimal); el gas usa ~1 km. Son
  ilustrativos y se rotulan "no flujo medido".
- km de ducto: largo de las geometrías originales en EPSG:5070 (73.131 km de oleoductos y
  71.425 km de poliductos en la capa de la EIA; no es el total de la red del país).
- Plataformas: color por década de instalación (más viejas, más claras). La profundidad no está.

## /mapa y /red

Hoy se solapan: los dos muestran la red de gas sobre MapLibre. Propuesta (no aplicada): dejar
`/red` como mapa claro de consulta (zoom fino, capas y fichas) y `/mapa` como la versión animada
para presentar; o fusionarlas en una sola página con un botón "modo presentación". Requiere tu OK.

## Cómo refrescar

```bash
python scripts/preparar_mapa_petroleo.py
```

Las capas se vuelven a bajar si cambia la fecha (carpeta de caché por día); las series siempre.
