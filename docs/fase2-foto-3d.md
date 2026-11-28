# Fase 2 (propuesta, NO implementada): "Ver foto 3D real" con Google Photorealistic 3D Tiles

Estado: **propuesta**. No se crearon claves, no se habilitó facturación y no hay credenciales
en el repo. Fuentes consultadas el 2026-11-28 (las páginas no muestran fecha de actualización).

## Qué sería

Un botón "Ver foto 3D real" en el modo Refinería real que abra la misma refinería sobre las
Photorealistic 3D Tiles de Google (malla 3D texturizada con fotos de alta resolución), dibujadas
con CesiumJS (soportado y documentado por Google, versión 1.91+) o deck.gl (tiene un ejemplo
"Google 3D Tiles").

## Qué requiere

- Proyecto de Google Cloud con **cuenta de facturación** y la **Map Tiles API** habilitada.
- Una **API key** que va en el navegador (la URL raíz es
  `https://tile.googleapis.com/v1/3dtiles/root.json?key=...`): no se puede esconder, se protege
  con restricciones.

## Costos y cuotas (según la tabla de precios de Google)

- SKU "Map Tiles API: Photorealistic 3D Tiles" (categoría Enterprise).
- **1.000 eventos gratis por mes.** Después, USD 6,00 cada 1.000 (hasta 100.000), y menos por
  volumen.
- El evento facturable es la **solicitud que devuelve una tesela 3D**. Una sola visita a una
  refinería puede pedir decenas o cientos de teselas mientras la cámara se mueve. La página de
  SKU no aclara si la solicitud raíz se factura aparte.
- Cuotas: hasta 10.000 solicitudes raíz por día; cada sesión dura al menos 3 horas.
- **Estimación gruesa** (hay que medirla con una prueba real): si una visita pide ~100 teselas,
  1.000 eventos gratis alcanzan para unas 10 visitas por mes, y 1.000 visitas costarían unos
  USD 600. Por eso conviene un tope de gasto bajo y mostrar el botón solo a pedido.

## Términos de uso que hay que cumplir

- Mostrar el **logo de Google Maps** (16 a 19 dp de alto) sin taparlo con otro logo, y la línea de
  atribuciones de datos que traen las teselas (campo `asset.copyright`), juntas y ordenadas,
  normalmente abajo. En CesiumJS: `showCreditsOnScreen: true`.
- **Prohibido** pre-descargar, indexar, guardar o cachear el contenido (salvo lo que permitan los
  encabezados `max-age` y similares), usarlo sin conexión, extraer geodatos o **crear modelos 3D
  derivados** de las teselas. Los tanques de OSM se pueden superponer porque no salen de Google,
  pero hay que aclarar en pantalla qué parte de la escena es de Google.
- Video promocional: máximo 30 segundos y rotulado "solo con fines promocionales".

## Cómo proteger la key

1. Restricción de aplicación **Sitios web (HTTP referrer)**: `https://energia-eeuu.vercel.app/*`
   y, si hace falta, el dominio de previews.
2. Restricción de API: solo **Map Tiles API**.
3. Una key exclusiva para esta web.
4. En Vercel, variable de entorno `NEXT_PUBLIC_GOOGLE_TILES_KEY` (es pública por naturaleza; las
   restricciones son la protección real). Nunca en el repo.
5. En Google Cloud: **presupuesto con alertas** (por ejemplo, USD 5 y USD 20) y **cuota diaria**
   baja para las solicitudes raíz en la página de Cuotas.

## Impacto en rendimiento

- CesiumJS pesa varios MB (bastante más que la escena actual): se cargaría solo al tocar el botón.
- Las teselas fotográficas consumen mucho ancho de banda y GPU; en celulares de gama media puede
  ir lento. Habría que ofrecerlo como opcional, nunca por defecto.

## Lo que tendrías que hacer vos (si lo aprobás)

1. Crear el proyecto y la cuenta de facturación en Google Cloud (requiere tarjeta: lo hacés vos).
2. Habilitar la Map Tiles API, crear la key con las restricciones de arriba y el presupuesto.
3. Cargar la key en Vercel como variable de entorno.

Después yo implemento el botón, la atribución y el corte de carga bajo demanda.
