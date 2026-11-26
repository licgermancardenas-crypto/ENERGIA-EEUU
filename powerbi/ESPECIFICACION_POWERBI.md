# Pulso Energético de EE. UU. — Especificación del informe Power BI

**Autor:** Germán Cárdenas · **Fase:** F4 · **Fuente de datos:** capa Gold del Lakehouse `lh_pulso_energetico` (ver `fabric/GUIA_FABRIC.md`)

Este documento alcanza para armar el informe de punta a punta sin un `.pbix`: modelo estrella, relaciones, medidas DAX, páginas, tema visual y validación. Las medidas también están en `powerbi/medidas.dax`, listas para pegar en la **vista de consultas DAX** de Power BI Desktop. Ese archivo se genera desde este documento con `python scripts/generar_powerbi.py`.

> **Qué está verificado y qué no.** Las medidas no se ejecutaron en Power BI: no hay Power BI ni Fabric en el entorno de desarrollo. Lo que sí está verificado con tests automáticos (`tests/test_powerbi.py`):
> - cada tabla y columna que se nombra existe en el esquema Gold;
> - cada medida referenciada está definida, y no hay nombres duplicados;
> - cada `serie_key` del código existe en la configuración.
>
> Los **valores esperados** de la §8 salen de la corrida local del pipeline y coinciden con lo que muestra la web. Usalos para validar el informe la primera vez que lo abras.

---

## 1. Conexión

### Opción A — Direct Lake (recomendada)

1. En el workspace de Fabric, abrí `lh_pulso_energetico` y elegí **New semantic model**.
2. Nombre: `sm_pulso_energetico`. Seleccioná estas tablas:
   - `dim_fecha`, `dim_serie`, `dim_region`;
   - los 8 `fact_*`;
   - `frescura` y `analisis_rezago`.
3. Abrí el modelo (**Open data model**) para crear relaciones y medidas desde el navegador, o editalo en Power BI Desktop con **OneLake data hub → Lakehouses → Connect → Edit**.

En Direct Lake **no hay refresh de datos que programar**: el paso *Semantic model refresh* del pipeline (guía §5) solo vuelve a encuadrar (*reframing*) el modelo sobre las tablas Delta nuevas.

**Limitación:** Direct Lake no admite columnas ni tablas calculadas. Este diseño no las usa: todo son medidas.

### Opción B — Import por SQL analytics endpoint

1. En Fabric, entrá en `lh_pulso_energetico` → **SQL analytics endpoint** → ⚙ **Settings** y copiá el **SQL connection string**.
2. En Power BI Desktop: **Get data → SQL Server**.
   - **Server:** el connection string.
   - **Database:** `lh_pulso_energetico`.
   - **Data connectivity mode:** *Import*.
3. Autenticación: **Microsoft account** (Entra ID) con tu usuario de Fabric.
4. Seleccioná las mismas tablas que en la opción A.
5. Al publicar, programá el refresh del modelo después de la corrida del pipeline (18:00 UTC), por ejemplo a las 19:00 UTC.

Para comprobar que el endpoint responde y que los datos coinciden con la §8:

```sql
-- Últimos datos por serie (debe devolver 29 filas)
SELECT s.nombre, u.fecha, u.valor, u.variacion_pct
FROM dbo.fact_ultimo_dato AS u
JOIN dbo.dim_serie AS s ON s.serie_key = u.serie_key
ORDER BY s.sector, s.categoria, s.orden;

-- Frescura: todas las fuentes deberían estar 'al_dia'
SELECT dataset, ultimo_periodo, dias_atraso, umbral_dias, estado FROM dbo.frescura;
```

---

## 2. Modelo estrella
```
                         ┌──────────────┐
                         │  dim_fecha   │  (tabla de fechas, diaria y continua)
                         └──────┬───────┘
                                │ 1
              ┌─────────────────┼──────────────────────────────┐
              │ *               │ *                            │ *
  ┌───────────┴──────────┐ ┌────┴──────────────────────┐  ┌────┴────────────────────┐
  │ fact_precios_diarios │ │ fact_precio_surtidor_sem. │  │ fact_produccion_mensual │  … 7 tablas de hechos
  └───────────┬──────────┘ └────┬──────────────────────┘  └────┬────────────────────┘
              │ *               │ *                            │ *
              └────────┬────────┴──────────────┬───────────────┘
                       │ 1                     │ 1
                 ┌─────┴──────┐          ┌─────┴──────┐
                 │ dim_serie  │          │ dim_region │
                 └─────┬──────┘          └────────────┘
                       │ 1
                       │ *
               ┌───────┴──────────┐     Desconectadas: frescura · analisis_rezago
               │ fact_ultimo_dato │
               └──────────────────┘
```

### Tablas

