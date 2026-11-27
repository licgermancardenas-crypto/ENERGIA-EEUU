// Tipos de los JSON que exporta `python -m eia_pulso export-web` desde la capa Gold.

export type Sector = "petroleo" | "gas";
export type Punto = [fecha: string, valor: number];

export interface Serie {
  key: string;
  serie_eia: string;
  nombre: string;
  unidad: string;
  frecuencia: "daily" | "weekly" | "monthly";
  sector: Sector;
  categoria: string;
  dataset: string;
  tabla_gold: string;
  region: string;
  descripcion_eia: string;
}

export interface UltimoDato {
  fecha: string;
  valor: number;
  fecha_anterior: string | null;
  valor_anterior: number | null;
  variacion_abs: number | null;
  variacion_pct: number | null;
}

export interface Frase {
  texto: string;
  valores: Record<string, number | string>;
  fecha: string;
  origen: string;
}

export interface Barras {
  titulo: string;
  unidad: string;
  fecha: string;
  fechas_distintas: boolean;
  items: (UltimoDato & { key: string; nombre: string })[];
}

export interface Destacado {
  banner: { principal: string; indicadores: string[] };
  frases: Frase[];
  barras: Barras;
}

export interface Frescura {
  calculado_al: string;
  datasets: {
    dataset: string;
    sector: Sector;
    categoria: string;
    frecuencia: "daily" | "weekly" | "monthly";
    ultimo_periodo: string;
    fin_periodo: string;
    dias_atraso: number;
    umbral_dias: number;
    estado: "al_dia" | "atrasado";
    filas: number;
  }[];
}

export interface EscenarioRezago {
  id: string;
  etiqueta: string;
  excluir: [string, string] | null;
  rezago_optimo_meses: number | null;
  correlacion: number | null;
  n_obs: number | null;
  desde: string | null;
  hasta: string | null;
  metodo: string;
  criterio: string;
  detalle: { rezago_meses: number; correlacion: number | null; n_obs: number }[];
}

export interface Rezago {
  serie_precio: string;
  serie_produccion: string;
  calculado_al: string;
  advertencia: string;
  escenarios: EscenarioRezago[];
}

export interface Meta {
  gold_generado_utc: string;
  calculado_al: string;
  conteos: Record<string, number>;
  fuente: string;
  fuente_url: string;
}

export interface Datos {
  meta: Meta;
  series: Record<string, Serie>;
  ultimo: Record<string, UltimoDato>;
  hechos: Record<string, Punto[]>;
  frescura: Frescura;
  rezago: Rezago;
  destacados: Record<Sector, Destacado>;
}

// ---------------------------------------------------------------- capa geoespacial
export interface EstadoGeo {
  k: string;
  fips: string;
  nombre: string;
  region: string | null;
  area_km2: number;
  km: number;
  km_inter: number;
  km_intra: number;
  densidad: number;
  operadores: number | null;
  km_hh: number;
  hh: boolean;
  hogares: number | null;
  pct_gas_red: number | null;
  pct_propano: number | null;
  condados_alerta: number | null;
  balance: number | null;
  anio_balance: number | null;
  /** punto interior del estado [lon, lat]: extremo de los arcos de flujo */
  centro: [number, number] | null;
}

/** Flujos interestatales de la EIA (MMcf por año). */
export interface Flujos {
  anios: number[];
  /** [origen, destino, año, MMcf entregados] */
  pares: [string, string, number, number][];
  /** [estado, año, recibe, entrega, neto] */
  estados: [string, number, number | null, number | null, number | null][];
}

/** condado_key -> [nombre, % gas de red, MOE, km a la red, 1 si alta dependencia lejos] */
export type CondadosGeo = Record<string, [string, number | null, number | null, number | null, number]>;

export interface Punto2 { nombre: string; lon: number; lat: number; [k: string]: unknown }

export interface Geo {
  estados: EstadoGeo[];
  condados: CondadosGeo;
  puntos: { hubs: Punto2[]; gnl: Punto2[]; reserva: Punto2[]; centrales: Punto2[] };
  henryHub: { gasoducto: string; operador_en_capa: string | null; en_capa: boolean;
    tipo_en_capa: string | null; km: number; estados_n: number; estados: string;
    nota: string | null }[];
  frescura: { capa: string; tipo: string; origen: string; vintage: string | null;
    registros: number | null; estado: string }[];
  flujos: Flujos;
  fuentes: { conexiones_henry_hub: string; flujos: string };
  validacion: { km_red_total: number; km_dentro_de_estados: number; pct_fuera: number;
    estados_sin_km: string[]; calefaccion: { condados_alta_dependencia_lejos: number } };
}
