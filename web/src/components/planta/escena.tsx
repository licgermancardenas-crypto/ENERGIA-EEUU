"use client";
/* eslint-disable react-hooks/immutability -- en React Three Fiber la animación muta objetos de
   three.js (geometrías, cámara) dentro de useFrame, fuera del render: es el patrón de la librería. */

// Escena 3D isométrica de /planta (React Three Fiber). Solo se carga en el navegador.
import { OrbitControls, OrthographicCamera } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";

import { fechaCorta, num } from "@/lib/formato";

import { Conteo } from "../mapa-animado/conteo";
import { GUION_PLANTA } from "./guion";
import { extension, RefineriaReal, type RefineriaOSM } from "./refineria-real";
import type { ModoPlanta } from "./index";
import { Agua, Arboles, Bomba, Buque, C, Plataforma, Refineria, Suelo, TanqueCrudo, TanqueGas, Tuberia } from "./modelos";
import type { DatosPlanta, Ficha, Indicador, Refinacion, Zona } from "./tipos";

// Centro y zoom de cada zona (zoom pensado para un lienzo de ~1200 px de ancho).
const ZONAS: Record<Zona, { centro: [number, number, number]; zoom: number; nombre: string }> = {
  general: { centro: [0, 0, 2], zoom: 7.6, nombre: "Vista general" },
  costa: { centro: [-50, 2, 3], zoom: 17, nombre: "Costa afuera" },
  refineria: { centro: [-4, 3, -10], zoom: 21, nombre: "Refinería" },
  almacenamiento: { centro: [16, 2, 10], zoom: 20, nombre: "Almacenamiento" },
  campo: { centro: [34, 1, -14], zoom: 20, nombre: "Campo" },
};
const DISTANCIA = 90;
const ANGULO_BASE = Math.PI / 4; // isométrico: 45° en planta

const FICHAS: Ficha[] = [
  { id: "tanques", titulo: "Tanques de crudo", representa: "El nivel de crudo (naranja) y el techo flotante suben con el inventario comercial de crudo de EE. UU.", indicador: "crudo", zona: "almacenamiento" },
  { id: "spr", titulo: "Reserva estratégica", representa: "Tanques con banda azul: su nivel sigue a la Reserva Estratégica de Petróleo (SPR). La SPR real está en cavernas de sal, no en tanques.", indicador: "spr", zona: "almacenamiento" },
  { id: "gas", titulo: "Gasómetros", representa: "La campana celeste sube con el gas natural almacenado en los 48 estados contiguos.", indicador: "gas", zona: "almacenamiento" },
  { id: "bombas", titulo: "Bombas de petróleo", representa: "El ritmo del cabeceo sigue a la producción de crudo de EE. UU. (más producción, más rápido).", indicador: "produccion", zona: "campo" },
  { id: "refineria", titulo: "Refinería", representa: "El humo de las chimeneas y el tamaño de la antorcha siguen a la utilización de las refinerías.", indicador: "utilizacion", zona: "refineria" },
  { id: "plataforma", titulo: "Plataforma costa afuera", representa: "Ilustrativa: esta escena no tiene un dato propio de la producción costa afuera.", indicador: null, zona: "costa" },
  { id: "buque", titulo: "Buque petrolero", representa: "Ilustrativo. Como referencia, el precio del crudo WTI.", indicador: "wti", zona: "costa" },
];

function valorTexto(i: Indicador) {
  if (i.valor == null) return "no disponible";
  const dec = i.key === "RWTC_D" || i.key === "WPULEUS3_W" ? (i.key === "WPULEUS3_W" ? 1 : 2) : 0;
  return `${i.key === "RWTC_D" ? "US$ " : ""}${num(i.valor, dec)}${i.key === "WPULEUS3_W" ? " %" : ""}`;
}