| Tabla | Grano | Filas* | Uso |
|---|---|---:|---|
| `dim_fecha` | 1 fila por día, sin huecos | 6.171 | Tabla de fechas. Se marca como *date table* sobre `fecha`. |
| `dim_serie` | 1 fila por serie y frecuencia (`serie_key` = código EIA + `_D`/`_W`/`_M`) | 29 | Nombre, unidad, sector y categoría de cada serie |
| `dim_region` | 1 fila por región | 10 | EE. UU., Cushing, Europa, Henry Hub y regiones de almacenamiento |
| `fact_precios_diarios` | serie × día hábil | 2.916 | WTI, Brent, Henry Hub |
| `fact_precios_mensuales` | serie × mes | 606 | WTI, Brent y Henry Hub mensuales |
| `fact_precio_surtidor_semanal` | serie × semana | 816 | Gasolinas y diésel |
| `fact_inventarios_semanales` | serie × semana | 808 | Crudo comercial, SPR, gasolina, destilados |
| `fact_almacenamiento_gas_semanal` | serie × semana | 1.212 | 5 regiones y el total Lower 48 |
| `fact_consumo_gas_mensual` | serie × mes | 1.200 | 5 sectores y el total |
| `fact_produccion_mensual` | serie × mes | 600 | Crudo, gas seco y gas comercializado |
| `fact_ultimo_dato` | 1 fila por serie | 29 | Último valor, valor anterior y variación |
| `frescura` | 1 fila por dataset | 10 | Atraso y estado de cada fuente |
| `analisis_rezago` | escenario × rezago (0–12) | 26 | Correlación WTI → producción en 2 escenarios |

\* Conteos de la corrida del 25/11/2026. Las tablas de hechos crecen con cada carga.

Todas las tablas de hechos comparten las columnas `fecha_key` (INT, AAAAMMDD), `fecha` (DATE), `serie_key`, `region_key` y `valor` (DOUBLE).

### Relaciones

Todas son *muchos a uno*, con filtro en **una sola dirección** (de la dimensión al hecho).

| Desde (muchos) | Hacia (uno) | Activa |
|---|---|---|
| `fact_*[fecha_key]` (las 7 de series) | `dim_fecha[fecha_key]` | Sí |
| `fact_*[serie_key]` (las 7 de series) | `dim_serie[serie_key]` | Sí |
| `fact_*[region_key]` (las 7 de series) | `dim_region[region_key]` | Sí |
| `fact_ultimo_dato[serie_key]` | `dim_serie[serie_key]` | Sí |

Decisiones de diseño:

- **`fact_ultimo_dato` no se relaciona con `dim_fecha`.** Así, las tarjetas de "último dato" no desaparecen cuando el usuario filtra un año.
- **`dim_serie` no se relaciona con `dim_region`.** Esa relación abriría un segundo camino (hecho → serie → región) y volvería ambiguo el modelo; la región llega directo desde cada hecho.
- **`frescura` y `analisis_rezago` quedan desconectadas.** Tienen otro grano y se leen solas.

### Configuración del modelo

1. **Marcar como tabla de fechas:** `dim_fecha`, columna `fecha`.
2. **Ordenar por columna:**
   - `dim_fecha[nombre_mes]` por `mes`;
   - `dim_fecha[nombre_dia]` por `dia_semana`;
   - `dim_serie[nombre]` por `orden`.
3. **Ocultar** en la vista de informe todas las columnas `*_key`, `fecha_key` y las columnas `valor` de los hechos. Así se usan siempre las medidas, que saben qué serie sumar o promediar.
4. **Tabla de medidas:** creá `_Medidas` con *Enter data* (una columna cualquiera, que después ocultás) y poné ahí todas las medidas. En Direct Lake, si *Enter data* no está disponible, colgá las medidas de `dim_serie` con las mismas carpetas.
5. **Formato de las medidas** (columna "Formato" de cada carpeta):

   | Tipo de medida | Formato |
   |---|---|
   | Termina en `%` | `0.0 %` |
   | Precio | `#,0.00` (o `#,0.000` para combustibles por galón) |
   | Volumen o stock | `#,0` |

   Las medidas de texto y HTML ya traen su formato con `FORMAT(…, "es-AR")`, así que no dependen del idioma del modelo.

---

## 3. Reglas que siguen todas las medidas

- **Una serie fija:** se filtra con `dim_serie[serie_key] = "…"` dentro de `CALCULATE`. Ese filtro *reemplaza* cualquier selección de serie del visual: es lo buscado en tarjetas como "Precio WTI".
- **Medidas genéricas por serie o sector:** usan `KEEPFILTERS`, así respetan la fila del visual. Ejemplos: "Consumo por sector" o "Gas almacenado por región".
- **Precios:** se **promedian** (un mes = promedio de sus días hábiles).
- **Producción en barriles por día:** también se promedia, porque es una tasa.
- **Volúmenes mensuales** (MMcf de consumo y producción de gas): se **suman**.
- **Stocks semanales:** son semiaditivos y se toman **a la última fecha con dato** del contexto, nunca se suman en el tiempo.
- **Variaciones:** comparan contra el dato anterior real de la serie (día hábil, semana o mes previo) e ignoran los filtros de fecha del visual. Así, el primer día de un año filtrado no queda en blanco.
- **Comparaciones interanuales:**
  - Semanales: contra la misma semana 52 semanas antes (364 días).
  - Mensuales: contra el mismo mes del año anterior.
  - Es el mismo criterio que usan las frases de la web.
- **Si falta el dato de comparación,** la medida devuelve `BLANK()` en lugar de un número engañoso.

---

## 4. Medidas DAX

Cada bloque `dax` define una o más medidas con la forma `Nombre =` seguida de la expresión. La carpeta (*display folder*) es el título de la sección.

### 4.1 Precios spot

Formato: precios `#,0.00`; `%` en `0.0 %`.

