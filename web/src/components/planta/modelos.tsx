"use client";
/* eslint-disable react-hooks/immutability -- en React Three Fiber la animación muta objetos de
   three.js (geometrías, cámara) dentro de useFrame, fuera del render: es el patrón de la librería. */

// Modelos de la planta, todos propios y hechos con geometrías simples (sin modelos externos).
// Estilo "arcilla": blancos y grises claros, acentos azules; naranja solo para el crudo.
import { useFrame } from "@react-three/fiber";
import { useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";

export const C = {
  blanco: "#f7f7f5", gris: "#dfe3e8", gris2: "#c3cad3", gris3: "#8e98a6",
  azul: "#1f6fd1", celeste: "#5fb3e6", crudo: "#c4531a", pasto: "#a9cf8f", pasto2: "#7fb36b",
  agua: "#79b4e3", suelo: "#ecebe6", llama: "#ffc94d",
};

type Vec = [number, number, number];
interface Anim { animar: boolean }

function Mat({ color, ...p }: { color: string } & Partial<THREE.MeshStandardMaterialParameters>) {
  return <meshStandardMaterial color={color} roughness={0.85} metalness={0.02} {...p} />;
}

// ------------------------------------------------------------------ suelo y agua
export function Suelo() {
  return (
    <group>
      <mesh position={[12, -0.6, 0]} receiveShadow>
        <boxGeometry args={[78, 1.2, 60]} />
        <Mat color={C.suelo} />
      </mesh>
      {/* playa en el borde con el mar */}
      <mesh position={[-26.5, -0.75, 0]} receiveShadow>
        <boxGeometry args={[3, 0.9, 60]} />
        <Mat color="#e6dcc4" />
      </mesh>
      {/* campo: pasto */}
      <mesh position={[34, 0.02, -14]} receiveShadow>
        <boxGeometry args={[30, 0.12, 26]} />
        <Mat color={C.pasto} />
      </mesh>
      <mesh position={[30, 0.02, 20]} receiveShadow>
        <boxGeometry args={[22, 0.12, 14]} />
        <Mat color={C.pasto} />
      </mesh>
    </group>
  );
}

export function Agua({ animar }: Anim) {
  const geo = useMemo(() => {
    const g = new THREE.PlaneGeometry(60, 60, 60, 60);
    g.rotateX(-Math.PI / 2);
    return g;
  }, []);
  const base = useMemo(() => Float32Array.from(geo.attributes.position.array), [geo]);
  useFrame(({ clock }) => {
    if (!animar) return;
    const p = geo.attributes.position as THREE.BufferAttribute;
    const t = clock.elapsedTime;
    for (let i = 0; i < p.count; i++) {
      const x = base[i * 3], z = base[i * 3 + 2];
      p.setY(i, Math.sin(x * 0.35 + t * 1.1) * 0.12 + Math.cos(z * 0.45 + t * 0.8) * 0.1);
    }
    p.needsUpdate = true;
    geo.computeVertexNormals();
  });
  return (
    <mesh geometry={geo} position={[-58, -0.55, 0]} receiveShadow>
      <meshStandardMaterial color={C.agua} roughness={0.35} metalness={0.05} flatShading />
    </mesh>
  );
}

// ------------------------------------------------------------------ árboles (instanciados)
export function Arboles({ puntos }: { puntos: Vec[] }) {
  const copa = useRef<THREE.InstancedMesh>(null);
  const tronco = useRef<THREE.InstancedMesh>(null);
  useLayoutEffect(() => {
    const m = new THREE.Matrix4();
    puntos.forEach((p, i) => {
      const s = 0.8 + ((i * 37) % 10) / 20;
      m.compose(new THREE.Vector3(p[0], 1.6 * s, p[2]), new THREE.Quaternion(), new THREE.Vector3(s, s, s));
      copa.current!.setMatrixAt(i, m);
      m.compose(new THREE.Vector3(p[0], 0.4, p[2]), new THREE.Quaternion(), new THREE.Vector3(1, 1, 1));
      tronco.current!.setMatrixAt(i, m);
    });
    copa.current!.instanceMatrix.needsUpdate = true;
    tronco.current!.instanceMatrix.needsUpdate = true;
  }, [puntos]);
  return (
    <group>
      <instancedMesh ref={copa} args={[undefined, undefined, puntos.length]} castShadow>
        <coneGeometry args={[0.9, 2.2, 7]} />
        <Mat color={C.pasto2} flatShading />
      </instancedMesh>
      <instancedMesh ref={tronco} args={[undefined, undefined, puntos.length]}>
        <cylinderGeometry args={[0.15, 0.18, 0.8, 6]} />
        <Mat color="#b8a58a" />
      </instancedMesh>
    </group>
  );
}

// ------------------------------------------------------------------ tuberías con pulsos
export function Tuberia({ puntos, color, pulso, animar, velocidad = 0.06, radio = 0.22 }:
  { puntos: Vec[]; color: string; pulso: string; animar: boolean; velocidad?: number; radio?: number }) {
  const curva = useMemo(() => new THREE.CatmullRomCurve3(puntos.map((p) => new THREE.Vector3(...p)), false, "catmullrom", 0.1), [puntos]);
  const pulsos = useRef<THREE.Mesh[]>([]);
  const n = 4;
  useFrame(({ clock }) => {
    pulsos.current.forEach((m, i) => {
      if (!m) return;
      const t = animar ? (clock.elapsedTime * velocidad + i / n) % 1 : i / n;
      m.position.copy(curva.getPointAt(t));
      m.visible = animar;
    });
  });
  return (
    <group>
      <mesh castShadow>
        <tubeGeometry args={[curva, 80, radio, 8, false]} />
        <Mat color={color} />
      </mesh>
      {Array.from({ length: n }, (_, i) => (
        <mesh key={i} ref={(m) => { if (m) pulsos.current[i] = m; }}>
          <sphereGeometry args={[radio * 1.6, 10, 10]} />
          <meshStandardMaterial color={pulso} emissive={pulso} emissiveIntensity={1.4} toneMapped={false} />
        </mesh>
      ))}
    </group>
  );
}

// ------------------------------------------------------------------ plataforma offshore
export function Plataforma({ position }: { position: Vec }) {
  return (
    <group position={position}>
      {[[-3, -3], [3, -3], [-3, 3], [3, 3]].map(([x, z]) => (
        <mesh key={`${x}${z}`} position={[x, 2.5, z]} castShadow>
          <cylinderGeometry args={[0.35, 0.45, 7, 12]} />
          <Mat color={C.gris} />
        </mesh>
      ))}
      <mesh position={[0, 6.2, 0]} castShadow receiveShadow>
        <boxGeometry args={[9, 0.7, 9]} />
        <Mat color={C.blanco} />
      </mesh>
      <mesh position={[-1, 7.6, -1]} castShadow>
        <boxGeometry args={[6, 2, 5]} />
        <Mat color={C.gris} />
      </mesh>
      {/* torre de perforación: tronco piramidal de 4 caras */}
      <mesh position={[2.3, 10.5, 2.3]} castShadow>
        <cylinderGeometry args={[0.35, 1.4, 8, 4]} />
        <Mat color={C.blanco} flatShading />
      </mesh>
      <mesh position={[2.3, 14.7, 2.3]}>
        <boxGeometry args={[0.9, 0.5, 0.9]} />
        <Mat color={C.azul} />
      </mesh>
      {/* helipuerto */}
      <mesh position={[-2.5, 8.75, 2.2]} castShadow>
        <cylinderGeometry args={[1.8, 1.8, 0.25, 24]} />
        <Mat color={C.azul} />
      </mesh>
      <mesh position={[-2.5, 8.9, 2.2]}>
        <torusGeometry args={[1.2, 0.08, 6, 24]} />
        <Mat color={C.blanco} />
      </mesh>
      {/* grúa */}
      <mesh position={[3.4, 8.6, -3]} rotation={[0, 0.6, -0.5]} castShadow>
        <boxGeometry args={[6, 0.3, 0.3]} />
        <Mat color={C.celeste} />
      </mesh>
    </group>
  );
}

// ------------------------------------------------------------------ buque petrolero
export function Buque({ animar }: Anim) {
  const ref = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    const g = ref.current;
    if (!g) return;
    const t = animar ? clock.elapsedTime * 0.035 : 0.3; // una vuelta cada ~3 minutos
    const a = t * Math.PI * 2;
    g.position.set(-52 + Math.cos(a) * 14, -0.2 + (animar ? Math.sin(clock.elapsedTime * 1.3) * 0.08 : 0), 4 + Math.sin(a) * 20);
    g.rotation.y = -a + Math.PI; // mira en la dirección de avance
  });
  const proa = useMemo(() => {
    const s = new THREE.Shape();
    s.moveTo(-7, -1.8); s.lineTo(5, -1.8); s.quadraticCurveTo(8.5, 0, 5, 1.8); s.lineTo(-7, 1.8); s.lineTo(-7, -1.8);
    return new THREE.ExtrudeGeometry(s, { depth: 1.6, bevelEnabled: false }).rotateX(-Math.PI / 2);
  }, []);
  return (
    <group ref={ref}>
      <mesh geometry={proa} position={[0, -0.4, 0]} castShadow>
        <Mat color={C.azul} />
      </mesh>
      <mesh position={[-0.5, 1.3, 0]} castShadow>
        <boxGeometry args={[12, 0.3, 3.4]} />
        <Mat color={C.blanco} />
      </mesh>
      <mesh position={[-5.6, 2.6, 0]} castShadow>
        <boxGeometry args={[1.8, 2.4, 3]} />
        <Mat color={C.blanco} />
      </mesh>
      <mesh position={[-5.9, 4.1, 0]}>
        <cylinderGeometry args={[0.3, 0.35, 1, 10]} />
        <Mat color={C.azul} />
      </mesh>
      {[-3, -0.5, 2, 4.5].map((x) => (
        <mesh key={x} position={[x, 1.65, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.12, 0.12, 2.6, 8]} />
          <Mat color={C.gris2} />
        </mesh>
      ))}
    </group>
  );
}

