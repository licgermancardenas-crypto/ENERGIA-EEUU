"use client";

// Modo "Refinería real": geometría de OpenStreetMap (© colaboradores de OSM, ODbL) en su
// posición y tamaño reales. Escala: 1 unidad de la escena = ESCALA_M metros (horizontal y
// vertical iguales, sin exagerar alturas).
import { useFrame } from "@react-three/fiber";
import { useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

import { C } from "./modelos";

export const ESCALA_M = 10;

/** Archivo web/public/data/refinerias-osm/<id>.json (ver scripts/preparar_refinerias_osm.py). */
export interface RefineriaOSM {
  id: string; empresa: string; sitio: string; estado: string; bcd: number; anio_capacidad: number | null;
  centro: [number, number]; extraido: string; licencia: string; predio_osm: string | null;
  radio_busqueda_m: number | null; predio: [number, number][] | null;
  cobertura: { tanques: number; chimeneas: number; antorchas: number; torres: number; edificios: number; tuberias: number };
  nivel_cobertura: "buena" | "parcial" | "pobre";
  /** x, y (m, este y norte), radio, alto, alto estimado (1/0), radio estimado (1/0), contenido */
  tanques: [number, number, number, number, number, number, string][];
  chimeneas: [number, number, number, number][];
  antorchas: [number, number, number, number][];
  torres: [number, number, number, number, string][];
  edificios: { p: [number, number][]; h: number; e: number }[];
  tuberias: [number, number][][];
}

const s = (v: number) => v / ESCALA_M;
/** Este → x, norte → -z (three.js mira hacia -z). */
const pos = (x: number, y: number): [number, number] => [s(x), -s(y)];

/** Extensión en unidades de escena, para encuadrar la cámara. */
/** Encuadre: la zona donde hay estructuras mapeadas (percentiles 5–95, para que un tanque
 *  suelto en un rincón no achique todo), o el predio si no hay estructuras. En unidades de escena. */
export function encuadre(r: RefineriaOSM): { ext: number; cx: number; cz: number } {
  let pts: [number, number][] = [
    ...r.tanques.map((t) => [t[0], t[1]] as [number, number]),
    ...r.chimeneas.map((t) => [t[0], t[1]] as [number, number]),
    ...r.edificios.map((b) => b.p[0]),
  ];
  if (pts.length < 5) pts = r.predio ?? [[-(r.radio_busqueda_m ?? 1500), 0], [r.radio_busqueda_m ?? 1500, 0]];
  const q = (v: number[], f: number) => [...v].sort((a, b) => a - b)[Math.floor((v.length - 1) * f)];
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const [x0, x1, y0, y1] = [q(xs, 0.05), q(xs, 0.95), q(ys, 0.05), q(ys, 0.95)];
  const [cx, cz] = pos((x0 + x1) / 2, (y0 + y1) / 2);
  return { ext: s(Math.max(x1 - x0, y1 - y0, 300)), cx, cz };
}

/** Extensión total (predio o estructuras), para el tamaño del terreno. */
export function extension(r: RefineriaOSM): number {
  const pts: [number, number][] = r.predio ?? [
    ...r.tanques.map((t) => [t[0], t[1]] as [number, number]),
    ...r.edificios.flatMap((b) => b.p),
  ];
  if (!pts.length) return s(r.radio_busqueda_m ?? 1500) * 2;
  const xs = pts.map((p) => Math.abs(p[0])), ys = pts.map((p) => Math.abs(p[1]));
  return s(Math.max(...xs, ...ys, 400) * 2);
}

function Instanciados({ datos, geometria, color, emisivo }:
  { datos: { x: number; z: number; sx: number; sy: number; sz: number; y?: number }[];
    geometria: THREE.BufferGeometry; color: string | ((i: number) => string); emisivo?: boolean }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  useLayoutEffect(() => {
    const m = ref.current;
    if (!m) return;
    const mat = new THREE.Matrix4();
    const c = new THREE.Color();
    datos.forEach((d, i) => {
      mat.compose(new THREE.Vector3(d.x, d.y ?? d.sy / 2, d.z), new THREE.Quaternion(),
        new THREE.Vector3(d.sx, d.sy, d.sz));
      m.setMatrixAt(i, mat);
      if (typeof color === "function") m.setColorAt(i, c.set(color(i)));
    });
    m.instanceMatrix.needsUpdate = true;
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
  }, [datos, color]);
  if (!datos.length) return null;
  return (
    <instancedMesh ref={ref} args={[geometria, undefined, datos.length]}>
      <meshStandardMaterial color={typeof color === "string" ? color : "#ffffff"} roughness={0.85}
        emissive={emisivo ? C.llama : "#000000"} emissiveIntensity={emisivo ? 1.4 : 0} toneMapped={!emisivo} />
    </instancedMesh>
  );
}

const CIL = new THREE.CylinderGeometry(1, 1, 1, 24);
const CIL_FINO = new THREE.CylinderGeometry(1, 1, 1, 10);
const CONO = new THREE.ConeGeometry(1, 1, 10);

export function RefineriaReal({ r, util, animar }: { r: RefineriaOSM; util: number | null; animar: boolean }) {
  const lado = extension(r) * 1.25;

  const tanques = useMemo(() => r.tanques.map(([x, y, rad, h]) => {
    const [px, pz] = pos(x, y);
    return { x: px, z: pz, sx: s(rad), sy: s(h), sz: s(rad) };
  }), [r]);
  // techo de cada tanque: naranja si OSM dice que guarda crudo, celeste si gas, gris si no se sabe
  const techos = useMemo(() => r.tanques.map(([x, y, rad, h]) => {
    const [px, pz] = pos(x, y);
    return { x: px, z: pz, sx: s(rad) * 0.98, sy: 0.06, sz: s(rad) * 0.98, y: s(h) + 0.03 };
  }), [r]);
  const colorTecho = useMemo(() => (i: number) => {
    const c = r.tanques[i][6];
    return c === "oil" || c === "crude_oil" ? C.crudo : ["gas", "LPG", "LNG"].includes(c) ? C.celeste : C.gris3;
  }, [r]);
  const chimeneas = useMemo(() => r.chimeneas.map(([x, y, h]) => {
    const [px, pz] = pos(x, y);
    return { x: px, z: pz, sx: 0.25, sy: s(h), sz: 0.25 };
  }), [r]);
  const torres = useMemo(() => r.torres.map(([x, y, h]) => {
    const [px, pz] = pos(x, y);
    return { x: px, z: pz, sx: 1.2, sy: s(h), sz: 1.2 };
  }), [r]);
  const antorchas = useMemo(() => r.antorchas.map(([x, y, h]) => {
    const [px, pz] = pos(x, y);
    return { x: px, z: pz, h: s(h) };
  }), [r]);

  // edificios: cada contorno se extruye a su altura y todo se une en una sola malla
  const edificios = useMemo(() => {
    const geos = r.edificios.map((b) => {
      const forma = new THREE.Shape(b.p.map(([x, y]) => new THREE.Vector2(s(x), s(y))));
      const g = new THREE.ExtrudeGeometry(forma, { depth: s(b.h), bevelEnabled: false });
      g.rotateX(-Math.PI / 2); // la forma queda en el plano XZ con la altura hacia +Y
      return g.toNonIndexed();
    });
    return geos.length ? mergeGeometries(geos, false) : null;
  }, [r]);
  const tuberias = useMemo(() => {
    const pts: number[] = [];
    for (const l of r.tuberias) {
      for (let i = 1; i < l.length; i++) {
        const [ax, az] = pos(...l[i - 1]), [bx, bz] = pos(...l[i]);
        pts.push(ax, 0.15, az, bx, 0.15, bz);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    return g;
  }, [r]);
  const predio = useMemo(() => {
    if (!r.predio) return null;
    const g = new THREE.ShapeGeometry(new THREE.Shape(r.predio.map(([x, y]) => new THREE.Vector2(s(x), s(y)))));
    g.rotateX(-Math.PI / 2);
    return g;
  }, [r]);

  // antorchas: parpadeo y tamaño según la utilización de refinerías (dato NACIONAL)
  const llamas = useRef<THREE.Group>(null);
  const base = util == null ? 0.7 : 0.5 + util * 0.8;
  useFrame(({ clock }) => {
    const g = llamas.current;
    if (!g) return;
    g.children.forEach((m, i) => {
      const f = animar ? 1 + Math.sin(clock.elapsedTime * 11 + i) * 0.15 : 1;
      m.scale.set(base * 1.2, base * f * 4, base * 1.2);
    });
  });

  return (
    <group>
      <mesh position={[0, -0.05, 0]} receiveShadow>
        <boxGeometry args={[lado, 0.1, lado]} />
        <meshStandardMaterial color={C.suelo} roughness={1} />
      </mesh>
      {predio && (
        <mesh geometry={predio} position={[0, 0.01, 0]}>
          <meshStandardMaterial color="#e4e8ed" roughness={1} />
        </mesh>
      )}
      <lineSegments geometry={tuberias}>
        <lineBasicMaterial color={C.gris3} />
      </lineSegments>
      {edificios && (
        <mesh geometry={edificios}>
          <meshStandardMaterial color={C.blanco} roughness={0.9} />
        </mesh>
      )}
      <Instanciados datos={tanques} geometria={CIL} color={C.blanco} />
      <Instanciados datos={techos} geometria={CIL} color={colorTecho} />
      <Instanciados datos={chimeneas} geometria={CIL_FINO} color={C.gris} />
      <Instanciados datos={torres} geometria={CIL} color={C.gris2} />
      {antorchas.map((a, i) => (
        <mesh key={`f${i}`} position={[a.x, a.h / 2, a.z]}>
          <cylinderGeometry args={[0.15, 0.2, a.h, 8]} />
          <meshStandardMaterial color={C.gris} />
        </mesh>
      ))}
      <group ref={llamas}>
        {antorchas.map((a, i) => (
          <mesh key={`l${i}`} position={[a.x, a.h + 1.2, a.z]} geometry={CONO}>
            <meshStandardMaterial color={C.llama} emissive={C.llama} emissiveIntensity={1.6} toneMapped={false} />
          </mesh>
        ))}
      </group>
    </group>
  );
}