```dax
Precio WTI =
CALCULATE ( AVERAGE ( fact_precios_diarios[valor] ), dim_serie[serie_key] = "RWTC_D" )

Precio Brent =
CALCULATE ( AVERAGE ( fact_precios_diarios[valor] ), dim_serie[serie_key] = "RBRTE_D" )

Precio Henry Hub =
CALCULATE ( AVERAGE ( fact_precios_diarios[valor] ), dim_serie[serie_key] = "RNGWHHD_D" )

Último WTI =
VAR f =
    CALCULATE ( MAX ( fact_precios_diarios[fecha] ), dim_serie[serie_key] = "RWTC_D" )
RETURN
    CALCULATE ( [Precio WTI], REMOVEFILTERS ( dim_fecha ), dim_fecha[fecha] = f )

Variación diaria WTI % =
VAR f =
    CALCULATE ( MAX ( fact_precios_diarios[fecha] ), dim_serie[serie_key] = "RWTC_D" )
VAR fAnterior =
    CALCULATE (
        MAX ( fact_precios_diarios[fecha] ),
        REMOVEFILTERS ( dim_fecha ),
        dim_serie[serie_key] = "RWTC_D",
        fact_precios_diarios[fecha] < f
    )
VAR anterior =
    CALCULATE ( [Precio WTI], REMOVEFILTERS ( dim_fecha ), dim_fecha[fecha] = fAnterior )
RETURN
    IF ( ISBLANK ( anterior ), BLANK (), DIVIDE ( [Último WTI] - anterior, anterior ) )

Promedio WTI 12 meses =
VAR f =
    CALCULATE ( MAX ( fact_precios_diarios[fecha] ), dim_serie[serie_key] = "RWTC_D" )
RETURN
    CALCULATE (
        [Precio WTI],
        REMOVEFILTERS ( dim_fecha ),
        DATESINPERIOD ( dim_fecha[fecha], f, -1, YEAR )
    )

WTI vs promedio 12 meses % =
VAR promedio = [Promedio WTI 12 meses]
RETURN
    IF ( ISBLANK ( promedio ), BLANK (), DIVIDE ( [Último WTI], promedio ) - 1 )

Último Henry Hub =
VAR f =
    CALCULATE ( MAX ( fact_precios_diarios[fecha] ), dim_serie[serie_key] = "RNGWHHD_D" )
RETURN
    CALCULATE ( [Precio Henry Hub], REMOVEFILTERS ( dim_fecha ), dim_fecha[fecha] = f )

Variación diaria Henry Hub % =
VAR f =
    CALCULATE ( MAX ( fact_precios_diarios[fecha] ), dim_serie[serie_key] = "RNGWHHD_D" )
VAR fAnterior =
    CALCULATE (
        MAX ( fact_precios_diarios[fecha] ),
        REMOVEFILTERS ( dim_fecha ),
        dim_serie[serie_key] = "RNGWHHD_D",
        fact_precios_diarios[fecha] < f
    )
VAR anterior =
    CALCULATE ( [Precio Henry Hub], REMOVEFILTERS ( dim_fecha ), dim_fecha[fecha] = fAnterior )
RETURN
    IF ( ISBLANK ( anterior ), BLANK (), DIVIDE ( [Último Henry Hub] - anterior, anterior ) )

Promedio Henry Hub 12 meses =
VAR f =
    CALCULATE ( MAX ( fact_precios_diarios[fecha] ), dim_serie[serie_key] = "RNGWHHD_D" )
RETURN
    CALCULATE (
        [Precio Henry Hub],
        REMOVEFILTERS ( dim_fecha ),
        DATESINPERIOD ( dim_fecha[fecha], f, -1, YEAR )
    )

Henry Hub vs promedio 12 meses % =
VAR promedio = [Promedio Henry Hub 12 meses]
RETURN
    IF ( ISBLANK ( promedio ), BLANK (), DIVIDE ( [Último Henry Hub], promedio ) - 1 )

Diferencial Brent-WTI =
-- Último día del contexto en que cotizaron ambos crudos
VAR f =
    MAXX (
        FILTER (
            VALUES ( dim_fecha[fecha] ),
            NOT ISBLANK ( [Precio WTI] ) && NOT ISBLANK ( [Precio Brent] )
        ),
        dim_fecha[fecha]
    )
RETURN
    CALCULATE ( [Precio Brent] - [Precio WTI], dim_fecha[fecha] = f )

Precio WTI mensual =
CALCULATE ( AVERAGE ( fact_precios_mensuales[valor] ), dim_serie[serie_key] = "RWTC_M" )
```

### 4.2 Combustibles en surtidor

Formato `#,0.000`.

```dax
Precio en surtidor =
-- Genérica: poné dim_serie[nombre] en el eje para comparar combustibles
AVERAGE ( fact_precio_surtidor_semanal[valor] )

Precio gasolina regular =
CALCULATE ( [Precio en surtidor], dim_serie[serie_key] = "EMM_EPMR_PTE_NUS_DPG_W" )
```

### 4.3 Inventarios de petróleo

Formato `#,0` (miles de barriles); `%` en `0.0 %`.

