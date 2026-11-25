# Borrador del post de LinkedIn

> Antes de publicar, reemplazá `[URL del dashboard]` con la URL de Vercel. Si el post sale después de otra corrida, revisá también las cifras: son del corte del 25/11/2026.

---

**¿Cuánto tarda la producción de petróleo de EE. UU. en reaccionar al precio? Depende de cómo mires 2020.** 🛢️

Armé **Pulso Energético de EE. UU.**, un proyecto de datos de punta a punta sobre petróleo y gas natural con datos oficiales de la EIA:

🔹 **Pipeline medallón** (Bronze → Silver → Gold) en Python:
- carga histórica acumulativa, sin duplicados, que no pisa datos ya cargados;
- validación antes de publicar cada capa;
- auditoría de las revisiones que hace la EIA.

🔹 **Dashboard web** en Next.js que se actualiza solo todos los días con una GitHub Action: precios, inventarios, producción, consumo y frescura de cada fuente.

🔹 **Versión en Microsoft Fabric:** Lakehouse, notebooks PySpark con MERGE en Delta y pipeline de Data Factory. Más la especificación de un informe **Power BI** con modelo estrella y 53 medidas DAX.

Lo que más me interesó fue la pregunta del rezago. Comparé la variación mensual del WTI con la de la producción de crudo, de 0 a 12 meses después:

📈 Con la historia completa (2010–2026), el mayor parecido aparece al **mes** (r = 0,36).
📉 Si saco 2020–2021, se corre a los **7 meses**, y con una relación más débil (r = 0,20).

La pandemia, con precio y producción desplomándose y rebotando casi juntos, alcanza para cambiar la respuesta. Por eso el dashboard muestra los dos escenarios y una advertencia clara: es **correlación, no causalidad**.

Algunos datos del último corte:
- WTI en **US$ 89,53**, un 6,8 % arriba de su promedio de 12 meses.
- Inventarios comerciales de crudo: **417,8 millones de barriles**.
- La **generación eléctrica** se lleva el **55,4 %** del gas que consume el país.

🔗 Dashboard: [URL del dashboard]
💻 Código: https://github.com/licgermancardenas-crypto/ENERGIA-EEUU

Gracias a Edgar Saico Zea y Vicente Antonio Juan Magallanes: su proyecto sobre la EIA fue la inspiración para este.

¿Qué otra pregunta le harían a estos datos? 👇

#DataEngineering #PowerBI #MicrosoftFabric #Python #NextJS #Energía #Petróleo #GasNatural #DataAnalytics
