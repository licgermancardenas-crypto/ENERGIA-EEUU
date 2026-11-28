# Planta 3D (`/planta`)

Escena isométrica esquemática de instalaciones de petróleo y gas que se mueve con datos reales
de la EIA. **No representa una instalación real ni su operación**: la interfaz lo dice en pantalla.

## Cómo se mapea cada dato

Todos los valores salen de los JSON que la web ya publica (`web/public/data/`), calculados en
`web/src/components/planta/tipos.ts` (`datosPlanta`). Para pasar de un dato a un movimiento se usa
la **posición del último valor dentro de su rango histórico** en la web:
`norm = (último − mínimo) / (máximo − mínimo)`, entre 0 y 1.

| Objeto | Dato (serie de la EIA) | Cómo se mueve |
|---|---|---|
| 6 tanques de crudo (techo flotante) | Inventario comercial de crudo, `WCESTUS1` (semanal) | El crudo (naranja) y el techo suben: nivel = 12 % + 82 % × norm |
| 2 tanques con banda azul | Reserva Estratégica (SPR), `WCSSTUS1` (semanal) | Igual que los de crudo; la ficha muestra la variación de la semana |
| 3 gasómetros telescópicos | Gas almacenado Lower 48, `NW2_EPG0_SWO_R48_BCF` (semanal) | La campana celeste sube: altura = 15 % + 80 % × norm |
| 6 bombas de varilla | Producción de crudo, `MCRFPUS2` (mensual) | Ritmo del cabeceo = 0,6 + 1,8 × norm radianes por segundo |
| Chimeneas y antorcha | Utilización de refinerías, `WPULEUS3` (semanal, `petroleum/pnp/wiup`) | Humo: cantidad y opacidad = 25 % + 75 % × norm. Antorcha: tamaño = 0,4 + 0,9 × norm |
| Refinería (selector de estado) | Capacidad de refinación por estado, API v2 `petroleum/pnp/cap1` y EIA-820 2026 | Tamaño = 0,45 + 0,7 × √(capacidad del estado ÷ la del estado con más capacidad); columnas = cantidad de refinerías (hasta 4) |
| Buque petrolero | Precio WTI, `RWTC` (diario) | Solo en la ficha, como referencia: el buque se mueve igual siempre |
| Plataforma costa afuera | — | Ilustrativa: la web no tiene un dato de producción costa afuera |
| Pulsos en las tuberías | — | Ilustrativos (naranja = crudo, celeste = gas): no representan caudal |

Si un dato no está disponible, el objeto queda en una posición neutra (mitad de rango) y la
ficha dice "no disponible".

Rangos usados hoy (se recalculan solos con cada actualización):

- Inventarios y gas: desde 2023, porque el pipeline guarda esas series semanales desde
  2023-01-01 (`config/pipeline.yaml`). Un "tanque lleno" significa "el máximo desde 2023", no la
  capacidad física.
- Producción de crudo: desde 2010.
- Utilización de refinerías: desde 2015.

## Fuentes

- U.S. Energy Information Administration (EIA), API v2: rutas y series en `config/pipeline.yaml`.
- La utilización de refinerías se verificó en la API el 2026-11-27: ruta `petroleum/pnp/wiup`,
  serie `WPULEUS3`, "U.S. Percent Utilization of Refinery Operable Capacity", unidad %.
  Entra al pipeline como el dataset `utilizacion_refinerias_semanal` y la Action diaria la actualiza.
- Modelos 3D: todos propios, hechos con geometrías simples de three.js (ver
  [creditos-3d.md](creditos-3d.md)).

## Limitaciones

- La escena es un esquema: tamaños, cantidades y ubicaciones no tienen relación con instalaciones
  reales.
- La reserva estratégica real está en cavernas de sal en Texas y Luisiana, no en tanques.
- Los niveles son relativos al rango de la web, no a la capacidad de almacenamiento.
- La producción es mensual y llega con unos 3 meses de rezago (publicación de la EIA).

## Rendimiento y accesibilidad

- Carga inicial de `/planta`: ~186 KB comprimidos. La escena (three.js, React Three Fiber,
  drei y los modelos) baja después, en segundo plano: ~247 KB comprimidos. No hay otros archivos.
- Equipos chicos (≤ 4 núcleos, ≤ 4 GB o pantalla ≤ 640 px): sin sombras, menos árboles y
  resolución 1×.
- `prefers-reduced-motion`: escena quieta (sin oleaje, bombas, humo, buque ni pulsos), sin
  conteo en los KPIs y sin órbita; la cámara salta a cada zona sin transición.
- Sin WebGL: los mismos datos en tarjetas.
- Teclado: los botones "Ir a" y la lista de instalaciones del panel muestran la misma ficha
  que el mouse.

## Cómo refrescar

No hace falta nada: los datos se actualizan con la Action diaria (`run --stage all` +
`export-web`) y la página los toma en el próximo build de Vercel.

## Modo grabación

`/planta/?record=1` (con `&formato=4x5` o `&formato=1x1`). Guion en
[guion-video-3d.md](guion-video-3d.md).
