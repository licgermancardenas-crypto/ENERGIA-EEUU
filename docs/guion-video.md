# Guion del video corto (modo grabación)

Abrí `https://energia-eeuu.vercel.app/mapa/?record=1` y grabá la pantalla. Con
`&formato=4x5` (1080×1350, vertical para LinkedIn) o `&formato=1x1` (1080×1080) el mapa queda
encuadrado en esa proporción. Esperá a que se vea el mapa antes de empezar a grabar: el
recorrido arranca cuando terminan de cargar los datos.

Los tiempos salen de `web/src/components/mapa-animado/guion.ts`: si cambiás uno, cambiá el otro.

| Tiempo | Cámara | Qué se ve |
|---|---|---|
| 0–2 s | País completo, sin inclinación | La red se enciende en azul; salen los primeros pulsos desde el Henry Hub. Título arriba: "La red de gas natural desde el Henry Hub". |
| 2–6 s | Vuelo al Golfo de México (zoom 5,6, inclinación 45°) | El marcador naranja del Henry Hub late; el rótulo muestra el precio actual. |
| 6,5–10 s | Paneo al noreste (Apalaches, Pensilvania) | Los pulsos suben por los gasoductos interestatales. |
| 10–13 s | Medio Oeste (Illinois) | Los pulsos llegan a los hubs del centro del país. |
| 13–17 s | Vista nacional inclinada (55°) | Se encienden los flujos entre estados (arcos con volumen real de la EIA, último año) y el almacenamiento por región en 3D. |
| 17,5–20 s | Fija | Cierre: km de gasoductos, precio del Henry Hub, fuentes, "pulsos ilustrativos" y autor. |

## Consejos para grabar

- Navegador a pantalla completa (F11) y zoom del navegador al 100 %.
- En Windows: Xbox Game Bar (Win + Alt + R) o OBS con una ventana de 1080×1350.
- Si el equipo tiene la opción "reducir movimiento" activada, el recorrido no anima los pulsos:
  desactivala para grabar.
- El texto del cierre dice que los pulsos son ilustrativos: no lo cortes en la edición.
