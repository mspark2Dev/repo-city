import { OrbitControls } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { Bloom, EffectComposer } from '@react-three/postprocessing'
import { Suspense } from 'react'
import { useCityStore } from '../store'
import { Buildings } from './Buildings'
import { CameraRig } from './CameraRig'
import { Controls } from './Controls'
import { Districts } from './Districts'
import { Links } from './Links'
import { Smoke } from './Smoke'
import { GROUND } from './palette'

/** The reference grid only reads correctly if it spans the city it sits under. */
function Ground() {
  const city = useCityStore((s) => s.city)
  const root = city?.districts.find((d) => d.depth === 0)
  const span = Math.max(root ? Math.max(root.rect.w, root.rect.d) * 6 : 400, 400)
  return (
    <gridHelper
      args={[span, 60, '#1A2233', '#121826']}
      position={[0, -0.2, 0]}
    />
  )
}

export function CityCanvas() {
  const status = useCityStore((s) => s.status)
  const clearSelection = useCityStore((s) => s.select)

  return (
    <Canvas
      shadows
      camera={{ position: [22, 20, 22], fov: 45, near: 0.1, far: 500 }}
      onPointerMissed={() => void clearSelection(null)}
    >
      <color attach="background" args={[GROUND]} />

      <ambientLight intensity={0.55} />
      <directionalLight
        position={[18, 30, 12]}
        intensity={1.1}
        castShadow
        shadow-mapSize={[2048, 2048]}
      />
      <hemisphereLight args={['#3E5A7A', '#0B0E14', 0.4]} />

      <Suspense fallback={null}>
        {status === 'ready' && (
          <>
            <CameraRig />
            <Controls />
            <Districts />
            <Buildings />
            <Links />
            <Smoke />
          </>
        )}
      </Suspense>

      <Ground />
      <EffectComposer>
        <Bloom intensity={0.55} luminanceThreshold={0.32} luminanceSmoothing={0.85} mipmapBlur />
      </EffectComposer>

      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.08}
        minDistance={3}
        maxDistance={200}
        minPolarAngle={Math.PI / 36}
        maxPolarAngle={Math.PI / 2.1}
      />
    </Canvas>
  )
}
