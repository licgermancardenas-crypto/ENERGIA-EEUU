# Guía paso a paso: Pulso Energético de EE. UU. en Microsoft Fabric

**Autor:** Germán Cárdenas

Esta guía reproduce en Microsoft Fabric el mismo pipeline medallón que corre localmente:

```
API EIA ──(Copy, REST anónima)──► Files/bronze/<dataset>/*.json      BRONZE (append, nunca se pisa)
                                        │
                                  NB01_Silver (PySpark + Delta MERGE insert-only)
                                        ▼
            silver_observaciones · silver_auditoria_revisiones · bronze_manifest   SILVER
                                        │
                                  NB02_Gold (reconstrucción completa + validaciones)
                                        ▼
   dim_fecha · dim_serie · dim_region · fact_* · frescura · analisis_rezago      GOLD
                                        │
                         Actualización del modelo semántico → Power BI
```

> ⏱️ Tiempo estimado: 45–60 minutos la primera vez.

---

## 0. Requisitos

- Un workspace de Fabric con capacidad: F2 o superior, o la **prueba gratuita de Fabric**.
- Permiso para crear Lakehouse, Notebooks, Data pipelines y conexiones.
- Tu key de la EIA (https://www.eia.gov/opendata/register.php).
- Este repo clonado, con el entorno de Python armado (ver README).

## 1. Generar los archivos de configuración

Desde la raíz del repo:

```bash
python scripts/generar_fabric.py
```

Genera (o actualiza) estos archivos a partir de `config/pipeline.yaml`:

| Archivo | Para qué |
|---|---|
| `fabric/config/eia_datasets.json` | Datasets, series, umbrales de frescura y rezago. No tiene secretos. |
| `fabric/config/eia_plan.json` | Plan de la actividad Copy: ruta + query de cada dataset. La primera vez pide la historia completa. Después NB01 lo regenera con la fecha incremental. |
| `fabric/notebooks/*.ipynb` | Notebooks importables. |

Después creá **tu** `eia_config.json` copiando `fabric/config/eia_config.example.json`:

```json
{ "api_key": "TU_KEY_REAL" }
```

> 🔐 `fabric/config/eia_config.json` está en `.gitignore`. **No lo subas al repo.**

## 2. Crear el Lakehouse y subir la configuración

1. En tu workspace: **+ New item → Lakehouse**, con el nombre `lh_pulso_energetico`.
2. En el explorador del Lakehouse, sobre **Files**: **… → New subfolder**. Creá `config`, `bronze` y `gold`.
3. Sobre `Files/config`: **… → Upload → Upload files**. Subí:
   - `eia_datasets.json`
   - `eia_plan.json`
   - `eia_config.json` (el que tiene la key)

> La key queda **solo** en `Files/config/eia_config.json`, dentro del Lakehouse. No se escribe en el pipeline ni en los notebooks. Limitá quién tiene acceso al workspace: los roles Viewer o superiores pueden leer `Files`.

## 3. Importar los notebooks

1. En el workspace: **Import → Notebook → From this computer**.
2. Seleccioná `NB01_Silver.ipynb` y `NB02_Gold.ipynb`. `NB00_Bronze_Alternativo.ipynb` es opcional (ver §8).
3. Abrí cada notebook y en el panel **Explorer → Lakehouses** agregá `lh_pulso_energetico` como **lakehouse predeterminado** (📌 *default*). Los notebooks leen `/lakehouse/default/Files/...`, así que sin esto no funcionan.
4. Comprobá que la primera celda de código diga **Parameters** arriba a la derecha. Si no aparece, en esa celda: **… → Toggle parameter cell**.

> Runtime recomendado: **Fabric Runtime 1.3 (Spark 3.5, Delta 3.x)** o superior. NB01 usa `try_to_timestamp` y `try_cast`, que necesitan Spark 3.5 o más.

## 4. Crear la conexión REST anónima a la EIA

1. ⚙️ **Settings → Manage connections and gateways → + New**.
2. Tipo **Cloud**, con estos datos:
   - **Connection name:** `cn_eia_api`
   - **Connection type:** `REST`
   - **Base URL:** `https://api.eia.gov/`
   - **Authentication method:** `Anonymous`
   - **Privacy level:** `Organizational` (o `None`)
3. **Create**.

> La conexión es anónima porque la EIA no usa encabezados de autenticación: la key viaja como parámetro `api_key`. El pipeline la agrega leyéndola del Lakehouse (paso 5.1).

## 5. Crear el pipeline de Data Factory

**+ New item → Data pipeline**, con el nombre `pl_pulso_energetico`. Agregá las actividades en este orden.

### 5.1 Lookup `Leer config` (la key)

| Campo | Valor |
|---|---|
| Connection | `lh_pulso_energetico` (Lakehouse) |
| Root folder | `Files` |
| File path | `config` / `eia_config.json` |
| File format | `JSON` |
| First row only | ✅ |

En **General**, activá **Secure output** ✅. Así la key no aparece en el monitoreo.

### 5.2 Lookup `Leer plan`

Igual que el anterior, pero con el archivo `eia_plan.json` y **First row only ❌**. Su salida es `@activity('Leer plan').output.value`.

### 5.3 ForEach `Por dataset`

Conectalo **On success** desde los dos Lookup.

| Campo | Valor |
|---|---|
| Items | `@activity('Leer plan').output.value` |
| Sequential | ❌ |
| Batch count | `3` (para no saturar la API) |

Dentro del ForEach agregá una actividad **Copy data** llamada `Bronze EIA`.

**General:** Retry `3`, Retry interval `60` s, **Secure input** ✅. La URL de la petición lleva la key.

**Source:**

| Campo | Valor |
|---|---|
| Connection | `cn_eia_api` |
| Relative URL | `@concat('v2/', item().ruta, '/data/?', item().query, '&api_key=', activity('Leer config').output.firstRow.api_key)` |
| Request method | `GET` |
| Pagination rules | ver abajo |

**Pagination rules.** La EIA devuelve como máximo 5.000 filas por llamada:

| Nombre | Valor |
|---|---|
| `QueryParameters` → `offset` | `RANGE:0:200000:5000` |
| `EndCondition` → `$.response.data` | `Empty` |
| `MaxRequestNumber` | `50` |

**Destination (Sink):**

| Campo | Valor |
|---|---|
| Connection | `lh_pulso_energetico` |
| Root folder | `Files` |
| File path (folder) | `@concat('bronze/', item().nombre)` |
| File name | `@concat(item().nombre, '__', formatDateTime(utcNow(), 'yyyyMMddTHHmmssfffffff'), 'Z.json')` |
| File format | `JSON` · File pattern `Set of objects` |

**Mapping:** dejalo vacío. Se copia la respuesta completa de la API, sin transformar, que es lo que corresponde a la capa Bronze.

> Cada corrida crea un archivo nuevo con un timestamp UTC en el nombre, así que **Bronze nunca se sobrescribe**. NB01 acepta las distintas formas en que Copy puede escribir las páginas: un objeto, un arreglo, uno por línea o concatenados.

### 5.4 Notebook `NB01_Silver`

Conectalo **On success** desde el ForEach. Notebook: `NB01_Silver`. Parámetros: los defaults sirven. Para reprocesar todo, usá `reprocesar_todo = true`.

### 5.5 Notebook `NB02_Gold`

Conectalo **On success** desde NB01.

### 5.6 Actualización del modelo semántico

Conectá **On success** desde NB02 una actividad **Semantic model refresh**:
- Workspace: el tuyo.
- Semantic model: el que crees en la F4 (especificación de Power BI).

Si todavía no creaste el modelo, agregá esta actividad más adelante.

> Con un modelo **Direct Lake** sobre el Lakehouse, el refresh es casi instantáneo porque solo reencuadra las tablas Delta. Con modo **Import** contra el punto de conexión SQL, el refresh reimporta los datos.

### 5.7 Aviso por falla

En los pipelines de Data Factory, una actividad con varias entradas *On fail* espera a que **todas** fallen. Por eso armá **un aviso por cada etapa crítica**:

1. Agregá una actividad **Office 365 Outlook** (o **Teams**) llamada `Aviso falla Bronze` y conectala **On fail** desde `Por dataset`.
   - To: tu email.
   - Subject: `@concat('[Pulso Energético] Falló ', pipeline().PipelineName)`
   - Body: `@concat('Run ', pipeline().RunId, ' falló en la ingesta Bronze. Revisá el monitoreo.')`
2. Duplicala como `Aviso falla Silver` (On fail desde `NB01_Silver`) y `Aviso falla Gold` (On fail desde `NB02_Gold`). En el cuerpo podés incluir `activity('NB02_Gold').error.message`.
3. Después de cada aviso, agregá una actividad **Fail**, con mensaje `Corrida fallida` y código `500`. Sin ella, el pipeline quedaría en estado *Succeeded* porque el aviso “manejó” el error.

### 5.8 Programación

**Schedule → On**, frecuencia **diaria**, por ejemplo a las **18:00 UTC** (15:00 en Argentina). A esa hora ya salieron los reportes de la EIA del día: el semanal de petróleo sale los miércoles y el de almacenamiento de gas los jueves, ambos a las 10:30 ET.

### 5.9 Diagrama del pipeline

```
[Leer config]──┐
               ├─► [Por dataset: Copy Bronze EIA] ─► [NB01_Silver] ─► [NB02_Gold] ─► [Refresh modelo]
[Leer plan]  ──┘            │ on fail                  │ on fail        │ on fail
                            ▼                          ▼                ▼
                   [Aviso]─►[Fail]            [Aviso]─►[Fail]   [Aviso]─►[Fail]
```

## 6. Primera corrida y validación

1. **Run** el pipeline y seguí el progreso en **Monitor**.
2. Comprobá en **Lakehouse → Files/bronze/** que haya una carpeta por dataset con un JSON cada una.
3. En el **punto de conexión SQL** del Lakehouse (selector arriba a la derecha → *SQL analytics endpoint*), corré:

```sql
SELECT 'fact_precios_diarios' AS tabla, COUNT(*) AS filas FROM fact_precios_diarios
UNION ALL SELECT 'fact_precios_mensuales', COUNT(*) FROM fact_precios_mensuales
UNION ALL SELECT 'fact_precio_surtidor_semanal', COUNT(*) FROM fact_precio_surtidor_semanal
UNION ALL SELECT 'fact_inventarios_semanales', COUNT(*) FROM fact_inventarios_semanales
UNION ALL SELECT 'fact_almacenamiento_gas_semanal', COUNT(*) FROM fact_almacenamiento_gas_semanal
UNION ALL SELECT 'fact_consumo_gas_mensual', COUNT(*) FROM fact_consumo_gas_mensual
UNION ALL SELECT 'fact_produccion_mensual', COUNT(*) FROM fact_produccion_mensual
UNION ALL SELECT 'fact_ultimo_dato', COUNT(*) FROM fact_ultimo_dato
UNION ALL SELECT 'dim_serie', COUNT(*) FROM dim_serie
UNION ALL SELECT 'dim_region', COUNT(*) FROM dim_region;
```

**Referencia:** la corrida local del 2026-11-25 dio estos conteos. Con datos de otra fecha van a ser algo mayores; lo importante es que local y Fabric coincidan **corriendo el mismo día**.

| Tabla | Filas (local, 2026-11-25) |
|---|---|
| fact_precios_diarios | 2.916 |
| fact_precios_mensuales | 606 |
| fact_precio_surtidor_semanal | 816 |
| fact_inventarios_semanales | 808 |
| fact_almacenamiento_gas_semanal | 1.212 |
| fact_consumo_gas_mensual | 1.200 |
| fact_produccion_mensual | 600 |
| fact_ultimo_dato | 29 |
| dim_serie / dim_region | 29 / 10 |

4. **Idempotencia:** corré el pipeline otra vez. En la salida de `NB01_Silver` (Monitor → actividad → Output), `insertadas` tiene que dar `0` o solo los datos nuevos del día, y los conteos no pueden duplicarse.
5. **Plan incremental:** abrí `Files/config/eia_plan.json`. Las fechas `inicio` ya no son 2010/2023: son el último período cargado menos la ventana de relectura.
6. **Revisiones:** `SELECT * FROM silver_auditoria_revisiones` muestra los cambios que la EIA hizo sobre valores ya cargados, que nunca se pisan.

## 7. Conectar Power BI

Lo detalla la especificación de la F4 (`powerbi/`). Hay dos caminos:

- **Direct Lake** (recomendado): desde el Lakehouse, **New semantic model**, seleccionando las tablas `dim_*` y `fact_*`.
- **Import / DirectQuery**: en Power BI Desktop, **Get data → Microsoft Fabric → Lakehouses → `lh_pulso_energetico` → Connect to SQL endpoint**.

**Atajo con la Fabric CLI** (`pip install ms-fabric-cli`, después `fab auth login`): el modelo Direct Lake completo, con tablas, relaciones, tabla de fechas y las 55 medidas, se genera desde la especificación y se importa de una vez.

```bash
fab get "<workspace>.Workspace/lh_pulso_energetico.Lakehouse" -q properties   # sqlEndpointProperties
python scripts/generar_modelo_semantico.py --server <connectionString> --endpoint-id <id> --out salida
fab import "<workspace>.Workspace/sm_pulso_energetico.SemanticModel" -i salida/sm_pulso_energetico.SemanticModel -f
```

Las medidas quedan en `dim_serie`, organizadas en carpetas, porque Direct Lake no admite tablas calculadas. Si una consulta devuelve `Invalid object name 'dbo.…'`, el SQL endpoint todavía no sincronizó las tablas nuevas: abrilo una vez o esperá unos minutos.

## 8. Plan B: Bronze con notebook

Si la paginación de la actividad Copy no se comporta como se espera (ver §9), reemplazá el ForEach por una actividad **Notebook** con `NB00_Bronze_Alternativo`:

- Lee la key de `Files/config/eia_config.json` y el plan de `Files/config/eia_plan.json`.
- Pagina con `offset`, reintenta con backoff exponencial y escribe en `Files/bronze/<dataset>/` con metadatos.

El resto del pipeline queda igual: Lookups opcionales, NB01, NB02, refresh y avisos.

## 9. Qué está verificado y qué no

| Componente | Estado |
|---|---|
| Rutas, series y parámetros de la API | ✅ Verificados contra la API real (2026-11-25) |
| Lógica pura de los notebooks: parser de Bronze, plan incremental, query, frescura, rezago | ✅ Probada con pytest y con paridad exacta contra el pipeline local |
| `.ipynb` válidos y con código que compila | ✅ Probado con pytest |
| Ejecución Spark/Delta (MERGE, escritura de tablas, `notebookutils`) | ⚠️ **No ejecutada**: no hay Spark/Fabric en el entorno de desarrollo. Validala con la checklist del §6. |
| Paginación de Copy (`RANGE` + `EndCondition`) contra la EIA | ⚠️ **No probada en Fabric.** Si falla, usá el plan B (§8). |
| Codificación de la query en la *Relative URL* | ⚠️ El plan usa `%5B%5D` para los corchetes. Si la EIA responde `400 invalid facet`, revisá que Copy no esté recodificando el `%`. |

## 10. Problemas comunes

| Síntoma | Causa probable / solución |
|---|---|
| `FileNotFoundError: /lakehouse/default/Files/config/...` | El notebook no tiene el Lakehouse como **predeterminado** (paso 3.3). |
| `API_KEY_MISSING` / `API_KEY_INVALID` | Revisá `eia_config.json` y la expresión de la Relative URL. |
| NB02 falla con «tabla vacía» | Algún dataset no trajo datos. Revisá su JSON en Bronze y la salida de NB01 (descartes). Gold **no se escribe** si falla una validación, así que el Gold anterior queda intacto. |
| Conteos duplicados | No debería pasar: el MERGE es insert-only por `(dataset, serie, periodo)`. Si pasa, abrí un issue con la salida de NB01. |
| La key aparece en el monitoreo | Activá **Secure output** en `Leer config` y **Secure input** en `Bronze EIA`. |