// ------------------------------------------------------------------ cámara
function Camara({ zona, giro, animar, orbita, controles, panel, objetivo }:
  { zona: Zona; giro: number; animar: boolean; orbita: boolean; controles: React.RefObject<OrbitControlsImpl | null>; panel: number;
    /** modo real: encuadra un área de `ext` unidades centrada en el origen */
    objetivo?: { ext: number; id: string } | null }) {
  const { camera, size, invalidate } = useThree();
  // el panel lateral tapa la derecha: se corre el encuadre para que la escena quede en lo visible
  useEffect(() => {
    const cam = camera as THREE.OrthographicCamera;
    if (panel > 0) cam.setViewOffset(size.width, size.height, panel / 2, 0, size.width, size.height);
    else cam.clearViewOffset();
    cam.updateProjectionMatrix();
    invalidate();
  }, [camera, size, panel, invalidate]);
  const escala = Math.max(0.45, (size.width - panel) / 1200);
  const meta = useRef({ centro: new THREE.Vector3(...ZONAS.general.centro), zoom: ZONAS.general.zoom * escala, angulo: ANGULO_BASE });
  useEffect(() => {
    if (objetivo) {
      meta.current.centro.set(0, 0, 0);
      meta.current.zoom = ((size.width - panel) * 0.62) / objetivo.ext;
    } else {
      meta.current.centro.set(...ZONAS[zona].centro);
      meta.current.zoom = ZONAS[zona].zoom * escala;
    }
    meta.current.angulo = ANGULO_BASE + (giro * Math.PI) / 180;
    invalidate();
  }, [zona, giro, escala, invalidate, objetivo, size.width, panel]);
  useFrame((_, dt) => {
    const c = controles.current;
    if (!c) return;
    const k = animar ? 1 - Math.exp(-dt * 2.2) : 1;
    const cam = camera as THREE.OrthographicCamera;
    const delta = meta.current.centro.clone().sub(c.target).multiplyScalar(k);
    if (delta.lengthSq() > 1e-6 || Math.abs(cam.zoom - meta.current.zoom) > 1e-3) {
      c.target.add(delta);
      cam.position.add(delta);
      cam.zoom += (meta.current.zoom - cam.zoom) * k;
      cam.updateProjectionMatrix();
      if (!animar) invalidate();
    }
    if (orbita && animar) {
      // órbita lenta: gira la cámara alrededor del centro
      const off = cam.position.clone().sub(c.target);
      off.applyAxisAngle(new THREE.Vector3(0, 1, 0), dt * 0.06);
      cam.position.copy(c.target).add(off);
    }
    c.update();
  });
  // giro programado (modo grabación y botones): reubica la cámara al ángulo pedido
  useEffect(() => {
    const c = controles.current;
    if (!c) return;
    const off = camera.position.clone().sub(c.target);
    const r = Math.hypot(off.x, off.z);
    const a = meta.current.angulo;
    const destino = new THREE.Vector3(Math.sin(a) * r, off.y, Math.cos(a) * r);
    if (!animar) { camera.position.copy(c.target).add(destino); c.update(); invalidate(); return; }
    let raf = 0;
    const desde = off.clone();
    const t0 = performance.now();
    const paso = () => {
      const s = Math.min(1, (performance.now() - t0) / 2500);
      const e = s < 0.5 ? 2 * s * s : 1 - (-2 * s + 2) ** 2 / 2;
      const a0 = Math.atan2(desde.x, desde.z);
      let da = a - a0;
      while (da > Math.PI) da -= 2 * Math.PI;
      while (da < -Math.PI) da += 2 * Math.PI;
      const ai = a0 + da * e;
      camera.position.set(c.target.x + Math.sin(ai) * r, c.target.y + off.y, c.target.z + Math.cos(ai) * r);
      c.update();
      if (s < 1) raf = requestAnimationFrame(paso);
    };
    raf = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(raf);
  }, [giro, animar, camera, controles, invalidate]);
  return null;
}