// ------------------------------------------------------------------ refinería
export function Refineria({ position, util, animar }: { position: Vec; util: number | null; animar: boolean }) {
  const columnas: [number, number, number, number][] = [[-4, -2, 1.1, 12], [-1, -3, 0.9, 9], [1.8, -2.2, 0.75, 7], [-2.5, 1.5, 0.7, 6]];
  return (
    <group position={position}>
      <mesh position={[0, 0.15, 0]} receiveShadow>
        <boxGeometry args={[18, 0.3, 14]} />
        <Mat color={C.gris} />
      </mesh>
      {columnas.map(([x, z, r, h]) => (
        <group key={`${x}${z}`} position={[x, 0, z]}>
          <mesh position={[0, h / 2, 0]} castShadow>
            <cylinderGeometry args={[r, r * 1.05, h, 20]} />
            <Mat color={C.blanco} />
          </mesh>
          {Array.from({ length: Math.floor(h / 3) }, (_, i) => (
            <mesh key={i} position={[0, 2.5 + i * 3, 0]}>
              <torusGeometry args={[r + 0.12, 0.08, 6, 24]} />
              <Mat color={i === 0 ? C.azul : C.gris2} />
            </mesh>
          ))}
          <mesh position={[0, h + 0.3, 0]}>
            <sphereGeometry args={[r * 0.95, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2]} />
            <Mat color={C.blanco} />
          </mesh>
        </group>
      ))}
      {/* rack de cañerías */}
      {[-5, -1, 3, 7].map((x) => (
        <mesh key={x} position={[x, 1.8, 4]} castShadow>
          <boxGeometry args={[0.3, 3.6, 0.3]} />
          <Mat color={C.gris2} />
        </mesh>
      ))}
      {[0.4, 0, -0.4].map((dz, i) => (
        <mesh key={dz} position={[1, 3.4 + i * 0.25, 4 + dz]} rotation={[0, 0, Math.PI / 2]} castShadow>
          <cylinderGeometry args={[0.16, 0.16, 13, 8]} />
          <Mat color={i === 1 ? C.celeste : C.blanco} />
        </mesh>
      ))}
      {/* hornos y esferas de proceso */}
      <mesh position={[5, 1.4, -2]} castShadow>
        <boxGeometry args={[3, 2.8, 4]} />
        <Mat color={C.gris} />
      </mesh>
      <mesh position={[5.5, 1.6, 2]} castShadow>
        <sphereGeometry args={[1.4, 20, 14]} />
        <Mat color={C.blanco} />
      </mesh>
      <Chimenea position={[6.5, 0, -4.5]} altura={14} util={util} animar={animar} />
      <Chimenea position={[4, 0, -5]} altura={11} util={util} animar={animar} />
      <Antorcha position={[-7.5, 0, 5]} util={util} animar={animar} />
    </group>
  );
}

