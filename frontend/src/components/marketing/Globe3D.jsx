// src/components/Globe3D.jsx
import { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Sphere, MeshDistortMaterial, OrbitControls, Html } from '@react-three/drei'
import * as THREE from 'three'

function AnimatedSphere() {
  const meshRef = useRef()
  const materialRef = useRef()
  
  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.y = state.clock.getElapsedTime() * 0.1
      meshRef.current.rotation.x = Math.sin(state.clock.getElapsedTime() * 0.2) * 0.1
    }
    if (materialRef.current) {
      const intensity = 0.5 + Math.sin(state.clock.getElapsedTime() * 0.5) * 0.3
      materialRef.current.emissiveIntensity = intensity
    }
  })
  
  return (
    <Sphere ref={meshRef} args={[1, 128, 128]} scale={2.5}>
      <MeshDistortMaterial
        ref={materialRef}
        color="#8b5cf6"
        emissive="#4c1d95"
        emissiveIntensity={0.6}
        roughness={0.3}
        metalness={0.8}
        distort={0.4}
        speed={2}
      />
    </Sphere>
  )
}

function Particles() {
  const particlesRef = useRef()
  const particlesCount = 2000
  const positions = useMemo(() => {
    const positions = new Float32Array(particlesCount * 3)
    for (let i = 0; i < particlesCount; i++) {
      const radius = 3.2
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta)
      positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta)
      positions[i * 3 + 2] = radius * Math.cos(phi)
    }
    return positions
  }, [])
  
  useFrame((state) => {
    if (particlesRef.current) {
      particlesRef.current.rotation.y = state.clock.getElapsedTime() * 0.05
      particlesRef.current.rotation.x = Math.sin(state.clock.getElapsedTime() * 0.1) * 0.05
    }
  })
  
  return (
    <points ref={particlesRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={particlesCount}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial color="#8b5cf6" size={0.02} transparent opacity={0.4} />
    </points>
  )
}

export default function Globe3D() {
  return (
    <Canvas
      camera={{ position: [0, 0, 6], fov: 45 }}
      style={{ background: 'transparent' }}
      className="w-full h-full"
    >
      <ambientLight intensity={0.5} />
      <pointLight position={[10, 10, 10]} intensity={1} />
      <pointLight position={[-10, -10, -10]} intensity={0.5} color="#8b5cf6" />
      <AnimatedSphere />
      <Particles />
      <OrbitControls
        enableZoom={false}
        enablePan={false}
        autoRotate={false}
        rotateSpeed={0.5}
      />
    </Canvas>
  )
}