```dax
Stock semanal =
-- Genérica y semiaditiva: valor a la última semana con dato del contexto
VAR f = MAX ( fact_inventarios_semanales[fecha] )
RETURN
    CALCULATE ( SUM ( fact_inventarios_semanales[valor] ), fact_inventarios_semanales[fecha] = f )

Stock crudo comercial =
CALCULATE ( [Stock semanal], dim_serie[serie_key] = "WCESTUS1_W" )

Stock SPR =
CALCULATE ( [Stock semanal], dim_serie[serie_key] = "WCSSTUS1_W" )

Variación semanal crudo comercial =
VAR f =
    CALCULATE ( MAX ( fact_inventarios_semanales[fecha] ), dim_serie[serie_key] = "WCESTUS1_W" )
VAR anterior =
    CALCULATE (
        SUM ( fact_inventarios_semanales[valor] ),
        REMOVEFILTERS ( dim_fecha ),
        dim_serie[serie_key] = "WCESTUS1_W",
        fact_inventarios_semanales[fecha] = f - 7
    )
RETURN
    IF ( ISBLANK ( anterior ), BLANK (), [Stock crudo comercial] - anterior )

Crudo comercial vs año anterior % =
VAR f =
    CALCULATE ( MAX ( fact_inventarios_semanales[fecha] ), dim_serie[serie_key] = "WCESTUS1_W" )
VAR haceUnAnio =
    CALCULATE (
        SUM ( fact_inventarios_semanales[valor] ),
        REMOVEFILTERS ( dim_fecha ),
        dim_serie[serie_key] = "WCESTUS1_W",
        fact_inventarios_semanales[fecha] = f - 364
    )
RETURN
    IF ( ISBLANK ( haceUnAnio ), BLANK (), DIVIDE ( [Stock crudo comercial], haceUnAnio ) - 1 )
```

### 4.4 Almacenamiento de gas

Formato `#,0` (Bcf); `%` en `0.0 %`.

```dax
Gas almacenado Lower 48 =
VAR f =
    CALCULATE (
        MAX ( fact_almacenamiento_gas_semanal[fecha] ),
        dim_serie[serie_key] = "NW2_EPG0_SWO_R48_BCF_W"
    )
RETURN
    CALCULATE (
        SUM ( fact_almacenamiento_gas_semanal[valor] ),
        dim_serie[serie_key] = "NW2_EPG0_SWO_R48_BCF_W",
        fact_almacenamiento_gas_semanal[fecha] = f
    )

Inyección neta semanal =
-- Positiva: se inyectó gas; negativa: se extrajo
VAR f =
    CALCULATE (
        MAX ( fact_almacenamiento_gas_semanal[fecha] ),
        dim_serie[serie_key] = "NW2_EPG0_SWO_R48_BCF_W"
    )
VAR anterior =
    CALCULATE (
        SUM ( fact_almacenamiento_gas_semanal[valor] ),
        REMOVEFILTERS ( dim_fecha ),
        dim_serie[serie_key] = "NW2_EPG0_SWO_R48_BCF_W",
        fact_almacenamiento_gas_semanal[fecha] = f - 7
    )
RETURN
    IF ( ISBLANK ( anterior ), BLANK (), [Gas almacenado Lower 48] - anterior )

Almacenamiento vs año anterior % =
VAR f =
    CALCULATE (
        MAX ( fact_almacenamiento_gas_semanal[fecha] ),
        dim_serie[serie_key] = "NW2_EPG0_SWO_R48_BCF_W"
    )
VAR haceUnAnio =
    CALCULATE (
        SUM ( fact_almacenamiento_gas_semanal[valor] ),
        REMOVEFILTERS ( dim_fecha ),
        dim_serie[serie_key] = "NW2_EPG0_SWO_R48_BCF_W",
        fact_almacenamiento_gas_semanal[fecha] = f - 364
    )
RETURN
    IF ( ISBLANK ( haceUnAnio ), BLANK (), DIVIDE ( [Gas almacenado Lower 48], haceUnAnio ) - 1 )

Gas almacenado por región =
-- Genérica: usá dim_region[nombre] en el eje. Excluye el total Lower 48.
VAR f = MAX ( fact_almacenamiento_gas_semanal[fecha] )
RETURN
    CALCULATE (
        SUM ( fact_almacenamiento_gas_semanal[valor] ),
        KEEPFILTERS ( dim_serie[serie_key] <> "NW2_EPG0_SWO_R48_BCF_W" ),
        fact_almacenamiento_gas_semanal[fecha] = f
    )

Participación regional % =
DIVIDE (
    [Gas almacenado por región],
    CALCULATE ( [Gas almacenado por región], REMOVEFILTERS ( dim_region ), REMOVEFILTERS ( dim_serie ) )
)
```

### 4.5 Producción

Formato `#,0`; `%` en `0.0 %`.

```dax
Producción de crudo =
-- Miles de barriles por día: es una tasa, se promedia
CALCULATE ( AVERAGE ( fact_produccion_mensual[valor] ), dim_serie[serie_key] = "MCRFPUS2_M" )

Producción de crudo interanual % =
VAR actual = [Producción de crudo]
VAR anterior =
    CALCULATE ( [Producción de crudo], DATEADD ( dim_fecha[fecha], -12, MONTH ) )
RETURN
    IF ( ISBLANK ( anterior ), BLANK (), DIVIDE ( actual - anterior, anterior ) )

Producción de gas seco =
CALCULATE ( SUM ( fact_produccion_mensual[valor] ), dim_serie[serie_key] = "N9070US2_M" )

Producción de gas comercializado =
CALCULATE ( SUM ( fact_produccion_mensual[valor] ), dim_serie[serie_key] = "N9050US2_M" )

Último mes de producción =
CALCULATE (
    MAX ( fact_produccion_mensual[fecha] ),
    REMOVEFILTERS ( dim_fecha ),
    dim_serie[serie_key] = "MCRFPUS2_M"
)
```

### 4.6 Consumo de gas

Formato `#,0` (MMcf); `%` en `0.0 %`.

