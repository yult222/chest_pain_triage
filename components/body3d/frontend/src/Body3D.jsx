import React from 'react'
import { Streamlit, StreamlitComponentBase, withStreamlitConnection } from 'streamlit-component-lib'
import * as THREE from 'three'

/**
 * A minimal 3D mannequin built from primitives.
 * Click on a body region -> returns region name to Streamlit.
 *
 * This is intentionally simple so it works out of the box.
 * You can later replace it with a real GLB model and keep the same "name" outputs.
 */
class Body3D extends StreamlitComponentBase {
  constructor(props) {
    super(props)
    this.containerRef = React.createRef()
    this.scene = null
    this.camera = null
    this.renderer = null
    this.raycaster = new THREE.Raycaster()
    this.pointer = new THREE.Vector2()
    this.meshes = []
    this.selectedName = null
    this.onPointerDown = this.onPointerDown.bind(this)
    this.onResize = this.onResize.bind(this)
    this.animate = this.animate.bind(this)
  }

  componentDidMount() {
    const height = this.props.args?.height || 420
    Streamlit.setFrameHeight(height)
    this.initThree()
  }

  componentWillUnmount() {
    if (this.renderer) {
      this.renderer.domElement.removeEventListener('pointerdown', this.onPointerDown)
    }
    window.removeEventListener('resize', this.onResize)
  }

  initThree() {
    const container = this.containerRef.current
    const width = container.clientWidth
    const height = container.clientHeight

    // Scene
    this.scene = new THREE.Scene()

    // Camera
    this.camera = new THREE.PerspectiveCamera(35, width / height, 0.1, 100)
    this.camera.position.set(0, 1.6, 4)

    // Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    this.renderer.setPixelRatio(window.devicePixelRatio || 1)
    this.renderer.setSize(width, height)
    container.appendChild(this.renderer.domElement)

    // Lights
    const hemi = new THREE.HemisphereLight(0xffffff, 0x444444, 1.0)
    this.scene.add(hemi)
    const dir = new THREE.DirectionalLight(0xffffff, 0.9)
    dir.position.set(3, 10, 10)
    this.scene.add(dir)

    // Ground reference (transparent)
    const grid = new THREE.GridHelper(10, 10, 0x888888, 0xcccccc)
    grid.position.y = 0
    grid.material.opacity = 0.15
    grid.material.transparent = true
    this.scene.add(grid)

    // Build mannequin
    this.buildMannequin()

    // Events
    this.renderer.domElement.addEventListener('pointerdown', this.onPointerDown)
    window.addEventListener('resize', this.onResize)

    // Start loop
    this.animate()
  }

  addRegionMesh(geometry, name, position, scale) {
    const material = new THREE.MeshStandardMaterial({
      color: 0x6aa9ff,
      roughness: 0.55,
      metalness: 0.05,
      emissive: 0x000000,
    })
    const mesh = new THREE.Mesh(geometry, material)
    mesh.name = name
    mesh.position.set(position.x, position.y, position.z)
    if (scale) mesh.scale.set(scale.x, scale.y, scale.z)
    this.scene.add(mesh)
    this.meshes.push(mesh)
    return mesh
  }

  buildMannequin() {
    // Head
    this.addRegionMesh(new THREE.SphereGeometry(0.25, 32, 32), 'head', { x: 0, y: 2.1, z: 0 })

    // Torso split into chest and abdomen (for triage)
    this.addRegionMesh(new THREE.CapsuleGeometry(0.35, 0.45, 8, 16), 'chest', { x: 0, y: 1.55, z: 0 })
    this.addRegionMesh(new THREE.CapsuleGeometry(0.33, 0.35, 8, 16), 'abdomen', { x: 0, y: 1.05, z: 0 })

    // Left arm / right arm
    this.addRegionMesh(new THREE.CylinderGeometry(0.10, 0.10, 0.75, 16), 'left_arm', { x: -0.65, y: 1.55, z: 0 }, { x: 1, y: 1, z: 1 })
    this.addRegionMesh(new THREE.CylinderGeometry(0.10, 0.10, 0.75, 16), 'right_arm', { x: 0.65, y: 1.55, z: 0 }, { x: 1, y: 1, z: 1 })

    // Legs
    this.addRegionMesh(new THREE.CylinderGeometry(0.12, 0.12, 0.9, 16), 'left_leg', { x: -0.22, y: 0.35, z: 0 })
    this.addRegionMesh(new THREE.CylinderGeometry(0.12, 0.12, 0.9, 16), 'right_leg', { x: 0.22, y: 0.35, z: 0 })

    // Back region (simple plate behind chest)
    const backGeom = new THREE.BoxGeometry(0.9, 0.8, 0.12)
    this.addRegionMesh(backGeom, 'back', { x: 0, y: 1.45, z: -0.35 })

    // A little hint text (in DOM) is handled by Streamlit side
  }

  highlight(name) {
    this.meshes.forEach((m) => {
      if (m.name === name) {
        m.material.emissive.setHex(0xffaa00)
      } else {
        m.material.emissive.setHex(0x000000)
      }
    })
  }

  onPointerDown(event) {
    if (!this.renderer || !this.camera || !this.scene) return

    const rect = this.renderer.domElement.getBoundingClientRect()
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

    this.raycaster.setFromCamera(this.pointer, this.camera)
    const intersects = this.raycaster.intersectObjects(this.meshes, false)

    if (intersects.length > 0) {
      const hit = intersects[0].object
      const name = hit.name || 'unknown'
      this.selectedName = name
      this.highlight(name)
      Streamlit.setComponentValue(name)
    }
  }

  onResize() {
    if (!this.containerRef.current || !this.camera || !this.renderer) return
    const width = this.containerRef.current.clientWidth
    const height = this.containerRef.current.clientHeight
    this.camera.aspect = width / height
    this.camera.updateProjectionMatrix()
    this.renderer.setSize(width, height)
  }

  animate() {
    if (!this.renderer || !this.scene || !this.camera) return

    // gentle auto-rotation for affordance
    this.scene.rotation.y += 0.003

    this.renderer.render(this.scene, this.camera)
    requestAnimationFrame(this.animate)
  }

  render() {
    const height = this.props.args?.height || 420
    return (
      <div style={{ width: '100%', height: `${height}px` }}>
        <div ref={this.containerRef} style={{ width: '100%', height: '100%' }} />
      </div>
    )
  }
}

export default withStreamlitConnection(Body3D)