/** Humo: cantidad y opacidad según la utilización de refinerías (neutro si no hay dato). */
function Chimenea({ position, altura, util, animar }: { position: Vec; altura: number; util: number | null; animar: boolean }) {
  const n = 10;
  const bolas = useRef<THREE.Mesh[]>([]);
  const intensidad = util == null ? 0.5 : 0.25 + 0.75 * util;
  useFrame(({ clock }) => {
    bolas.current.forEach((m, i) => {
      if (!m) return;
      const s = animar ? (clock.elapsedTime * 0.12 + i / n) % 1 : i / n;
      m.position.set(Math.sin(i * 1.7) * 0.3 + s * 1.6, altura + 0.6 + s * 6, Math.cos(i) * 0.3);
      m.scale.setScalar(0.5 + s * 1.6);
      (m.material as THREE.MeshStandardMaterial).opacity = (1 - s) * 0.5 * intensidad;
      m.visible = i / n < intensidad + 0.05;
    });
  });
  return (
    <group position={position}>
      <mesh position={[0, altura / 2, 0]} castShadow>
        <cylinderGeometry args={[0.45, 0.6, altura, 16]} />
        <Mat color={C.blanco} />
      </mesh>
      <mesh position={[0, altura - 0.8, 0]}>
        <cylinderGeometry args={[0.47, 0.47, 0.6, 16]} />
        <Mat color={C.azul} />
      </mesh>
      {Array.from({ length: n }, (_, i) => (
        <mesh key={i} ref={(m) => { if (m) bolas.current[i] = m; }}>
          <sphereGeometry args={[0.5, 10, 8]} />
          <meshStandardMaterial color="#ffffff" transparent depthWrite={false} roughness={1} />
        </mesh>
      ))}
    </group>
  );
}

