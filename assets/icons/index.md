# Íconos del informe Power BI

Un solo set propio: grilla 24×24, trazo 2, extremos redondeados, sin relleno. El color (`currentColor` en el archivo) lo pone cada uso según la familia: petróleo `#C4531A`, gas `#1F6FD1`, OK `#1D7A3B`, alerta `#A35400`, error `#B42318`.

Generados por `scripts/generar_iconos.py`: no los edites a mano.

| Archivo | Qué representa | Dónde se usa |
|---|---|---|
| `pulso.svg` | Pulso (Resumen) | Encabezado de Resumen; botón Resumen |
| `gota.svg` | Gota de petróleo | Encabezado de Petróleo; botón Petróleo; sección PETRÓLEO; KPI WTI; diagrama de Rezago |
| `llama.svg` | Llama de gas | Encabezado de Gas; botón Gas; sección GAS NATURAL; KPI Henry Hub |
| `reloj.svg` | Reloj (rezago, atraso) | Encabezado de Rezago; botón Rezago; KPI rezago óptimo; diagrama; estado ámbar |
| `escudo-check.svg` | Escudo con check (Calidad) | Encabezado de Calidad; botón Calidad |
| `tendencia-sube.svg` | Tendencia en alza | KPIs de variación (signo +) |
| `tendencia-baja.svg` | Tendencia en baja | KPIs de variación (signo −) |
| `flechas-opuestas.svg` | Flechas opuestas (diferencial) | KPI Brent − WTI |
| `tanque.svg` | Tanque de crudo | KPI crudo comercial |
| `cilindro.svg` | Cilindro de gas | KPI gas almacenado |
| `flecha-sube.svg` | Flecha arriba | KPI inyección neta (positiva) |
| `flecha-baja.svg` | Flecha abajo | KPI inyección neta (negativa) |
| `rayo.svg` | Rayo (generación eléctrica) | KPI generación eléctrica; leyenda de consumo |
| `boveda.svg` | Escudo con cerradura (reserva estratégica) | KPI reserva estratégica (SPR) |
| `surtidor.svg` | Surtidor de combustible | Título de Precio en surtidor |
| `alerta.svg` | Alerta | Nota de la reserva estratégica 2026; KPI fuentes atrasadas; aviso de causalidad |
| `copo.svg` | Copo de nieve (invierno, extracción) | Nota de picos de invierno del Henry Hub; ciclo de almacenamiento (extracción) |
| `sol.svg` | Sol (verano, inyección) | Ciclo de almacenamiento (inyección) |
| `casa.svg` | Casa (residencial) | Leyenda de consumo: residencial |
| `edificio.svg` | Edificio (comercial) | Leyenda de consumo: comercial |
| `fabrica.svg` | Fábrica (industrial) | Leyenda de consumo: industrial |
| `auto.svg` | Auto (vehicular) | Leyenda de consumo: vehicular |
| `info.svg` | Información | Caja Cómo leerlo; nota de COVID 2020 |
| `torre.svg` | Torre de perforación (producción) | Diagrama de Rezago (producción) |
| `calendario.svg` | Calendario (frecuencia) | Tabla de frescura: frecuencia |
| `check-circulo.svg` | Check (al día) | Tabla de frescura: al día; KPI fuentes al día |
| `x-circulo.svg` | X (atrasada) | Tabla de frescura: atrasada |
| `red.svg` | Red de nodos (mapa de la red) | Encabezado y botón de la página Mapa de la red |
| `capas.svg` | Capas (análisis geoespacial) | Encabezado y botón de la página Análisis geoespacial |
| `mapa-pin.svg` | Ubicación con pulso (mapa animado, web) | Botón de la sección Mapa animado de la web |

## Medidas de imagen

`dax/iconos.dax` define las medidas que devuelven estos íconos (y el mapa, el diagrama del rezago, la textura y la leyenda) como `data:image/svg+xml;utf8,…`. En el modelo llevan la categoría *Image URL* y viven en la carpeta *Íconos e imágenes* de `dim_serie`.

## Foto del encabezado (pendiente)

El encabezado del Resumen usa solo la textura SVG. Si se suma una foto libre de derechos (refinería o campo de gas), debe ir muy oscura y con overlay navy (`#0B1F3A` al 85 %), detrás de la textura: un visual de imagen de 1280×92 en la posición (0, 0) de la página Resumen, agregado en `scripts/generar_informe.py` justo después de la banda y antes de la textura.