```dax
Consumo total de gas =
CALCULATE ( SUM ( fact_consumo_gas_mensual[valor] ), dim_serie[serie_key] = "N9140US2_M" )

Consumo por sector =
-- Genérica: usá dim_serie[nombre] en el eje. Excluye el total para no contarlo como sector.
CALCULATE (
    SUM ( fact_consumo_gas_mensual[valor] ),
    KEEPFILTERS ( dim_serie[serie_key] <> "N9140US2_M" )
)

Participación del sector % =
DIVIDE ( [Consumo por sector], [Consumo total de gas] )

Participación generación eléctrica % =
-- Del último mes publicado, sin importar los filtros de fecha
VAR f =
    CALCULATE (
        MAX ( fact_consumo_gas_mensual[fecha] ),
        REMOVEFILTERS ( dim_fecha ),
        dim_serie[serie_key] = "N9140US2_M"
    )
VAR generacion =
    CALCULATE (
        SUM ( fact_consumo_gas_mensual[valor] ),
        REMOVEFILTERS ( dim_fecha ),
        dim_serie[serie_key] = "N3045US2_M",
        fact_consumo_gas_mensual[fecha] = f
    )
VAR total =
    CALCULATE ( [Consumo total de gas], REMOVEFILTERS ( dim_fecha ), fact_consumo_gas_mensual[fecha] = f )
RETURN
    DIVIDE ( generacion, total )
```

### 4.7 Último dato (tarjetas)

Para usar con una serie en contexto: un segmentador o un visual por `dim_serie[nombre]`. Formatos: valor `#,0.00`; `%` en `0.0 %`.

```dax
Último valor =
IF ( HASONEVALUE ( dim_serie[serie_key] ), MAX ( fact_ultimo_dato[valor] ) )

Variación vs dato anterior % =
IF ( HASONEVALUE ( dim_serie[serie_key] ), MAX ( fact_ultimo_dato[variacion_pct] ) )

Fecha del último dato =
IF ( HASONEVALUE ( dim_serie[serie_key] ), MAX ( fact_ultimo_dato[fecha] ) )

Indicador de variación =
-- Flecha + signo + texto: el sentido no depende solo del color
VAR v = [Variación vs dato anterior %]
RETURN
    IF (
        ISBLANK ( v ),
        "sin dato previo",
        IF ( v > 0, "▲ ", IF ( v < 0, "▼ ", "■ " ) )
            & FORMAT ( v, "+0.0 %;−0.0 %;0.0 %", "es-AR" )
    )
```

### 4.8 Rezago precio → producción

Para usar con `analisis_rezago`. Formatos: correlación `0.000`; meses `0`.

```dax
Correlación =
AVERAGE ( analisis_rezago[correlacion] )

Rezago óptimo (meses) =
-- Mayor correlación con signo; ante empate, el rezago más corto (igual que el pipeline)
IF (
    HASONEVALUE ( analisis_rezago[escenario] ),
    VAR mejores =
        TOPN (
            1,
            FILTER (
                CALCULATETABLE ( analisis_rezago, REMOVEFILTERS ( analisis_rezago[rezago_meses] ) ),
                NOT ISBLANK ( analisis_rezago[correlacion] )
            ),
            analisis_rezago[correlacion], DESC
        )
    RETURN
        MINX ( mejores, analisis_rezago[rezago_meses] )
)

Correlación en el óptimo =
VAR k = [Rezago óptimo (meses)]
RETURN
    CALCULATE (
        AVERAGE ( analisis_rezago[correlacion] ),
        REMOVEFILTERS ( analisis_rezago[rezago_meses] ),
        analisis_rezago[rezago_meses] = k
    )

Es rezago óptimo =
-- 1 en la barra del óptimo: usalo en el formato condicional del color de las barras
IF ( SELECTEDVALUE ( analisis_rezago[rezago_meses] ) = [Rezago óptimo (meses)], 1, 0 )

Color barra rezago =
-- Color de relleno por valor de campo: naranja en el óptimo, gris en el resto
IF ( [Es rezago óptimo] = 1, "#C4531A", "#B9B3A8" )

Texto rezago =
VAR k = [Rezago óptimo (meses)]
RETURN
    IF (
        ISBLANK ( k ),
        "Elegí un escenario",
        "Mayor correlación a " & k & IF ( k = 1, " mes", " meses" ) & " (r = "
            & FORMAT ( [Correlación en el óptimo], "0.00", "es-AR" ) & ")"
    )
```

### 4.9 Frescura y calidad

```dax
Fuentes al día =
CALCULATE ( COUNTROWS ( frescura ), frescura[estado] = "al_dia" ) + 0

Fuentes atrasadas =
CALCULATE ( COUNTROWS ( frescura ), frescura[estado] = "atrasado" ) + 0

Fuentes al día de total =
-- Texto para la tarjeta de Calidad, por ejemplo "10 de 10"
[Fuentes al día] & " de " & COUNTROWS ( frescura )

Máximo atraso (días) =
MAX ( frescura[dias_atraso] )

Fecha de cálculo =
MAX ( frescura[calculado_al] )

Estado de los datos =
VAR n = [Fuentes atrasadas]
RETURN
    IF (
        n = 0,
        "● Todas las fuentes al día",
        "▲ " & n & IF ( n = 1, " fuente atrasada", " fuentes atrasadas" )
    )
        & " · calculado al " & FORMAT ( [Fecha de cálculo], "dd/mm/yyyy", "es-AR" )

Icono de estado =
-- Para la tabla de frescura (una fila por dataset)
SWITCH (
    SELECTEDVALUE ( frescura[estado] ),
    "al_dia", "● Al día",
    "atrasado", "▲ Atrasado"
)
```