/** Antorcha: tamaño y parpadeo según la utilización de refinerías. */
function Antorcha({ position, util, animar }: { position: Vec; util: number | null; animar: boolean }) {
  const llama = useRef<THREE.Mesh>(null);
  const base = util == null ? 0.6 : 0.4 + util * 0.9;
  useFrame(({ clock }) => {
    const m = llama.current;
    if (!m) return;
    const f = animar ? 1 + Math.sin(clock.elapsedTime * 13) * 0.12 + Math.sin(clock.elapsedTime * 7.3) * 0.1 : 1;
    m.scale.set(base * 0.9, base * f * 1.6, base * 0.9);
  });
  return (
    <group position={position}>
      <mesh position={[0, 6, 0]} castShadow>
        <cylinderGeometry args={[0.22, 0.3, 12, 10]} />
        <Mat color={C.gris} />
      </mesh>
      <mesh ref={llama} position={[0, 12.8, 0]}>
        <coneGeometry args={[0.7, 1.8, 12]} />
        <meshStandardMaterial color={C.llama} emissive={C.llama} emissiveIntensity={1.6} toneMapped={false} />
      </mesh>
      <pointLight position={[0, 13, 0]} color={C.llama} intensity={(util ?? 0.5) * 30} distance={14} />
    </group>
  );
}

