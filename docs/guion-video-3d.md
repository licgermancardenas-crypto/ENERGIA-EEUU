# Guion del video de la planta 3D (modo grabación)

Abrí `https://energia-eeuu.vercel.app/planta/?record=1&formato=4x5` (vertical, 1080×1350) o
`&formato=1x1` (1080×1080) y grabá la pantalla unos 20 segundos. Los tiempos salen de
`web/src/components/planta/guion.ts`: si cambiás uno, cambiá el otro.

| Tiempo | Cámara | Qué se ve |
|---|---|---|
| 0–2,5 s | Vista general isométrica | Toda la planta; título "Petróleo y gas, movidos por datos reales". |
| 2,5–6,5 s | Costa afuera, girando 20° | Plataforma sobre el agua con oleaje y el buque avanzando. |
| 6,5–10,5 s | Refinería | Humo y antorcha: su intensidad sigue a la utilización de refinerías. |
| 10,5–14 s | Almacenamiento | Tanques de crudo y reserva estratégica con su nivel; gasómetros con el gas almacenado. |
| 14–17 s | Campo | Bombas cabeceando al ritmo de la producción de crudo. |
| 17–18,5 s | Vista general, girada 60° | Pulsos recorriendo las tuberías (ilustrativos). |
| 18,5–20 s | Fija | Cierre con los últimos valores, la fuente (EIA), "escena esquemática" y el autor. |

## Consejos

- Pantalla completa (F11) y zoom del navegador al 100 %. Esperá a que aparezca la escena antes de
  grabar.
- Si el equipo tiene activado "reducir movimiento", la escena queda quieta: desactivalo para grabar.
- El rótulo "escena esquemática" y el cierre con la fuente tienen que quedar en el video.