### 4.10 HTML para el visual *HTML Content*

Estas medidas devuelven HTML para el visual **HTML Content** (AppSource, ver §6). Usan solo estilos inline y los colores del tema. Los números se formatean con `es-AR`.

```dax
HTML Banner petróleo =
VAR fecha =
    CALCULATE ( MAX ( fact_precios_diarios[fecha] ), dim_serie[serie_key] = "RWTC_D" )
VAR v = [Variación diaria WTI %]
VAR colorV = IF ( v > 0, "#1d7a3b", IF ( v < 0, "#b3261e", "#565b62" ) )
VAR flecha = IF ( v > 0, "▲", IF ( v < 0, "▼", "■" ) )
VAR anual = [Crudo comercial vs año anterior %]
RETURN
    "<div style='font-family:Segoe UI,sans-serif;background:#fbfaf7;border:1px solid #ded7ca;border-radius:12px;padding:16px 20px;color:#1c1f22'>"
        & "<div style='font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#565b62'>WTI (Cushing) · "
        & FORMAT ( fecha, "dd/mm/yyyy", "es-AR" ) & "</div>"
        & "<div style='font-size:44px;font-weight:600;line-height:1.1'>"
        & FORMAT ( [Último WTI], "#,0.00", "es-AR" )
        & " <span style='font-size:14px;font-weight:400;color:#565b62'>US$/barril</span></div>"
        & "<div style='font-size:13px'><span style='color:" & colorV & "'>" & flecha & "</span> "
        & FORMAT ( v, "+0.0 %;−0.0 %;0.0 %", "es-AR" ) & " vs. día hábil anterior</div>"
        & "<div style='margin-top:10px;font-size:13px;color:#565b62'>Brent: <b style='color:#1c1f22'>"
        & FORMAT ( [Diferencial Brent-WTI], "#,0.00", "es-AR" ) & "</b> US$ sobre el WTI · Crudo comercial: <b style='color:#1c1f22'>"
        & FORMAT ( [Stock crudo comercial], "#,0", "es-AR" ) & "</b> miles de barriles ("
        & FORMAT ( anual, "+0.0 %;−0.0 %", "es-AR" ) & " interanual)</div>"
        & "</div>"

HTML Banner gas =
VAR fecha =
    CALCULATE ( MAX ( fact_precios_diarios[fecha] ), dim_serie[serie_key] = "RNGWHHD_D" )
VAR v = [Variación diaria Henry Hub %]
VAR colorV = IF ( v > 0, "#1d7a3b", IF ( v < 0, "#b3261e", "#565b62" ) )
VAR flecha = IF ( v > 0, "▲", IF ( v < 0, "▼", "■" ) )
RETURN
    "<div style='font-family:Segoe UI,sans-serif;background:#fbfaf7;border:1px solid #ded7ca;border-radius:12px;padding:16px 20px;color:#1c1f22'>"
        & "<div style='font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#565b62'>Henry Hub · "
        & FORMAT ( fecha, "dd/mm/yyyy", "es-AR" ) & "</div>"
        & "<div style='font-size:44px;font-weight:600;line-height:1.1'>"
        & FORMAT ( [Último Henry Hub], "#,0.00", "es-AR" )
        & " <span style='font-size:14px;font-weight:400;color:#565b62'>US$/MMBtu</span></div>"
        & "<div style='font-size:13px'><span style='color:" & colorV & "'>" & flecha & "</span> "
        & FORMAT ( v, "+0.0 %;−0.0 %;0.0 %", "es-AR" ) & " vs. día hábil anterior</div>"
        & "<div style='margin-top:10px;font-size:13px;color:#565b62'>Almacenamiento Lower 48: <b style='color:#1c1f22'>"
        & FORMAT ( [Gas almacenado Lower 48], "#,0", "es-AR" ) & "</b> Bcf ("
        & FORMAT ( [Almacenamiento vs año anterior %], "+0.0 %;−0.0 %", "es-AR" ) & " interanual)</div>"
        & "</div>"

HTML Frases petróleo =
VAR dif = [WTI vs promedio 12 meses %]
VAR anual = [Crudo comercial vs año anterior %]
VAR item = "<li style='margin:0 0 10px;padding-left:4px'>"
RETURN
    "<ol style='font-family:Segoe UI,sans-serif;font-size:14px;line-height:1.5;color:#1c1f22;margin:0;padding-left:20px'>"
        & item & "El WTI cerró en US$ " & FORMAT ( [Último WTI], "#,0.00", "es-AR" )
        & " por barril, un " & FORMAT ( ABS ( dif ), "0.0 %", "es-AR" )
        & IF ( dif >= 0, " por encima", " por debajo" )
        & " de su promedio de los últimos 12 meses (US$ "
        & FORMAT ( [Promedio WTI 12 meses], "#,0.00", "es-AR" ) & ").</li>"
        & item & "El Brent cotizó US$ " & FORMAT ( ABS ( [Diferencial Brent-WTI] ), "#,0.00", "es-AR" )
        & IF ( [Diferencial Brent-WTI] >= 0, " por encima", " por debajo" ) & " del WTI.</li>"
        & item & "Los inventarios comerciales de crudo suman "
        & FORMAT ( [Stock crudo comercial] / 1000, "#,0.0", "es-AR" ) & " millones de barriles: un "
        & FORMAT ( ABS ( anual ), "0.0 %", "es-AR" ) & IF ( anual >= 0, " más", " menos" )
        & " que un año atrás.</li>"
        & "</ol>"

HTML Advertencia rezago =
"<div style='font-family:Segoe UI,sans-serif;font-size:13px;line-height:1.5;background:#efebe2;border-left:4px solid #a35400;border-radius:8px;padding:12px 14px;color:#1c1f22'>"
    & "<b>⚠ Correlación no es causalidad.</b> Este análisis es descriptivo: mide cuánto se parecen los movimientos "
    & "del WTI y de la producción de crudo con distintos desfasajes. No prueba que el precio cause la producción, "
    & "que también depende de costos, tecnología, infraestructura y decisiones de las empresas. "
    & "Comparalo en los dos escenarios: con la historia completa y sin 2020-2021."
    & "</div>"
```