// ------------------------------------------------------------------ escena
function Mundo({ datos, animar, baja, onFicha, refinacion }:
  { datos: DatosPlanta; animar: boolean; baja: boolean; onFicha: (f: Ficha | null, e?: { x: number; y: number }) => void;
    refinacion: { escala: number; columnas: number } }) {
  const ficha = (id: string) => FICHAS.find((f) => f.id === id)!;
  const sobre = (id: string) => ({
    onPointerOver: (e: { stopPropagation: () => void; nativeEvent: PointerEvent }) => {
      e.stopPropagation(); document.body.style.cursor = "pointer";
      onFicha(ficha(id), { x: e.nativeEvent.clientX, y: e.nativeEvent.clientY });
    },
    onPointerOut: () => { document.body.style.cursor = ""; onFicha(null); },
    onClick: (e: { stopPropagation: () => void; nativeEvent: MouseEvent }) => {
      e.stopPropagation();
      onFicha(ficha(id), { x: e.nativeEvent.clientX, y: e.nativeEvent.clientY });
    },
  });
  // producción → velocidad del cabeceo (rad/s): 0,6 en el mínimo histórico, 2,4 en el máximo
  const vel = datos.produccion.norm == null ? 1.2 : 0.6 + 1.8 * datos.produccion.norm;
  const arboles = useMemo<[number, number, number][]>(() => {
    const pts: [number, number, number][] = [];
    for (let i = 0; i < (baja ? 18 : 42); i++) {
      const a = i * 2.399, r = 4 + (i % 7) * 1.6;
      const zona = i % 3 === 0 ? [30, 20] : [42, -4];
      pts.push([zona[0] + Math.cos(a) * r * 0.9, 0, zona[1] + Math.sin(a) * r * 0.55]);
    }
    return pts;
  }, [baja]);
  return (
    <group>
      <Suelo />
      <Agua animar={animar} />
      <Arboles puntos={arboles} />
      <group {...sobre("plataforma")}><Plataforma position={[-50, 0, -4]} /></group>
      <group {...sobre("buque")}><Buque animar={animar} /></group>
      <group {...sobre("refineria")}><Refineria position={[-4, 0, -10]} util={datos.utilizacion.norm} animar={animar}
        escala={refinacion.escala} nColumnas={refinacion.columnas} /></group>
      <group {...sobre("tanques")}>
        {[0, 1, 2].flatMap((i) => [0, 1].map((j) => (
          <TanqueCrudo key={`${i}${j}`} position={[8 + i * 6, 0.1, 4 + j * 6]} nivel={datos.crudo.norm} />
        )))}
      </group>
      <group {...sobre("spr")}>
        {[0, 1].map((i) => (
          <TanqueCrudo key={i} position={[8 + i * 7, 0.1, 17]} nivel={datos.spr.norm} radio={2.9} alto={4} banda={C.azul} />
        ))}
      </group>
      <group {...sobre("gas")}>
        {[0, 1, 2].map((i) => <TanqueGas key={i} position={[27, 0.1, 2 + i * 6.5]} nivel={datos.gas.norm} />)}
      </group>
      <group {...sobre("bombas")}>
        {[[28, -20], [34, -22], [40, -19], [27, -11], [33, -9], [40, -10]].map(([x, z], i) => (
          <Bomba key={i} position={[x, 0.1, z]} rotacion={0.4 + (i % 2) * 0.3} velocidad={vel} fase={i * 1.3} animar={animar} />
        ))}
      </group>
      {/* tuberías: crudo en naranja (pulsos ilustrativos, no representan caudal) */}
      <Tuberia animar={animar} color={C.gris2} pulso={C.crudo}
        puntos={[[-50, 6, -4], [-40, 0.4, -6], [-26, 0.4, -6], [-14, 0.4, -6], [-12, 0.4, -10]]} />
      <Tuberia animar={animar} color={C.gris2} pulso={C.crudo} velocidad={0.05}
        puntos={[[4, 0.4, -6], [6, 0.4, 0], [10, 0.4, 1]]} />
      <Tuberia animar={animar} color={C.gris2} pulso={C.crudo} velocidad={0.04}
        puntos={[[30, 0.4, -14], [22, 0.4, -6], [12, 0.4, -2], [9, 0.4, 1]]} />
      <Tuberia animar={animar} color={C.gris} pulso={C.celeste} velocidad={0.05} radio={0.18}
        puntos={[[36, 0.4, -16], [31, 0.4, -4], [27, 0.4, 1]]} />
    </group>
  );
}

