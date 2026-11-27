# Créditos de los modelos 3D

La escena de `/planta` **no usa modelos 3D externos**. Plataforma, buque, refinería, chimeneas,
antorcha, tanques, gasómetros, bombas de varilla, árboles y tuberías se construyen por código con
geometrías básicas de three.js (cajas, cilindros, conos, esferas, toros, tubos y una extrusión
para el casco), en `web/src/components/planta/modelos.tsx`. Son originales de este proyecto.

La referencia de estilo ("maqueta de arcilla" isométrica) se tomó como descripción general:
no se copió ninguna escena, modelo, textura ni logo de terceros.

| Modelo | Fuente | Licencia |
|---|---|---|
| — | No hay modelos externos | — |

Librerías usadas para dibujar (no son modelos):

- three.js (MIT)
- @react-three/fiber (MIT)
- @react-three/drei (MIT)

Si en el futuro se agrega un modelo externo, va en esta tabla con su autor, URL y licencia
(solo CC0 o CC-BY), comprimido con Draco o meshopt.
