// src/components/GlobeNetwork.jsx
import { useRef, useMemo, useState, useEffect } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Sphere, Line, OrbitControls } from '@react-three/drei'
import * as THREE from 'three'

function SimpleGlobe() {
  const meshRef = useRef()
  
  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.y = state.clock.getElapsedTime() * 0.05
    }
  })
  
  return (
    <Sphere ref={meshRef} args={[1, 32, 32]}>
      <meshPhongMaterial color="#3b82f6" emissive="#1e40af" emissiveIntensity={0.2} transparent opacity={0.8} />
    </Sphere>
  )
}

function Particles() {
  const particlesRef = useRef()
  const particleCount = 500
  const positions = useMemo(() => {
    const positions = new Float32Array(particleCount * 3)
    for (let i = 0; i < particleCount; i++) {
      const radius = 1.4
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta)
      positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta)
      positions[i * 3 + 2] = radius * Math.cos(phi)
    }
    return positions
  }, [])
  
  return (
    <points ref={particlesRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={particleCount}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial color="#60a5fa" size={0.036} transparent opacity={0.4} />
    </points>
  )
}

export default function GlobeNetwork() {
  const [hasError, setHasError] = useState(false)
  
  useEffect(() => {
    const handleContextLost = (event) => {
      event.preventDefault()
      setHasError(true)
    }
    
    window.addEventListener('webglcontextlost', handleContextLost)
    return () => window.removeEventListener('webglcontextlost', handleContextLost)
  }, [])
  
  if (hasError) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-16 h-16 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center mx-auto mb-3">
            🌍
          </div>
          <p className="text-sm text-gray-500">Globe 3D temporairement indisponible</p>
        </div>
      </div>
    )
  }
  
  return (
    <Canvas camera={{ position: [0, 0, 3], fov: 45 }} style={{ background: 'transparent' }}>
      <ambientLight intensity={0.5} />
      <pointLight position={[5, 5, 5]} intensity={1} />
      <SimpleGlobe />
      <Particles />
      <OrbitControls
        enableZoom={false}
        enablePan={false}
        autoRotate={true}
        autoRotateSpeed={0.8}
        rotateSpeed={0.5}
      />
    </Canvas>
  )
}