export default function EscenaPlanta({ datos, modo, refinacion }:
  { datos: DatosPlanta; modo: ModoPlanta; refinacion: Refinacion }) {
  const [estadoRef, setEstadoRef] = useState("");
  const est = refinacion.estados.find((e) => e.k === estadoRef) ?? null;
  // tamaño de la refinería: raíz de la capacidad del estado frente al de mayor capacidad (Texas)
  const formaRef = est
    ? { escala: 0.45 + 0.7 * Math.sqrt(est.bcd / refinacion.maxBcd), columnas: Math.min(4, est.n) }
    : { escala: 1, columnas: 4 };
  const animar = !modo.movimientoReducido;
  const controles = useRef<OrbitControlsImpl | null>(null);
  const [zona, setZona] = useState<Zona>("general");
  const [giro, setGiro] = useState(0);
  const [orbita, setOrbita] = useState(false);
  const [hover, setHover] = useState<{ f: Ficha; x: number; y: number } | null>(null);
  const [elegida, setElegida] = useState<Ficha | null>(null);
  const [titulo, setTitulo] = useState(false);
  // ---- modo "Refinería real" (geometría de OpenStreetMap, se baja al elegir cada refinería)
  const [vista, setVista] = useState<"maqueta" | "real">("maqueta");
  const [indice, setIndice] = useState<IndiceOSM | null>(null);
  const [idReal, setIdReal] = useState("");
  const [real, setReal] = useState<RefineriaOSM | null>(null);
  useEffect(() => {
    if (vista !== "real" || indice) return;
    fetch("/data/refinerias-osm/indice.json").then((r) => r.json()).then((d: IndiceOSM) => {
      setIndice(d);
      setIdReal((id) => id || d.refinerias[0]?.id || "");
    });
  }, [vista, indice]);
  useEffect(() => {
    if (vista !== "real" || !idReal) return;
    let vivo = true;
    fetch(`/data/refinerias-osm/${idReal}.json`).then((r) => r.json()).then((d: RefineriaOSM) => {
      if (vivo) setReal(d);
    });
    return () => { vivo = false; };
  }, [vista, idReal]);
  const cargandoReal = vista === "real" && real?.id !== idReal;
  const objetivo = useMemo(() => (vista === "real" && real ? { ext: extension(real), id: real.id } : null), [vista, real]);

  // modo grabación: recorrido automático
  useEffect(() => {
    if (!modo.grabacion) return;
    const ts = GUION_PLANTA.map((p) => setTimeout(() => {
      setZona(p.zona); setGiro(p.giro);
      if (p.titulo) setTitulo(true);
    }, p.t * 1000));
    return () => ts.forEach(clearTimeout);
  }, [modo.grabacion]);

  const ir = (z: Zona) => { setZona(z); setGiro(0); };
  // ancho que ocupa el panel sobre el lienzo (en pantallas chicas va debajo, no encima)
  const panel = !modo.grabacion && typeof window !== "undefined" && window.innerWidth >= 1024 ? 334 : 0;
  const marco = modo.formato === "4x5" ? "aspect-[4/5] h-full max-h-screen" : modo.formato === "1x1" ? "aspect-square h-full max-h-screen" : "h-full w-full";
  const kpis: [keyof DatosPlanta, string][] = [["wti", "#c4531a"], ["crudo", "#c4531a"], ["spr", "#c4531a"], ["gas", "#1f6fd1"], ["produccion", "#c4531a"], ["utilizacion", "#4a5260"]];

  return (
    <div className={modo.grabacion ? "fixed inset-0 z-50 grid place-items-center bg-[#eef1f4]" : "relative h-full"}>
      <div className={`relative overflow-hidden rounded-xl bg-[#eef1f4] ${modo.grabacion ? marco : "h-full"}`}>
        <Canvas shadows={!modo.bajaPotencia && vista === "maqueta"} dpr={modo.bajaPotencia ? 1 : [1, 1.75]} frameloop={animar ? "always" : "demand"}
          gl={{ antialias: true }} aria-label={vista === "real" && real
            ? `Refinería ${real.empresa} en ${real.sitio}, ${real.estado}: geometría de OpenStreetMap en 3D`
            : "Escena 3D esquemática de instalaciones de petróleo y gas"}
          onPointerMissed={() => setHover(null)}>
          <color attach="background" args={["#eef1f4"]} />
          <OrthographicCamera makeDefault position={[DISTANCIA * Math.sin(ANGULO_BASE) + 4, DISTANCIA * 0.8, DISTANCIA * Math.cos(ANGULO_BASE)]} zoom={9} near={-500} far={1000} />
          <OrbitControls ref={controles} makeDefault enableDamping={animar} minZoom={vista === "real" ? 0.2 : 4} maxZoom={60}
            maxPolarAngle={Math.PI / 2.6} minPolarAngle={0.35} target={[4, 0, 0]} />
          <Camara zona={zona} giro={giro} animar={animar} orbita={orbita} controles={controles} panel={panel} objetivo={objetivo} />
          <hemisphereLight args={["#ffffff", "#c9d3df", 1.1]} />
          <directionalLight position={[30, 60, 25]} intensity={2.2} castShadow={!modo.bajaPotencia}
            shadow-mapSize={[2048, 2048]} shadow-camera-left={-80} shadow-camera-right={80}
            shadow-camera-top={60} shadow-camera-bottom={-60} shadow-bias={-0.0004} />
          {vista === "maqueta" ? (
            <Mundo datos={datos} animar={animar} baja={modo.bajaPotencia} refinacion={formaRef}
              onFicha={(f, e) => setHover(f && e ? { f, x: e.x, y: e.y } : null)} />
          ) : real && <RefineriaReal r={real} util={datos.utilizacion.norm} animar={animar} />}
        </Canvas>

        {vista === "maqueta" ? (
          <p className="pointer-events-none absolute bottom-3 left-3 z-10 max-w-[300px] rounded-md bg-white/90 px-2.5 py-1.5 text-[11px] text-tinta-2 shadow">
            Escena esquemática: no representa una instalación real ni su operación. Los pulsos en las
            tuberías son ilustrativos, no representan caudal.
          </p>
        ) : (
          <p className="absolute bottom-3 left-3 z-10 max-w-[360px] rounded-md bg-white/95 px-2.5 py-1.5 text-[11px] text-tinta-2 shadow">
            Geometría de OpenStreetMap (© <a className="underline" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">colaboradores de OpenStreetMap</a>,
            licencia ODbL). Alturas estimadas cuando OSM no las trae. Capacidad: EIA.
            {cargandoReal && " Cargando…"}
          </p>
        )}

        {modo.grabacion && (
          <>
            <div className={`pointer-events-none absolute inset-x-0 top-0 z-10 p-5 transition-opacity duration-1000 ${titulo ? "opacity-0" : "opacity-100"}`}>
              <p className="text-[11px] font-semibold tracking-wide text-gas">PULSO ENERGÉTICO DE EE. UU.</p>
              <p className="text-xl font-semibold text-tinta">Petróleo y gas, movidos por datos reales</p>
            </div>
            <div className={`pointer-events-none absolute inset-0 z-20 grid place-items-center bg-white/92 p-8 text-center transition-opacity duration-1000 ${titulo ? "opacity-100" : "opacity-0"}`}>
              <div>
                <p className="text-xs font-semibold tracking-wide text-gas">PULSO ENERGÉTICO DE EE. UU.</p>
                <p className="mt-2 text-3xl font-semibold text-tinta">Cada tanque, bomba y antorcha<br />sigue un dato de la EIA</p>
                <p className="mt-3 text-sm text-tinta-2">
                  Crudo comercial {valorTexto(datos.crudo)} miles de barriles · Gas {valorTexto(datos.gas)} Bcf ·
                  Refinerías al {valorTexto(datos.utilizacion)}
                </p>
                <p className="mt-6 text-[11px] text-tinta-3">Fuente: U.S. Energy Information Administration (EIA), API v2 · Escena esquemática, modelos propios · Autor: Germán Cárdenas</p>
              </div>
            </div>
          </>
        )}
      </div>

      {hover && !modo.grabacion && (
        <div role="tooltip" className="pointer-events-none fixed z-50 max-w-[280px] rounded-lg border border-linea bg-white p-3 text-xs shadow-lg"
          style={{ left: Math.min(hover.x + 14, window.innerWidth - 300), top: hover.y + 14 }}>
          <FichaTexto f={hover.f} datos={datos} />
        </div>
      )}

      {!modo.grabacion && (
        <aside className="absolute right-3 top-3 bottom-3 z-10 w-[310px] overflow-y-auto rounded-xl border border-linea bg-white/95 p-4 shadow-lg max-lg:static max-lg:mt-3 max-lg:w-full"
          aria-label="Indicadores y controles de la escena">
          <div role="group" aria-label="Modo de la escena" className="mb-3 grid grid-cols-2 gap-1 rounded-lg bg-[#eef1f4] p-1">
            {(["maqueta", "real"] as const).map((v) => (
              <button key={v} type="button" aria-pressed={vista === v} onClick={() => setVista(v)}
                className={`rounded-md px-2 py-1.5 text-xs font-semibold ${vista === v ? "bg-white text-gas shadow" : "text-tinta-2 hover:text-tinta"}`}>
                {v === "maqueta" ? "Maqueta" : "Refinería real"}
              </button>
            ))}
          </div>
          {vista === "real" && (
            <PanelReal indice={indice} idReal={idReal} setIdReal={setIdReal} real={real}
              util={datos.utilizacion} volverMaqueta={() => setVista("maqueta")} />
          )}
          <div className={vista === "real" ? "hidden" : ""}>
          <div className="grid grid-cols-2 gap-2">
            {kpis.map(([k, color]) => {
              const i = datos[k];
              return (
                <div key={k} className="rounded-lg border border-linea p-2">
                  <p className="text-[10px] font-semibold uppercase tracking-wide" style={{ color }}>{i.nombre}</p>
                  <p className="cifra text-lg font-semibold text-tinta">
                    <Conteo valor={i.valor} decimales={k === "wti" ? 2 : k === "utilizacion" ? 1 : 0} animar={animar}
                      prefijo={k === "wti" ? "US$ " : ""} />{k === "utilizacion" && i.valor != null ? " %" : ""}
                  </p>
                  <p className="text-[10px] text-tinta-3">{i.unidad}{i.fecha ? ` · ${fechaCorta(i.fecha)}` : ""}</p>
                </div>
              );
            })}
          </div>

          <label className="mt-4 block text-[11px] font-semibold tracking-wide text-tinta-3" htmlFor="estado-ref">
            REFINERÍAS DE UN ESTADO
          </label>
          <select id="estado-ref" value={estadoRef} onChange={(e) => { setEstadoRef(e.target.value); if (e.target.value) ir("refineria"); }}
            className="mt-1 w-full rounded-md border border-linea bg-white px-2 py-1.5 text-xs">
            <option value="">Todo el país</option>
            {refinacion.estados.map((e) => <option key={e.k} value={e.k}>{e.nombre} ({e.n})</option>)}
          </select>
          <div className="mt-1.5 rounded-lg border border-linea bg-[#fbf7ec] p-2.5 text-xs text-tinta-2" aria-live="polite">
            {est ? (
              <>
                <p className="font-semibold text-tinta">{est.nombre}: {est.n} {est.n === 1 ? "refinería" : "refinerías"}</p>
                <p>{num(est.bcd, 0)} barriles por día de capacidad de destilación ({num((est.bcd / refinacion.estados.reduce((s, e) => s + e.bcd, 0)) * 100, 1)} % del país)</p>
                {est.mayores.length > 0 && <p className="mt-1">Mayores: {est.mayores.map((r) => `${r.sitio} (${num(r.bcd / 1000, 0)} mil b/d)`).join(" · ")}</p>}
                <p className="mt-1 text-tinta-3">La refinería de la escena cambia de tamaño con la capacidad del estado y muestra hasta 4 columnas según cuántas refinerías tiene.</p>
              </>
            ) : <p>Elegí un estado para ver cuántas refinerías tiene y su capacidad (EIA, al 1/1/{refinacion.anio ?? "—"}).</p>}
          </div>

          <p className="mt-4 text-[11px] font-semibold tracking-wide text-tinta-3">IR A</p>
          <div className="mt-1 grid grid-cols-2 gap-1.5">
            {(Object.keys(ZONAS) as Zona[]).map((z) => (
              <button key={z} type="button" onClick={() => ir(z)} aria-pressed={zona === z}
                className={`rounded-md border px-2 py-1.5 text-xs ${zona === z ? "border-gas bg-[#e8f0fb] text-gas" : "border-linea text-tinta-2 hover:border-gas"}`}>
                {ZONAS[z].nombre}
              </button>
            ))}
          </div>
          <label className="mt-2 flex cursor-pointer items-center gap-2 text-xs text-tinta-2">
            <input type="checkbox" checked={orbita} disabled={!animar} onChange={(e) => setOrbita(e.target.checked)} />
            Órbita lenta de la cámara{!animar ? " (desactivada: movimiento reducido)" : ""}
          </label>

          <p className="mt-4 text-[11px] font-semibold tracking-wide text-tinta-3">INSTALACIONES</p>
          <ul className="mt-1 grid gap-1">
            {FICHAS.map((f) => (
              <li key={f.id}>
                <button type="button" onClick={() => { setElegida(f); ir(f.zona); }}
                  className={`w-full rounded-md border px-2 py-1 text-left text-xs ${elegida?.id === f.id ? "border-gas text-gas" : "border-linea text-tinta-2 hover:border-gas"}`}>
                  {f.titulo}
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-2 rounded-lg border border-linea bg-[#f8f9fb] p-2.5 text-xs" aria-live="polite">
            {elegida ? <FichaTexto f={elegida} datos={datos} /> : <p className="text-tinta-3">Pasá el mouse por una instalación o elegila en la lista para ver qué dato representa.</p>}
          </div>
          </div>
        </aside>
      )}
    </div>
  );
}

function FichaTexto({ f, datos }: { f: Ficha; datos: DatosPlanta }) {
  const i = f.indicador ? datos[f.indicador] : null;
  return (
    <>
      <p className="text-[13px] font-semibold text-tinta">{f.titulo}</p>
      <p className="mt-1 text-tinta-2">{f.representa}</p>
      {i && (
        <p className="mt-1.5 text-tinta">
          <strong>{i.nombre}:</strong> {valorTexto(i)} {i.key === "RWTC_D" || i.key === "WPULEUS3_W" ? "" : i.unidad}
          {i.fecha ? ` (${fechaCorta(i.fecha)})` : ""}
          {i.key === "WCSSTUS1_W" && i.variacion != null ? ` · ${i.variacion > 0 ? "+" : ""}${num(i.variacion, 0)} en la semana` : ""}
          {i.norm != null && <span className="block text-tinta-3">Posición en su rango desde {i.desde.slice(0, 4)}: {num(i.norm * 100, 0)} % (mín. {num(i.min, 0)}, máx. {num(i.max, 0)})</span>}
        </p>
      )}
    </>
  );
}

// ------------------------------------------------------------------ panel del modo real
interface IndiceOSM {
  anio_capacidad: number | null;
  refinerias: { id: string; empresa: string; sitio: string; estado: string; bcd: number;
    cobertura: RefineriaOSM["cobertura"]; nivel_cobertura: RefineriaOSM["nivel_cobertura"]; extraido: string }[];
}

function PanelReal({ indice, idReal, setIdReal, real, util, volverMaqueta }:
  { indice: IndiceOSM | null; idReal: string; setIdReal: (id: string) => void; real: RefineriaOSM | null;
    util: Indicador; volverMaqueta: () => void }) {
  if (!indice) return <p className="text-xs text-tinta-3">Cargando la lista de refinerías…</p>;
  const porEstado = new Map<string, IndiceOSM["refinerias"]>();
  for (const r of [...indice.refinerias].sort((a, b) => b.bcd - a.bcd)) {
    porEstado.set(r.estado, [...(porEstado.get(r.estado) ?? []), r]);
  }
  const estimadas = real ? real.tanques.filter((t) => t[4] === 1).length : 0;
  const c = real?.cobertura;
  return (
    <div className="mb-3 text-xs">
      <label htmlFor="ref-real" className="text-[11px] font-semibold tracking-wide text-tinta-3">REFINERÍA</label>
      <select id="ref-real" value={idReal} onChange={(e) => setIdReal(e.target.value)}
        className="mt-1 w-full rounded-md border border-linea bg-white px-2 py-1.5 text-xs">
        {[...porEstado.entries()].map(([est, lista]) => (
          <optgroup key={est} label={est}>
            {lista.map((r) => (
              <option key={r.id} value={r.id}>{r.sitio} · {r.empresa.split(" ").slice(0, 2).join(" ")} ({num(r.bcd / 1000, 0)} mil b/d)</option>
            ))}
          </optgroup>
        ))}
      </select>
      {real && real.id === idReal && (
        <div className="mt-2 rounded-lg border border-linea bg-[#f8f9fb] p-2.5 text-tinta-2" aria-live="polite">
          <p className="text-[13px] font-semibold text-tinta">{real.sitio}, {real.estado}</p>
          <p>{real.empresa}</p>
          <p className="mt-1"><strong className="text-tinta">{num(real.bcd, 0)} barriles por día</strong> de capacidad de destilación de crudo, al 1/1/{real.anio_capacidad ?? "—"} (EIA)</p>
          <p className="mt-2 font-semibold text-tinta">Mapeado en OpenStreetMap</p>
          <p>{c!.tanques} tanques · {c!.chimeneas} chimeneas · {c!.antorchas} antorchas · {c!.torres} torres · {c!.edificios} edificios · {c!.tuberias} tramos de tubería</p>
          <p className={`mt-1 font-semibold ${real.nivel_cobertura === "pobre" ? "text-alerta" : real.nivel_cobertura === "parcial" ? "text-tinta" : "text-ok"}`}>
            Cobertura {real.nivel_cobertura}
          </p>
          {real.nivel_cobertura === "pobre" && (
            <div className="mt-1 rounded-md border border-alerta/40 bg-[#fff7ed] p-2">
              <p>Esta refinería casi no está mapeada en OpenStreetMap: no inventamos estructuras para rellenarla.</p>
              <button type="button" onClick={volverMaqueta} className="mt-1 text-gas underline">Ver la maqueta esquemática</button>
            </div>
          )}
          <ul className="mt-2 list-disc space-y-0.5 pl-4 text-[11px] text-tinta-3">
            <li>Posición y tamaño de los tanques: reales (huella en OSM). Alturas: {estimadas} de {real.tanques.length} tanques sin altura en OSM, estimadas como 0,6 × diámetro (máx. 20 m).</li>
            <li>Techo naranja: tanque de crudo según OSM; celeste: gas; gris: contenido no informado.</li>
            <li>La antorcha se mueve con la utilización de refinerías de todo EE. UU. ({util.valor == null ? "no disponible" : `${num(util.valor, 1)} %`}), no con la de esta refinería.</li>
            <li>{real.predio_osm ? `Predio: ${real.predio_osm} en OSM.` : `Sin predio mapeado: se tomó un radio de ${num((real.radio_busqueda_m ?? 0) / 1000, 0)} km alrededor del punto de la EIA, que puede incluir instalaciones vecinas.`} Datos extraídos el {fechaCorta(real.extraido)}.</li>
          </ul>
        </div>
      )}
    </div>
  );
}