---

## 5. Páginas del informe

Lienzo de **1280 × 720**, márgenes de 24 px, grilla de 12 columnas.

En todas las páginas:
- encabezado con el título de la página, la medida **Estado de los datos** y la fuente ("EIA, API v2");
- navegación con botones arriba a la derecha: Resumen · Petróleo · Gas · Rezago · Calidad.

### Página 1 — Resumen ("El pulso hoy")
```
┌────────────────────────────────────────────────────────────────────────────┐
│ PULSO ENERGÉTICO DE EE. UU.                ● Todas las fuentes al día · …  │
├──────────────────────────────────┬─────────────────────────────────────────┤
│ [HTML Content] HTML Banner       │ [HTML Content] HTML Banner gas          │
│ petróleo                         │                                         │
├──────────────────────────────────┴─────────────────────────────────────────┤
│ [HTML Content] HTML Frases petróleo                                        │
├────────────┬────────────┬────────────┬────────────┬───────────────────────┤
│ Tarjeta    │ Tarjeta    │ Tarjeta    │ Tarjeta    │ Tarjeta               │
│ Producción │ Prod. crudo│ Inyección  │ Gasolina   │ Participación         │
│ de crudo   │ interanual │ neta sem.  │ regular    │ generación eléctrica %│
└────────────┴────────────┴────────────┴────────────┴───────────────────────┘
```

- Las tarjetas de producción llevan un filtro de visual al último mes publicado. Usá `dim_fecha[anio_mes]` con un filtro *Top N 1* por **Último mes de producción**, o un segmentador de mes. Como subtítulo de la tarjeta, mostrá **Último mes de producción** con formato `mmmm yyyy`.
- **Participación generación eléctrica %** ya se calcula sobre el último mes publicado, así que no necesita filtros.

### Página 2 — Petróleo

| Zona | Visual | Campos |
|---|---|---|
| Arriba izq. | Segmentador de **año** (botones) | `dim_fecha[anio]`, con el último año seleccionado por defecto |
| Arriba (8 col.) | Gráfico de líneas | Eje: `dim_fecha[fecha]`. Valores: **Precio WTI**, **Precio Brent**. Leyenda arriba; un solo eje Y. |
| Arriba der. (4 col.) | Barras horizontales | Eje: `dim_serie[nombre]` (filtro: categoría `precio_surtidor`). Valor: **Precio en surtidor**. Filtro de fecha: última semana. Etiquetas de datos activadas. |
| Abajo izq. | Líneas | Eje: `dim_fecha[fecha]`. Valores: **Stock crudo comercial**, **Stock SPR** |
| Abajo der. | Líneas | Eje: `dim_fecha[anio_mes]`. Valor: **Producción de crudo** |
| Tarjetas | Tarjeta (nuevo visual de tarjeta) | **Variación semanal crudo comercial**, **Crudo comercial vs año anterior %**, **Stock SPR** |

### Página 3 — Gas natural

| Zona | Visual | Campos |
|---|---|---|
| Arriba | Líneas con segmentador de año | **Precio Henry Hub** por `dim_fecha[fecha]` |
| Centro izq. | Columnas apiladas al 100 % | Eje: `dim_fecha[anio_mes]` (últimos 24 meses). Leyenda: `dim_serie[nombre]`. Valor: **Consumo por sector**. |
| Centro der. | Barras horizontales | `dim_region[nombre]` × **Gas almacenado por región**; información sobre herramientas: **Participación regional %** |
| Abajo | Líneas | **Gas almacenado Lower 48** por `dim_fecha[fecha]`. Tarjeta al lado con **Inyección neta semanal**. |
| Tarjetas | Tarjeta | **Producción de gas seco**, **Producción de gas comercializado**, **Consumo total de gas** |

En **Consumo por sector**, la leyenda de colores sigue el orden fijo de `dim_serie[orden]`. No reordenes por valor: el color tiene que seguir al sector.

### Página 4 — ¿Cuánto tarda la producción en reaccionar al precio?

| Zona | Visual | Campos |
|---|---|---|
| Arriba | Segmentador de **escenario** (botones, selección única) | `analisis_rezago[escenario]`. Etiquetas: *Historia completa* / *Sin 2020-2021 (pandemia)*. |
| Arriba der. | Tarjetas | **Rezago óptimo (meses)**, **Correlación en el óptimo**, **Texto rezago** |
| Centro | Columnas | Eje: `analisis_rezago[rezago_meses]` (0–12, categórico). Valor: **Correlación**. Color por formato condicional con reglas sobre **Es rezago óptimo**: 1 → naranja `#C4531A`, 0 → gris `#B9B3A8`. Línea de referencia en 0. |
| Abajo izq. | Líneas (pequeños múltiplos o dos gráficos) | **Precio WTI mensual** y **Producción de crudo** por `dim_fecha[anio_mes]`. Son **dos gráficos separados**, uno arriba del otro: nunca un solo gráfico con dos ejes Y. |
| Abajo der. | HTML Content | **HTML Advertencia rezago** |