// ------------------------------------------------------------------ tanques de techo flotante
/** Tanque de crudo: el techo flotante y el crudo (naranja) suben con el nivel 0..1. */
export function TanqueCrudo({ position, nivel, radio = 2.4, alto = 3.4, banda = C.gris2 }:
  { position: Vec; nivel: number | null; radio?: number; alto?: number; banda?: string }) {
  const n = nivel == null ? 0.5 : 0.12 + 0.82 * Math.min(1, Math.max(0, nivel));
  return (
    <group position={position}>
      <mesh position={[0, alto / 2, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[radio, radio, alto, 32, 1, true]} />
        <Mat color={C.blanco} side={THREE.DoubleSide} />
      </mesh>
      <mesh position={[0, alto - 0.25, 0]}>
        <cylinderGeometry args={[radio + 0.03, radio + 0.03, 0.3, 32, 1, true]} />
        <Mat color={banda} side={THREE.DoubleSide} />
      </mesh>
      {nivel != null && (
        <mesh position={[0, (alto * n) / 2, 0]}>
          <cylinderGeometry args={[radio - 0.08, radio - 0.08, alto * n, 32]} />
          <Mat color={C.crudo} />
        </mesh>
      )}
      <mesh position={[0, alto * n + 0.07, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[radio - 0.1, radio - 0.1, 0.14, 32]} />
        <Mat color={C.gris} />
      </mesh>
    </group>
  );
}

/** Gasómetro telescópico: la campana sube con el gas almacenado 0..1. */
export function TanqueGas({ position, nivel }: { position: Vec; nivel: number | null }) {
  const alto = 6;
  const n = nivel == null ? 0.5 : 0.15 + 0.8 * Math.min(1, Math.max(0, nivel));
  return (
    <group position={position}>
      {Array.from({ length: 8 }, (_, i) => {
        const a = (i / 8) * Math.PI * 2;
        return (
          <mesh key={i} position={[Math.cos(a) * 2.7, alto / 2, Math.sin(a) * 2.7]} castShadow>
            <boxGeometry args={[0.18, alto, 0.18]} />
            <Mat color={C.gris2} />
          </mesh>
        );
      })}
      {[2, 4, 6].map((y) => (
        <mesh key={y} position={[0, y, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[2.7, 0.07, 6, 32]} />
          <Mat color={C.gris2} />
        </mesh>
      ))}
      <mesh position={[0, (alto * n) / 2, 0]} castShadow>
        <cylinderGeometry args={[2.4, 2.4, alto * n, 32]} />
        <Mat color={C.celeste} />
      </mesh>
      <mesh position={[0, alto * n, 0]} castShadow>
        <sphereGeometry args={[2.4, 32, 8, 0, Math.PI * 2, 0, Math.PI / 6]} />
        <Mat color={C.blanco} />
      </mesh>
    </group>
  );
}

// ------------------------------------------------------------------ bomba de petróleo (cigüeñal)
/** Bomba de varilla: la velocidad del cabeceo depende de la producción de crudo 0..1. */
export function Bomba({ position, rotacion = 0, velocidad, fase, animar }:
  { position: Vec; rotacion?: number; velocidad: number; fase: number; animar: boolean }) {
  const balancin = useRef<THREE.Group>(null);
  const manivela = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    const a = animar ? clock.elapsedTime * velocidad + fase : fase;
    if (balancin.current) balancin.current.rotation.z = Math.sin(a) * 0.32;
    if (manivela.current) manivela.current.rotation.z = a;
  });
  return (
    <group position={position} rotation={[0, rotacion, 0]}>
      <mesh position={[0, 0.2, 0]} castShadow receiveShadow>
        <boxGeometry args={[5.4, 0.4, 1.4]} />
        <Mat color={C.gris} />
      </mesh>
      {/* caballete en A */}
      {[-0.45, 0.45].map((z) => (
        <mesh key={z} position={[0.2, 1.5, z]} rotation={[z > 0 ? 0.25 : -0.25, 0, 0]} castShadow>
          <boxGeometry args={[0.22, 2.7, 0.22]} />
          <Mat color={C.blanco} />
        </mesh>
      ))}
      <group ref={balancin} position={[0.2, 2.8, 0]}>
        <mesh castShadow>
          <boxGeometry args={[4.6, 0.35, 0.4]} />
          <Mat color={C.azul} />
        </mesh>
        {/* cabeza de caballo */}
        <mesh position={[2.45, -0.35, 0]} castShadow>
          <boxGeometry args={[0.45, 1.2, 0.5]} />
          <Mat color={C.azul} />
        </mesh>
      </group>
      <group ref={manivela} position={[-1.9, 1, 0]}>
        <mesh rotation={[Math.PI / 2, 0, 0]} castShadow>
          <cylinderGeometry args={[0.75, 0.75, 0.3, 20]} />
          <Mat color={C.gris2} />
        </mesh>
      </group>
      {/* boca de pozo */}
      <mesh position={[2.65, 0.9, 0]}>
        <cylinderGeometry args={[0.12, 0.12, 1.4, 8]} />
        <Mat color={C.gris3} />
      </mesh>
    </group>
  );
}
