// Detalles visuales opcionales de la web. Poner en false apaga cada uno sin tocar el resto.
export const FLAGS = {
  /** B1: el fondo de los mapas oscuros cambia sutilmente de tono según la hora local */
  diaNoche: true,
  /** B2: capa de luces nocturnas (NASA GIBS, VIIRS Black Marble 2016) en el Mapa gas */
  lucesNocturnas: true,
  /** B3: parallax suave (máx. 20 px) en la foto del hero de la portada */
  parallax: true,
  /** B4: botón "Modo presentación" en la portada (pantalla completa y recorrido automático) */
  modoPresentacion: true,
} as const;