Texto fijo de la página (cuadro de texto):

> Comparamos la variación mensual del WTI con la de la producción de crudo entre 0 y 12 meses después. Lo calculamos de dos maneras porque 2020 fue un año extremo: precio y producción se desplomaron y rebotaron casi a la vez. Que el resultado cambie tanto entre escenarios muestra que ninguna de las dos cifras es una regla fija.

### Página 5 — Calidad de los datos

| Visual | Campos |
|---|---|
| Tabla | `frescura`: dataset, frecuencia, ultimo_periodo, dias_atraso, umbral_dias y **Icono de estado**. Formato condicional del color de fuente sobre `estado`: `al_dia` → `#1D7A3B`, `atrasado` → `#A35400`. |
| Tarjetas | **Fuentes al día**, **Fuentes atrasadas**, **Máximo atraso (días)** |
| Tabla (opcional) | `silver_auditoria_revisiones` (se agrega al modelo desde el Lakehouse): revisiones de la EIA a datos ya cargados |

---

## 6. Visual *HTML Content*

1. **Instalación:** en Power BI Desktop, **Visualizaciones → … → Obtener más objetos visuales**, buscá **HTML Content** (de Daniel Marsh-Patrick) y agregalo. Si tu organización bloquea los visuales de AppSource, pedile al administrador que lo habilite en el portal de administración.
2. **Uso:** arrastrá la medida HTML al campo **Values**.
   - En *Format visual → Content formatting*, dejá **Show raw HTML** desactivado para que renderice.
   - Activá **Allow opening URLs** solo si agregás enlaces.
3. **Seguridad:** el visual ignora `<script>`. Por eso estas medidas usan solo HTML y CSS inline, sin JavaScript ni recursos externos, y no muestran datos ingresados por usuarios.
4. **Accesibilidad:** el texto queda como HTML legible por lectores de pantalla. Las flechas ▲▼ acompañan al signo, así que el sentido no depende del color.

> No verificado acá: el renderizado exacto del visual en tu versión de Power BI. Si algún estilo no se aplica, simplificá el CSS (por ejemplo, quitá `letter-spacing`).

---

## 7. Tema visual

Importá `powerbi/tema_pulso_energetico.json` desde **Vista → Temas → Buscar temas**. Es la misma paleta del dashboard web, validada para daltonismo: azul `#1F6FD1`, naranja `#C4531A`, violeta `#7A45C2` y ocre `#A87D00`, sobre fondo papel `#FBFAF7`. Además:

- Los colores *good*, *neutral* y *bad* quedan reservados para estados y variaciones.
- En los gráficos de líneas con dos series, la primera serie (WTI o crudo comercial) usa siempre el azul y la segunda el naranja.

---

## 8. Validación: valores esperados (corte del 25/11/2026)

Con el modelo cargado a esa fecha, sin filtros, las medidas tienen que devolver lo mismo que la web y que Gold:

| Medida | Valor esperado |
|---|---|
| Último WTI | 89,53 |
| Variación diaria WTI % | +0,3 % |
| Promedio WTI 12 meses | 83,85 |
| WTI vs promedio 12 meses % | +6,8 % |
| Diferencial Brent-WTI | 3,41 |
| Último Henry Hub | 3,10 |
| Variación diaria Henry Hub % | −3,1 % |
| Henry Hub vs promedio 12 meses % | −11,3 % |
| Stock crudo comercial | 417.797 |
| Variación semanal crudo comercial | 3.380 |
| Crudo comercial vs año anterior % | −1,5 % |
| Stock SPR | 276.361 |
| Gas almacenado Lower 48 | 3.882 |
| Inyección neta semanal | 20 |
| Almacenamiento vs año anterior % | −1,4 % |
| Precio gasolina regular (última semana) | 3,642 |
| Producción de crudo (agosto 2026) | 13.965 |
| Producción de crudo interanual % (agosto 2026) | +0,9 % |
| Producción de gas seco (agosto 2026) | 3.590.584 |
| Participación generación eléctrica % | 55,4 % |
| Rezago óptimo (meses) — completo / sin_pandemia | 1 / 7 |
| Correlación en el óptimo — completo / sin_pandemia | 0,364 / 0,204 |
| Fuentes al día | 10 |

Si algún valor no coincide, revisá en este orden:

1. **Relaciones:** que filtren en una sola dirección.
2. **Tabla de fechas:** que `dim_fecha` esté marcada como tabla de fechas.
3. **Datos del Lakehouse:** que sean del mismo corte; compará los conteos con la §6 de la guía de Fabric.

---

## 9. Publicación y actualización

- **Direct Lake:** el pipeline diario termina con *Semantic model refresh* (guía de Fabric, §5), que deja visibles los datos nuevos. No hace falta otra programación.
- **Import:** programá el refresh del modelo después de la corrida (19:00 UTC) y activá las notificaciones de error al propietario.
- **Seguridad:** el modelo no tiene datos personales ni necesita RLS, porque todas las series son públicas de la EIA. Compartilo con permiso de lectura, o publicalo en una app del workspace.
- **Cuidado con *Publish to web*:** expone el informe sin autenticación. Usalo solo si querés que sea público, y nunca con modelos que tengan otros datos.
